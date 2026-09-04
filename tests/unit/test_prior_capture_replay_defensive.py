from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any

import pytest

from neuroai_workbench.collector.acquisition_policy import (
    FALLBACK_PRIOR_CAPTURE,
    ONLINE_PREFERRED,
    REPLAY_ONLY,
    AcquisitionPolicyError,
    build_acquisition_policy,
)
from neuroai_workbench.collector.config import CollectorConfig
from neuroai_workbench.collector.dns import DnsGuard
from neuroai_workbench.collector.prior_capture_replay import (
    PolicyBoundFallbackCollectionScheduler,
    PriorCaptureError,
    ReplayOnlyCollectionScheduler,
    _capture_age_seconds,
    _parse_timestamp,
    _reference_from_result,
    build_prior_capture_snapshot,
    verify_prior_capture_reference,
)
from neuroai_workbench.collector.scheduler import SchedulerConfig
from neuroai_workbench.collector.url_normalize import RetrievalTargetGroup, normalize_retrieval_url, retrieval_target_id
from neuroai_workbench.util import sha256_bytes

PROGRAMME_ID = "OBS-PROGRAMME"
REGISTRY_HASH = "a" * 64
CONFIG_HASH = "b" * 64
URL = "https://a.example.org/data"
GLOBAL_IP = "93.184.216.34"


class NoCallTransport:
    def send(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, str], bytes]:
        del args, kwargs
        raise AssertionError("transport must not be called")


def _resolver(host: str, port: Any, *args: Any, **kwargs: Any) -> list[tuple[Any, ...]]:
    del host, port, args, kwargs
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (GLOBAL_IP, 0))]


def _config() -> CollectorConfig:
    return CollectorConfig(
        collector_version="0.3.0.dev0-collector",
        configuration_hash=CONFIG_HASH,
        max_attempts=1,
        requests_per_host_per_minute=100,
    )


def _rule(source_id: str, *, replay: bool = False) -> dict[str, Any]:
    if replay:
        return {
            "source_id": source_id,
            "execution_modes": [REPLAY_ONLY],
            "allowed_origins": [],
            "fallback_policy": "FORBID",
        }
    return {
        "source_id": source_id,
        "execution_modes": [ONLINE_PREFERRED],
        "allowed_origins": ["https://a.example.org"],
        "fallback_policy": FALLBACK_PRIOR_CAPTURE,
    }


def _policy(*rules: dict[str, Any]) -> dict[str, Any]:
    return build_acquisition_policy(
        policy_id="POLICY-2B-DEFENSIVE",
        programme_id=PROGRAMME_ID,
        approved_by="automated-technical-disposition",
        source_rules=rules,
        approved_at="2026-01-01T00:00:00Z",
        expires_at="2027-01-01T00:00:00Z",
    )


def _source(source_id: str = "SRC-A", url: str = URL) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "monitor_id": f"MON-{source_id}",
        "source_class": "OFFICIAL_COMPANY_PAGE",
        "url": url,
    }


def _plan(source_id: str = "SRC-A", url: str = URL) -> dict[str, Any]:
    return {
        "plan_id": "PLAN-2B-DEFENSIVE",
        "as_of": "2026-09-04",
        "due": [{"source_id": source_id, "monitor_id": f"MON-{source_id}", "url": url}],
        "manual": [],
        "not_due": [],
    }


def _seed_capture(
    root: Path,
    *,
    result_id: str = "CRES-DEFENSIVE",
    retrieved_at: str = "2026-09-03T00:00:00Z",
    body: bytes = b"prior",
) -> dict[str, Any]:
    digest = sha256_bytes(body)
    quarantine_path = f"incoming/SRC-A/{digest[:12]}/capture.bin"
    byte_path = root / quarantine_path
    byte_path.parent.mkdir(parents=True, exist_ok=True)
    byte_path.write_bytes(body)
    record = {
        "result_id": result_id,
        "source_id": "SRC-A",
        "monitor_id": "MON-SRC-A",
        "requested_url": URL,
        "retrieved_at": retrieved_at,
        "sha256": digest,
        "quarantine_path": quarantine_path,
        "size_bytes": len(body),
        "media_type": "application/octet-stream",
        "original_filename": "capture.bin",
    }
    results = root / "results"
    results.mkdir(parents=True, exist_ok=True)
    (results / f"{result_id}.json").write_text(json.dumps(record), encoding="utf-8")
    return record


def _replay_scheduler(tmp_path: Path, policy: dict[str, Any], *, programme_id: str = PROGRAMME_ID) -> ReplayOnlyCollectionScheduler:
    return ReplayOnlyCollectionScheduler(
        acquisition_policy=policy,
        programme_id=programme_id,
        collector_config=_config(),
        quarantine_root=tmp_path / "quarantine",
        scheduler_config=SchedulerConfig(max_workers=1, max_workers_per_host=1),
    )


