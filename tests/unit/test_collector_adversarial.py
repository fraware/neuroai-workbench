from __future__ import annotations

import socket
from pathlib import Path

import pytest
from tests.unit.test_collector_schemas import CONFIG_HASH, valid_collection_request

from neuroai_workbench.collector import CollectorConfig, PriorCapture
from neuroai_workbench.collector.dns import DnsGuard
from neuroai_workbench.collector.errors import CollectionFailureError
from neuroai_workbench.collector.http_client import HttpClient, HttpRequest, filename_from_url
from neuroai_workbench.collector.quarantine import build_quarantine_record, write_quarantine_bytes
from neuroai_workbench.collector.rate_limit import RateLimiter
from neuroai_workbench.collector.url_policy import public_url_error, validate_public_url
from tests.unit.test_collector_http import GLOBAL_IP, FakeTransport, _collector, global_getaddrinfo


def test_public_url_error_cases() -> None:
    assert public_url_error("https://example.org/path") is None
    assert public_url_error("http://127.0.0.1/x") is not None
    assert public_url_error("https://user:pass@example.org/x") is not None
    assert public_url_error("ftp://example.org/x") is not None
    assert public_url_error("https://localhost/x") is not None
    assert public_url_error("https://host.local/x") is not None


def test_validate_public_url_raises() -> None:
    with pytest.raises(CollectionFailureError) as exc:
        validate_public_url("http://10.0.0.1/internal")
    assert exc.value.failure_class == "SSRF_BLOCKED"


def test_dns_guard_rejects_non_global_resolved_address() -> None:
    def private_getaddrinfo(host: str, port: object, *args: object, **kwargs: object) -> list[tuple[object, ...]]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 0))]

    guard = DnsGuard(getaddrinfo=private_getaddrinfo)
    with pytest.raises(CollectionFailureError) as exc:
        guard.resolve("https://example.org/source")
    assert exc.value.failure_class == "SSRF_BLOCKED"


def test_dns_guard_accepts_literal_global_ip() -> None:
    guard = DnsGuard(getaddrinfo=global_getaddrinfo)
    record = guard.resolve(f"https://{GLOBAL_IP}/source")
    assert record.addresses == [GLOBAL_IP]


def test_rate_limiter_window_expiry() -> None:
    limiter = RateLimiter(requests_per_minute=1)
    limiter.check("https://example.org/a", now=0.0)
    with pytest.raises(ValueError, match="Rate limit"):
        limiter.check("https://example.org/a", now=1.0)
    limiter.check("https://example.org/a", now=61.0)


def test_quarantine_rejects_unsafe_filename(tmp_path: Path) -> None:
    with pytest.raises(CollectionFailureError) as exc:
        build_quarantine_record(
            result_id="CRES-" + "1" * 32,
            source_id="SRC-0001",
            monitor_id="MON-SRC-0001",
            captured_at="2026-08-02T08:00:01Z",
            content_sha256="c" * 64,
            size_bytes=10,
            original_filename="../escape.html",
            quarantine_path="incoming/safe.html",
            collector_version="0.3.0.dev0-collector",
            configuration_hash=CONFIG_HASH,
        )
    assert exc.value.failure_class == "UNSAFE_FILENAME"


def test_quarantine_refuses_path_traversal(tmp_path: Path) -> None:
    with pytest.raises(CollectionFailureError):
        write_quarantine_bytes(tmp_path, "../escape.bin", b"x")


def test_http_client_missing_redirect_location() -> None:
    transport = FakeTransport(
        responses={
            "https://example.org/source": (302, {}, b""),
        }
    )
    config = CollectorConfig(collector_version="v", configuration_hash="a" * 64)
    client = HttpClient(config=config, transport=transport, dns_guard=DnsGuard(getaddrinfo=global_getaddrinfo))
    with pytest.raises(CollectionFailureError) as exc:
        client.fetch("https://example.org/source")
    assert exc.value.failure_class == "REDIRECT_BLOCKED"


def test_http_client_unsupported_encoding() -> None:
    transport = FakeTransport(
        responses={
            "https://example.org/source": (
                200,
                {"Content-Type": "text/plain", "Content-Encoding": "br"},
                b"data",
            )
        }
    )
    config = CollectorConfig(collector_version="v", configuration_hash="a" * 64)
    client = HttpClient(config=config, transport=transport, dns_guard=DnsGuard(getaddrinfo=global_getaddrinfo))
    with pytest.raises(CollectionFailureError) as exc:
        client.fetch("https://example.org/source")
    assert exc.value.failure_class == "CONTENT_TYPE_REJECTED"


