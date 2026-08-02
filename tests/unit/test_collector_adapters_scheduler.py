from __future__ import annotations

import ast
import json
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from neuroai_workbench.collector import (
    CollectionScheduler,
    SchedulerConfig,
    StaticCredentialProvider,
    approve_quarantine_record,
    prepare_monitoring_handoff,
)
from neuroai_workbench.collector.adapters.registry_stub import REGISTRY_STUB_BODY
from neuroai_workbench.collector.config import CollectorConfig
from neuroai_workbench.collector.credentials import (
    embedded_credential_in_url,
    refuse_embedded_secrets_in_request,
)
from neuroai_workbench.collector.dns import DnsGuard
from neuroai_workbench.collector.errors import CollectionFailureError
from neuroai_workbench.collector.http_client import HttpRequest
from neuroai_workbench.monitoring import plan_monitoring_run
from neuroai_workbench.util import atomic_write_json
from tests.unit.test_collector_schemas import CONFIG_HASH, valid_collection_request
from tests.unit.test_monitoring import small_registry

GLOBAL_IP = "93.184.216.34"


def global_getaddrinfo(host: str, port: Any, *args: Any, **kwargs: Any) -> list[tuple[Any, ...]]:
    if host.endswith(".example.org"):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (GLOBAL_IP, 0))]
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


def _scheduler(
    tmp_path: Path,
    transport: FakeTransport,
    *,
    scheduler_config: SchedulerConfig | None = None,
    credential_provider: StaticCredentialProvider | None = None,
) -> CollectionScheduler:
    config = CollectorConfig(
        collector_version="0.3.0.dev0-collector",
        configuration_hash=CONFIG_HASH,
        requests_per_host_per_minute=100,
    )
    return CollectionScheduler(
        collector_config=config,
        transport=transport,
        quarantine_root=tmp_path / "quarantine",
        scheduler_config=scheduler_config or SchedulerConfig(),
        credential_provider=credential_provider,
        dns_guard=DnsGuard(getaddrinfo=global_getaddrinfo),
    )


def _source_index(records: list[dict[str, object]]) -> dict[str, dict[str, Any]]:
    return {str(record["source_id"]): dict(record) for record in records}


def _registry_with_classes(tmp_path: Path) -> tuple[Path, dict[str, dict[str, Any]], str]:
    records = small_registry()
    records[0]["source_class"] = "REGULATORY_RECORD"
    records[0]["url"] = "https://registry.example.org/entry"
    records[1]["source_class"] = "PUBLIC_JSON_API"
    records[1]["url"] = "https://api.example.org/status.json"
    records[1]["cadence"] = "DAILY"
    records[1]["last_successful_retrieval"] = "2026-07-01"
    registry_path = tmp_path / "registry.json"
    atomic_write_json(registry_path, records)
    workspace = tmp_path / "workspace"
    from neuroai_workbench.monitoring import initialize_monitoring

    init = initialize_monitoring(workspace, registry_path, actor="tester")
    return workspace, _source_index(records), init["registry_sha256"]


@pytest.fixture
def html_transport() -> FakeTransport:
    return FakeTransport(
        responses={
            "https://registry.example.org/entry": (200, {"Content-Type": "text/html"}, b"<!doctype html><html></html>"),
            "https://api.example.org/status.json": (200, {"Content-Type": "application/json"}, b'{"status":"ok"}'),
            "https://registry.example.org/stub": (200, {"Content-Type": "application/xml"}, REGISTRY_STUB_BODY),
            "https://protected.example.org/report.pdf": (
                200,
                {"Content-Type": "application/octet-stream"},
                b"%PDF-1.4 protected",
            ),
        }
    )


def test_html_page_adapter(tmp_path: Path) -> None:
    records = small_registry()
    records[0]["source_class"] = "OFFICIAL_COMPANY_PAGE"
    records[0]["url"] = "https://pages.example.org/about"
    registry_path = tmp_path / "registry.json"
    atomic_write_json(registry_path, records)
    workspace = tmp_path / "workspace"
    from neuroai_workbench.monitoring import initialize_monitoring

    init = initialize_monitoring(workspace, registry_path, actor="tester")
    transport = FakeTransport(
        responses={
            "https://pages.example.org/about": (
                200,
                {"Content-Type": "text/html"},
                b"<!doctype html><html><body>about</body></html>",
            )
        }
    )
    scheduler = _scheduler(tmp_path, transport)
    plan = plan_monitoring_run(workspace, as_of="2026-08-02", source_ids=["SRC-0001"])
    run = scheduler.run_plan(plan, registry_sha256=init["registry_sha256"], source_index=_source_index(records))
    assert run["outcomes"][0]["adapter_id"] == "html"
    assert run["outcomes"][0]["status"] == "RESULT"