def _fallback_scheduler(tmp_path: Path, policy: dict[str, Any]) -> PolicyBoundFallbackCollectionScheduler:
    return PolicyBoundFallbackCollectionScheduler(
        acquisition_policy=policy,
        programme_id=PROGRAMME_ID,
        execution_mode=ONLINE_PREFERRED,
        collector_config=_config(),
        transport=NoCallTransport(),
        quarantine_root=tmp_path / "quarantine",
        scheduler_config=SchedulerConfig(max_workers=1, max_workers_per_host=1),
        dns_guard=DnsGuard(getaddrinfo=_resolver),
        sleeper=lambda _: None,
    )


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("", "non-empty timestamp"),
        ("2026-99-99", "ISO-8601"),
        ("not-a-timestamp", "ISO-8601"),
        ("2026-09-04T12:00:00", "explicit timezone"),
    ],
)
def test_parse_timestamp_rejects_invalid_forms(value: str, message: str) -> None:
    with pytest.raises(PriorCaptureError, match=message):
        _parse_timestamp(value, field="test_time")


def test_capture_age_rejects_future_capture() -> None:
    with pytest.raises(PriorCaptureError, match="later than the replay cutoff"):
        _capture_age_seconds(as_of="2026-09-04T00:00:00Z", retrieved_at="2026-09-05T00:00:00Z")


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"monitor_id": None}, "missing prior-capture fields"),
        ({"requested_url": "file:///tmp/evidence"}, "not HTTP"),
        ({"sha256": "XYZ"}, "SHA-256 is malformed"),
        ({"size_bytes": True}, "size_bytes is invalid"),
        ({"size_bytes": -1}, "size_bytes is invalid"),
        ({"result_id": ""}, "result_id is empty"),
    ],
)
def test_reference_from_result_rejects_malformed_metadata(
    tmp_path: Path,
    mutation: dict[str, Any],
    message: str,
) -> None:
    root = tmp_path / "quarantine"
    record = _seed_capture(root)
    if "monitor_id" in mutation:
        record.pop("monitor_id")
    else:
        record.update(mutation)
    with pytest.raises(PriorCaptureError, match=message):
        _reference_from_result(root, record)


def test_snapshot_ignores_malformed_json_and_non_object_records(tmp_path: Path) -> None:
    results = tmp_path / "quarantine" / "results"
    results.mkdir(parents=True)
    (results / "broken.json").write_text("{", encoding="utf-8")
    (results / "array.json").write_text("[]", encoding="utf-8")
    (results / "incomplete.json").write_text(json.dumps({"result_id": "CRES-INCOMPLETE"}), encoding="utf-8")

    snapshot = build_prior_capture_snapshot(tmp_path / "quarantine")

    assert snapshot.captures == ()


