from __future__ import annotations

from typing import Any

import pytest

from neuroai_workbench.delta import validate_adjudicated_delta, validate_delta_operation
from neuroai_workbench.delta.schemas import validate_adjudicated_delta_semantics


def _minimal_delta(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "metadata": {
            "title": "Test delta",
            "delta_id": "DELTA-" + "a" * 32,
            "version": "1.0",
            "generated_at": "2026-08-02T10:00:00Z",
            "generated_by": "tester",
            "status": "NON_CANONICAL",
            "refresh_package_version": "refresh-test",
            "refresh_package_sha256": "b" * 64,
        },
        "predecessor": {
            "release_id": "v1.0-synthetic",
            "sha256": "c" * 64,
            "source_registry_sha256": "d" * 64,
            "policy_version": "MONITORING_POLICY_v1",
        },
        "candidate_references": [],
        "operations": [],
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
        "withheld_claims": ["Synthetic test fixture."],
        "boundary": "Test boundary.",
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize(
    "operation_type,required_fields",
    [
        ("ADD_RECORD", {"record": {"source_id": "SRC-0001"}}),
        ("ADD_RELATIONSHIP", {"record": {"relationship_id": "REL-001"}}),
        (
            "UPDATE_FIELD_WITH_PREDECESSOR",
            {
                "record_id_field": "source_id",
                "record_id": "SRC-0001",
                "field": "baseline_verification_state",
                "before_value": "CURRENT_VERIFIED",
                "after_value": "CURRENT_PARTIAL",
            },
        ),
        (
            "ADD_EVENT",
            {"record": {"event_id": "REG-002", "event_date": "2026-08-02", "source_ids": ["SRC-0001"]}},
        ),
        (
            "SUPERSEDE_RECORD",
            {
                "record_id_field": "source_id",
                "record_id": "SRC-0001",
                "superseded_by": "SRC-0001-T2",
                "tombstone": {"source_id": "SRC-0001", "superseded": True},
            },
        ),
        ("ADD_ALIAS", {"entity_id": "ENT-001", "alias": "Example Org"}),
        (
            "RECORD_SOURCE_INACCESSIBILITY",
            {
                "source_id": "SRC-0001",
                "inaccessibility_reason": "HTTP 403",
                "evidence_state": "SOURCE_INACCESSIBLE",
            },
        ),
        (
            "QUEUE_ASSESSMENT_REVIEW",
            {
                "assessment_id": "ASMT-PILOT-01",
                "reopening_effect": "REVIEW_REQUIRED",
                "rationale": "Material source change.",
            },
        ),
    ],
)
def test_operation_schema_accepts_typed_operations(operation_type: str, required_fields: dict[str, Any]) -> None:
    operation = {
        "operation_id": "OP-000001",
        "operation_type": operation_type,
        "target_section": "sources",
        **required_fields,
    }
    assert validate_delta_operation(operation) == []


def test_adjudicated_delta_schema_validates_minimal_package() -> None:
    assert validate_adjudicated_delta(_minimal_delta()) == []
    assert validate_adjudicated_delta_semantics(_minimal_delta()) == []


def test_adjudicated_delta_rejects_canonical_status() -> None:
    delta = _minimal_delta()
    delta["metadata"]["status"] = "CANONICAL"
    errors = validate_adjudicated_delta(delta)
    assert errors
    semantic = validate_adjudicated_delta_semantics(delta)
    assert any(item["code"] == "INVALID_STATUS" for item in semantic)


def test_validate_adjudicated_delta_non_dict_input() -> None:
    errors = validate_adjudicated_delta(["not-a-delta"])
    assert errors


def test_validate_adjudicated_delta_operation_path_prefix() -> None:
    delta = _minimal_delta(
        operations=[{"operation_type": "JSON_PATCH", "operation_id": "OP-000001", "target_section": "sources"}]
    )
    errors = validate_adjudicated_delta(delta)
    assert any("operations[0]" in item["path"] for item in errors)


def test_semantic_validation_returns_early_when_operations_not_list() -> None:
    assert validate_adjudicated_delta_semantics({"metadata": {"status": "NON_CANONICAL"}}) == []
