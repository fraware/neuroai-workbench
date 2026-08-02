from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from neuroai_workbench.delta import (
    APPLY_BOUNDARY,
    DeltaApplyError,
    apply_delta,
    compile_adjudicated_delta,
)
from neuroai_workbench.util import canonical_json_bytes, load_json, sha256_bytes

FIXTURES = Path(__file__).parents[1] / "fixtures" / "delta"
PREDECESSOR = FIXTURES / "synthetic_predecessor_release.json"


def _compile_sample_delta() -> tuple[dict[str, Any], dict[str, Any]]:
    predecessor = load_json(PREDECESSOR)
    candidate_id = "CAND-" + "a" * 32
    package = {
        "metadata": {"version": "refresh-apply", "status": "REVIEW_CANDIDATE_NOT_CANONICAL"},
        "registry_reference": {"sha256": "d" * 64, "source_count": 2},
        "change_candidates": [
            {
                "candidate_id": candidate_id,
                "source_id": "SRC-0001",
                "source_snapshot_ids": ["SNAP-1"],
                "current_snapshot_sha256": "e" * 64,
            }
        ],
        "adjudications": [
            {
                "adjudication_id": f"ADJ-{candidate_id.removeprefix('CAND-')}",
                "candidate_id": candidate_id,
                "candidate_sha256": "f" * 64,
                "decided_at": "2026-08-02T09:00:00Z",
                "decided_by": "reviewer",
                "decision": "ACCEPT",
                "change_class": "FIELD_UPDATE",
                "materiality": "NON_MATERIAL",
                "reopening_effect": "NO_EFFECT",
                "rationale": "Synthetic field update.",
                "canonical_observatory_mutation_performed": False,
                "boundary": "Boundary.",
            }
        ],
    }
    delta = compile_adjudicated_delta(
        package,
        predecessor,
        predecessor_release_id="v1.0-synthetic",
        operation_specs={
            candidate_id: [
                {
                    "operation_type": "UPDATE_FIELD_WITH_PREDECESSOR",
                    "target_section": "sources",
                    "record_id_field": "source_id",
                    "record_id": "SRC-0001",
                    "field": "baseline_verification_state",
                    "before_value": "CURRENT_VERIFIED",
                    "after_value": "CURRENT_PARTIAL",
                },
                {
                    "operation_id": "OP-000002",
                    "operation_type": "ADD_EVENT",
                    "target_section": "regulatory_and_market_events",
                    "record": {
                        "event_id": "REG-002",
                        "event_date": "2026-08-02",
                        "source_ids": ["SRC-0001"],
                        "evidence_state": "SYNTHETIC_APPLY",
                        "summary": "Applied event fixture.",
                    },
                },
            ]
        },
    )
    return predecessor, delta


def test_apply_produces_candidate_successor_and_leaves_predecessor_untouched(tmp_path: Path) -> None:
    predecessor, delta = _compile_sample_delta()
    predecessor_hash_before = sha256_bytes(canonical_json_bytes(predecessor))
    predecessor_copy = load_json(PREDECESSOR)

    result = apply_delta(predecessor, delta, tmp_path / "out", apply_id="apply-test-001")
    assert result["predecessor_unchanged"] is True
    assert sha256_bytes(canonical_json_bytes(predecessor)) == predecessor_hash_before
    assert sha256_bytes(canonical_json_bytes(predecessor_copy)) == predecessor_hash_before

    successor = load_json(tmp_path / "out" / "candidate-successor.json")
    assert successor["metadata"]["status"] == "CANDIDATE_SUCCESSOR_NOT_CANONICAL"
    assert successor["sources"][0]["baseline_verification_state"] == "CURRENT_PARTIAL"
    assert len(successor["regulatory_and_market_events"]) == 2
    manifest = load_json(tmp_path / "out" / "apply-manifest.json")
    assert manifest["delta_sha256"] == result["manifest"]["delta_sha256"]
    assert result["boundary"] == APPLY_BOUNDARY


def test_apply_rejects_predecessor_hash_mismatch(tmp_path: Path) -> None:
    predecessor, delta = _compile_sample_delta()
    delta["predecessor"]["sha256"] = "0" * 64
    with pytest.raises(DeltaApplyError, match="Predecessor sha256 mismatch"):
        apply_delta(predecessor, delta, tmp_path / "out", apply_id="apply-bad-hash")


def test_apply_rejects_before_value_mismatch(tmp_path: Path) -> None:
    predecessor, delta = _compile_sample_delta()
    delta["operations"][0]["before_value"] = "WRONG"
    with pytest.raises(DeltaApplyError, match="Before-value mismatch"):
        apply_delta(predecessor, delta, tmp_path / "out", apply_id="apply-bad-before")


def test_double_apply_is_rejected(tmp_path: Path) -> None:
    predecessor, delta = _compile_sample_delta()
    output = tmp_path / "out"
    apply_delta(predecessor, delta, output, apply_id="apply-once")
    with pytest.raises(DeltaApplyError, match="double-apply"):
        apply_delta(predecessor, delta, output, apply_id="apply-twice")


def test_apply_rejects_duplicate_record_append(tmp_path: Path) -> None:
    predecessor, delta = _compile_sample_delta()
    delta["operations"].append(
        {
            "operation_id": "OP-000003",
            "operation_type": "ADD_EVENT",
            "target_section": "regulatory_and_market_events",
            "record": delta["operations"][1]["record"],
        }
    )
    with pytest.raises(DeltaApplyError, match="Duplicate record append blocked"):
        apply_delta(predecessor, delta, tmp_path / "out", apply_id="apply-dup-record")