def test_http_client_network_error() -> None:
    class BrokenTransport(FakeTransport):
        def send(
            self, request: HttpRequest, *, connect_timeout: float, read_timeout: float
        ) -> tuple[int, dict[str, str], bytes]:
            raise OSError("connection refused")

    config = CollectorConfig(collector_version="v", configuration_hash="a" * 64)
    client = HttpClient(config=config, transport=BrokenTransport(), dns_guard=DnsGuard(getaddrinfo=global_getaddrinfo))
    with pytest.raises(CollectionFailureError) as exc:
        client.fetch("https://example.org/source")
    assert exc.value.failure_class == "NETWORK_ERROR"


def test_filename_from_url() -> None:
    assert filename_from_url("https://example.org/") == "index.html"
    assert filename_from_url("https://example.org/docs/report.json") == "report.json"


def test_quarantine_refuses_conflicting_rewrite(tmp_path: Path) -> None:
    from neuroai_workbench.collector.quarantine import write_quarantine_bytes

    write_quarantine_bytes(tmp_path, "incoming/a.bin", b"original")
    with pytest.raises(CollectionFailureError) as exc:
        write_quarantine_bytes(tmp_path, "incoming/a.bin", b"changed")
    assert exc.value.failure_class == "QUARANTINE_REJECTED"


def test_http_client_http_error_status() -> None:
    transport = FakeTransport(
        responses={"https://example.org/source": (500, {"Content-Type": "text/plain"}, b"err")},
    )
    config = CollectorConfig(collector_version="v", configuration_hash="a" * 64)
    client = HttpClient(config=config, transport=transport, dns_guard=DnsGuard(getaddrinfo=global_getaddrinfo))
    with pytest.raises(CollectionFailureError) as exc:
        client.fetch("https://example.org/source")
    assert exc.value.failure_class == "HTTP_ERROR"


def test_http_client_deflate_response() -> None:
    import zlib

    payload = zlib.compress(b"deflated-content")
    transport = FakeTransport(
        responses={
            "https://example.org/source": (
                200,
                {"Content-Type": "text/plain", "Content-Encoding": "deflate"},
                payload,
            )
        },
    )
    config = CollectorConfig(collector_version="v", configuration_hash="a" * 64)
    client = HttpClient(config=config, transport=transport, dns_guard=DnsGuard(getaddrinfo=global_getaddrinfo))
    response = client.fetch("https://example.org/source")
    assert response.body == b"deflated-content"


def test_dns_guard_rejects_missing_hostname() -> None:
    guard = DnsGuard(getaddrinfo=global_getaddrinfo)
    with pytest.raises(CollectionFailureError) as exc:
        guard.resolve("https:///missing")
    assert exc.value.failure_class == "SSRF_BLOCKED"


def test_dns_guard_reports_resolution_failure() -> None:
    def failing_getaddrinfo(host: str, port: object, *args: object, **kwargs: object) -> list[tuple[object, ...]]:
        raise socket.gaierror("temporary failure")

    guard = DnsGuard(getaddrinfo=failing_getaddrinfo)
    with pytest.raises(CollectionFailureError) as exc:
        guard.resolve("https://example.org/source")
    assert exc.value.failure_class == "NETWORK_ERROR"


def test_quarantine_rejects_control_characters_in_filename() -> None:
    with pytest.raises(CollectionFailureError) as exc:
        build_quarantine_record(
            result_id="CRES-" + "1" * 32,
            source_id="SRC-0001",
            monitor_id="MON-SRC-0001",
            captured_at="2026-08-02T08:00:01Z",
            content_sha256="c" * 64,
            size_bytes=10,
            original_filename="bad\x01name.html",
            quarantine_path="incoming/safe.html",
            collector_version="0.3.0.dev0-collector",
            configuration_hash=CONFIG_HASH,
        )
    assert exc.value.failure_class == "UNSAFE_FILENAME"


def test_dns_guard_rejects_empty_resolution() -> None:
    def empty_getaddrinfo(host: str, port: object, *args: object, **kwargs: object) -> list[tuple[object, ...]]:
        return []

    guard = DnsGuard(getaddrinfo=empty_getaddrinfo)
    with pytest.raises(CollectionFailureError) as exc:
        guard.resolve("https://example.org/source")
    assert exc.value.failure_class == "NETWORK_ERROR"


