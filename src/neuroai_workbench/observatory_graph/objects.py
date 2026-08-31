from __future__ import annotations

from typing import Any

from .digest import attach_digest, object_digest
from .identity import GRAPH_BOUNDARY, dump_identity_ref, require_resolved_entity_id
from .schemas import validate_or_raise

OBJECT_CLASSES = (
    "Entity",
    "Source",
    "Observation",
    "Assertion",
    "Event",
    "Relationship",
    "Candidate",
    "ReopeningDecision",
)


def _base(*, object_class: str, object_id: str, extra: dict[str, Any]) -> dict[str, Any]:
    record = {
        "object_class": object_class,
        **extra,
        "boundary": extra.get("boundary") or GRAPH_BOUNDARY,
    }
    if object_class == "Entity":
        record["entity_id"] = object_id
    elif object_class == "Source":
        record["source_id"] = object_id
    elif object_class == "Observation":
        record["observation_id"] = object_id
    elif object_class == "Assertion":
        record["assertion_id"] = object_id
    elif object_class == "Event":
        record["event_id"] = object_id
    elif object_class == "Relationship":
        record["relationship_id"] = object_id
    elif object_class == "Candidate":
        record["candidate_id"] = object_id
    elif object_class == "ReopeningDecision":
        record["reopening_decision_id"] = object_id
    validate_or_raise(record, object_class)
    return attach_digest(record)


def build_entity(
    *,
    entity_id: str,
    entity_type: str,
    canonical_label: str,
    status: str = "ACTIVE",
    aliases: list[str] | None = None,
    identifiers: list[dict[str, Any]] | None = None,
    lineage: dict[str, Any] | None = None,
    boundary: str | None = None,
) -> dict[str, Any]:
    return _base(
        object_class="Entity",
        object_id=entity_id,
        extra={
            "entity_type": entity_type,
            "canonical_label": canonical_label,
            "aliases": list(aliases or []),
            "identifiers": list(identifiers or []),
            "status": status,
            "lineage": lineage
            or {"predecessor_entity_ids": [], "successor_entity_ids": [], "supersession_state": "NONE"},
            "boundary": boundary or GRAPH_BOUNDARY,
        },
    )


def build_source(
    *,
    source_id: str,
    source_class: str,
    title: str,
    publisher: str,
    canonical_url_or_reference: str,
    access_class: str = "PUBLIC",
    redistribution_state: str = "UNKNOWN_NOT_ADJUDICATED",
    jurisdiction: str | None = None,
    language: str | None = None,
    publication_or_record_date: dict[str, Any] | None = None,
    boundary: str | None = None,
) -> dict[str, Any]:
    extra: dict[str, Any] = {
        "source_class": source_class,
        "title": title,
        "publisher": publisher,
        "canonical_url_or_reference": canonical_url_or_reference,
        "access_class": access_class,
        "redistribution_state": redistribution_state,
        "jurisdiction": jurisdiction,
        "language": language,
        "boundary": boundary or GRAPH_BOUNDARY,
    }
    if publication_or_record_date is not None:
        extra["publication_or_record_date"] = publication_or_record_date
    return _base(object_class="Source", object_id=source_id, extra=extra)


def build_observation(
    *,
    observation_id: str,
    source_id: str,
    observed_at: dict[str, Any],
    retrieval_method: str,
    retrieval_outcome: str,
    requested_locator: str,
    capture_state: str = "QUARANTINE_OR_EXTERNAL",
    resolved_locator: str | None = None,
    content_type: str | None = None,
    content_sha256: str | None = None,
    capture_reference: str | None = None,
    collector_or_operator_version: str | None = None,
    boundary: str | None = None,
) -> dict[str, Any]:
    extra: dict[str, Any] = {
        "source_id": source_id,
        "observed_at": observed_at,
        "retrieval_method": retrieval_method,
        "retrieval_outcome": retrieval_outcome,
        "requested_locator": requested_locator,
        "resolved_locator": resolved_locator,
        "content_type": content_type,
        "content_sha256": content_sha256,
        "normalized_content_sha256": None,
        "capture_state": capture_state,
        "capture_reference": capture_reference,
        "collector_or_operator_version": collector_or_operator_version,
        "boundary": boundary or GRAPH_BOUNDARY,
    }
    return _base(object_class="Observation", object_id=observation_id, extra=extra)


def build_assertion(
    *,
    assertion_id: str,
    subject: dict[str, Any],
    predicate: str,
    evidence_state: str,
    verification_state: str,
    review_state: str,
    claim_boundary: str,
    object_ref: dict[str, Any] | None = None,
    value: Any = None,
    scope: str | None = None,
    jurisdiction: str | None = None,
    valid_from: dict[str, Any] | None = None,
    valid_until: dict[str, Any] | None = None,
    observed_at: dict[str, Any] | None = None,
    source_ids: list[str] | None = None,
    observation_ids: list[str] | None = None,
    prohibited_inferences: list[str] | None = None,
    supersedes_assertion_ids: list[str] | None = None,
    boundary: str | None = None,
) -> dict[str, Any]:
    require_resolved_entity_id(subject, field="subject")
    if object_ref is None and value is None:
        raise ValueError("Assertion requires object_ref or value")
    extra: dict[str, Any] = {
        "subject": dump_identity_ref(subject),
        "predicate": predicate,
        "object_ref": dump_identity_ref(object_ref) if object_ref is not None else None,
        "value": value,
        "scope": scope,
        "jurisdiction": jurisdiction,
        "source_ids": list(source_ids or []),
        "observation_ids": list(observation_ids or []),
        "evidence_state": evidence_state,
        "verification_state": verification_state,
        "review_state": review_state,
        "claim_boundary": claim_boundary,
        "prohibited_inferences": list(prohibited_inferences or []),
        "supersedes_assertion_ids": list(supersedes_assertion_ids or []),
        "boundary": boundary or GRAPH_BOUNDARY,
    }
    if valid_from is not None:
        extra["valid_from"] = valid_from
    if valid_until is not None:
        extra["valid_until"] = valid_until
    if observed_at is not None:
        extra["observed_at"] = observed_at
    return _base(object_class="Assertion", object_id=assertion_id, extra=extra)


