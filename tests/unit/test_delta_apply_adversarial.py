from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from neuroai_workbench.delta import DeltaApplyError, apply_delta, compile_adjudicated_delta
from neuroai_workbench.delta.apply import _apply_operation
from neuroai_workbench.util import atomic_write_json, load_json

FIXTURES = Path(__file__).parents[1] / "fixtures" / "delta"
PREDECESSOR = FIXTURES / "synthetic_predecessor_release.json"


def test_apply_all_operation_types(tmp_path: Path) -> None:
    predecessor = load_json(PREDECESSOR)
    candidate_id = "CAND-" + "b" * 32
    package = {
        "metadata": {"version": "refresh-all-ops"},
        "registry_reference": {"sha256": "d" * 64},
        "change_candidates": [
            {
                "candidate_id": candidate_id,
                "source_id": "SRC-0002",
                "source_snapshot_ids": [],
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
                "rationale": "Coverage for all operation handlers.",
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
                    "operation_id": "OP-000001",
                    "operation_type": "ADD_RECORD",
                    "target_section": "sources",
                    "record": {"source_id": "SRC-0099", "publisher": "Synthetic"},
                },
                {
                    "operation_id": "OP-000002",
                    "operation_type": "ADD_RELATIONSHIP",
                    "target_section": "trial_site_relationships",
                    "record": {"relationship_id": "REL-001", "site": "Example"},
                },
                {
                    "operation_id": "OP-000003",
                    "operation_type": "SUPERSEDE_RECORD",
                    "target_section": "sources",
                    "record_id_field": "source_id",
                    "record_id": "SRC-0002",
                    "superseded_by": "SRC-0002-T2",
                    "tombstone": {"source_id": "SRC-0002", "superseded": True},
                },
                {
                    "operation_id": "OP-000004",
                    "operation_type": "ADD_ALIAS",
                    "target_section": "entity_aliases",
                    "entity_id": "ENT-001",
                    "alias": "Example Org",
                },
                {
                    "operation_id": "OP-000005",
                    "operation_type": "RECORD_SOURCE_INACCESSIBILITY",
                    "target_section": "sources",
                    "source_id": "SRC-0001",
                    "inaccessibility_reason": "HTTP 403",
                    "evidence_state": "SOURCE_INACCESSIBLE",
                },
                {
                    "operation_id": "OP-000006",
                    "operation_type": "QUEUE_ASSESSMENT_REVIEW",
                    "target_section": "assessment_reviews",
                    "assessment_id": "ASMT-PILOT-01",
                    "reopening_effect": "REVIEW_REQUIRED",
                    "rationale": "Material source change.",
                },
            ]
        },
    )
    result = apply_delta(predecessor, delta, tmp_path / "all-ops", apply_id="apply-all")
    successor = load_json(tmp_path / "all-ops" / result["successor_path"])
    assert any(item.get("source_id") == "SRC-0099" for item in successor["sources"])
    assert successor["entity_aliases"][0]["alias"] == "Example Org"
    assert successor["assessment_reviews"][0]["status"] == "QUEUED_FOR_HUMAN_REVIEW"


