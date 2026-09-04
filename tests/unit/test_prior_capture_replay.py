from __future__ import annotations

import json
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from neuroai_workbench.collector.acquisition_policy import (
    FALLBACK_FORBID,
    FALLBACK_PRIOR_CAPTURE,
    ONLINE_PREFERRED,
    ONLINE_REQUIRED,
    REPLAY_ONLY,
    build_acquisition_policy,
)
from neuroai_workbench.collector.config import CollectorConfig
from neuroai_workbench.collector.dns import DnsGuard
from neuroai_workbench.collector.http_client import HttpRequest
from neuroai_workbench.collector.prior_capture_replay import (
    FALLBACK_PENDING,
    FALLBACK_ROUTE,
    REPLAY_ROUTE,
    PolicyBoundFallbackCollectionScheduler,
    PriorCaptureError,
    PriorCaptureReference,
    ReplayOnlyCollectionScheduler,
    build_prior_capture_snapshot,
    verify_prior_capture_reference,
)
from neuroai_workbench.collector.run_ledger import RUN_LEDGER_BOUNDARY
from neuroai_workbench.collector.scheduler import SchedulerConfig
from neuroai_workbench.collector.url_normalize import (
    RetrievalTargetGroup,
    normalize_retrieval_url,
    retrieval_target_id,
)
from neuroai_workbench.util import sha256_bytes

GLOBAL_IP = "93.184.216.34"
CONFIG_HASH = "b" * 64
REGISTRY_HASH = "a" * 64
PROGRAMME_ID = "OBS-PROGRAMME"
URL = "https://a.example.org/data"


@dataclass
class FailingTransport:
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
        raise OSError("offline for test")


@dataclass
class SuccessTransport:
    body: bytes = b"live"
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
        return 200, {"content-type": "text/html"}, self.body


@dataclass
class RecordingResolver:
    hosts: list[str] = field(default_factory=list)

    def __call__(self, host: str, port: Any, *args: Any, **kwargs: Any) -> list[tuple[Any, ...]]:
        del port, args, kwargs
        self.hosts.append(host)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (GLOBAL_IP, 0))]


def _source(source_id: str = "SRC-A", url: str = URL) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "monitor_id": f"MON-{source_id}",
        "source_class": "OFFICIAL_COMPANY_PAGE",
        "url": url,
    }


def _plan(*sources: dict[str, Any], plan_id: str = "PLAN-2B", as_of: str = "2026-09-04") -> dict[str, Any]:
    return {
        "plan_id": plan_id,
        "as_of": as_of,
        "due": [
            {
                "source_id": source["source_id"],
                "monitor_id": source["monitor_id"],
                "url": source["url"],
            }
            for source in sources
        ],
        "manual": [],
        "not_due": [],
    }


def _rule(
    source_id: str,
    *,
    modes: tuple[str, ...],
    fallback: str = FALLBACK_FORBID,
    origin: str = "https://a.example.org",
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "execution_modes": list(modes),
        "allowed_origins": [origin] if any(mode in {ONLINE_REQUIRED, ONLINE_PREFERRED} for mode in modes) else [],
        "fallback_policy": fallback,
    }


def _policy(*rules: dict[str, Any], policy_id: str = "POLICY-2B") -> dict[str, Any]:
    return build_acquisition_policy(
        policy_id=policy_id,
        programme_id=PROGRAMME_ID,
        approved_by="automated-technical-disposition",
        source_rules=rules,
        approved_at="2026-01-01T00:00:00Z",
        expires_at="2027-01-01T00:00:00Z",
    )


def _config(*, max_attempts: int = 1) -> CollectorConfig:
    return CollectorConfig(
        collector_version="0.3.0.dev0-collector",
        configuration_hash=CONFIG_HASH,
        max_attempts=max_attempts,
        requests_per_host_per_minute=100,
    )