def test_validate_public_url_rejects_at_sign() -> None:
    with pytest.raises(CollectionFailureError) as exc:
        validate_public_url("https://example.org/@hidden")
    assert exc.value.failure_class == "CREDENTIAL_LEAK_PREVENTED"


def test_http_client_empty_gzip_body() -> None:
    transport = FakeTransport(
        responses={
            "https://example.org/source": (
                200,
                {"Content-Type": "text/plain", "Content-Encoding": "gzip"},
                b"",
            )
        },
    )
    config = CollectorConfig(collector_version="v", configuration_hash="a" * 64)
    client = HttpClient(config=config, transport=transport, dns_guard=DnsGuard(getaddrinfo=global_getaddrinfo))
    response = client.fetch("https://example.org/source")
    assert response.body == b""


def test_http_client_corrupt_gzip() -> None:
    transport = FakeTransport(
        responses={
            "https://example.org/source": (
                200,
                {"Content-Type": "text/plain", "Content-Encoding": "gzip"},
                b"not-gzip",
            )
        },
    )
    config = CollectorConfig(collector_version="v", configuration_hash="a" * 64)
    client = HttpClient(config=config, transport=transport, dns_guard=DnsGuard(getaddrinfo=global_getaddrinfo))
    with pytest.raises(CollectionFailureError) as exc:
        client.fetch("https://example.org/source")
    assert exc.value.failure_class == "DECOMPRESSION_BOMB"


def test_http_client_corrupt_deflate() -> None:
    transport = FakeTransport(
        responses={
            "https://example.org/source": (
                200,
                {"Content-Type": "text/plain", "Content-Encoding": "deflate"},
                b"not-deflate",
            )
        },
    )
    config = CollectorConfig(collector_version="v", configuration_hash="a" * 64)
    client = HttpClient(config=config, transport=transport, dns_guard=DnsGuard(getaddrinfo=global_getaddrinfo))
    with pytest.raises(CollectionFailureError) as exc:
        client.fetch("https://example.org/source")
    assert exc.value.failure_class == "DECOMPRESSION_BOMB"


def test_http_client_identity_size_limit() -> None:
    transport = FakeTransport(
        responses={
            "https://example.org/source": (
                200,
                {"Content-Type": "text/plain"},
                b"x" * 20,
            )
        },
    )
    config = CollectorConfig(collector_version="v", configuration_hash="a" * 64, max_response_bytes=10)
    client = HttpClient(config=config, transport=transport, dns_guard=DnsGuard(getaddrinfo=global_getaddrinfo))
    with pytest.raises(CollectionFailureError) as exc:
        client.fetch("https://example.org/source")
    assert exc.value.failure_class == "SIZE_LIMIT_EXCEEDED"


def test_quarantine_deduplicates_identical_bytes(tmp_path: Path) -> None:
    first = write_quarantine_bytes(tmp_path, "incoming/a.bin", b"same")
    second = write_quarantine_bytes(tmp_path, "incoming/a.bin", b"same")
    assert first == second


def test_prior_capture_last_modified_header(tmp_path: Path) -> None:
    transport = FakeTransport(
        responses={"https://example.org/source": (304, {}, b"")},
    )
    collector = _collector(tmp_path, transport)
    prior = PriorCapture(
        last_modified="Sat, 01 Aug 2026 08:00:00 GMT",
        content_sha256="c" * 64,
        quarantine_path="incoming/SRC-0001/abc/source.html",
        size_bytes=10,
        media_type="text/html",
        original_filename="source.html",
    )
    outcome = collector.collect(valid_collection_request(), prior_capture=prior)
    assert outcome.kind == "result"
    assert transport.calls[0].headers["If-Modified-Since"] == "Sat, 01 Aug 2026 08:00:00 GMT"


def test_304_without_prior_capture_fails(tmp_path: Path) -> None:
    transport = FakeTransport(
        responses={"https://example.org/source": (304, {}, b"")},
    )
    collector = _collector(tmp_path, transport)
    outcome = collector.collect(valid_collection_request())
    assert outcome.kind == "failure"
    assert outcome.record["failure_class"] == "HTTP_ERROR"