def test_html_adapter_rejects_non_html(tmp_path: Path) -> None:
    records = small_registry()
    records[0]["source_class"] = "OFFICIAL_COMPANY_PAGE"
    records[0]["url"] = "https://pages.example.org/plain"
    registry_path = tmp_path / "registry.json"
    atomic_write_json(registry_path, records)
    workspace = tmp_path / "workspace"
    from neuroai_workbench.monitoring import initialize_monitoring

    init = initialize_monitoring(workspace, registry_path, actor="tester")
    transport = FakeTransport(
        responses={
            "https://pages.example.org/plain": (
                200,
                {"Content-Type": "text/html"},
                b"plain text without html markers",
            )
        }
    )
    scheduler = _scheduler(tmp_path, transport)
    plan = plan_monitoring_run(workspace, as_of="2026-08-02", source_ids=["SRC-0001"])
    run = scheduler.run_plan(plan, registry_sha256=init["registry_sha256"], source_index=_source_index(records))
    assert run["outcomes"][0]["adapter_id"] == "html"
    assert run["outcomes"][0]["status"] == "FAILURE"


def test_registry_stub_adapter_collects_stub_payload(tmp_path: Path, html_transport: FakeTransport) -> None:
    workspace, source_index, registry_sha256 = _registry_with_classes(tmp_path)
    html_transport.responses["https://registry.example.org/entry"] = (
        200,
        {"Content-Type": "application/xml"},
        REGISTRY_STUB_BODY,
    )
    scheduler = _scheduler(tmp_path, html_transport)
    plan = plan_monitoring_run(workspace, as_of="2026-08-02", source_ids=["SRC-0001"])
    run = scheduler.run_plan(plan, registry_sha256=registry_sha256, source_index=source_index)
    assert run["outcomes"][0]["adapter_id"] == "registry_stub"
    assert run["outcomes"][0]["status"] == "RESULT"


def test_json_api_adapter_validates_json(tmp_path: Path, html_transport: FakeTransport) -> None:
    workspace, source_index, registry_sha256 = _registry_with_classes(tmp_path)
    html_transport.responses["https://api.example.org/status.json"] = (
        200,
        {"Content-Type": "application/json"},
        b"not-json",
    )
    scheduler = _scheduler(tmp_path, html_transport)
    plan = plan_monitoring_run(workspace, as_of="2026-08-02", source_ids=["SRC-0002"])
    run = scheduler.run_plan(plan, registry_sha256=registry_sha256, source_index=source_index)
    assert run["outcomes"][0]["adapter_id"] == "json_api"
    assert run["outcomes"][0]["status"] == "FAILURE"


def test_json_api_adapter_success(tmp_path: Path, html_transport: FakeTransport) -> None:
    workspace, source_index, registry_sha256 = _registry_with_classes(tmp_path)
    scheduler = _scheduler(tmp_path, html_transport)
    plan = plan_monitoring_run(workspace, as_of="2026-08-02", source_ids=["SRC-0002"])
    run = scheduler.run_plan(plan, registry_sha256=registry_sha256, source_index=source_index)
    assert run["outcomes"][0]["status"] == "RESULT"


def test_xml_feed_adapter_accepts_rss(tmp_path: Path) -> None:
    records = small_registry()
    records[0]["source_class"] = "RSS_FEED"
    records[0]["url"] = "https://feed.example.org/rss.xml"
    registry_path = tmp_path / "registry.json"
    atomic_write_json(registry_path, records)
    workspace = tmp_path / "workspace"
    from neuroai_workbench.monitoring import initialize_monitoring

    init = initialize_monitoring(workspace, registry_path, actor="tester")
    transport = FakeTransport(
        responses={
            "https://feed.example.org/rss.xml": (
                200,
                {"Content-Type": "application/xml"},
                b'<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>',
            )
        }
    )
    scheduler = _scheduler(tmp_path, transport)
    plan = plan_monitoring_run(workspace, as_of="2026-08-02", source_ids=["SRC-0001"])
    run = scheduler.run_plan(plan, registry_sha256=init["registry_sha256"], source_index=_source_index(records))
    assert run["outcomes"][0]["adapter_id"] == "xml_feed"
    assert run["outcomes"][0]["status"] == "RESULT"


