from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench.observatory import (
    import_release,
    load_imported_release,
    load_release,
    queue_release,
    summarize_release,
    validate_release,
    verify_baseline_bytes,
)
from neuroai_workbench.util import atomic_write_json, sha256_file

EXAMPLE = Path(__file__).parents[2] / "examples" / "observatory" / "evidence_depth_release_v1.4.json"
SUCCESSOR = Path(__file__).parents[2] / "examples" / "observatory" / "canonical_successor_snapshot_v1.7.json"



def test_example_validates():
    release = load_release(EXAMPLE)
    report = validate_release(release)
    assert report["valid"] is True
    assert report["counts"]["organizations"] >= 200


def test_summary_preserves_boundary():
    value = summarize_release(load_release(EXAMPLE))
    assert value["valid"] is True
    assert value["coverage"]["verification_rate"] > 0.9
    assert any("source universes" in x for x in value["boundaries"])


def test_queue_retains_partial_records():
    value = queue_release(load_release(EXAMPLE))
    assert value["counts"]["organizations"] == 3


def test_duplicate_identifier_fails():
    value = load_release(EXAMPLE)
    value["organizations"].append(dict(value["organizations"][0]))
    assert validate_release(value)["valid"] is False


def test_unresolved_source_fails():
    value = load_release(EXAMPLE)
    value["capital_and_ownership_events"][0]["source_ids"] = ["MISSING"]
    assert validate_release(value)["valid"] is False


def test_import_round_trip(tmp_path: Path):
    result = import_release(tmp_path, EXAMPLE)
    assert Path(result["target"]).is_dir()
    loaded = load_imported_release(tmp_path, "v1.4")
    assert loaded["metadata"]["version"] == "v1.4"


def test_compact_successor_validates_and_summarizes():
    release = load_release(SUCCESSOR)
    report = validate_release(release)
    assert report["valid"] is True
    assert report["release_kind"] == "COMPACT_SUCCESSOR_SNAPSHOT"
    assert report["counts"]["organizations"] == 153
    summary = summarize_release(release)
    assert summary["metadata"]["version"] == "v1.7"
    assert summary["baseline_reference"]["immutable"] is True
    assert summary["reopening_decision_states"]["PRIMA observatory system record"] == (
        "REOPENING_EXECUTED_RECORD_UPDATED_OPEN_CONDITIONS"
    )


def test_compact_successor_queue_retains_open_conditions():
    queue = queue_release(load_release(SUCCESSOR))
    assert queue["counts"]["reopening_decisions"] == 2
    assert any(item["object"] == "PRIMA observatory system record" for item in queue["reopening_queue"])


def test_compact_successor_rejects_bad_baseline_hash():
    release = load_release(SUCCESSOR)
    release["baseline_reference"]["canonical_sha256"] = "bad"
    report = validate_release(release)
    assert report["valid"] is False
    assert any(item["code"] == "BASELINE_SHA256_REQUIRED" for item in report["errors"])


def test_import_refuses_silent_overwrite(tmp_path: Path):
    import_release(tmp_path, SUCCESSOR)
    mutated = load_release(SUCCESSOR)
    mutated["metadata"]["title"] = "Mutated historical snapshot"
    mutated_path = tmp_path / "mutated_v1.7.json"
    atomic_write_json(mutated_path, mutated)
    with pytest.raises(ValueError, match="Refusing to overwrite"):
        import_release(tmp_path, mutated_path)
    stored = load_imported_release(tmp_path, "v1.7")
    assert stored["metadata"]["title"] == load_release(SUCCESSOR)["metadata"]["title"]


def test_import_idempotent_identical_bytes(tmp_path: Path):
    first = import_release(tmp_path, SUCCESSOR)
    second = import_release(tmp_path, SUCCESSOR)
    assert first["manifest"]["stored_sha256"] == second["manifest"]["stored_sha256"]


def test_invalid_temporal_order_rejected():
    release = load_release(SUCCESSOR)
    events = release["delta"]["regulatory_and_market_events"]
    events[0]["event_date"] = "2099-01-01"
    report = validate_release(release)
    assert report["valid"] is False
    assert any(item["code"] == "INVALID_TEMPORAL_ORDER" for item in report["errors"])


def test_unsupported_reopening_state_rejected():
    release = load_release(SUCCESSOR)
    release["reopening_decisions"][0]["decision"] = "SILENTLY_CLOSE_WITHOUT_REVIEW"
    report = validate_release(release)
    assert report["valid"] is False
    assert any(item["code"] == "UNSUPPORTED_REOPENING_STATE" for item in report["errors"])


def test_unsupported_reopening_transition_rejected():
    release = load_release(SUCCESSOR)
    release["assessment_successor_delta"]["reopening_transition"] = {
        "predecessor_decision_id": "ROP-16-001",
        "predecessor_state": "NO_REOPENING_TRIGGER_IDENTIFIED",
        "successor_decision_id": "ROP-17-001",
        "successor_state": "REOPENING_EXECUTED_RECORD_UPDATED_OPEN_CONDITIONS",
    }
    report = validate_release(release)
    assert report["valid"] is False
    assert any(item["code"] == "UNSUPPORTED_REOPENING_TRANSITION" for item in report["errors"])


def test_baseline_sha_verified_against_stored_v1_4_bytes(tmp_path: Path):
    import_release(tmp_path, EXAMPLE)
    release = load_release(SUCCESSOR)
    baseline_path = tmp_path / "observatory" / "releases" / "v1.4" / "release.json"
    assert sha256_file(baseline_path) == release["baseline_reference"]["canonical_sha256"]
    assert verify_baseline_bytes(release, baseline_path) == []
    report = validate_release(release, baseline_path=baseline_path)
    assert report["valid"] is True

    # Tamper stored baseline bytes and confirm mismatch is detected.
    tampered = json.loads(baseline_path.read_text(encoding="utf-8"))
    tampered["metadata"]["title"] = "tampered"
    atomic_write_json(baseline_path, tampered)
    errors = verify_baseline_bytes(release, baseline_path)
    assert any(item["code"] == "BASELINE_SHA256_MISMATCH" for item in errors)
    report = validate_release(release, baseline_path=baseline_path)
    assert report["valid"] is False


def test_successor_import_checks_imported_baseline(tmp_path: Path):
    import_release(tmp_path, EXAMPLE)
    result = import_release(tmp_path, SUCCESSOR)
    assert result["manifest"]["validation"]["valid"] is True
    assert result["manifest"]["release_kind"] == "COMPACT_SUCCESSOR_SNAPSHOT"
