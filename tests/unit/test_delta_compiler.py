from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from neuroai_workbench.delta import (
    DELTA_BOUNDARY,
    DeltaCompileError,
    compile_adjudicated_delta,
    validate_adjudicated_delta,
    validate_adjudicated_delta_semantics,
    validate_delta_operation,
)
from neuroai_workbench.util import canonical_json_bytes, load_json, sha256_bytes

FIXTURES = Path(__file__).parents[1] / "fixtures" / "delta"
PREDECESSOR = FIXTURES / "synthetic_predecessor_release.json"


def _sample_candidate(candidate_id: str = "CAND-" + "a" * 32) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "created_at": "2026-08-02T08:00:00Z",
        "created_by": "tester",
        "source_id": "SRC-0001",
        "source_snapshot_ids": ["SNAP-OLD", "SNAP-NEW"],
        "current_snapshot_sha256": "b" * 64,
        "detection": {"classification": "CONTENT_CHANGED_REQUIRES_REVIEW"},
        "summary": "Synthetic regulatory update detected.",
        "proposed_change_class": "UNCLASSIFIED",
        "proposed_materiality": "UNDETERMINED",
        "proposed_reopening_effect": "UNDETERMINED",
        "extracted_claims": [],
        "status": "PENDING_HUMAN_ADJUDICATION",
        "automatic_mutation_performed": False,
        "boundary": DELTA_BOUNDARY,
    }


def _sample_adjudication(
    candidate_id: str = "CAND-" + "a" * 32,
    *,
    decision: str = "ACCEPT",
    change_class: str = "REGULATORY_OR_MARKET_EVENT",
) -> dict[str, Any]:
    return {
        "adjudication_id": f"ADJ-{candidate_id.removeprefix('CAND-')}",
        "candidate_id": candidate_id,
        "candidate_sha256": "c" * 64,
        "decided_at": "2026-08-02T09:00:00Z",
        "decided_by": "reviewer",
        "decision": decision,
        "change_class": change_class,
        "materiality": "MATERIAL",
        "reopening_effect": "REVIEW_REQUIRED",
        "rationale": "Controlled synthetic adjudication.",
        "canonical_observatory_mutation_performed": False,
        "boundary": DELTA_BOUNDARY,
    }


def _refresh_package(
    *,
    candidates: list[dict[str, Any]] | None = None,
    adjudications: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "metadata": {
            "title": "Synthetic refresh package",
            "version": "refresh-2026-08",
            "evidence_cutoff": "2026-08-02",
            "generated_at": "2026-08-02T10:00:00Z",
            "generated_by": "tester",
            "status": "REVIEW_CANDIDATE_NOT_CANONICAL",
        },
        "registry_reference": {"sha256": "d" * 64, "source_count": 2},
        "change_candidates": candidates or [],
        "adjudications": adjudications or [],
        "accepted_changes": [],
        "unresolved_candidates": [],
        "reopening_queue": [],
        "counts": {},
        "withheld_claims": ["Synthetic fixture."],
        "boundary": DELTA_BOUNDARY,
    }


def test_predecessor_fixture_loads() -> None:
    predecessor = load_json(PREDECESSOR)
    assert predecessor["metadata"]["version"] == "v1.0-synthetic"
    assert len(predecessor["sources"]) == 2


def test_compile_delta_with_explicit_operation_specs() -> None:
    candidate_id = "CAND-" + "e" * 32
    candidate = _sample_candidate(candidate_id)
    adjudication = _sample_adjudication(candidate_id, change_class="FIELD_UPDATE")
    package = _refresh_package(candidates=[candidate], adjudications=[adjudication])
    predecessor = load_json(PREDECESSOR)
    operation_specs = {
        candidate_id: [
            {
                "operation_type": "UPDATE_FIELD_WITH_PREDECESSOR",
                "target_section": "sources",
                "record_id_field": "source_id",
                "record_id": "SRC-0001",
                "field": "baseline_verification_state",
                "before_value": "CURRENT_VERIFIED",
                "after_value": "CURRENT_PARTIAL",
            }
        ]
    }
    delta = compile_adjudicated_delta(
        package,
        predecessor,
        predecessor_release_id="v1.0-synthetic",
        operation_specs=operation_specs,
    )
    assert delta["metadata"]["status"] == "NON_CANONICAL"
    assert delta["predecessor"]["sha256"] == sha256_bytes(canonical_json_bytes(predecessor))
    assert len(delta["operations"]) == 1
    assert delta["operations"][0]["operation_type"] == "UPDATE_FIELD_WITH_PREDECESSOR"
    assert len(delta["disposition_registers"]["accepted"]) == 1
    assert validate_adjudicated_delta(delta) == []
    assert validate_adjudicated_delta_semantics(delta) == []