def _seed_capture(
    quarantine_root: Path,
    *,
    result_id: str,
    url: str = URL,
    retrieved_at: str = "2026-09-03T00:00:00Z",
    body: bytes = b"prior",
    source_id: str = "SRC-A",
    sha256_override: str | None = None,
    size_override: int | None = None,
) -> dict[str, Any]:
    digest = sha256_bytes(body)
    quarantine_path = f"incoming/{source_id}/{digest[:12]}/capture.bin"
    byte_path = quarantine_root / quarantine_path
    byte_path.parent.mkdir(parents=True, exist_ok=True)
    byte_path.write_bytes(body)
    record = {
        "result_id": result_id,
        "source_id": source_id,
        "monitor_id": f"MON-{source_id}",
        "requested_url": url,
        "retrieved_at": retrieved_at,
        "sha256": sha256_override or digest,
        "quarantine_path": quarantine_path,
        "size_bytes": len(body) if size_override is None else size_override,
        "media_type": "application/octet-stream",
        "original_filename": "capture.bin",
    }
    results = quarantine_root / "results"
    results.mkdir(parents=True, exist_ok=True)
    (results / f"{result_id}.json").write_text(json.dumps(record), encoding="utf-8")
    return record


def _fallback_scheduler(
    tmp_path: Path,
    transport: Any,
    policy: dict[str, Any],
    *,
    execution_mode: str = ONLINE_PREFERRED,
    max_attempts: int = 1,
) -> PolicyBoundFallbackCollectionScheduler:
    return PolicyBoundFallbackCollectionScheduler(
        acquisition_policy=policy,
        programme_id=PROGRAMME_ID,
        execution_mode=execution_mode,
        collector_config=_config(max_attempts=max_attempts),
        transport=transport,
        quarantine_root=tmp_path / "quarantine",
        scheduler_config=SchedulerConfig(max_workers=2, max_workers_per_host=2),
        dns_guard=DnsGuard(getaddrinfo=RecordingResolver()),
        sleeper=lambda _: None,
    )


def _replay_scheduler(tmp_path: Path, policy: dict[str, Any]) -> ReplayOnlyCollectionScheduler:
    return ReplayOnlyCollectionScheduler(
        acquisition_policy=policy,
        programme_id=PROGRAMME_ID,
        collector_config=_config(),
        quarantine_root=tmp_path / "quarantine",
        scheduler_config=SchedulerConfig(max_workers=1, max_workers_per_host=1),
    )


