from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench.collector import SchedulerConfig
from neuroai_workbench.collector.rate_limit import RateLimiter
from neuroai_workbench.collector.run_ledger import (
    RUN_LEDGER_BOUNDARY,
    _hash_record,
    build_run_binding,
    deterministic_request_id,
    deterministic_run_id,
    ensure_run_manifest,
    load_run_summary,
    load_target_checkpoint,
    new_target_checkpoint,
    scan_persisted_attempt_records,
    verify_run_manifest,
    verify_target_checkpoint,
    write_run_summary,
    write_target_checkpoint,
)
from neuroai_workbench.util import atomic_write_json

REGISTRY_SHA = "a" * 64


def _binding() -> dict[str, object]:
    target = {
        "retrieval_target_id": "RTGT-0123456789abcdef0123456789abcdef",
        "normalized_url": "https://example.org/item",
        "requested_url": "https://example.org/item",
        "source_ids": ["SRC-1"],
        "primary_source_id": "SRC-1",
        "primary_monitor_id": "MON-1",
        "adapter_id": "json_api",
    }
    return build_run_binding(
        plan={"plan_id": "PLAN-1", "due": [], "manual": [], "not_due": []},
        registry_sha256=REGISTRY_SHA,
        collector_configuration={"collector_version": "v", "configuration_hash": "b" * 64},
        scheduler_configuration={"max_workers": 8},
        targets=[target],
        pre_outcomes=[],
    )


def _target() -> dict[str, object]:
    return {
        "retrieval_target_id": "RTGT-0123456789abcdef0123456789abcdef",
        "normalized_url": "https://example.org/item",
        "requested_url": "https://example.org/item",
        "source_ids": ["SRC-1"],
        "primary_source_id": "SRC-1",
        "primary_monitor_id": "MON-1",
        "adapter_id": "json_api",
    }


def test_rate_limiter_acquire_waits_without_busy_loop() -> None:
    limiter = RateLimiter(1)
    now = {"value": 0.0}
    sleeps: list[float] = []

    def clock() -> float:
        return now["value"]

    def sleeper(seconds: float) -> None:
        sleeps.append(seconds)
        now["value"] += seconds

    limiter.check("https://rate.example.org/item", now=0.0)
    waited = limiter.acquire("https://rate.example.org/item", sleeper=sleeper, clock=clock)

    assert waited == pytest.approx(60.0)
    assert sleeps == [pytest.approx(60.0)]
    with pytest.raises(ValueError, match="Rate limit exceeded"):
        limiter.check("https://rate.example.org/item", now=60.0)


def test_disabled_rate_limiter_never_blocks() -> None:
    limiter = RateLimiter(0)
    limiter.check("https://rate.example.org/item", now=0.0)
    assert limiter.acquire("https://rate.example.org/item", sleeper=lambda _: None, clock=lambda: 0.0) == 0.0


def test_scheduler_config_rejects_invalid_worker_bounds() -> None:
    with pytest.raises(ValueError, match="max_workers"):
        SchedulerConfig(max_workers=0)
    with pytest.raises(ValueError, match="max_workers_per_host"):
        SchedulerConfig(max_workers=2, max_workers_per_host=0)
    with pytest.raises(ValueError, match="cannot exceed"):
        SchedulerConfig(max_workers=2, max_workers_per_host=3)


def test_run_binding_rejects_invalid_registry_digest() -> None:
    with pytest.raises(ValueError, match="registry_sha256"):
        build_run_binding(
            plan={},
            registry_sha256="bad",
            collector_configuration={},
            scheduler_configuration={},
            targets=[],
            pre_outcomes=[],
        )


def test_deterministic_request_id_requires_positive_attempt() -> None:
    with pytest.raises(ValueError, match="attempt_count"):
        deterministic_request_id("CRUN-x", "RTGT-x", 0)


