from __future__ import annotations

import json
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from neuroai_workbench.collector.acquisition_policy import (
    FALLBACK_FORBID,
    ONLINE_PREFERRED,
    ONLINE_REQUIRED,
    REPLAY_ONLY,
    AcquisitionPolicyError,
    build_acquisition_policy,
)
from neuroai_workbench.collector.config import CollectorConfig
from neuroai_workbench.collector.dns import DnsGuard
from neuroai_workbench.collector.http_client import HttpRequest
from neuroai_workbench.collector.policy_execution import (
    AcquisitionPolicyRuntimeGuard,
    PolicyBoundCollectionScheduler,
    PolicyBoundDnsGuard,
    PolicyBoundTransport,
    PolicyExecutionBlocked,
)
from neuroai_workbench.collector.scheduler import CollectionScheduler, SchedulerConfig
from neuroai_workbench.util import canonical_json_bytes, sha256_bytes

GLOBAL_IP = "93.184.216.34"
CONFIG_HASH = "b" * 64
REGISTRY_HASH = "a" * 64
PROGRAMME_ID = "OBS-PROGRAMME"


@dataclass
class FakeTransport:
    responses: dict[str, tuple[int, dict[str, str], bytes]]
    calls: list[HttpRequest] = field(default_factory=list)

    def send(
        self,
        request: HttpRequest,
        *,
        connect_timeout: float,
        read_timeout: float,
    ) -> tuple[int, dict[str, str], bytes]:
        del connect_timeout, read_timeout
        self.calls.append(request)
        if request.url not in self.responses:
            raise OSError(f"unexpected URL {request.url!r}")
        return self.responses[request.url]


@dataclass
class RecordingResolver:
    hosts: list[str] = field(default_factory=list)

    def __call__(self, host: str, port: Any, *args: Any, **kwargs: Any) -> list[tuple[Any, ...]]:
        del port, args, kwargs
        self.hosts.append(host)
        if host.endswith(".example.org"):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (GLOBAL_IP, 0))]
        raise socket.gaierror("unknown host")


def _source(source_id: str, monitor_id: str, url: str) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "monitor_id": monitor_id,
        "source_class": "OFFICIAL_COMPANY_PAGE",
        "url": url,
    }


def _plan(*items: dict[str, Any], plan_id: str = "PLAN-POLICY-BOUND") -> dict[str, Any]:
    return {
        "plan_id": plan_id,
        "as_of": "2026-09-04",
        "due": [
            {
                "source_id": item["source_id"],
                "monitor_id": item["monitor_id"],
                "url": item["url"],
            }
            for item in items
        ],
        "manual": [],
        "not_due": [],
    }


def _rule(source_id: str, *origins: str, modes: tuple[str, ...] = (ONLINE_REQUIRED,)) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "execution_modes": list(modes),
        "allowed_origins": list(origins),
        "fallback_policy": FALLBACK_FORBID,
    }


def _policy(
    *rules: dict[str, Any],
    policy_id: str = "POLICY-2A",
    programme_id: str = PROGRAMME_ID,
    approved_at: str = "2026-01-01T00:00:00Z",
    expires_at: str | None = "2027-01-01T00:00:00Z",
) -> dict[str, Any]:
    return build_acquisition_policy(
        policy_id=policy_id,
        programme_id=programme_id,
        approved_by="local-reviewer",
        source_rules=rules,
        approved_at=approved_at,
        expires_at=expires_at,
    )


def _config() -> CollectorConfig:
    return CollectorConfig(
        collector_version="0.3.0.dev0-collector",
        configuration_hash=CONFIG_HASH,
        max_attempts=1,
        requests_per_host_per_minute=100,
    )


def _scheduler(
    tmp_path: Path,
    transport: FakeTransport,
    policy: dict[str, Any],
    *,
    execution_mode: str = ONLINE_REQUIRED,
    resolver: RecordingResolver | None = None,
    scheduler_config: SchedulerConfig | None = None,
) -> PolicyBoundCollectionScheduler:
    return PolicyBoundCollectionScheduler(
        acquisition_policy=policy,
        programme_id=PROGRAMME_ID,
        execution_mode=execution_mode,
        collector_config=_config(),
        transport=transport,
        quarantine_root=tmp_path / "quarantine",
        scheduler_config=scheduler_config or SchedulerConfig(max_workers=2, max_workers_per_host=2),
        dns_guard=DnsGuard(getaddrinfo=resolver or RecordingResolver()),
        sleeper=lambda _: None,
    )


