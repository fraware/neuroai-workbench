from __future__ import annotations

from neuroai_workbench.observatory_graph import (
    GRAPH_BOUNDARY,
    KIND_RESOLVED_ENTITY_REFERENCE,
    build_assertion,
    build_entity,
    build_event,
    build_observation,
    compile_temporal_graph,
    state_as_of_release,
    state_valid_at,
)
from neuroai_workbench.temporal import TIME_VALUE_BOUNDARY


def _time(value: str | None, precision: str) -> dict[str, str | None]:
    return {"value": value, "precision": precision, "boundary": TIME_VALUE_BOUNDARY}


def _resolved(entity_id: str) -> dict[str, str]:
    return {
        "kind": KIND_RESOLVED_ENTITY_REFERENCE,
        "entity_id": entity_id,
        "boundary": GRAPH_BOUNDARY,
    }


def test_cross_class_id_cannot_satisfy_source_reference() -> None:
    colliding_entity = build_entity(
        entity_id="SRC-COLLISION",
        entity_type="SYSTEM",
        canonical_label="Not a source",
    )
    observation = build_observation(
        observation_id="OBS-COLLISION",
        source_id="SRC-COLLISION",
        observed_at=_time("2026-08-31", "DATE"),
        retrieval_method="HTTP_GET",
        retrieval_outcome="RETRIEVED",
        requested_locator="https://example.test/collision",
    )

    compiled = compile_temporal_graph([colliding_entity, observation])

    assert compiled["mechanical_pass"] is False
    assert "OBS-COLLISION.source_id->SRC-COLLISION dangling" in compiled["integrity_errors"]


def test_event_objects_and_entity_lineage_are_referentially_checked() -> None:
    subject = build_entity(entity_id="ENT-SUBJECT", entity_type="SYSTEM", canonical_label="Subject")
    lineage = build_entity(
        entity_id="ENT-LINEAGE",
        entity_type="SYSTEM",
        canonical_label="Lineage",
        lineage={
            "predecessor_entity_ids": ["ENT-MISSING-PREDECESSOR"],
            "successor_entity_ids": [],
            "supersession_state": "NONE",
        },
    )
    event = build_event(
        event_id="EVT-DANGLE",
        event_type="OWNERSHIP_TRANSITION",
        subject=_resolved("ENT-SUBJECT"),
        objects=[_resolved("ENT-MISSING-OBJECT")],
        evidence_state="SOURCE_STATED",
        verification_state="UNVERIFIED",
        claim_boundary="test",
        occurred_at=_time("2026-08-31", "DATE"),
    )

    compiled = compile_temporal_graph([subject, lineage, event])

    assert compiled["mechanical_pass"] is False
    assert "EVT-DANGLE.objects[0]->ENT-MISSING-OBJECT dangling" in compiled["integrity_errors"]
    assert (
        "ENT-LINEAGE.lineage.predecessor_entity_ids->ENT-MISSING-PREDECESSOR dangling" in compiled["integrity_errors"]
    )


def test_mixed_precision_interval_uses_calendar_overlap_not_precision_label_order() -> None:
    entity = build_entity(entity_id="ENT-TIME", entity_type="SYSTEM", canonical_label="Timed")
    assertion = build_assertion(
        assertion_id="AST-TIME",
        subject=_resolved("ENT-TIME"),
        predicate="STATUS",
        value="ACTIVE",
        evidence_state="SOURCE_STATED",
        verification_state="UNVERIFIED",
        review_state="NOT_REVIEWED",
        claim_boundary="test",
        valid_from=_time("2026-08-31T23:00:00+02:00", "TIMESTAMP"),
        valid_until=_time("2026-09-01", "DATE"),
    )

    compiled = compile_temporal_graph([entity, assertion])

    assert compiled["mechanical_pass"] is True
    assert not any("valid_until" in error and "precedes" in error for error in compiled["integrity_errors"])


def test_coarse_precision_overlap_is_retained_in_as_of_projection() -> None:
    entity = build_entity(entity_id="ENT-YEAR", entity_type="SYSTEM", canonical_label="Year")
    assertion = build_assertion(
        assertion_id="AST-YEAR",
        subject=_resolved("ENT-YEAR"),
        predicate="STATUS",
        value="ACTIVE",
        evidence_state="SOURCE_STATED",
        verification_state="UNVERIFIED",
        review_state="NOT_REVIEWED",
        claim_boundary="test",
        valid_from=_time("2026", "YEAR"),
        valid_until=_time("2026", "YEAR"),
    )

    inside = state_valid_at([entity, assertion], as_of=_time("2026-08-31", "DATE"))
    outside = state_valid_at([entity, assertion], as_of=_time("2027-01-01", "DATE"))

    assert any(item.get("assertion_id") == "AST-YEAR" for item in inside["objects"])
    assert not any(item.get("assertion_id") == "AST-YEAR" for item in outside["objects"])


def test_candidate_snapshot_projection_does_not_claim_authority() -> None:
    entity = build_entity(entity_id="ENT-PROJ", entity_type="SYSTEM", canonical_label="Projection")

    projection = state_as_of_release([entity])

    assert projection["authoritative"] is False
    assert projection["release_authorized"] is False
