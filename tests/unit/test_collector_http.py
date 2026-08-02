from __future__ import annotations

import ast
import gzip
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from tests.unit.test_collector_schemas import CONFIG_HASH, valid_collection_request

from neuroai_workbench.collector import CollectorConfig, HttpCollector, PriorCapture
from neuroai_workbench.collector.dns import DnsGuard
from neuroai_workbench.collector.errors import CollectionFailureError
from neuroai_workbench.collector.http_client import HttpRequest
from neuroai_workbench.collector.schemas import FAILURE_SCHEMA, RESULT_SCHEMA
from neuroai_workbench.collector.schemas import validate_or_raise as validate_schema

GLOBAL_IP = "93.184.216.34"
PRIVATE_IP = "192.168.1.10"
LOOPBACK_IP = "127.0.0.1"


def global_getaddrinfo(host: str, port: Any, *args: Any, **kwargs: Any) -> list[tuple[Any, ...]]:
    if host in {"example.org", "redirect.example.org", "final.example.org"}:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (GLOBAL_IP, 0))]
    if host == "private.example.org":
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (PRIVATE_IP, 0))]
    if host == "rebind.example.org":
        if not hasattr(global_getaddrinfo, "calls"):
            global_getaddrinfo.calls = 0  # type: ignore[attr-defined]
        global_getaddrinfo.calls += 1  # type: ignore[attr-defined]
        ip = GLOBAL_IP if global_getaddrinfo.calls == 1 else PRIVATE_IP  # type: ignore[attr-defined]
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]
    raise socket.gaierror("unknown host")


@dataclass
class FakeTransport:
    responses: dict[str, tuple[int, dict[str, str], bytes]] = field(default_factory=dict)
    calls: list[HttpRequest] = field(default_factory=list)

    def send(
        self,
        request: HttpRequest,
        *,
        connect_timeout: float,
        read_timeout: float,
    ) -> tuple[int, dict[str, str], bytes]:
        self.calls.append(request)
        if request.url not in self.responses:
            raise OSError(f"unexpected URL {request.url!r}")
        return self.responses[request.url]


def _collector(tmp_path: Path, transport: FakeTransport) -> HttpCollector:
    config = CollectorConfig(
        collector_version="0.3.0.dev0-collector",
        configuration_hash=CONFIG_HASH,
        requests_per_host_per_minute=100,
    )
    collector = HttpCollector(config=config, transport=transport, quarantine_root=tmp_path / "quarantine")
    collector.http_client.dns_guard = DnsGuard(getaddrinfo=global_getaddrinfo)
    return collector


def test_successful_collection_writes_quarantine_and_validates_schema(tmp_path: Path) -> None:
    body = b"<html>hello</html>"
    transport = FakeTransport(
        responses={
            "https://example.org/source": (
                200,
                {"Content-Type": "text/html"},
                body,
            )
        }
    )
    collector = _collector(tmp_path, transport)
    request = valid_collection_request()
    outcome = collector.collect(request)

    assert outcome.kind == "result"
    validate_schema(outcome.record, RESULT_SCHEMA)
    assert outcome.record["http_status"] == 200
    assert outcome.record["sha256"]
    assert outcome.record["result_id"].startswith("CRES-")
    quarantine_file = tmp_path / "quarantine" / outcome.record["quarantine_path"]
    assert quarantine_file.is_file()
    assert quarantine_file.read_bytes() == body
    assert "If-None-Match" not in transport.calls[0].headers


def test_conditional_get_304_emits_new_capture_with_same_content_hash(tmp_path: Path) -> None:
    prior_body = b"<html>unchanged</html>"
    from neuroai_workbench.util import sha256_bytes

    prior_hash = sha256_bytes(prior_body)
    prior_path = f"incoming/SRC-0001/{prior_hash[:12]}/source.html"
    transport = FakeTransport(
        responses={
            "https://example.org/source": (
                304,
                {"ETag": '"same"'},
                b"",
            )
        }
    )
    collector = _collector(tmp_path, transport)
    request = valid_collection_request()
    prior = PriorCapture(
        etag='"same"',
        content_sha256=prior_hash,
        quarantine_path=prior_path,
        size_bytes=len(prior_body),
        media_type="text/html",
        original_filename="source.html",
    )
    outcome = collector.collect(request, prior_capture=prior)

    assert outcome.kind == "result"
    assert outcome.record["http_status"] == 304
    assert outcome.record["sha256"] == prior_hash
    assert outcome.record["result_id"].startswith("CRES-")
    assert transport.calls[0].headers["If-None-Match"] == '"same"'