def _manifest(tmp_path: Path, run_id: str) -> dict[str, Any]:
    return json.loads((tmp_path / "quarantine" / "run-ledgers" / run_id / "manifest.json").read_text(encoding="utf-8"))


def _checkpoint(tmp_path: Path, run_id: str, target_id: str) -> dict[str, Any]:
    return json.loads(
        (tmp_path / "quarantine" / "run-ledgers" / run_id / "targets" / f"{target_id}.json").read_text(encoding="utf-8")
    )


def test_runtime_guard_requires_request_scoped_sources() -> None:
    policy = _policy(_rule("SRC-A", "https://a.example.org"))
    guard = AcquisitionPolicyRuntimeGuard(
        policy=policy,
        programme_id=PROGRAMME_ID,
        execution_mode=ONLINE_REQUIRED,
    )
    with pytest.raises(PolicyExecutionBlocked, match="no request-scoped logical-source binding"):
        guard.require_url("https://a.example.org/start")


def test_runtime_guard_rejects_empty_source_scope() -> None:
    policy = _policy(_rule("SRC-A", "https://a.example.org"))
    guard = AcquisitionPolicyRuntimeGuard(
        policy=policy,
        programme_id=PROGRAMME_ID,
        execution_mode=ONLINE_REQUIRED,
    )
    with pytest.raises(AcquisitionPolicyError, match="at least one logical source"):
        with guard.bind_source_ids([]):
            raise AssertionError("empty scope must never become active")


def test_runtime_guard_rejects_unsupported_mode() -> None:
    policy = _policy(_rule("SRC-A", "https://a.example.org"))
    with pytest.raises(AcquisitionPolicyError, match="Unsupported execution_mode"):
        AcquisitionPolicyRuntimeGuard(
            policy=policy,
            programme_id=PROGRAMME_ID,
            execution_mode="INVALID",
        )


def test_runtime_guard_context_resets_after_use() -> None:
    policy = _policy(_rule("SRC-A", "https://a.example.org"))
    guard = AcquisitionPolicyRuntimeGuard(
        policy=policy,
        programme_id=PROGRAMME_ID,
        execution_mode=ONLINE_REQUIRED,
    )
    with guard.bind_source_ids(["SRC-A", "SRC-A"]):
        guard.require_url("https://a.example.org/start", at="2026-09-04T00:00:00Z")
    with pytest.raises(PolicyExecutionBlocked, match="no request-scoped logical-source binding"):
        guard.require_url("https://a.example.org/start", at="2026-09-04T00:00:00Z")


def test_policy_dns_guard_checks_before_delegate_dns() -> None:
    resolver = RecordingResolver()
    policy = _policy(_rule("SRC-A", "https://a.example.org"))
    guard = AcquisitionPolicyRuntimeGuard(
        policy=policy,
        programme_id=PROGRAMME_ID,
        execution_mode=ONLINE_REQUIRED,
    )
    dns_guard = PolicyBoundDnsGuard(DnsGuard(getaddrinfo=resolver), guard)
    with guard.bind_source_ids(["SRC-A"]):
        with pytest.raises(PolicyExecutionBlocked, match="outside the source rule"):
            dns_guard.resolve("https://b.example.org/blocked")
    assert resolver.hosts == []


def test_policy_dns_guard_session_and_reset_preserve_policy_guard() -> None:
    resolver = RecordingResolver()
    policy = _policy(_rule("SRC-A", "https://a.example.org"))
    guard = AcquisitionPolicyRuntimeGuard(
        policy=policy,
        programme_id=PROGRAMME_ID,
        execution_mode=ONLINE_REQUIRED,
    )
    session = PolicyBoundDnsGuard(DnsGuard(getaddrinfo=resolver), guard).new_session()
    with guard.bind_source_ids(["SRC-A"]):
        first = session.resolve("https://a.example.org/start")
        session.reset()
        second = session.resolve("https://a.example.org/start")
    assert first.addresses == [GLOBAL_IP]
    assert second.addresses == [GLOBAL_IP]
    assert resolver.hosts == ["a.example.org", "a.example.org"]