def test_manifest_is_idempotent_and_detects_hash_and_binding_tampering(tmp_path: Path) -> None:
    binding = _binding()
    first = ensure_run_manifest(tmp_path, binding=binding)
    second = ensure_run_manifest(tmp_path, binding=binding)
    assert first == second
    verify_run_manifest(first, expected_binding=binding)

    tampered = json.loads(json.dumps(first))
    tampered["binding_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="binding hash mismatch"):
        verify_run_manifest(tampered)

    wrong_binding = json.loads(json.dumps(binding))
    wrong_binding["plan_id"] = "PLAN-SUBSTITUTED"
    with pytest.raises(ValueError, match="requested execution binding"):
        verify_run_manifest(first, expected_binding=wrong_binding)


def test_manifest_validation_rejects_bad_schema_boundary_and_missing_binding(tmp_path: Path) -> None:
    manifest = ensure_run_manifest(tmp_path, binding=_binding())
    bad_schema = dict(manifest)
    bad_schema["schema_version"] = "999"
    with pytest.raises(ValueError, match="schema version"):
        verify_run_manifest(bad_schema)
    bad_boundary = dict(manifest)
    bad_boundary["boundary"] = "wrong"
    with pytest.raises(ValueError, match="boundary"):
        verify_run_manifest(bad_boundary)
    missing = dict(manifest)
    missing.pop("binding")
    with pytest.raises(ValueError, match="missing binding"):
        verify_run_manifest(missing)


def test_existing_manifest_and_checkpoint_files_must_be_objects(tmp_path: Path) -> None:
    binding = _binding()
    run_id, _ = deterministic_run_id(binding)
    manifest_path = tmp_path / "run-ledgers" / run_id / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(manifest_path, [])
    with pytest.raises(ValueError, match="must be a JSON object"):
        ensure_run_manifest(tmp_path, binding=binding)

    checkpoint_path = tmp_path / "run-ledgers" / run_id / "targets" / f"{_target()['retrieval_target_id']}.json"
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(checkpoint_path, [])
    with pytest.raises(ValueError, match="must be a JSON object"):
        load_target_checkpoint(tmp_path, run_id=run_id, target=_target())


def test_run_manifest_and_summary_detect_identity_and_hash_tampering(tmp_path: Path) -> None:
    manifest = ensure_run_manifest(tmp_path, binding=_binding())
    wrong_run = dict(manifest)
    wrong_run["run_id"] = "CRUN-wrong"
    with pytest.raises(ValueError, match="run_id does not match"):
        verify_run_manifest(wrong_run)

    bad_hash = dict(manifest)
    bad_hash["manifest_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_run_manifest(bad_hash)

    run_id = "CRUN-" + "7" * 32
    summary = write_run_summary(
        tmp_path,
        {"run_id": run_id, "status": "COMPLETED", "run_ledger_boundary": RUN_LEDGER_BOUNDARY},
    )
    wrong_summary_run = dict(summary)
    wrong_summary_run["run_id"] = "CRUN-other"
    atomic_write_json(tmp_path / "run-ledgers" / run_id / "summary.json", wrong_summary_run)
    with pytest.raises(ValueError, match="hash mismatch"):
        load_run_summary(tmp_path, run_id)

    atomic_write_json(
        tmp_path / "run-ledgers" / run_id / "summary.json",
        {"run_id": run_id, "status": "COMPLETED", "run_ledger_boundary": "wrong"},
    )
    with pytest.raises(ValueError, match="hash mismatch|ledger boundary mismatch"):
        load_run_summary(tmp_path, run_id)


def test_load_run_summary_rejects_nonobject_run_id_and_boundary_mismatches(tmp_path: Path) -> None:
    run_id = "CRUN-" + "8" * 32
    path = tmp_path / "run-ledgers" / run_id / "summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, [])
    with pytest.raises(ValueError, match="must be a JSON object"):
        load_run_summary(tmp_path, run_id)

    summary = {
        "run_id": "CRUN-other",
        "status": "COMPLETED",
        "run_ledger_boundary": RUN_LEDGER_BOUNDARY,
    }
    summary["summary_sha256"] = _hash_record(summary, "summary_sha256")
    atomic_write_json(path, summary)
    with pytest.raises(ValueError, match="run_id mismatch"):
        load_run_summary(tmp_path, run_id)

    summary = {
        "run_id": run_id,
        "status": "COMPLETED",
        "run_ledger_boundary": "wrong",
    }
    summary["summary_sha256"] = _hash_record(summary, "summary_sha256")
    atomic_write_json(path, summary)
    with pytest.raises(ValueError, match="ledger boundary mismatch"):
        load_run_summary(tmp_path, run_id)


def test_target_checkpoint_roundtrip_and_tampering_detection(tmp_path: Path) -> None:
    binding = _binding()
    run_id, _ = deterministic_run_id(binding)
    target = _target()
    pending = load_target_checkpoint(tmp_path, run_id=run_id, target=target)
    assert pending["state"] == "PENDING"
    pending["state"] = "ATTEMPTING"
    pending["attempts"] = [{"attempt_count": 1, "request_id": "CREQ-" + "1" * 32}]
    persisted = write_target_checkpoint(tmp_path, pending)
    loaded = load_target_checkpoint(tmp_path, run_id=run_id, target=target)
    assert loaded == persisted

    bad_hash = dict(loaded)
    bad_hash["checkpoint_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_target_checkpoint(bad_hash, run_id=run_id, expected_target=target)

    bad_state = dict(loaded)
    bad_state["state"] = "IMPOSSIBLE"
    # Re-hash through the writer, then validate semantic state.
    bad_state = write_target_checkpoint(tmp_path, bad_state)
    with pytest.raises(ValueError, match="invalid state"):
        verify_target_checkpoint(bad_state, run_id=run_id, expected_target=target)


def test_target_checkpoint_rejects_identity_target_boundary_and_attempt_shape(tmp_path: Path) -> None:
    run_id, _ = deterministic_run_id(_binding())
    target = _target()
    checkpoint = new_target_checkpoint(run_id=run_id, target=target)
    checkpoint = write_target_checkpoint(tmp_path, checkpoint)

    wrong_schema = dict(checkpoint)
    wrong_schema["schema_version"] = "999"
    with pytest.raises(ValueError, match="unsupported schema version"):
        verify_target_checkpoint(wrong_schema, run_id=run_id, expected_target=target)

    wrong_run = dict(checkpoint)
    wrong_run["run_id"] = "CRUN-wrong"
    with pytest.raises(ValueError, match="run binding"):
        verify_target_checkpoint(wrong_run, run_id=run_id, expected_target=target)

    wrong_target = dict(checkpoint)
    wrong_target["retrieval_target_id"] = "RTGT-wrong"
    with pytest.raises(ValueError, match="identity mismatch"):
        verify_target_checkpoint(wrong_target, run_id=run_id, expected_target=target)

    wrong_boundary = dict(checkpoint)
    wrong_boundary["boundary"] = "wrong"
    with pytest.raises(ValueError, match="boundary"):
        verify_target_checkpoint(wrong_boundary, run_id=run_id, expected_target=target)

    wrong_binding = dict(target)
    wrong_binding["requested_url"] = "https://example.org/substituted"
    with pytest.raises(ValueError, match="target binding"):
        verify_target_checkpoint(checkpoint, run_id=run_id, expected_target=wrong_binding)

    bad_attempts = dict(checkpoint)
    bad_attempts["attempts"] = "bad"
    # Force the hash branch to pass by persisting a semantically invalid record.
    bad_attempts = write_target_checkpoint(tmp_path, bad_attempts)
    with pytest.raises(ValueError, match="attempts must be a list"):
        verify_target_checkpoint(bad_attempts, run_id=run_id, expected_target=target)


def test_scan_persisted_attempt_records_detects_duplicate_request_ids(tmp_path: Path) -> None:
    request_id = "CREQ-" + "2" * 32
    atomic_write_json(tmp_path / "results" / "one.json", {"request_id": request_id, "result_id": "R1"})
    atomic_write_json(tmp_path / "failures" / "two.json", {"request_id": request_id, "failure_id": "F1"})
    with pytest.raises(ValueError, match="Multiple durable collector records"):
        scan_persisted_attempt_records(tmp_path)


def test_scan_persisted_attempt_records_ignores_nonobjects_and_missing_ids(tmp_path: Path) -> None:
    atomic_write_json(tmp_path / "results" / "list.json", [])
    atomic_write_json(tmp_path / "results" / "missing.json", {"result_id": "R"})
    assert scan_persisted_attempt_records(tmp_path) == {}


def test_scan_persisted_attempt_records_ignores_corrupt_historical_json(tmp_path: Path) -> None:
    (tmp_path / "results").mkdir(parents=True)
    (tmp_path / "results" / "corrupt.json").write_text("{not-json", encoding="utf-8")
    atomic_write_json(tmp_path / "failures" / "ok.json", {"request_id": "CREQ-" + "9" * 32, "failure_id": "F-1"})

    assert scan_persisted_attempt_records(tmp_path) == {
        "CREQ-" + "9" * 32: {"request_id": "CREQ-" + "9" * 32, "failure_id": "F-1"}
    }


def test_run_summary_roundtrip_and_corruption_detection(tmp_path: Path) -> None:
    run_id = "CRUN-" + "3" * 32
    summary = write_run_summary(
        tmp_path,
        {
            "run_id": run_id,
            "status": "COMPLETED",
            "run_ledger_boundary": RUN_LEDGER_BOUNDARY,
        },
    )
    assert load_run_summary(tmp_path, run_id) == summary
    assert load_run_summary(tmp_path, "CRUN-" + "4" * 32) is None

    path = tmp_path / "run-ledgers" / run_id / "summary.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["status"] = "TAMPERED"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_run_summary(tmp_path, run_id)