def build_event(
    *,
    event_id: str,
    event_type: str,
    subject: dict[str, Any],
    evidence_state: str,
    verification_state: str,
    claim_boundary: str,
    occurred_at: dict[str, Any] | None = None,
    objects: list[dict[str, Any]] | None = None,
    jurisdiction: str | None = None,
    source_ids: list[str] | None = None,
    observation_ids: list[str] | None = None,
    boundary: str | None = None,
) -> dict[str, Any]:
    require_resolved_entity_id(subject, field="subject")
    extra: dict[str, Any] = {
        "event_type": event_type,
        "subject": dump_identity_ref(subject),
        "objects": [dump_identity_ref(item) for item in (objects or [])],
        "jurisdiction": jurisdiction,
        "source_ids": list(source_ids or []),
        "observation_ids": list(observation_ids or []),
        "evidence_state": evidence_state,
        "verification_state": verification_state,
        "claim_boundary": claim_boundary,
        "boundary": boundary or GRAPH_BOUNDARY,
    }
    if occurred_at is not None:
        extra["occurred_at"] = occurred_at
    return _base(object_class="Event", object_id=event_id, extra=extra)


def build_relationship(
    *,
    relationship_id: str,
    relationship_type: str,
    subject: dict[str, Any],
    object_ref: dict[str, Any],
    evidence_state: str,
    claim_boundary: str,
    valid_from: dict[str, Any] | None = None,
    valid_until: dict[str, Any] | None = None,
    source_ids: list[str] | None = None,
    observation_ids: list[str] | None = None,
    boundary: str | None = None,
) -> dict[str, Any]:
    require_resolved_entity_id(subject, field="subject")
    require_resolved_entity_id(object_ref, field="object_ref")
    extra: dict[str, Any] = {
        "relationship_type": relationship_type,
        "subject": dump_identity_ref(subject),
        "object_ref": dump_identity_ref(object_ref),
        "source_ids": list(source_ids or []),
        "observation_ids": list(observation_ids or []),
        "evidence_state": evidence_state,
        "claim_boundary": claim_boundary,
        "boundary": boundary or GRAPH_BOUNDARY,
    }
    if valid_from is not None:
        extra["valid_from"] = valid_from
    if valid_until is not None:
        extra["valid_until"] = valid_until
    return _base(object_class="Relationship", object_id=relationship_id, extra=extra)


def build_candidate(
    *,
    candidate_id: str,
    candidate_class: str,
    payload: dict[str, Any],
    provenance_mode: str,
    status: str = "PENDING_HUMAN_REVIEW",
    identity_key: str | None = None,
    source_universe_id: str | None = None,
    boundary: str | None = None,
) -> dict[str, Any]:
    extra = {
        "candidate_class": candidate_class,
        "payload": payload,
        "provenance_mode": provenance_mode,
        "status": status,
        "identity_key": identity_key,
        "source_universe_id": source_universe_id,
        "canonical_write_performed": False,
        "boundary": boundary or GRAPH_BOUNDARY,
    }
    return _base(object_class="Candidate", object_id=candidate_id, extra=extra)


def build_reopening_decision(
    *,
    reopening_decision_id: str,
    subject: dict[str, Any],
    decision: str,
    decided_at: dict[str, Any],
    trigger_assertion_ids: list[str] | None = None,
    trigger_event_ids: list[str] | None = None,
    required_actions: list[str] | None = None,
    provenance: str | None = None,
    boundary: str | None = None,
) -> dict[str, Any]:
    require_resolved_entity_id(subject, field="subject")
    extra = {
        "subject": dump_identity_ref(subject),
        "decision": decision,
        "decided_at": decided_at,
        "trigger_assertion_ids": list(trigger_assertion_ids or []),
        "trigger_event_ids": list(trigger_event_ids or []),
        "required_actions": list(required_actions or []),
        "provenance": provenance or "WORKBENCH_REOPENING_RECOMMENDATION",
        "assessment_mutated": False,
        "boundary": boundary or GRAPH_BOUNDARY,
    }
    return _base(object_class="ReopeningDecision", object_id=reopening_decision_id, extra=extra)


def persistable(record: dict[str, Any]) -> dict[str, Any]:
    """Return the schema-validated dict used for persistence. Digests are recomputed."""
    object_class = str(record.get("object_class"))
    body = {key: value for key, value in record.items() if key != "canonical_sha256"}
    validate_or_raise(body, object_class)
    persisted = attach_digest(body)
    if object_digest(persisted) != persisted["canonical_sha256"]:
        raise ValueError("Digest recomputation failed")
    return persisted