def test_policy_transport_checks_before_inner_send() -> None:
    transport = FakeTransport({"https://a.example.org/start": (200, {"Content-Type": "text/html"}, b"<html></html>")})
    policy = _policy(_rule("SRC-A", "https://a.example.org"))
    guard = AcquisitionPolicyRuntimeGuard(
        policy=policy,
        programme_id=PROGRAMME_ID,
        execution_mode=ONLINE_REQUIRED,
    )
    wrapped = PolicyBoundTransport(transport, guard)
    request = HttpRequest("GET", "https://b.example.org/blocked", {}, (GLOBAL_IP,))
    with guard.bind_source_ids(["SRC-A"]):
        with pytest.raises(PolicyExecutionBlocked, match="outside the source rule"):
            wrapped.send(request, connect_timeout=1.0, read_timeout=1.0)
    assert transport.calls == []


def test_policy_transport_forwards_authorized_send() -> None:
    url = "https://a.example.org/start"
    transport = FakeTransport({url: (200, {"Content-Type": "text/html"}, b"<html></html>")})
    policy = _policy(_rule("SRC-A", "https://a.example.org"))
    guard = AcquisitionPolicyRuntimeGuard(
        policy=policy,
        programme_id=PROGRAMME_ID,
        execution_mode=ONLINE_REQUIRED,
    )
    wrapped = PolicyBoundTransport(transport, guard)
    request = HttpRequest("GET", url, {}, (GLOBAL_IP,))
    with guard.bind_source_ids(["SRC-A"]):
        status, headers, body = wrapped.send(request, connect_timeout=1.0, read_timeout=1.0)
    assert status == 200
    assert headers["Content-Type"] == "text/html"
    assert body == b"<html></html>"
    assert [call.url for call in transport.calls] == [url]


def test_programme_mismatch_fails_at_construction(tmp_path: Path) -> None:
    policy = _policy(_rule("SRC-A", "https://a.example.org"), programme_id="OTHER-PROGRAMME")
    with pytest.raises(AcquisitionPolicyError, match="programme_id"):
        _scheduler(tmp_path, FakeTransport({}), policy)


def test_replay_only_cannot_enter_http_executor(tmp_path: Path) -> None:
    policy = _policy(_rule("SRC-A", modes=(REPLAY_ONLY,)))
    with pytest.raises(AcquisitionPolicyError, match="REPLAY_ONLY"):
        _scheduler(tmp_path, FakeTransport({}), policy, execution_mode=REPLAY_ONLY)


def test_tampered_policy_fails_at_construction(tmp_path: Path) -> None:
    policy = _policy(_rule("SRC-A", "https://a.example.org"))
    policy["approved_by"] = "tampered-reviewer"
    with pytest.raises(AcquisitionPolicyError, match="digest mismatch"):
        _scheduler(tmp_path, FakeTransport({}), policy)


def test_scheduler_constructor_defaults_remain_explicitly_policy_bound(tmp_path: Path) -> None:
    policy = _policy(_rule("SRC-A", "https://a.example.org"))
    scheduler = PolicyBoundCollectionScheduler(
        acquisition_policy=policy,
        programme_id=PROGRAMME_ID,
        execution_mode=ONLINE_REQUIRED,
        collector_config=_config(),
        transport=FakeTransport({}),
        quarantine_root=tmp_path / "quarantine",
        monotonic_clock=lambda: 0.0,
    )
    assert scheduler.acquisition_binding == {
        "policy_id": policy["policy_id"],
        "policy_sha256": policy["policy_sha256"],
        "programme_id": PROGRAMME_ID,
        "execution_mode": ONLINE_REQUIRED,
    }


def test_missing_source_is_policy_blocked_without_network(tmp_path: Path) -> None:
    source = _source("SRC-A", "MON-A", "https://a.example.org/start")
    policy = _policy(_rule("SRC-B", "https://a.example.org"))
    transport = FakeTransport({source["url"]: (200, {"Content-Type": "text/html"}, b"<html>ok</html>")})
    run = _scheduler(tmp_path, transport, policy).run_plan(
        _plan(source), registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source}
    )
    assert transport.calls == []
    assert run["counts"]["failed"] == 1
    assert run["outcomes"][0]["failure_class"] == "POLICY_BLOCK"
    assert run["outcomes"][0]["acquisition_route"] == "LIVE"


def test_expired_policy_is_blocked_without_network(tmp_path: Path) -> None:
    source = _source("SRC-A", "MON-A", "https://a.example.org/start")
    policy = _policy(
        _rule("SRC-A", "https://a.example.org"),
        approved_at="2026-01-01T00:00:00Z",
        expires_at="2026-02-01T00:00:00Z",
    )
    transport = FakeTransport({source["url"]: (200, {"Content-Type": "text/html"}, b"<html>ok</html>")})
    run = _scheduler(tmp_path, transport, policy).run_plan(
        _plan(source), registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source}
    )
    assert transport.calls == []
    assert run["outcomes"][0]["failure_class"] == "POLICY_BLOCK"
    assert "expired" in run["outcomes"][0]["message"]


