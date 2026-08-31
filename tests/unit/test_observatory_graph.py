from __future__ import annotations

import pytest

from neuroai_workbench.entities.schemas import validate_registry_container
from neuroai_workbench.observatory_graph import (
    GRAPH_BOUNDARY,
    KIND_RESOLVED_ENTITY_REFERENCE,
    KIND_UNRESOLVED_LITERAL,
    UnresolvedLiteralError,
    build_assertion,
    build_candidate,
    build_entity,
    build_event,
    build_observation,
    build_relationship,
    build_reopening_decision,
    build_source,
    persistable,
    require_resolved_entity_id,
    validate_graph_object,
)
from neuroai_workbench.temporal import TIME_VALUE_BOUNDARY


def _resolved(entity_id: str) -> dict[str, str]:
    return {"kind": KIND_RESOLVED_ENTITY_REFERENCE, "entity_id": entity_id, "boundary": GRAPH_BOUNDARY}


def _literal(value: str) -> dict[str, str]:
    return {"kind": KIND_UNRESOLVED_LITERAL, "value": value, "boundary": GRAPH_BOUNDARY}


def _date() -> dict[str, str | None]:
    return {"value": "2026-08-31", "precision": "DATE", "boundary": TIME_VALUE_BOUNDARY}


def test_entity_registry_schema_is_present() -> None:
    errors = validate_registry_container(
        {
            "metadata": {
                "title": "t",
                "version": "1",
                "status": "SYNTHETIC_FIXTURE",
                "record_count": 0,
                "boundary": "b",
            },
            "entities": [],
        }
    )
    assert errors == []


def test_graph_objects_round_trip_and_digest_determinism() -> None:
    entity = build_entity(entity_id="ENT-1", entity_type="SYSTEM", canonical_label="Exact System")
    source = build_source(
        source_id="SRC-1",
        source_class="OFFICIAL_TRIAL_REGISTRY",
        title="Study page",
        publisher="ClinicalTrials.gov",
        canonical_url_or_reference="https://clinicaltrials.gov/study/NCT00000001",
        publication_or_record_date=_date(),
    )
    observation = build_observation(
        observation_id="OBS-1",
        source_id="SRC-1",
        observed_at={"value": "2026-08-31T12:00:00Z", "precision": "TIMESTAMP", "boundary": TIME_VALUE_BOUNDARY},
        retrieval_method="HTTP_GET",
        retrieval_outcome="RETRIEVED",
        requested_locator="https://clinicaltrials.gov/study/NCT00000001",
        content_sha256="a" * 64,
    )
    assertion = build_assertion(
        assertion_id="AST-1",
        subject=_resolved("ENT-1"),
        predicate="TRIAL_STATUS",
        value="RECRUITING",
        evidence_state="SOURCE_STATED",
        verification_state="RETRIEVAL_VERIFIED_BYTES_ONLY",
        review_state="NOT_REVIEWED",
        claim_boundary=GRAPH_BOUNDARY,
        valid_from=_date(),
        source_ids=["SRC-1"],
        observation_ids=["OBS-1"],
    )
    again = persistable(assertion)
    assert again["canonical_sha256"] == assertion["canonical_sha256"]
    assert again["valid_from"]["value"] == "2026-08-31"
    event = build_event(
        event_id="EVT-1",
        event_type="TRIAL_STATUS_TRANSITION",
        subject=_resolved("ENT-1"),
        evidence_state="SOURCE_STATED",
        verification_state="UNVERIFIED_SUBSTANTIVELY",
        claim_boundary=GRAPH_BOUNDARY,
        occurred_at=_date(),
    )
    rel = build_relationship(
        relationship_id="REL-1",
        relationship_type="STUDIED_IN",
        subject=_resolved("ENT-1"),
        object_ref=_resolved("ENT-1"),
        evidence_state="SOURCE_STATED",
        claim_boundary=GRAPH_BOUNDARY,
    )
    candidate = build_candidate(
        candidate_id="CAND-1",
        candidate_class="SOURCE_PROPOSAL",
        payload={"nct_id": "NCT00000001"},
        provenance_mode="OFFLINE_FIXTURE",
        identity_key="NCT00000001",
        source_universe_id="SU-TRIAL",
    )
    reopening = build_reopening_decision(
        reopening_decision_id="ROP-1",
        subject=_resolved("ENT-1"),
        decision="NO_REOPENING",
        decided_at={"value": "2026-08-31T12:00:00Z", "precision": "TIMESTAMP", "boundary": TIME_VALUE_BOUNDARY},
    )
    assert entity["object_class"] == "Entity"
    assert source["source_id"] == "SRC-1"
    assert observation["capture_state"]
    assert rel["relationship_type"] == "STUDIED_IN"
    assert candidate["canonical_write_performed"] is False
    assert reopening["assessment_mutated"] is False
    assert event["event_id"] == "EVT-1"


def test_unresolved_literal_rejected_by_resolved_id_api() -> None:
    with pytest.raises(UnresolvedLiteralError):
        require_resolved_entity_id(_literal("Science Corporation"), field="subject")
    with pytest.raises(ValueError, match="UNRESOLVED_LITERAL|resolved"):
        build_assertion(
            assertion_id="AST-BAD",
            subject=_literal("Science Corporation"),
            predicate="DEVELOPED_BY",
            value="claimed",
            evidence_state="SOURCE_STATED",
            verification_state="UNVERIFIED",
            review_state="NOT_REVIEWED",
            claim_boundary=GRAPH_BOUNDARY,
        )


def test_invalid_mixed_provenance_rejected() -> None:
    entity = {
        "object_class": "Source",
        "source_id": "SRC-MIX",
        "source_class": "WEBSITE",
        "title": "t",
        "publisher": "p",
        "canonical_url_or_reference": "https://example.org/x",
        "access_class": "PUBLIC",
        "redistribution_state": "UNKNOWN_NOT_ADJUDICATED",
        "publication_or_record_date": _date(),
        "publication_or_record_date_timestamp": "2026-08-31T00:00:00Z",
        "boundary": GRAPH_BOUNDARY,
    }
    errors = validate_graph_object(entity, "Source")
    assert any(item["code"] == "TEMPORAL_ERROR" for item in errors)


def test_unknown_enum_on_graph_object() -> None:
    errors = validate_graph_object({"object_class": "Entity"}, "Entity")
    assert errors


def test_identifier_kind_cannot_satisfy_resolved_id_api() -> None:
    from neuroai_workbench.observatory_graph import KIND_IDENTIFIER, dump_identity_ref, parse_identity_ref

    identifier = parse_identity_ref(
        {"kind": KIND_IDENTIFIER, "value": "NCT00000001", "scheme": "NCT", "boundary": GRAPH_BOUNDARY}
    )
    dumped = dump_identity_ref(identifier)
    assert dumped["kind"] == KIND_IDENTIFIER
    with pytest.raises(UnresolvedLiteralError):
        require_resolved_entity_id(identifier, field="subject")