def test_snapshot_selects_latest_eligible_capture_deterministically(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    _seed_capture(root, result_id="CRES-OLD", retrieved_at="2026-09-01T00:00:00Z")
    _seed_capture(root, result_id="CRES-LATEST-B", retrieved_at="2026-09-03T00:00:00Z", body=b"b")
    _seed_capture(root, result_id="CRES-LATEST-A", retrieved_at="2026-09-03T00:00:00Z", body=b"a")
    _seed_capture(root, result_id="CRES-FUTURE", retrieved_at="2026-09-05T00:00:00Z", body=b"future")

    snapshot = build_prior_capture_snapshot(root)
    selected = snapshot.select(URL, as_of="2026-09-04")

    assert selected is not None
    assert selected.result_id == "CRES-LATEST-B"
    assert len(snapshot.snapshot_sha256) == 64


def test_snapshot_skips_missing_or_corrupt_bytes(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    _seed_capture(root, result_id="CRES-BAD-HASH", sha256_override="0" * 64)
    record = _seed_capture(root, result_id="CRES-MISSING", body=b"missing")
    (root / record["quarantine_path"]).unlink()
    _seed_capture(root, result_id="CRES-BAD-SIZE", body=b"bad-size", size_override=999)

    snapshot = build_prior_capture_snapshot(root)

    assert snapshot.captures == ()
    assert snapshot.select(URL, as_of="2026-09-04") is None


def test_bound_reference_detects_record_or_byte_mutation(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    record = _seed_capture(root, result_id="CRES-STABLE")
    reference = build_prior_capture_snapshot(root).select(URL, as_of="2026-09-04")
    assert reference is not None
    verify_prior_capture_reference(root, reference)

    (root / record["quarantine_path"]).write_bytes(b"tampered")
    with pytest.raises(PriorCaptureError, match="byte size|SHA-256"):
        verify_prior_capture_reference(root, reference)


def test_reference_binding_rejects_malformed_binding() -> None:
    with pytest.raises(PriorCaptureError, match="binding is malformed"):
        PriorCaptureReference.from_binding({"result_id": "CRES-X"})


def test_online_preferred_retryable_failure_uses_bound_prior_capture(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    _seed_capture(root, result_id="CRES-PRIOR")
    source = _source()
    policy = _policy(
        _rule(
            "SRC-A",
            modes=(ONLINE_PREFERRED, REPLAY_ONLY),
            fallback=FALLBACK_PRIOR_CAPTURE,
        )
    )
    transport = FailingTransport()
    scheduler = _fallback_scheduler(tmp_path, transport, policy)

    summary = scheduler.run_plan(_plan(source), registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source})

    assert len(transport.calls) == 1
    assert summary["execution_status"] == "COMPLETE"
    assert summary["acquisition"]["fallback_used"] is True
    assert summary["counts"]["prior_capture_fallbacks"] == 1
    assert summary["outcomes"][0]["record_id"] == "CRES-PRIOR"
    assert summary["outcomes"][0]["acquisition_route"] == FALLBACK_ROUTE
    prior = summary["outcomes"][0]["prior_capture"]
    assert prior["result_id"] == "CRES-PRIOR"
    assert prior["retrieved_at"] == "2026-09-03T00:00:00Z"
    assert prior["content_sha256"] == sha256_bytes(b"prior")
    assert prior["capture_age_seconds"] == 172799


def test_online_required_never_uses_prior_capture(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    _seed_capture(root, result_id="CRES-PRIOR")
    source = _source()
    policy = _policy(
        _rule(
            "SRC-A",
            modes=(ONLINE_REQUIRED, ONLINE_PREFERRED),
            fallback=FALLBACK_PRIOR_CAPTURE,
        )
    )
    scheduler = _fallback_scheduler(tmp_path, FailingTransport(), policy, execution_mode=ONLINE_REQUIRED)

    summary = scheduler.run_plan(_plan(source), registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source})

    assert summary["execution_status"] == "COMPLETE_WITH_SOURCE_FAILURES"
    assert summary["acquisition"]["fallback_used"] is False
    assert summary["counts"]["prior_capture_fallbacks"] == 0
    assert summary["outcomes"][0]["status"] == "FAILURE"


def test_online_preferred_forbid_policy_never_uses_prior_capture(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    _seed_capture(root, result_id="CRES-PRIOR")
    source = _source()
    policy = _policy(_rule("SRC-A", modes=(ONLINE_PREFERRED,), fallback=FALLBACK_FORBID))
    scheduler = _fallback_scheduler(tmp_path, FailingTransport(), policy)

    summary = scheduler.run_plan(_plan(source), registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source})

    assert summary["acquisition"]["fallback_used"] is False
    assert summary["outcomes"][0]["status"] == "FAILURE"


def test_nonretryable_live_failure_does_not_fallback(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    _seed_capture(root, result_id="CRES-PRIOR")
    source = _source()
    policy = _policy(_rule("SRC-A", modes=(ONLINE_PREFERRED,), fallback=FALLBACK_PRIOR_CAPTURE))
    transport = SuccessTransport(body=b"not-json")
    source["source_class"] = "PUBLIC_JSON_API"
    scheduler = _fallback_scheduler(tmp_path, transport, policy)

    summary = scheduler.run_plan(_plan(source), registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source})

    assert summary["acquisition"]["fallback_used"] is False
    assert summary["outcomes"][0]["status"] == "FAILURE"


def test_coalesced_fallback_requires_every_logical_source_permission(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    _seed_capture(root, result_id="CRES-PRIOR")
    source_a = _source("SRC-A")
    source_b = _source("SRC-B")
    policy = _policy(
        _rule("SRC-A", modes=(ONLINE_PREFERRED,), fallback=FALLBACK_PRIOR_CAPTURE),
        _rule("SRC-B", modes=(ONLINE_PREFERRED,), fallback=FALLBACK_FORBID),
    )
    transport = FailingTransport()
    scheduler = _fallback_scheduler(tmp_path, transport, policy)

    summary = scheduler.run_plan(
        _plan(source_a, source_b),
        registry_sha256=REGISTRY_HASH,
        source_index={"SRC-A": source_a, "SRC-B": source_b},
    )

    assert len(transport.calls) == 1
    assert summary["counts"]["prior_capture_fallbacks"] == 0
    assert [item["status"] for item in summary["outcomes"]] == ["FAILURE", "FAILURE"]


def test_policy_block_does_not_use_prior_capture_or_transport(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    blocked_url = "https://b.example.org/data"
    _seed_capture(root, result_id="CRES-PRIOR", url=blocked_url)
    source = _source(url=blocked_url)
    policy = _policy(
        _rule(
            "SRC-A",
            modes=(ONLINE_PREFERRED,),
            fallback=FALLBACK_PRIOR_CAPTURE,
            origin="https://a.example.org",
        )
    )
    transport = FailingTransport()
    scheduler = _fallback_scheduler(tmp_path, transport, policy)

    summary = scheduler.run_plan(_plan(source), registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source})

    assert transport.calls == []
    assert summary["acquisition"]["fallback_used"] is False
    assert summary["outcomes"][0]["failure_class"] == "POLICY_BLOCK"


def test_successful_live_result_wins_over_available_prior_capture(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    _seed_capture(root, result_id="CRES-PRIOR")
    source = _source()
    policy = _policy(_rule("SRC-A", modes=(ONLINE_PREFERRED,), fallback=FALLBACK_PRIOR_CAPTURE))
    transport = SuccessTransport()
    scheduler = _fallback_scheduler(tmp_path, transport, policy)

    summary = scheduler.run_plan(_plan(source), registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source})

    assert summary["acquisition"]["fallback_used"] is False
    assert summary["counts"]["prior_capture_fallbacks"] == 0
    assert summary["outcomes"][0]["record_id"] != "CRES-PRIOR"


def test_replay_only_uses_exact_capture_and_creates_no_new_result(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    _seed_capture(root, result_id="CRES-REPLAY")
    before = sorted((root / "results").glob("*.json"))
    source = _source()
    policy = _policy(_rule("SRC-A", modes=(REPLAY_ONLY,)))
    scheduler = _replay_scheduler(tmp_path, policy)

    summary = scheduler.run_plan(_plan(source), registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source})

    after = sorted((root / "results").glob("*.json"))
    assert before == after
    assert summary["acquisition"]["route"] == REPLAY_ROUTE
    assert summary["counts"]["collection_attempts"] == 0
    assert summary["counts"]["replays"] == 1
    assert summary["outcomes"][0]["record_id"] == "CRES-REPLAY"
    assert summary["outcomes"][0]["prior_capture"]["capture_age_seconds"] == 172799


def test_replay_missing_capture_is_accounted_as_source_failure(tmp_path: Path) -> None:
    source = _source()
    policy = _policy(_rule("SRC-A", modes=(REPLAY_ONLY,)))
    scheduler = _replay_scheduler(tmp_path, policy)

    summary = scheduler.run_plan(_plan(source), registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source})

    assert summary["execution_status"] == "COMPLETE_WITH_SOURCE_FAILURES"
    assert summary["counts"]["collection_attempts"] == 0
    assert summary["outcomes"][0]["failure_class"] == "REPLAY_CAPTURE_MISSING"


def test_replay_policy_block_is_accounted_without_target_execution(tmp_path: Path) -> None:
    source = _source()
    policy = _policy(_rule("SRC-A", modes=(ONLINE_PREFERRED,), fallback=FALLBACK_FORBID))
    scheduler = _replay_scheduler(tmp_path, policy)

    summary = scheduler.run_plan(_plan(source), registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source})

    assert summary["execution_status"] == "COMPLETE_WITH_SOURCE_FAILURES"
    assert summary["counts"]["retrieval_target_groups"] == 0
    assert summary["outcomes"][0]["failure_class"] == "POLICY_BLOCK"


def test_replay_run_identity_changes_when_selected_capture_changes(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    _seed_capture(root, result_id="CRES-OLD", retrieved_at="2026-09-01T00:00:00Z")
    source = _source()
    policy = _policy(_rule("SRC-A", modes=(REPLAY_ONLY,)))
    scheduler = _replay_scheduler(tmp_path, policy)
    plan = _plan(source)

    first = scheduler.run_plan(plan, registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source})
    _seed_capture(root, result_id="CRES-NEW", retrieved_at="2026-09-03T00:00:00Z", body=b"new")
    second = scheduler.run_plan(plan, registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source})

    assert first["run_id"] != second["run_id"]
    assert first["outcomes"][0]["record_id"] == "CRES-OLD"
    assert second["outcomes"][0]["record_id"] == "CRES-NEW"


def test_replay_completed_run_is_idempotent(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    _seed_capture(root, result_id="CRES-REPLAY")
    source = _source()
    policy = _policy(_rule("SRC-A", modes=(REPLAY_ONLY,)))
    scheduler = _replay_scheduler(tmp_path, policy)
    plan = _plan(source)

    first = scheduler.run_plan(plan, registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source})
    second = scheduler.run_plan(plan, registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source})

    assert second == first