def test_verify_reference_rejects_missing_result_record(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    _seed_capture(root)
    reference = build_prior_capture_snapshot(root).select(normalize_retrieval_url(URL), as_of="2026-09-04")
    assert reference is not None
    (root / "results" / f"{reference.result_id}.json").unlink()

    with pytest.raises(PriorCaptureError, match="result record is missing"):
        verify_prior_capture_reference(root, reference)


def test_verify_reference_rejects_non_object_result_record(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    _seed_capture(root)
    reference = build_prior_capture_snapshot(root).select(normalize_retrieval_url(URL), as_of="2026-09-04")
    assert reference is not None
    (root / "results" / f"{reference.result_id}.json").write_text("[]", encoding="utf-8")

    with pytest.raises(PriorCaptureError, match="not an object"):
        verify_prior_capture_reference(root, reference)


def test_verify_reference_rejects_metadata_substitution(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    record = _seed_capture(root)
    reference = build_prior_capture_snapshot(root).select(normalize_retrieval_url(URL), as_of="2026-09-04")
    assert reference is not None
    record["source_id"] = "SRC-SUBSTITUTED"
    (root / "results" / f"{reference.result_id}.json").write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(PriorCaptureError, match="identity changed"):
        verify_prior_capture_reference(root, reference)


def test_replay_scheduler_rejects_programme_substitution(tmp_path: Path) -> None:
    policy = _policy(_rule("SRC-A", replay=True))
    with pytest.raises(AcquisitionPolicyError, match="programme_id"):
        _replay_scheduler(tmp_path, policy, programme_id="OTHER-PROGRAMME")


def test_replay_accounts_unknown_source_without_target(tmp_path: Path) -> None:
    policy = _policy(_rule("SRC-A", replay=True))
    scheduler = _replay_scheduler(tmp_path, policy)

    summary = scheduler.run_plan(
        _plan(source_id="SRC-UNKNOWN"),
        registry_sha256=REGISTRY_HASH,
        source_index={},
    )

    assert summary["counts"]["retrieval_target_groups"] == 0
    assert summary["outcomes"][0]["reason"] == "unknown_source"


def test_replay_rejects_non_public_url_without_network(tmp_path: Path) -> None:
    policy = _policy(_rule("SRC-A", replay=True))
    scheduler = _replay_scheduler(tmp_path, policy)
    source = _source(url="http://127.0.0.1/private")

    summary = scheduler.run_plan(
        _plan(url=source["url"]),
        registry_sha256=REGISTRY_HASH,
        source_index={"SRC-A": source},
    )

    assert summary["counts"]["collection_attempts"] == 0
    assert summary["outcomes"][0]["failure_class"] == "POLICY_BLOCK"


def test_replay_resumes_terminal_checkpoint_when_summary_is_missing(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    _seed_capture(root)
    policy = _policy(_rule("SRC-A", replay=True))
    scheduler = _replay_scheduler(tmp_path, policy)
    source = _source()

    first = scheduler.run_plan(_plan(), registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source})
    summary_path = root / "run-ledgers" / first["run_id"] / "summary.json"
    summary_path.unlink()
    second = scheduler.run_plan(_plan(), registry_sha256=REGISTRY_HASH, source_index={"SRC-A": source})

    assert second["run_id"] == first["run_id"]
    assert second["counts"]["resumed_targets"] == 1
    assert second["outcomes"][0]["record_id"] == "CRES-DEFENSIVE"


def test_apply_bound_fallback_without_capture_fails_closed(tmp_path: Path) -> None:
    policy = _policy(_rule("SRC-A"))
    scheduler = _fallback_scheduler(tmp_path, policy)
    normalized = normalize_retrieval_url(URL)
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
    checkpoint = {
        "schema_version": "1",
        "run_id": "CRUN-DEFENSIVE",
        "retrieval_target_id": target_id,
        "target": {
            "retrieval_target_id": target_id,
            "normalized_url": normalized,
            "source_ids": ["SRC-A"],
            "prior_capture": None,
        },
        "state": "INTERNAL_ERROR",
        "attempts": [],
        "outcome": None,
        "fallback_pending": {},
        "internal_error": {"type": "FALLBACK_PENDING", "message": "test"},
        "updated_at": "2026-09-04T00:00:00Z",
        "boundary": "Collector run ledgers record operational execution and recovery state over exact monitoring-plan, registry, configuration, and retrieval-target bindings. They do not modify canonical evidence, establish source truth, convert retrieval failure into assessment failure, or authorize governance or release decisions.",
    }

    resolved = scheduler._apply_bound_fallback(checkpoint, group)  # noqa: SLF001

    assert resolved["state"] == "FAILURE"
    assert "fallback_pending" not in resolved
    assert "internal_error" not in resolved


def test_apply_bound_fallback_revalidates_bound_bytes(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    record = _seed_capture(root)
    policy = _policy(_rule("SRC-A"))
    scheduler = _fallback_scheduler(tmp_path, policy)
    scheduler._fallback_as_of = "2026-09-04"  # noqa: SLF001
    reference = build_prior_capture_snapshot(root).select(normalize_retrieval_url(URL), as_of="2026-09-04")
    assert reference is not None
    (root / record["quarantine_path"]).write_bytes(b"tampered")
    normalized = normalize_retrieval_url(URL)
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
    checkpoint = {
        "schema_version": "1",
        "run_id": "CRUN-DEFENSIVE-TAMPER",
        "retrieval_target_id": target_id,
        "target": {
            "retrieval_target_id": target_id,
            "normalized_url": normalized,
            "source_ids": ["SRC-A"],
            "prior_capture": reference.binding(),
        },
        "state": "INTERNAL_ERROR",
        "attempts": [],
        "outcome": {"kind": "FAILURE", "retryable": True},
        "fallback_pending": reference.binding(),
        "internal_error": {"type": "FALLBACK_PENDING", "message": "test"},
        "updated_at": "2026-09-04T00:00:00Z",
        "boundary": "Collector run ledgers record operational execution and recovery state over exact monitoring-plan, registry, configuration, and retrieval-target bindings. They do not modify canonical evidence, establish source truth, convert retrieval failure into assessment failure, or authorize governance or release decisions.",
    }

    resolved = scheduler._apply_bound_fallback(checkpoint, group)  # noqa: SLF001

    assert resolved["state"] == "FAILURE"
    assert resolved["fallback_rejected"]["type"] == "PriorCaptureError"
    assert "fallback_pending" not in resolved