def test_apply_operation_fail_closed_paths() -> None:
    predecessor = load_json(PREDECESSOR)
    successor: dict[str, Any] = load_json(PREDECESSOR)
    with pytest.raises(DeltaApplyError, match="requires a record object"):
        _apply_operation(successor, {"operation_type": "ADD_RECORD", "target_section": "sources"}, predecessor)
    with pytest.raises(DeltaApplyError, match="not a list"):
        _apply_operation(
            {"sources": "bad"},
            {
                "operation_type": "ADD_RECORD",
                "target_section": "sources",
                "record": {"source_id": "SRC-0100"},
            },
            predecessor,
        )
    with pytest.raises(DeltaApplyError, match="Unsupported operation type"):
        _apply_operation(successor, {"operation_type": "JSON_PATCH", "target_section": "sources"}, predecessor)
    with pytest.raises(DeltaApplyError, match="already exists"):
        _apply_operation(
            successor,
            {
                "operation_type": "ADD_RECORD",
                "target_section": "sources",
                "record_id_field": "source_id",
                "record_id": "SRC-0001",
                "record": {"source_id": "SRC-0001"},
            },
            predecessor,
        )
    with pytest.raises(DeltaApplyError, match="not found in predecessor"):
        _apply_operation(
            successor,
            {
                "operation_type": "UPDATE_FIELD_WITH_PREDECESSOR",
                "target_section": "sources",
                "record_id_field": "source_id",
                "record_id": "SRC-MISSING",
                "field": "baseline_verification_state",
                "before_value": "CURRENT_VERIFIED",
                "after_value": "CURRENT_PARTIAL",
            },
            predecessor,
        )
    with pytest.raises(DeltaApplyError, match="not found for supersession"):
        _apply_operation(
            successor,
            {
                "operation_type": "SUPERSEDE_RECORD",
                "target_section": "sources",
                "record_id_field": "source_id",
                "record_id": "SRC-MISSING",
                "superseded_by": "SRC-X",
                "tombstone": {},
            },
            predecessor,
        )
    with pytest.raises(DeltaApplyError, match="Unknown source"):
        _apply_operation(
            successor,
            {
                "operation_type": "RECORD_SOURCE_INACCESSIBILITY",
                "target_section": "sources",
                "source_id": "SRC-MISSING",
                "inaccessibility_reason": "HTTP 403",
                "evidence_state": "SOURCE_INACCESSIBLE",
            },
            predecessor,
        )
    with pytest.raises(DeltaApplyError, match="already registered"):
        successor_with_alias = load_json(PREDECESSOR)
        successor_with_alias["entity_aliases"] = [{"entity_id": "ENT-001", "alias": "Example Org"}]
        _apply_operation(
            successor_with_alias,
            {
                "operation_type": "ADD_ALIAS",
                "target_section": "entity_aliases",
                "entity_id": "ENT-001",
                "alias": "Example Org",
            },
            predecessor,
        )


def test_apply_from_paths_and_invalid_inputs(tmp_path: Path) -> None:
    from neuroai_workbench.delta import apply_delta_from_paths

    predecessor, delta = _compile_sample_delta()
    pred_path = tmp_path / "pred.json"
    delta_path = tmp_path / "delta.json"
    pred_path.write_text("[]", encoding="utf-8")
    delta_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="must be JSON objects"):
        apply_delta_from_paths(pred_path, delta_path, tmp_path / "out", apply_id="apply-invalid")


def _compile_sample_delta() -> tuple[dict[str, Any], dict[str, Any]]:
    predecessor = load_json(PREDECESSOR)
    candidate_id = "CAND-" + "c" * 32
    package = {
        "metadata": {"version": "refresh-apply"},
        "registry_reference": {"sha256": "d" * 64},
        "change_candidates": [
            {
                "candidate_id": candidate_id,
                "source_id": "SRC-0001",
                "source_snapshot_ids": [],
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
                "change_class": "REGULATORY_OR_MARKET_EVENT",
                "materiality": "NON_MATERIAL",
                "reopening_effect": "NO_EFFECT",
                "rationale": "test",
                "canonical_observatory_mutation_performed": False,
                "boundary": "Boundary.",
            }
        ],
    }
    delta = compile_adjudicated_delta(package, predecessor, predecessor_release_id="v1.0-synthetic")
    return predecessor, delta


def test_apply_rejects_conflicting_manifest(tmp_path: Path) -> None:
    predecessor, delta = _compile_sample_delta()
    output = tmp_path / "out"
    apply_delta(predecessor, delta, output, apply_id="first")
    other_delta_package = compile_adjudicated_delta(
        {
            "metadata": {"version": "refresh-other"},
            "registry_reference": {"sha256": "d" * 64},
            "change_candidates": [],
            "adjudications": [],
        },
        predecessor,
        predecessor_release_id="v1.0-synthetic",
    )
    with pytest.raises(DeltaApplyError, match="existing delta application manifest"):
        apply_delta(predecessor, other_delta_package, output, apply_id="second")


def test_apply_rejects_invalid_delta_schema(tmp_path: Path) -> None:
    from neuroai_workbench.delta import DeltaValidationError

    predecessor = load_json(PREDECESSOR)
    _, delta = _compile_sample_delta()
    bad_delta = dict(delta)
    bad_delta["metadata"]["status"] = "CANONICAL"
    with pytest.raises(DeltaValidationError, match="Delta failed schema validation"):
        apply_delta(predecessor, bad_delta, tmp_path / "bad-schema", apply_id="apply-bad-schema")