def test_replay_respects_source_kill_switch(tmp_path: Path) -> None:
    source = _source()
    policy = _policy(_rule("SRC-A", modes=(REPLAY_ONLY,)))
    scheduler = ReplayOnlyCollectionScheduler(
        acquisition_policy=policy,
        programme_id=PROGRAMME_ID,
        collector_config=_config(),
        quarantine_root=tmp_path / "quarantine",
        scheduler_config=SchedulerConfig(
            disabled_source_ids=frozenset({"SRC-A"}),
            max_workers=1,
            max_workers_per_host=1,
        ),
    )

    summary = scheduler.run_plan(_plan(source), registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source})

    assert summary["counts"]["skipped"] == 1
    assert summary["outcomes"][0]["reason"] == "source_kill_switch"


def test_replay_rejects_disabled_execution(tmp_path: Path) -> None:
    source = _source()
    policy = _policy(_rule("SRC-A", modes=(REPLAY_ONLY,)))
    scheduler = ReplayOnlyCollectionScheduler(
        acquisition_policy=policy,
        programme_id=PROGRAMME_ID,
        collector_config=_config(),
        quarantine_root=tmp_path / "quarantine",
        scheduler_config=SchedulerConfig(
            collection_enabled=False,
            max_workers=1,
            max_workers_per_host=1,
        ),
    )

    with pytest.raises(ValueError, match="Replay execution is disabled"):
        scheduler.run_plan(_plan(source), registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source})