def test_not_yet_active_policy_is_blocked_without_network(tmp_path: Path) -> None:
    source = _source("SRC-A", "MON-A", "https://a.example.org/start")
    policy = _policy(
        _rule("SRC-A", "https://a.example.org"),
        approved_at="2026-12-01T00:00:00Z",
        expires_at="2027-01-01T00:00:00Z",
    )
    transport = FakeTransport({source["url"]: (200, {"Content-Type": "text/html"}, b"<html>ok</html>")})
    run = _scheduler(tmp_path, transport, policy).run_plan(
        _plan(source), registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source}
    )
    assert transport.calls == []
    assert "not active" in run["outcomes"][0]["message"]


def test_manual_source_policy_precheck_runs_before_grouping(tmp_path: Path) -> None:
    source = _source("SRC-A", "MON-A", "https://a.example.org/manual")
    policy = _policy(_rule("SRC-B", "https://a.example.org"))
    transport = FakeTransport({source["url"]: (200, {"Content-Type": "text/html"}, b"<html>ok</html>")})
    plan = _plan()
    plan["manual"] = [
        {
            "source_id": source["source_id"],
            "monitor_id": source["monitor_id"],
            "url": source["url"],
        }
    ]
    scheduler_config = SchedulerConfig(include_manual_sources=True, max_workers=2, max_workers_per_host=2)
    run = _scheduler(tmp_path, transport, policy, scheduler_config=scheduler_config).run_plan(
        plan,
        registry_sha256=REGISTRY_HASH,
        source_index={"SRC-A": source},
    )
    assert transport.calls == []
    assert run["outcomes"][0]["failure_class"] == "POLICY_BLOCK"


def test_unauthorized_member_cannot_inherit_coalesced_result(tmp_path: Path) -> None:
    source_a = _source("SRC-A", "MON-A", "https://a.example.org/shared")
    source_b = _source("SRC-B", "MON-B", "https://a.example.org/shared")
    policy = _policy(_rule("SRC-A", "https://a.example.org"))
    transport = FakeTransport({source_a["url"]: (200, {"Content-Type": "text/html"}, b"<html>ok</html>")})
    run = _scheduler(tmp_path, transport, policy).run_plan(
        _plan(source_a, source_b),
        registry_sha256=REGISTRY_HASH,
        source_index={"SRC-A": source_a, "SRC-B": source_b},
    )
    assert len(transport.calls) == 1
    by_source = {item["source_id"]: item for item in run["outcomes"]}
    assert by_source["SRC-A"]["status"] == "RESULT"
    assert by_source["SRC-B"]["status"] == "FAILURE"
    assert by_source["SRC-B"]["failure_class"] == "POLICY_BLOCK"
    assert "record_id" not in by_source["SRC-B"]


def test_two_authorized_sources_coalesce_to_one_fetch(tmp_path: Path) -> None:
    source_a = _source("SRC-A", "MON-A", "https://a.example.org/shared")
    source_b = _source("SRC-B", "MON-B", "https://a.example.org/shared")
    policy = _policy(
        _rule("SRC-A", "https://a.example.org"),
        _rule("SRC-B", "https://a.example.org"),
    )
    transport = FakeTransport({source_a["url"]: (200, {"Content-Type": "text/html"}, b"<html>ok</html>")})
    run = _scheduler(tmp_path, transport, policy).run_plan(
        _plan(source_a, source_b),
        registry_sha256=REGISTRY_HASH,
        source_index={"SRC-A": source_a, "SRC-B": source_b},
    )
    assert len(transport.calls) == 1
    by_source = {item["source_id"]: item for item in run["outcomes"]}
    assert by_source["SRC-A"]["status"] == "RESULT"
    assert by_source["SRC-B"]["status"] == "RESULT"
    assert by_source["SRC-A"]["record_id"] == by_source["SRC-B"]["record_id"]


def test_adapter_resolved_origin_is_blocked_before_dns_or_send(tmp_path: Path) -> None:
    source = _source("SRC-A", "MON-A", "https://a.example.org/device/K123456")
    source["source_class"] = "REGULATORY_RECORD"
    source["fda_device_id"] = "K123456"
    policy = _policy(_rule("SRC-A", "https://a.example.org"))
    resolver = RecordingResolver()
    transport = FakeTransport({})
    run = _scheduler(tmp_path, transport, policy, resolver=resolver).run_plan(
        _plan(source), registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source}
    )
    assert transport.calls == []
    assert resolver.hosts == []
    outcome = run["outcomes"][0]
    assert outcome["adapter_id"] == "fda_device"
    assert outcome["status"] == "FAILURE"
    assert outcome["failure_class"] == "POLICY_BLOCK"
    assert "api.fda.gov" in outcome["message"]


