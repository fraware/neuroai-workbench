from __future__ import annotations

import neuroai_workbench.observatory_gate_a_validation as validation_module
from neuroai_workbench.observatory_gate_a_validation import validate_gate_a_native_graph
from neuroai_workbench.observatory_graph import (
    GRAPH_BOUNDARY,
    build_candidate,
    build_entity,
    build_event,
    build_relationship,
    build_source,
)
from neuroai_workbench.temporal import TIME_VALUE_BOUNDARY


def _resolved(entity_id: str) -> dict:
    return {
        "kind": "RESOLVED_ENTITY_REFERENCE",
        "entity_id": entity_id,
        "boundary": GRAPH_BOUNDARY,
    }


def _unresolved(value: str) -> dict:
    return {
        "kind": "UNRESOLVED_LITERAL",
        "value": value,
        "boundary": GRAPH_BOUNDARY,
    }


def _time(value: str, precision: str) -> dict:
    return {"value": value, "precision": precision, "boundary": TIME_VALUE_BOUNDARY}


def _checkpoint(objects: list[dict]) -> dict:
    return {"candidate": {"native_objects": objects}}


def _bypass_checkpoint_validation(monkeypatch) -> None:
    monkeypatch.setattr(
        validation_module,
        "verify_gate_a_migration_checkpoint",
        lambda checkpoint, delta16: {"valid": True, "errors": []},
    )


def test_valid_mini_graph_uses_class_qualified_references(monkeypatch) -> None:
    _bypass_checkpoint_validation(monkeypatch)
    entity = build_entity(entity_id="ORG-1", entity_type="ORGANIZATION", canonical_label="Example")
    source = build_source(
        source_id="SRC-1",
        source_class="OFFICIAL_PAGE",
        title="Official",
        publisher="Publisher",
        canonical_url_or_reference="https://example.test/source",
    )
    event = build_event(
        event_id="EV-1",
        event_type="FINANCING",
        subject=_resolved("ORG-1"),
        objects=[_unresolved("Investor A")],
        occurred_at=_time("2026", "YEAR"),
        source_ids=["SRC-1"],
        observation_ids=[],
        evidence_state="COMPANY_ANNOUNCEMENT",
        verification_state="MIGRATED_PREDECESSOR_STATE",
        claim_boundary="Bounded event.",
    )
    candidate = build_candidate(
        candidate_id="CAND-1",
        candidate_class="CHANGE",
        payload={"source_ids": ["SRC-1"], "summary": "Bounded"},
        provenance_mode="OFFLINE_REPLAY",
        status="ACCEPT_WITH_EVIDENCE_BOUNDARY",
    )

    report = validate_gate_a_native_graph(
        _checkpoint([entity, source, event, candidate]),
        delta16={},
    )

    assert report["valid"] is True
    assert report["errors"] == []
    assert report["class_counts"] == {"Candidate": 1, "Entity": 1, "Event": 1, "Source": 1}
    assert report["typed_reference_semantics"] == "CLASS_QUALIFIED"
    assert report["temporal_semantics"] == "PRECISION_PRESERVING_INTERVAL_BOUNDS"
    assert report["temporal_values_checked"] == 1


def test_cross_class_id_collision_cannot_satisfy_source_reference(monkeypatch) -> None:
    _bypass_checkpoint_validation(monkeypatch)
    entity = build_entity(entity_id="COLLIDE", entity_type="ORGANIZATION", canonical_label="Example")
    candidate = build_candidate(
        candidate_id="COLLIDE",
        candidate_class="CHANGE",
        payload={},
        provenance_mode="OFFLINE_REPLAY",
    )
    event = build_event(
        event_id="EV-1",
        event_type="FINANCING",
        subject=_resolved("COLLIDE"),
        source_ids=["COLLIDE"],
        observation_ids=[],
        evidence_state="SOURCE_BACKED",
        verification_state="MIGRATED_PREDECESSOR_STATE",
        claim_boundary="Bounded event.",
    )

    report = validate_gate_a_native_graph(
        _checkpoint([entity, candidate, event]),
        delta16={},
    )

    assert report["valid"] is False
    assert report["cross_class_id_collisions"] == {"COLLIDE": ["Candidate", "Entity"]}
    assert any("source_ids references missing Source 'COLLIDE'" in error for error in report["errors"])


def test_resolved_subject_must_resolve_to_entity_but_unresolved_event_object_is_allowed(monkeypatch) -> None:
    _bypass_checkpoint_validation(monkeypatch)
    source = build_source(
        source_id="SRC-1",
        source_class="OFFICIAL_PAGE",
        title="Official",
        publisher="Publisher",
        canonical_url_or_reference="https://example.test/source",
    )
    # Builder validation requires a syntactically resolved subject but cannot know whether
    # that Entity exists in the composed graph. Gate-A validation supplies that check.
    event = build_event(
        event_id="EV-1",
        event_type="FINANCING",
        subject=_resolved("ORG-MISSING"),
        objects=[_unresolved("Counterparty literal")],
        source_ids=["SRC-1"],
        observation_ids=[],
        evidence_state="SOURCE_BACKED",
        verification_state="MIGRATED_PREDECESSOR_STATE",
        claim_boundary="Bounded event.",
    )

    report = validate_gate_a_native_graph(_checkpoint([source, event]), delta16={})

    assert report["valid"] is False
    assert any("subject references missing Entity 'ORG-MISSING'" in error for error in report["errors"])
    assert not any("Counterparty literal" in error for error in report["errors"])