def test_auth_download_stub_uses_runtime_credentials(tmp_path: Path) -> None:
    records = small_registry()
    records[0]["source_class"] = "CONTROLLED_AUTHENTICATED_DOWNLOAD"
    records[0]["url"] = "https://protected.example.org/report.pdf"
    registry_path = tmp_path / "registry.json"
    atomic_write_json(registry_path, records)
    workspace = tmp_path / "workspace"
    from neuroai_workbench.monitoring import initialize_monitoring

    init = initialize_monitoring(workspace, registry_path, actor="tester")
    transport = FakeTransport(
        responses={
            "https://protected.example.org/report.pdf": (
                200,
                {"Content-Type": "application/octet-stream"},
                b"%PDF-1.4 protected",
            )
        }
    )
    scheduler = _scheduler(
        tmp_path,
        transport,
        credential_provider=StaticCredentialProvider({"SRC-0001": "Bearer test-token-offline"}),
    )
    plan = plan_monitoring_run(workspace, as_of="2026-08-02", source_ids=["SRC-0001"])
    run = scheduler.run_plan(plan, registry_sha256=init["registry_sha256"], source_index=_source_index(records))
    assert run["outcomes"][0]["adapter_id"] == "auth_download"
    assert run["outcomes"][0]["status"] == "RESULT"
    assert transport.calls[0].headers["Authorization"] == "Bearer test-token-offline"
    result_path = tmp_path / "quarantine" / "results" / f"{run['outcomes'][0]['record_id']}.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert "Bearer" not in json.dumps(result)
    assert "test-token-offline" not in json.dumps(result)


def test_auth_download_refuses_missing_credentials(tmp_path: Path) -> None:
    records = small_registry()
    records[0]["source_class"] = "CONTROLLED_AUTHENTICATED_DOWNLOAD"
    records[0]["url"] = "https://protected.example.org/report.pdf"
    registry_path = tmp_path / "registry.json"
    atomic_write_json(registry_path, records)
    workspace = tmp_path / "workspace"
    from neuroai_workbench.monitoring import initialize_monitoring

    init = initialize_monitoring(workspace, registry_path, actor="tester")
    transport = FakeTransport(responses={})
    scheduler = _scheduler(tmp_path, transport, credential_provider=StaticCredentialProvider({}))
    plan = plan_monitoring_run(workspace, as_of="2026-08-02", source_ids=["SRC-0001"])
    run = scheduler.run_plan(plan, registry_sha256=init["registry_sha256"], source_index=_source_index(records))
    assert run["outcomes"][0]["status"] == "FAILURE"


def test_refuses_embedded_credentials_in_request() -> None:
    request = valid_collection_request()
    request["requested_url"] = "https://user:secret@example.org/source"
    with pytest.raises(CollectionFailureError) as exc:
        refuse_embedded_secrets_in_request(request)
    assert exc.value.failure_class == "CREDENTIAL_LEAK_PREVENTED"
    assert embedded_credential_in_url(request["requested_url"])


def test_scheduler_consumes_monitor_plan(tmp_path: Path, html_transport: FakeTransport) -> None:
    workspace, source_index, registry_sha256 = _registry_with_classes(tmp_path)
    scheduler = _scheduler(tmp_path, html_transport)
    plan = plan_monitoring_run(workspace, as_of="2026-08-02")
    run = scheduler.run_plan(plan, registry_sha256=registry_sha256, source_index=source_index)
    assert run["plan_id"] == plan["plan_id"]
    assert run["counts"]["total"] == len(plan["due"])


def test_scheduler_policy_blocks_non_http_without_aborting_plan(
    tmp_path: Path, html_transport: FakeTransport
) -> None:
    workspace, source_index, registry_sha256 = _registry_with_classes(tmp_path)
    scheduler = _scheduler(tmp_path, html_transport)
    plan = {
        "plan_id": "PLAN-TEST",
        "as_of": "2026-08-02",
        "due": [
            {
                "monitor_id": "MON-SRC-0001",
                "source_id": "SRC-0001",
                "url": "https://registry.example.org/entry",
            },
            {
                "monitor_id": "MON-BAD",
                "source_id": "SRC-LOCAL-BAD",
                "url": "/mnt/data/controlled/local.json",
            },
        ],
        "manual": [],
        "not_due": [],
    }
    source_index = {
        **source_index,
        "SRC-LOCAL-BAD": {
            "source_id": "SRC-LOCAL-BAD",
            "monitor_id": "MON-BAD",
            "source_class": "CONTROLLED_LOCAL_INPUT",
            "url": "/mnt/data/controlled/local.json",
        },
    }
    run = scheduler.run_plan(plan, registry_sha256=registry_sha256, source_index=source_index)
    assert run["status"] == "COMPLETED"
    by_id = {item["source_id"]: item for item in run["outcomes"]}
    assert by_id["SRC-LOCAL-BAD"]["status"] == "FAILURE"
    assert by_id["SRC-LOCAL-BAD"]["reason"] == "POLICY_BLOCK"
    assert by_id["SRC-0001"]["status"] == "RESULT"
    assert len(html_transport.calls) == 1


