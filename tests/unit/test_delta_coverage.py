from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from neuroai_workbench.delta import DeltaCompileError, DeltaValidationError, compile_adjudicated_delta
from neuroai_workbench.delta.compiler import _default_operation_from_change_class
from neuroai_workbench.delta.schemas import (
    validate_adjudicated_delta,
    validate_adjudicated_delta_semantics,
)
from neuroai_workbench.util import load_json

FIXTURES = Path(__file__).parents[1] / "fixtures" / "delta"


def test_default_operations_for_remaining_change_classes() -> None:
    candidate = {"candidate_id": "CAND-" + "a" * 32, "source_id": "SRC-0001", "summary": "test"}
    adjudication = {
        "adjudication_id": "ADJ-" + "a" * 32,
        "decided_at": "2026-08-02T09:00:00Z",
        "rationale": "test",
        "reopening_effect": "REVIEW_REQUIRED",
        "boundary": "boundary",
    }
    for change_class in (
        "NEW_SOURCE_RECORD",
        "SOURCE_INACCESSIBILITY",
        "ASSESSMENT_REOPENING",
        "FIELD_UPDATE",
        "RECORD_SUPERSESSION",
    ):
        operation = _default_operation_from_change_class(change_class, candidate, adjudication, 1)
        if change_class in {"FIELD_UPDATE", "RECORD_SUPERSESSION"}:
            assert operation is None
        else:
            assert operation is not None


def test_validate_adjudicated_delta_rejects_non_object_operations() -> None:
    payload: dict[str, Any] = {
        "metadata": {
            "title": "Test",
            "delta_id": "DELTA-" + "b" * 32,
            "version": "1.0",
            "generated_at": "2026-08-02T10:00:00Z",
            "generated_by": "tester",
            "status": "NON_CANONICAL",
            "refresh_package_version": "refresh-test",
        },
        "predecessor": {
            "release_id": "v1.0-synthetic",
            "sha256": "c" * 64,
            "source_registry_sha256": "d" * 64,
        },
        "candidate_references": [],
        "operations": ["bad"],
        "disposition_registers": {
            "accepted": [],
            "rejected": [],
            "deferred": [],
            "duplicate": [],
            "needs_evidence": [],
            "unresolved": [],
        },
        "blocked_operations": [],
        "reopening_decisions": [],
        "withheld_claims": ["Synthetic."],
        "boundary": "Boundary.",
    }
    errors = validate_adjudicated_delta(payload)
    assert errors


def test_semantic_validation_skips_non_dict_operations() -> None:
    delta = {
        "metadata": {"status": "NON_CANONICAL"},
        "operations": ["skip", {"operation_type": "JSON_PATCH", "operation_id": "OP-000001"}],
    }
    errors = validate_adjudicated_delta_semantics(delta)
    assert any(item["code"] == "UNSUPPORTED_OPERATION" for item in errors)


def test_semantic_validation_returns_early_when_operations_not_list() -> None:
    assert validate_adjudicated_delta_semantics({"metadata": {"status": "NON_CANONICAL"}}) == []


def test_compile_rejects_missing_package_fields() -> None:
    predecessor = load_json(FIXTURES / "synthetic_predecessor_release.json")
    with pytest.raises(DeltaCompileError, match="metadata is required"):
        compile_adjudicated_delta({"registry_reference": {"sha256": "a" * 64}}, predecessor, predecessor_release_id="x")
    with pytest.raises(DeltaCompileError, match="version is required"):
        compile_adjudicated_delta(
            {"metadata": {}, "registry_reference": {"sha256": "a" * 64}},
            predecessor,
            predecessor_release_id="x",
        )
    with pytest.raises(DeltaCompileError, match="registry_reference is required"):
        compile_adjudicated_delta({"metadata": {"version": "v1"}}, predecessor, predecessor_release_id="x")
    with pytest.raises(DeltaCompileError, match="registry sha256 is required"):
        compile_adjudicated_delta(
            {"metadata": {"version": "v1"}, "registry_reference": {}},
            predecessor,
            predecessor_release_id="x",
        )


def test_compile_skips_malformed_candidates() -> None:
    predecessor = load_json(FIXTURES / "synthetic_predecessor_release.json")
    package = {
        "metadata": {"version": "refresh-x"},
        "registry_reference": {"sha256": "d" * 64},
        "change_candidates": [
            "bad",
            {"candidate_id": 123},
            {
                "candidate_id": "CAND-" + "4" * 32,
                "source_id": "SRC-0001",
                "source_snapshot_ids": [],
                "current_snapshot_sha256": "e" * 64,
            },
        ],
        "adjudications": [],
    }
    delta = compile_adjudicated_delta(package, predecessor, predecessor_release_id="v1.0-synthetic")
    assert len(delta["candidate_references"]) == 1


def test_compile_rejects_invalid_operation_in_specs() -> None:
    predecessor = load_json(FIXTURES / "synthetic_predecessor_release.json")
    candidate_id = "CAND-" + "5" * 32
    package = {
        "metadata": {"version": "refresh-x"},
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
                "decided_at": "2026-08-02T09:00:00Z",
                "decided_by": "reviewer",
                "decision": "ACCEPT",
                "change_class": "FIELD_UPDATE",
                "materiality": "NON_MATERIAL",
                "reopening_effect": "NO_EFFECT",
                "rationale": "test",
            }
        ],
    }
    with pytest.raises(DeltaValidationError, match="schema validation"):
        compile_adjudicated_delta(
            package,
            predecessor,
            predecessor_release_id="v1.0-synthetic",
            operation_specs={candidate_id: [{"operation_type": "ADD_RECORD", "target_section": "sources"}]},
        )


def test_compile_handles_non_string_change_class() -> None:
    predecessor = load_json(FIXTURES / "synthetic_predecessor_release.json")
    candidate_id = "CAND-" + "6" * 32
    package = {
        "metadata": {"version": "refresh-x"},
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
                "decided_at": "2026-08-02T09:00:00Z",
                "decided_by": "reviewer",
                "decision": "ACCEPT",
                "change_class": 123,
                "materiality": "NON_MATERIAL",
                "reopening_effect": "NO_EFFECT",
                "rationale": "test",
            }
        ],
    }
    delta = compile_adjudicated_delta(package, predecessor, predecessor_release_id="v1.0-synthetic")
    assert delta["blocked_operations"]