def test_same_origin_redirect_remains_policy_authorized(tmp_path: Path) -> None:
    source = _source("SRC-A", "MON-A", "https://a.example.org/start")
    policy = _policy(_rule("SRC-A", "https://a.example.org"))
    transport = FakeTransport(
        {
            source["url"]: (302, {"Location": "/final"}, b""),
            "https://a.example.org/final": (200, {"Content-Type": "text/html"}, b"<html>final</html>"),
        }
    )
    run = _scheduler(tmp_path, transport, policy).run_plan(
        _plan(source), registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source}
    )
    assert [call.url for call in transport.calls] == [source["url"], "https://a.example.org/final"]
    assert run["outcomes"][0]["status"] == "RESULT"


def test_cross_origin_redirect_is_policy_failure_without_collector_failure_record(tmp_path: Path) -> None:
    source = _source("SRC-A", "MON-A", "https://a.example.org/start")
    policy = _policy(_rule("SRC-A", "https://a.example.org"))
    resolver = RecordingResolver()
    transport = FakeTransport(
        {
            source["url"]: (302, {"Location": "https://b.example.org/final"}, b""),
            "https://b.example.org/final": (200, {"Content-Type": "text/html"}, b"<html>final</html>"),
        }
    )
    run = _scheduler(tmp_path, transport, policy, resolver=resolver).run_plan(
        _plan(source), registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source}
    )
    assert [call.url for call in transport.calls] == [source["url"]]
    assert resolver.hosts == ["a.example.org"]
    outcome = run["outcomes"][0]
    assert outcome["status"] == "FAILURE"
    assert outcome["failure_class"] == "POLICY_BLOCK"
    assert outcome["record_id"] is None
    assert "b.example.org" in outcome["message"]

    target_id = str(outcome["retrieval_target_id"])
    checkpoint = _checkpoint(tmp_path, run["run_id"], target_id)
    assert checkpoint["state"] == "FAILURE"
    assert checkpoint["outcome"]["failure_class"] == "POLICY_BLOCK"
    assert checkpoint["outcome"]["record_id"] is None
    assert checkpoint["attempts"][0]["policy_blocked"] is True
    assert "b.example.org" in checkpoint["attempts"][0]["policy_block_message"]

    failure_root = tmp_path / "quarantine" / "failures"
    assert not failure_root.exists() or list(failure_root.glob("*.json")) == []


def test_coalesced_redirect_requires_every_logical_source_permission(tmp_path: Path) -> None:
    source_a = _source("SRC-A", "MON-A", "https://a.example.org/start")
    source_b = _source("SRC-B", "MON-B", "https://a.example.org/start")
    policy = _policy(
        _rule("SRC-A", "https://a.example.org", "https://b.example.org"),
        _rule("SRC-B", "https://a.example.org"),
    )
    transport = FakeTransport(
        {
            source_a["url"]: (302, {"Location": "https://b.example.org/final"}, b""),
            "https://b.example.org/final": (200, {"Content-Type": "text/html"}, b"<html>final</html>"),
        }
    )
    run = _scheduler(tmp_path, transport, policy).run_plan(
        _plan(source_a, source_b),
        registry_sha256=REGISTRY_HASH,
        source_index={"SRC-A": source_a, "SRC-B": source_b},
    )
    assert [call.url for call in transport.calls] == [source_a["url"]]
    assert {item["status"] for item in run["outcomes"]} == {"FAILURE"}
    assert {item["failure_class"] for item in run["outcomes"]} == {"POLICY_BLOCK"}
    assert {item["record_id"] for item in run["outcomes"]} == {None}
    assert len({item["retrieval_target_id"] for item in run["outcomes"]}) == 1
    assert all("SRC-B" in item["message"] for item in run["outcomes"])