def test_redirect_revalidates_dns_and_records_chain(tmp_path: Path) -> None:
    transport = FakeTransport(
        responses={
            "https://example.org/source": (
                302,
                {"Location": "https://final.example.org/page"},
                b"",
            ),
            "https://final.example.org/page": (
                200,
                {"Content-Type": "text/plain"},
                b"final-body",
            ),
        }
    )
    collector = _collector(tmp_path, transport)
    outcome = collector.collect(valid_collection_request())

    assert outcome.kind == "result"
    assert outcome.record["redirect_chain"] == ["https://example.org/source"]
    assert outcome.record["final_url"] == "https://final.example.org/page"
    assert len(transport.calls) == 2


def test_private_redirect_target_is_blocked(tmp_path: Path) -> None:
    transport = FakeTransport(
        responses={
            "https://example.org/source": (
                302,
                {"Location": f"http://{PRIVATE_IP}/admin"},
                b"",
            ),
        }
    )
    collector = _collector(tmp_path, transport)
    outcome = collector.collect(valid_collection_request())

    assert outcome.kind == "failure"
    validate_schema(outcome.record, FAILURE_SCHEMA)
    assert outcome.record["failure_class"] == "REDIRECT_BLOCKED"


def test_private_dns_resolution_is_blocked(tmp_path: Path) -> None:
    request = valid_collection_request()
    request["requested_url"] = "https://private.example.org/internal"
    transport = FakeTransport(responses={})
    collector = _collector(tmp_path, transport)
    outcome = collector.collect(request)

    assert outcome.kind == "failure"
    assert outcome.record["failure_class"] == "SSRF_BLOCKED"


def test_dns_rebinding_is_blocked_on_redirect(tmp_path: Path) -> None:
    call_count = {"n": 0}

    def rebind_getaddrinfo(host: str, port: Any, *args: Any, **kwargs: Any) -> list[tuple[Any, ...]]:
        if host != "rebind.example.org":
            raise socket.gaierror("unknown host")
        call_count["n"] += 1
        ip = "93.184.216.34" if call_count["n"] == 1 else "93.184.216.35"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]

    request = valid_collection_request()
    request["requested_url"] = "https://rebind.example.org/a"
    transport = FakeTransport(
        responses={
            "https://rebind.example.org/a": (
                302,
                {"Location": "https://rebind.example.org/b"},
                b"",
            ),
            "https://rebind.example.org/b": (200, {"Content-Type": "text/plain"}, b"x"),
        }
    )
    config = CollectorConfig(
        collector_version="0.3.0.dev0-collector",
        configuration_hash=CONFIG_HASH,
        requests_per_host_per_minute=100,
    )
    collector = HttpCollector(config=config, transport=transport, quarantine_root=tmp_path / "quarantine")
    collector.http_client.dns_guard = DnsGuard(getaddrinfo=rebind_getaddrinfo)
    outcome = collector.collect(request)

    assert outcome.kind == "failure"
    assert outcome.record["failure_class"] == "DNS_REBINDING_BLOCKED"


def test_size_limit_exceeded(tmp_path: Path) -> None:
    transport = FakeTransport(
        responses={
            "https://example.org/source": (
                200,
                {"Content-Type": "text/plain"},
                b"x" * 100,
            )
        }
    )
    config = CollectorConfig(
        collector_version="0.3.0.dev0-collector",
        configuration_hash=CONFIG_HASH,
        max_response_bytes=50,
        requests_per_host_per_minute=100,
    )
    collector = HttpCollector(config=config, transport=transport, quarantine_root=tmp_path / "quarantine")
    collector.http_client.dns_guard = DnsGuard(getaddrinfo=global_getaddrinfo)
    outcome = collector.collect(valid_collection_request())

    assert outcome.kind == "failure"
    assert outcome.record["failure_class"] == "SIZE_LIMIT_EXCEEDED"


