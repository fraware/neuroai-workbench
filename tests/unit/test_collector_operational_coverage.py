from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench.collector.rate_limit import RateLimiter
from neuroai_workbench.collector.run_ledger import (
    RUN_LEDGER_BOUNDARY,
    deterministic_run_id,
    ensure_run_manifest,
    load_run_summary,
    load_target_checkpoint,
    write_run_summary,
    write_target_checkpoint,
)
from neuroai_workbench.util import atomic_write_json


def _binding() -> dict[str, object]:
    return {
        "plan_id": "PLAN-COVERAGE",
        "plan_sha256": "a" * 64,
        "registry_sha256": "b" * 64,
        "collector_configuration": {},
        "collector_configuration_sha256": "c" * 64,
        "scheduler_configuration": {},
        "scheduler_configuration_sha256": "d" * 64,
        "retrieval_targets": [],
        "pre_outcomes": [],
    }


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


def test_rate_limiter_uses_unknown_bucket_for_url_without_hostname() -> None:
    limiter = RateLimiter(1)
    limiter.check("relative-path", now=1.0)
    with pytest.raises(ValueError, match="unknown"):
        limiter.check("another-relative-path", now=1.0)


def test_existing_manifest_must_be_json_object(tmp_path: Path) -> None:
    binding = _binding()
    run_id, _ = deterministic_run_id(binding)
    path = tmp_path / "run-ledgers" / run_id / "manifest.json"
    atomic_write_json(path, ["not", "an", "object"])
    with pytest.raises(ValueError, match="manifest must be a JSON object"):
        ensure_run_manifest(tmp_path, binding=binding)


def test_existing_target_checkpoint_must_be_json_object(tmp_path: Path) -> None:
    binding = _binding()
    run_id, _ = deterministic_run_id(binding)
    target = _target()
    path = tmp_path / "run-ledgers" / run_id / "targets" / f"{target['retrieval_target_id']}.json"
    atomic_write_json(path, ["not", "an", "object"])
    with pytest.raises(ValueError, match="checkpoint .* JSON object"):
        load_target_checkpoint(tmp_path, run_id=run_id, target=target)


def test_target_checkpoint_rejects_unsupported_schema_version(tmp_path: Path) -> None:
    binding = _binding()
    run_id, _ = deterministic_run_id(binding)
    target = _target()
    checkpoint = {
        "schema_version": "999",
        "run_id": run_id,
        "retrieval_target_id": target["retrieval_target_id"],
        "target": target,
        "state": "PENDING",
        "attempts": [],
        "outcome": None,
        "boundary": RUN_LEDGER_BOUNDARY,
    }
    write_target_checkpoint(tmp_path, checkpoint)
    with pytest.raises(ValueError, match="unsupported schema version"):
        load_target_checkpoint(tmp_path, run_id=run_id, target=target)


def test_run_summary_requires_object_exact_run_and_ledger_boundary(tmp_path: Path) -> None:
    run_id = "CRUN-" + "1" * 32
    path = tmp_path / "run-ledgers" / run_id / "summary.json"
    atomic_write_json(path, ["bad"])
    with pytest.raises(ValueError, match="summary must be a JSON object"):
        load_run_summary(tmp_path, run_id)

    summary = write_run_summary(
        tmp_path,
        {
            "run_id": run_id,
            "run_ledger_boundary": RUN_LEDGER_BOUNDARY,
            "status": "COMPLETED",
        },
    )
    wrong_run = dict(summary)
    wrong_run["run_id"] = "CRUN-" + "2" * 32
    wrong_run.pop("summary_sha256")
    wrong_run = write_run_summary(tmp_path, wrong_run)
    wrong_path = tmp_path / "run-ledgers" / wrong_run["run_id"] / "summary.json"
    # Copy a hash-valid different-run summary under the expected run path.
    path.write_text(wrong_path.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(ValueError, match="run_id mismatch"):
        load_run_summary(tmp_path, run_id)

    boundary_summary = write_run_summary(
        tmp_path,
        {
            "run_id": run_id,
            "run_ledger_boundary": "WRONG",
            "status": "COMPLETED",
        },
    )
    assert boundary_summary["run_id"] == run_id
    with pytest.raises(ValueError, match="ledger boundary mismatch"):
        load_run_summary(tmp_path, run_id)


def test_resume_scan_ignores_malformed_json_but_keeps_valid_request_record(tmp_path: Path) -> None:
    from neuroai_workbench.collector.run_ledger import scan_persisted_attempt_records

    (tmp_path / "results").mkdir(parents=True)
    (tmp_path / "results" / "bad.json").write_text("{bad-json", encoding="utf-8")
    atomic_write_json(
        tmp_path / "results" / "good.json",
        {"request_id": "CREQ-" + "3" * 32, "result_id": "CRES-1"},
    )
    records = scan_persisted_attempt_records(tmp_path)
    assert set(records) == {"CREQ-" + "3" * 32}


def test_summary_corrupt_utf8_or_json_remains_visible_to_loader(tmp_path: Path) -> None:
    run_id = "CRUN-" + "4" * 32
    path = tmp_path / "run-ledgers" / run_id / "summary.json"
    path.parent.mkdir(parents=True)
    path.write_text("{bad-json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_run_summary(tmp_path, run_id)