def test_fallback_pending_checkpoint_resumes_bound_capture_without_new_live_call(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    _seed_capture(root, result_id="CRES-PRIOR")
    source = _source()
    policy = _policy(_rule("SRC-A", modes=(ONLINE_PREFERRED,), fallback=FALLBACK_PRIOR_CAPTURE))
    transport = FailingTransport()
    scheduler = _fallback_scheduler(tmp_path, transport, policy)

    normalized = normalize_retrieval_url(URL)
    capture = build_prior_capture_snapshot(root).select(normalized, as_of="2026-09-04")
    assert capture is not None
    target_id = retrieval_target_id(normalized)
    group = RetrievalTargetGroup(
        retrieval_target_id=target_id,
        normalized_url=normalized,
        requested_url=URL,
        source_ids=("SRC-A",),
        primary_source_id="SRC-A",
        primary_monitor_id="MON-SRC-A",
        primary_item={"source_id": "SRC-A", "monitor_id": "MON-SRC-A", "url": URL},
    )
    target = {
        "retrieval_target_id": target_id,
        "normalized_url": normalized,
        "requested_url": URL,
        "source_ids": ["SRC-A"],
        "primary_source_id": "SRC-A",
        "primary_monitor_id": "MON-SRC-A",
        "adapter_id": "html",
        "prior_capture": capture.binding(),
        "fallback_snapshot_sha256": "0" * 64,
    }
    scheduler._fallback_as_of = "2026-09-04"  # noqa: SLF001
    checkpoint = {
        "schema_version": "1",
        "run_id": "CRUN-TEST",
        "retrieval_target_id": target_id,
        "target": target,
        "state": "INTERNAL_ERROR",
        "attempts": [],
        "outcome": {
            "kind": "FAILURE",
            "record_id": "CFAL-LIVE",
            "request_id": "CREQ-LIVE",
            "failure_class": "NETWORK_ERROR",
            "retryable": True,
        },
        "fallback_pending": target["prior_capture"],
        "updated_at": "2026-09-04T00:00:00Z",
        "boundary": RUN_LEDGER_BOUNDARY,
    }
    resolved = scheduler._execute_target(  # noqa: SLF001
        run_id="CRUN-TEST",
        group=group,
        checkpoint=checkpoint,
        adapter=None,
        source_record=source,
        registry_sha256=REGISTRY_HASH,
        persisted_records={},
    )

    assert transport.calls == []
    assert resolved["state"] == "RESULT"
    assert resolved["fallback"]["result_id"] == "CRES-PRIOR"
    assert resolved["live_terminal_outcome"]["failure_class"] == "NETWORK_ERROR"
    assert "fallback_pending" not in resolved
    assert resolved.get("internal_error") is None
    assert FALLBACK_PENDING == "FALLBACK_PENDING"