def test_apply_from_paths_success(tmp_path: Path) -> None:
    from neuroai_workbench.delta import apply_delta_from_paths

    predecessor = load_json(PREDECESSOR)
    _, delta = _compile_sample_delta()
    pred_path = tmp_path / "pred.json"
    delta_path = tmp_path / "delta.json"
    atomic_write_json(pred_path, predecessor)
    atomic_write_json(delta_path, delta)
    result = apply_delta_from_paths(pred_path, delta_path, tmp_path / "from-paths", apply_id="apply-paths")
    assert result["apply_id"] == "apply-paths"


def test_apply_rejects_existing_successor_file(tmp_path: Path) -> None:
    predecessor = load_json(PREDECESSOR)
    _, delta = _compile_sample_delta()
    successor_path = tmp_path / "blocked" / "candidate-successor.json"
    successor_path.parent.mkdir(parents=True)
    successor_path.write_text("{}", encoding="utf-8")
    with pytest.raises(DeltaApplyError, match="existing candidate successor"):
        apply_delta(predecessor, delta, tmp_path / "blocked", apply_id="apply-blocked")


def test_apply_rejects_semantic_validation_errors(tmp_path: Path) -> None:
    from neuroai_workbench.delta import DeltaValidationError

    predecessor = load_json(PREDECESSOR)
    _, delta = _compile_sample_delta()
    delta["operations"].append(
        {
            "operation_id": "OP-000001",
            "operation_type": "ADD_RECORD",
            "target_section": "sources",
            "record": {"source_id": "SRC-0100"},
        }
    )
    with pytest.raises(DeltaValidationError, match="semantic validation"):
        apply_delta(predecessor, delta, tmp_path / "bad-semantic", apply_id="apply-bad-semantic")


def test_apply_operation_type_guard_branches() -> None:
    predecessor = load_json(PREDECESSOR)
    with pytest.raises(DeltaApplyError, match="is not a list"):
        _apply_operation(
            {"sources": "bad", "regulatory_and_market_events": []},
            {
                "operation_type": "UPDATE_FIELD_WITH_PREDECESSOR",
                "target_section": "sources",
                "record_id_field": "source_id",
                "record_id": "SRC-0001",
                "field": "baseline_verification_state",
                "before_value": "CURRENT_VERIFIED",
                "after_value": "CURRENT_PARTIAL",
            },
            predecessor,
        )
    mutated = load_json(PREDECESSOR)
    mutated["sources"][0]["baseline_verification_state"] = "ALREADY_CHANGED"
    with pytest.raises(DeltaApplyError, match="Successor state diverged"):
        _apply_operation(
            mutated,
            {
                "operation_type": "UPDATE_FIELD_WITH_PREDECESSOR",
                "target_section": "sources",
                "record_id_field": "source_id",
                "record_id": "SRC-0001",
                "field": "baseline_verification_state",
                "before_value": "CURRENT_VERIFIED",
                "after_value": "CURRENT_PARTIAL",
            },
            predecessor,
        )
    with pytest.raises(DeltaApplyError, match="entity_aliases must be a list"):
        _apply_operation(
            {"entity_aliases": "bad"},
            {
                "operation_type": "ADD_ALIAS",
                "target_section": "entity_aliases",
                "entity_id": "ENT-002",
                "alias": "Other",
            },
            predecessor,
        )
    with pytest.raises(DeltaApplyError, match="sources must be a list"):
        _apply_operation(
            {"sources": "bad"},
            {
                "operation_type": "RECORD_SOURCE_INACCESSIBILITY",
                "target_section": "sources",
                "source_id": "SRC-0001",
                "inaccessibility_reason": "HTTP 403",
                "evidence_state": "SOURCE_INACCESSIBLE",
            },
            predecessor,
        )
    with pytest.raises(DeltaApplyError, match="assessment_reviews must be a list"):
        _apply_operation(
            {"assessment_reviews": "bad"},
            {
                "operation_type": "QUEUE_ASSESSMENT_REVIEW",
                "target_section": "assessment_reviews",
                "assessment_id": "ASMT-1",
                "reopening_effect": "REVIEW_REQUIRED",
                "rationale": "test",
            },
            predecessor,
        )
    with pytest.raises(DeltaApplyError, match="is not a list"):
        _apply_operation(
            {"sources": "bad"},
            {
                "operation_type": "SUPERSEDE_RECORD",
                "target_section": "sources",
                "record_id_field": "source_id",
                "record_id": "SRC-0001",
                "superseded_by": "SRC-0001-T2",
                "tombstone": {},
            },
            predecessor,
        )


