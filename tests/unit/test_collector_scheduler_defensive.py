from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from neuroai_workbench.collector.config import CollectorConfig
from neuroai_workbench.collector.scheduler import (
    CollectionScheduler,
    SchedulerConfig,
    _failure_is_retryable,
    _HostPermitPool,
    _jsonable,
    _outcome_from_persisted,
    _record_id,
)
from neuroai_workbench.collector.service import CollectionOutcome

REGISTRY_SHA = "a" * 64
CONFIG_SHA = "b" * 64


class NoNetworkTransport:
    def send(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, str], bytes]:
        raise AssertionError("network transport must not be called")


def _scheduler(tmp_path: Path, *, scheduler_config: SchedulerConfig | None = None) -> CollectionScheduler:
    return CollectionScheduler(
        collector_config=CollectorConfig(
            collector_version="0.3.0.dev0-defensive-test",
            configuration_hash=CONFIG_SHA,
            requests_per_host_per_minute=1000,
            retry_initial_delay_seconds=0.0,
            retry_max_delay_seconds=0.0,
        ),
        transport=NoNetworkTransport(),
        quarantine_root=tmp_path / "quarantine",
        scheduler_config=scheduler_config or SchedulerConfig(),
        sleeper=lambda _seconds: None,
    )


def test_scheduler_private_normalizers_cover_nested_sets_tuples_and_scalars() -> None:
    assert _jsonable({"set": {"b", "a"}, "tuple": (2, 1), "scalar": 3}) == {
        "scalar": 3,
        "set": ["a", "b"],
        "tuple": [2, 1],
    }


def test_retry_classifier_handles_transient_permanent_malformed_and_other_failures() -> None:
    assert _failure_is_retryable({"failure_class": "TIMEOUT"}) is True
    assert _failure_is_retryable({"failure_class": "NETWORK_ERROR"}) is True
    assert _failure_is_retryable({"failure_class": "HTTP_ERROR", "failure_message": "Unexpected HTTP status 503"}) is True
    assert _failure_is_retryable({"failure_class": "HTTP_ERROR", "failure_message": "Unexpected HTTP status 404"}) is False
    assert _failure_is_retryable({"failure_class": "HTTP_ERROR", "failure_message": "missing status"}) is False
    assert _failure_is_retryable({"failure_class": "POLICY_BLOCK"}) is False


def test_persisted_outcome_rehydration_and_record_id_defensive_paths() -> None:
    result = {"result_id": "CRES-1", "request_id": "CREQ-1"}
    failure = {"failure_id": "CFAIL-1", "request_id": "CREQ-2"}
    assert _outcome_from_persisted(result) == CollectionOutcome(kind="result", record=result)
    assert _outcome_from_persisted(failure) == CollectionOutcome(kind="failure", record=failure)
    assert _record_id(result) == "CRES-1"
    assert _record_id(failure) == "CFAIL-1"
    assert _record_id({}) is None
    with pytest.raises(ValueError, match="neither a result nor a failure"):
        _outcome_from_persisted({"request_id": "CREQ-BAD"})


def test_host_permit_pool_has_explicit_unknown_host_bucket_and_reuses_semaphore() -> None:
    pool = _HostPermitPool(1)
    assert pool._host("relative-path") == "unknown"
    first = pool._permit("example.org")
    second = pool._permit("example.org")
    assert first is second
    with pool.acquire("relative-path") as host:
        assert host == "unknown"


def test_apply_attempt_outcome_rejects_missing_attempt_record(tmp_path: Path) -> None:
    scheduler = _scheduler(tmp_path)
    with pytest.raises(ValueError, match="without an attempt record"):
        scheduler._apply_attempt_outcome(
            {"attempts": []},
            CollectionOutcome(kind="result", record={"result_id": "CRES-1"}),
            recovered=False,
            sleep_before_retry=False,
        )


def test_collection_kill_switch_returns_without_network(tmp_path: Path) -> None:
    scheduler = _scheduler(tmp_path, scheduler_config=SchedulerConfig(collection_enabled=False))
    run = scheduler.run_plan(
        {"plan_id": "PLAN-KILLED", "as_of": "2026-08-14", "due": [], "manual": [], "not_due": []},
        registry_sha256=REGISTRY_SHA,
        source_index={},
    )
    assert run["status"] == "KILLED"
    assert run["execution_status"] == "KILLED"
    assert run["kill_reason"] == "collection_disabled"


def test_resume_disabled_creates_fresh_run_identity_for_exact_same_empty_plan(tmp_path: Path) -> None:
    scheduler = _scheduler(
        tmp_path,
        scheduler_config=SchedulerConfig(resume_enabled=False),
    )
    plan = {"plan_id": "PLAN-FRESH", "as_of": "2026-08-14", "due": [], "manual": [], "not_due": []}
    first = scheduler.run_plan(plan, registry_sha256=REGISTRY_SHA, source_index={})
    second = scheduler.run_plan(plan, registry_sha256=REGISTRY_SHA, source_index={})
    assert first["status"] == "COMPLETED"
    assert second["status"] == "COMPLETED"
    assert first["run_id"] != second["run_id"]


def test_handoff_kill_switch_fails_closed(tmp_path: Path) -> None:
    scheduler = _scheduler(tmp_path)
    with pytest.raises(ValueError, match="handoff kill switch"):
        scheduler.attempt_handoff("QREC-TEST")