def test_decompression_bomb_is_blocked(tmp_path: Path) -> None:
    payload = gzip.compress(b"x" * 5000)
    transport = FakeTransport(
        responses={
            "https://example.org/source": (
                200,
                {"Content-Type": "text/plain", "Content-Encoding": "gzip"},
                payload,
            )
        }
    )
    config = CollectorConfig(
        collector_version="0.3.0.dev0-collector",
        configuration_hash=CONFIG_HASH,
        max_response_bytes=10_000,
        max_decompression_ratio=2,
        requests_per_host_per_minute=100,
    )
    collector = HttpCollector(config=config, transport=transport, quarantine_root=tmp_path / "quarantine")
    collector.http_client.dns_guard = DnsGuard(getaddrinfo=global_getaddrinfo)
    outcome = collector.collect(valid_collection_request())

    assert outcome.kind == "failure"
    assert outcome.record["failure_class"] == "DECOMPRESSION_BOMB"


def test_rate_limit_blocks_excessive_requests(tmp_path: Path) -> None:
    transport = FakeTransport(
        responses={
            "https://example.org/source": (
                200,
                {"Content-Type": "text/plain"},
                b"ok",
            )
        }
    )
    config = CollectorConfig(
        collector_version="0.3.0.dev0-collector",
        configuration_hash=CONFIG_HASH,
        requests_per_host_per_minute=1,
    )
    collector = HttpCollector(config=config, transport=transport, quarantine_root=tmp_path / "quarantine")
    collector.http_client.dns_guard = DnsGuard(getaddrinfo=global_getaddrinfo)
    request = valid_collection_request()
    assert collector.collect(request).kind == "result"
    outcome = collector.collect(request)
    assert outcome.kind == "failure"
    assert outcome.record["failure_class"] == "UNKNOWN"


def test_timeout_is_recorded(tmp_path: Path) -> None:
    class TimeoutTransport(FakeTransport):
        def send(
            self, request: HttpRequest, *, connect_timeout: float, read_timeout: float
        ) -> tuple[int, dict[str, str], bytes]:
            raise TimeoutError("timed out")

    collector = _collector(tmp_path, TimeoutTransport())
    outcome = collector.collect(valid_collection_request())
    assert outcome.kind == "failure"
    assert outcome.record["failure_class"] == "TIMEOUT"


def test_loopback_literal_in_url_is_blocked_before_network() -> None:
    from neuroai_workbench.collector.http_client import HttpClient

    config = CollectorConfig(collector_version="v", configuration_hash="a" * 64)
    client = HttpClient(config=config, transport=FakeTransport(), dns_guard=DnsGuard(getaddrinfo=global_getaddrinfo))
    with pytest.raises(CollectionFailureError) as exc:
        client.fetch(f"http://{LOOPBACK_IP}/admin")
    assert exc.value.failure_class == "SSRF_BLOCKED"


def test_disallowed_content_type_is_rejected(tmp_path: Path) -> None:
    transport = FakeTransport(
        responses={
            "https://example.org/source": (
                200,
                {"Content-Type": "application/x-msdownload"},
                b"binary",
            )
        }
    )
    collector = _collector(tmp_path, transport)
    outcome = collector.collect(valid_collection_request())
    assert outcome.kind == "failure"
    assert outcome.record["failure_class"] == "CONTENT_TYPE_REJECTED"


def test_redirect_chain_limit(tmp_path: Path) -> None:
    transport = FakeTransport(
        responses={
            "https://example.org/source": (
                302,
                {"Location": "https://example.org/source"},
                b"",
            ),
        }
    )
    config = CollectorConfig(
        collector_version="0.3.0.dev0-collector",
        configuration_hash=CONFIG_HASH,
        max_redirects=1,
        requests_per_host_per_minute=100,
    )
    collector = HttpCollector(config=config, transport=transport, quarantine_root=tmp_path / "quarantine")
    collector.http_client.dns_guard = DnsGuard(getaddrinfo=global_getaddrinfo)
    outcome = collector.collect(valid_collection_request())
    assert outcome.kind == "failure"
    assert outcome.record["failure_class"] == "REDIRECT_BLOCKED"


def test_collector_modules_do_not_import_monitoring_write_apis() -> None:
    collector_root = Path(__file__).resolve().parents[2] / "src" / "neuroai_workbench" / "collector"
    forbidden = {"record_snapshot", "record_snapshot_file", "adjudicate", "create_change_candidate"}
    for path in collector_root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.endswith("monitoring"):
                imported = {alias.name for alias in node.names}
                assert imported.isdisjoint(forbidden), f"{path.name} imports forbidden monitoring APIs: {imported}"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "neuroai_workbench.monitoring"