def test_compile_delta_default_add_event_from_change_class() -> None:
    candidate_id = "CAND-" + "f" * 32
    candidate = _sample_candidate(candidate_id)
    adjudication = _sample_adjudication(candidate_id, change_class="REGULATORY_OR_MARKET_EVENT")
    package = _refresh_package(candidates=[candidate], adjudications=[adjudication])
    predecessor = load_json(PREDECESSOR)
    delta = compile_adjudicated_delta(
        package,
        predecessor,
        predecessor_release_id="v1.0-synthetic",
    )
    assert delta["operations"][0]["operation_type"] == "ADD_EVENT"
    assert delta["reopening_decisions"][0]["reopening_effect"] == "REVIEW_REQUIRED"


def test_disposition_registers_capture_all_decisions() -> None:
    candidates = []
    adjudications = []
    for index, decision in enumerate(["ACCEPT", "REJECT", "DEFER", "DUPLICATE", "NEEDS_EVIDENCE"]):
        candidate_id = f"CAND-{index:032x}"
        candidates.append(_sample_candidate(candidate_id))
        adjudications.append(
            _sample_adjudication(candidate_id, decision=decision, change_class="REGULATORY_OR_MARKET_EVENT")
        )
    unresolved = _sample_candidate("CAND-" + "9" * 32)
    candidates.append(unresolved)
    package = _refresh_package(candidates=candidates, adjudications=adjudications)
    predecessor = load_json(PREDECESSOR)
    delta = compile_adjudicated_delta(package, predecessor, predecessor_release_id="v1.0-synthetic")
    registers = delta["disposition_registers"]
    assert len(registers["accepted"]) == 1
    assert len(registers["rejected"]) == 1
    assert len(registers["deferred"]) == 1
    assert len(registers["duplicate"]) == 1
    assert len(registers["needs_evidence"]) == 1
    assert len(registers["unresolved"]) == 1


def test_blocked_operation_when_change_class_unmapped() -> None:
    candidate_id = "CAND-" + "b" * 32
    candidate = _sample_candidate(candidate_id)
    adjudication = _sample_adjudication(candidate_id, change_class="UNKNOWN_CLASS")
    package = _refresh_package(candidates=[candidate], adjudications=[adjudication])
    predecessor = load_json(PREDECESSOR)
    delta = compile_adjudicated_delta(package, predecessor, predecessor_release_id="v1.0-synthetic")
    assert delta["operations"] == []
    assert delta["blocked_operations"][0]["code"] == "MISSING_OPERATION_SPEC"


def test_rejects_unrestricted_patch_operation_type() -> None:
    operation = {
        "operation_id": "OP-000001",
        "operation_type": "JSON_PATCH",
        "target_section": "sources",
    }
    errors = validate_delta_operation(operation)
    assert errors


def test_non_canonical_status_required() -> None:
    candidate_id = "CAND-" + "c" * 32
    package = _refresh_package(
        candidates=[_sample_candidate(candidate_id)],
        adjudications=[_sample_adjudication(candidate_id)],
    )
    predecessor = load_json(PREDECESSOR)
    delta = compile_adjudicated_delta(package, predecessor, predecessor_release_id="v1.0-synthetic")
    delta["metadata"]["status"] = "CANONICAL"
    errors = validate_adjudicated_delta_semantics(delta)
    assert any(item["code"] == "INVALID_STATUS" for item in errors)


def test_compile_rejects_invalid_refresh_package() -> None:
    predecessor = load_json(PREDECESSOR)
    with pytest.raises(DeltaCompileError):
        compile_adjudicated_delta({}, predecessor, predecessor_release_id="v1.0-synthetic")


def test_operation_ordering_is_deterministic() -> None:
    candidate_id = "CAND-" + "d" * 32
    candidate = _sample_candidate(candidate_id)
    adjudication = _sample_adjudication(candidate_id, change_class="FIELD_UPDATE")
    package = _refresh_package(candidates=[candidate], adjudications=[adjudication])
    predecessor = load_json(PREDECESSOR)
    specs = {
        candidate_id: [
            {
                "operation_id": "OP-000002",
                "operation_type": "ADD_RECORD",
                "target_section": "sources",
                "record": {"source_id": "SRC-0099", "summary": "second"},
            },
            {
                "operation_id": "OP-000001",
                "operation_type": "ADD_RECORD",
                "target_section": "sources",
                "record": {"source_id": "SRC-0098", "summary": "first"},
            },
        ]
    }
    delta = compile_adjudicated_delta(
        package,
        predecessor,
        predecessor_release_id="v1.0-synthetic",
        operation_specs=specs,
    )
    assert [item["operation_id"] for item in delta["operations"]] == ["OP-000001", "OP-000002"]