def test_candidate_payload_source_ids_are_typed_source_references(monkeypatch) -> None:
    _bypass_checkpoint_validation(monkeypatch)
    entity = build_entity(entity_id="SRC-COLLISION", entity_type="ORGANIZATION", canonical_label="Not a Source")
    candidate = build_candidate(
        candidate_id="CAND-1",
        candidate_class="CHANGE",
        payload={"source_ids": ["SRC-COLLISION"]},
        provenance_mode="OFFLINE_REPLAY",
    )

    report = validate_gate_a_native_graph(_checkpoint([entity, candidate]), delta16={})

    assert report["valid"] is False
    assert any("payload.source_ids references missing Source 'SRC-COLLISION'" in error for error in report["errors"])


def test_mixed_precision_interval_uses_calendar_bounds_not_precision_labels(monkeypatch) -> None:
    _bypass_checkpoint_validation(monkeypatch)
    subject = build_entity(entity_id="ORG-1", entity_type="ORGANIZATION", canonical_label="Subject")
    object_entity = build_entity(entity_id="ORG-2", entity_type="ORGANIZATION", canonical_label="Object")
    source = build_source(
        source_id="SRC-1",
        source_class="OFFICIAL_PAGE",
        title="Official",
        publisher="Publisher",
        canonical_url_or_reference="https://example.test/source",
    )
    relationship = build_relationship(
        relationship_id="REL-1",
        relationship_type="LINKED_TO",
        subject=_resolved("ORG-1"),
        object_ref=_resolved("ORG-2"),
        valid_from=_time("2026-05-01", "DATE"),
        valid_until=_time("2026-05-01T12:00:00Z", "TIMESTAMP"),
        source_ids=["SRC-1"],
        observation_ids=[],
        evidence_state="SOURCE_BACKED",
        claim_boundary="Bounded relationship.",
    )

    report = validate_gate_a_native_graph(
        _checkpoint([subject, object_entity, source, relationship]),
        delta16={},
    )

    assert report["valid"] is True
    assert not any("valid_until definitely precedes valid_from" in error for error in report["errors"])


def test_year_precision_overlap_is_preserved(monkeypatch) -> None:
    _bypass_checkpoint_validation(monkeypatch)
    subject = build_entity(entity_id="ORG-1", entity_type="ORGANIZATION", canonical_label="Subject")
    object_entity = build_entity(entity_id="ORG-2", entity_type="ORGANIZATION", canonical_label="Object")
    relationship = build_relationship(
        relationship_id="REL-1",
        relationship_type="LINKED_TO",
        subject=_resolved("ORG-1"),
        object_ref=_resolved("ORG-2"),
        valid_from=_time("2026", "YEAR"),
        valid_until=_time("2026-01-15", "DATE"),
        source_ids=[],
        observation_ids=[],
        evidence_state="SOURCE_BACKED",
        claim_boundary="Bounded relationship.",
    )

    report = validate_gate_a_native_graph(_checkpoint([subject, object_entity, relationship]), delta16={})

    assert report["valid"] is True


def test_definitely_invalid_temporal_interval_fails(monkeypatch) -> None:
    _bypass_checkpoint_validation(monkeypatch)
    subject = build_entity(entity_id="ORG-1", entity_type="ORGANIZATION", canonical_label="Subject")
    object_entity = build_entity(entity_id="ORG-2", entity_type="ORGANIZATION", canonical_label="Object")
    relationship = build_relationship(
        relationship_id="REL-1",
        relationship_type="LINKED_TO",
        subject=_resolved("ORG-1"),
        object_ref=_resolved("ORG-2"),
        valid_from=_time("2027", "YEAR"),
        valid_until=_time("2026-12-31", "DATE"),
        source_ids=[],
        observation_ids=[],
        evidence_state="SOURCE_BACKED",
        claim_boundary="Bounded relationship.",
    )

    report = validate_gate_a_native_graph(_checkpoint([subject, object_entity, relationship]), delta16={})

    assert report["valid"] is False
    assert any("valid_until definitely precedes valid_from" in error for error in report["errors"])


def test_canonical_digest_tampering_is_detected(monkeypatch) -> None:
    _bypass_checkpoint_validation(monkeypatch)
    entity = build_entity(entity_id="ORG-1", entity_type="ORGANIZATION", canonical_label="Original")
    entity["canonical_label"] = "Tampered"

    report = validate_gate_a_native_graph(_checkpoint([entity]), delta16={})

    assert report["valid"] is False
    assert any("digest does not match canonical JSON" in error for error in report["errors"])