def test_collection_kill_switch(tmp_path: Path, html_transport: FakeTransport) -> None:
    workspace, source_index, registry_sha256 = _registry_with_classes(tmp_path)
    scheduler = _scheduler(tmp_path, html_transport, scheduler_config=SchedulerConfig(collection_enabled=False))
    plan = plan_monitoring_run(workspace, as_of="2026-08-02")
    run = scheduler.run_plan(plan, registry_sha256=registry_sha256, source_index=source_index)
    assert run["status"] == "KILLED"
    assert run["kill_reason"] == "collection_disabled"


def test_source_kill_switch(tmp_path: Path, html_transport: FakeTransport) -> None:
    workspace, source_index, registry_sha256 = _registry_with_classes(tmp_path)
    scheduler = _scheduler(
        tmp_path,
        html_transport,
        scheduler_config=SchedulerConfig(disabled_source_ids=frozenset({"SRC-0001"})),
    )
    plan = plan_monitoring_run(workspace, as_of="2026-08-02", source_ids=["SRC-0001"])
    run = scheduler.run_plan(plan, registry_sha256=registry_sha256, source_index=source_index)
    assert run["outcomes"][0]["status"] == "SKIPPED"
    assert run["outcomes"][0]["reason"] == "source_kill_switch"


def test_adapter_kill_switch(tmp_path: Path, html_transport: FakeTransport) -> None:
    workspace, source_index, registry_sha256 = _registry_with_classes(tmp_path)
    scheduler = _scheduler(
        tmp_path,
        html_transport,
        scheduler_config=SchedulerConfig(disabled_adapter_ids=frozenset({"registry_stub"})),
    )
    plan = plan_monitoring_run(workspace, as_of="2026-08-02", source_ids=["SRC-0001"])
    run = scheduler.run_plan(plan, registry_sha256=registry_sha256, source_index=source_index)
    assert run["outcomes"][0]["status"] == "SKIPPED"
    assert run["outcomes"][0]["reason"] == "adapter_kill_switch"


def test_handoff_blocked_without_quarantine_approval(tmp_path: Path, html_transport: FakeTransport) -> None:
    workspace, source_index, registry_sha256 = _registry_with_classes(tmp_path)
    scheduler = _scheduler(tmp_path, html_transport, scheduler_config=SchedulerConfig(handoff_enabled=True))
    plan = plan_monitoring_run(workspace, as_of="2026-08-02", source_ids=["SRC-0002"])
    run = scheduler.run_plan(plan, registry_sha256=registry_sha256, source_index=source_index)
    result_id = run["outcomes"][0]["record_id"]
    quarantine_id = next((tmp_path / "quarantine" / "records").glob("*.json")).stem
    with pytest.raises(ValueError, match="Quarantine approval is required"):
        prepare_monitoring_handoff(tmp_path / "quarantine", quarantine_id)
    with pytest.raises(ValueError, match="approval"):
        scheduler.attempt_handoff(quarantine_id)
    approve_quarantine_record(tmp_path / "quarantine", quarantine_id, approved_by="reviewer")
    payload = prepare_monitoring_handoff(tmp_path / "quarantine", quarantine_id)
    assert payload.result_id == result_id
    handoff = scheduler.attempt_handoff(quarantine_id)
    assert handoff["handoff_state"] == "READY_FOR_MONITORING_SNAPSHOT"
    assert handoff["sha256"]


def test_handoff_kill_switch(tmp_path: Path, html_transport: FakeTransport) -> None:
    workspace, source_index, registry_sha256 = _registry_with_classes(tmp_path)
    scheduler = _scheduler(tmp_path, html_transport, scheduler_config=SchedulerConfig(handoff_enabled=False))
    plan = plan_monitoring_run(workspace, as_of="2026-08-02", source_ids=["SRC-0002"])
    scheduler.run_plan(plan, registry_sha256=registry_sha256, source_index=source_index)
    quarantine_id = next((tmp_path / "quarantine" / "records").glob("*.json")).stem
    approve_quarantine_record(tmp_path / "quarantine", quarantine_id, approved_by="reviewer")
    with pytest.raises(ValueError, match="handoff kill switch"):
        scheduler.attempt_handoff(quarantine_id)