def test_policy_metadata_is_bound_into_manifest_summary_and_attempt(tmp_path: Path) -> None:
    source = _source("SRC-A", "MON-A", "https://a.example.org/start")
    policy = _policy(_rule("SRC-A", "https://a.example.org"))
    transport = FakeTransport({source["url"]: (200, {"Content-Type": "text/html"}, b"<html>ok</html>")})
    scheduler = _scheduler(tmp_path, transport, policy)
    run = scheduler.run_plan(_plan(source), registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source})

    manifest = _manifest(tmp_path, run["run_id"])
    scheduler_binding = manifest["binding"]["scheduler_configuration"]
    assert scheduler_binding["acquisition_policy_id"] == policy["policy_id"]
    assert scheduler_binding["acquisition_policy_sha256"] == policy["policy_sha256"]
    assert scheduler_binding["acquisition_programme_id"] == PROGRAMME_ID
    assert scheduler_binding["acquisition_execution_mode"] == ONLINE_REQUIRED
    assert run["acquisition"]["policy_sha256"] == policy["policy_sha256"]
    assert run["acquisition"]["route"] == "LIVE"
    assert run["acquisition"]["fallback_used"] is False
    assert run["retrieval_targets"][0]["acquisition_route"] == "LIVE"

    target_id = manifest["binding"]["retrieval_targets"][0]["retrieval_target_id"]
    checkpoint = _checkpoint(tmp_path, run["run_id"], target_id)
    assert checkpoint["attempts"][0]["acquisition_route"] == "LIVE"
    assert checkpoint["attempts"][0]["acquisition_policy_sha256"] == policy["policy_sha256"]

    semantic = {
        key: run[key]
        for key in (
            "run_id",
            "plan_id",
            "execution_status",
            "counts",
            "slo",
            "retrieval_targets",
            "outcomes",
            "per_host",
        )
    }
    semantic["acquisition"] = run["acquisition"]
    assert run["semantic_summary_sha256"] == sha256_bytes(canonical_json_bytes(semantic))


def test_policy_identity_changes_deterministic_run_lineage(tmp_path: Path) -> None:
    source = _source("SRC-A", "MON-A", "https://a.example.org/start")
    policy_a = _policy(_rule("SRC-A", "https://a.example.org"), policy_id="POLICY-A")
    policy_b = _policy(_rule("SRC-A", "https://a.example.org"), policy_id="POLICY-B")
    transport = FakeTransport({source["url"]: (200, {"Content-Type": "text/html"}, b"<html>ok</html>")})
    plan = _plan(source)
    run_a = _scheduler(tmp_path, transport, policy_a).run_plan(
        plan, registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source}
    )
    run_b = _scheduler(tmp_path, transport, policy_b).run_plan(
        plan, registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source}
    )
    assert policy_a["policy_sha256"] != policy_b["policy_sha256"]
    assert run_a["run_id"] != run_b["run_id"]
    assert run_a["binding_sha256"] != run_b["binding_sha256"]
    assert len(transport.calls) == 2


def test_online_preferred_live_path_records_no_fallback(tmp_path: Path) -> None:
    source = _source("SRC-A", "MON-A", "https://a.example.org/start")
    policy = _policy(_rule("SRC-A", "https://a.example.org", modes=(ONLINE_PREFERRED,)))
    transport = FakeTransport({source["url"]: (200, {"Content-Type": "text/html"}, b"<html>ok</html>")})
    run = _scheduler(tmp_path, transport, policy, execution_mode=ONLINE_PREFERRED).run_plan(
        _plan(source), registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source}
    )
    assert run["outcomes"][0]["status"] == "RESULT"
    assert run["acquisition"]["execution_mode"] == ONLINE_PREFERRED
    assert run["acquisition"]["fallback_used"] is False


def test_legacy_scheduler_binding_has_no_policy_fields(tmp_path: Path) -> None:
    source = _source("SRC-A", "MON-A", "https://a.example.org/start")
    transport = FakeTransport({source["url"]: (200, {"Content-Type": "text/html"}, b"<html>ok</html>")})
    legacy = CollectionScheduler(
        collector_config=_config(),
        transport=transport,
        quarantine_root=tmp_path / "legacy-quarantine",
        scheduler_config=SchedulerConfig(max_workers=1, max_workers_per_host=1),
        dns_guard=DnsGuard(getaddrinfo=RecordingResolver()),
        sleeper=lambda _: None,
    )
    run = legacy.run_plan(_plan(source), registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source})
    manifest = json.loads(
        (tmp_path / "legacy-quarantine" / "run-ledgers" / run["run_id"] / "manifest.json").read_text(encoding="utf-8")
    )
    scheduler_binding = manifest["binding"]["scheduler_configuration"]
    assert all(not key.startswith("acquisition_") for key in scheduler_binding)
    assert "acquisition" not in run