def test_collector_package_forbids_monitoring_write_apis() -> None:
    collector_root = Path(__file__).resolve().parents[2] / "src" / "neuroai_workbench" / "collector"
    forbidden_names = {
        "record_snapshot",
        "record_snapshot_file",
        "adjudicate_change_candidate",
        "adjudicate",
        "create_change_candidate",
    }
    for path in collector_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.endswith("monitoring"):
                imported = {alias.name for alias in node.names}
                assert imported.isdisjoint(forbidden_names), (
                    f"{path.relative_to(collector_root)} imports forbidden monitoring APIs: {imported}"
                )
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "neuroai_workbench.monitoring", (
                        f"{path.relative_to(collector_root)} imports monitoring module"
                    )
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in forbidden_names:
                    raise AssertionError(
                        f"{path.relative_to(collector_root)} calls forbidden monitoring API {node.func.attr!r}"
                    )


def test_reject_quarantine_record(tmp_path: Path, html_transport: FakeTransport) -> None:
    workspace, source_index, registry_sha256 = _registry_with_classes(tmp_path)
    scheduler = _scheduler(tmp_path, html_transport)
    plan = plan_monitoring_run(workspace, as_of="2026-08-02", source_ids=["SRC-0002"])
    scheduler.run_plan(plan, registry_sha256=registry_sha256, source_index=source_index)
    quarantine_id = next((tmp_path / "quarantine" / "records").glob("*.json")).stem
    from neuroai_workbench.collector import reject_quarantine_record

    rejected = reject_quarantine_record(
        tmp_path / "quarantine",
        quarantine_id,
        rejected_by="reviewer",
        rejection_reason="suspicious payload",
    )
    assert rejected["approval_state"] == "REJECTED"
    with pytest.raises(ValueError, match="cannot be approved"):
        approve_quarantine_record(tmp_path / "quarantine", quarantine_id, approved_by="reviewer")


def test_handoff_rejects_missing_bytes(tmp_path: Path, html_transport: FakeTransport) -> None:
    workspace, source_index, registry_sha256 = _registry_with_classes(tmp_path)
    scheduler = _scheduler(tmp_path, html_transport)
    plan = plan_monitoring_run(workspace, as_of="2026-08-02", source_ids=["SRC-0002"])
    scheduler.run_plan(plan, registry_sha256=registry_sha256, source_index=source_index)
    quarantine_id = next((tmp_path / "quarantine" / "records").glob("*.json")).stem
    approve_quarantine_record(tmp_path / "quarantine", quarantine_id, approved_by="reviewer")
    record = json.loads((tmp_path / "quarantine" / "records" / f"{quarantine_id}.json").read_text(encoding="utf-8"))
    (tmp_path / "quarantine" / record["quarantine_path"]).unlink()
    with pytest.raises(ValueError, match="Quarantine bytes missing"):
        prepare_monitoring_handoff(tmp_path / "quarantine", quarantine_id)


def test_scheduler_skips_unknown_source(tmp_path: Path, html_transport: FakeTransport) -> None:
    workspace, source_index, registry_sha256 = _registry_with_classes(tmp_path)
    scheduler = _scheduler(tmp_path, html_transport)
    plan = plan_monitoring_run(workspace, as_of="2026-08-02", source_ids=["SRC-0002"])
    source_index.pop("SRC-0002")
    run = scheduler.run_plan(plan, registry_sha256=registry_sha256, source_index=source_index)
    assert run["outcomes"][0]["reason"] == "unknown_source"


def test_scheduler_never_calls_record_snapshot(
    tmp_path: Path,
    html_transport: FakeTransport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, source_index, registry_sha256 = _registry_with_classes(tmp_path)
    scheduler = _scheduler(tmp_path, html_transport, scheduler_config=SchedulerConfig(handoff_enabled=True))

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("record_snapshot must not be called from collector scheduler")

    monkeypatch.setattr("neuroai_workbench.monitoring.record_snapshot", forbidden)
    plan = plan_monitoring_run(workspace, as_of="2026-08-02", source_ids=["SRC-0002"])
    run = scheduler.run_plan(plan, registry_sha256=registry_sha256, source_index=source_index)
    quarantine_id = next((tmp_path / "quarantine" / "records").glob("*.json")).stem
    approve_quarantine_record(tmp_path / "quarantine", quarantine_id, approved_by="reviewer")
    handoff = scheduler.attempt_handoff(quarantine_id)
    assert handoff["handoff_state"] == "READY_FOR_MONITORING_SNAPSHOT"
    assert run["status"] == "COMPLETED"
