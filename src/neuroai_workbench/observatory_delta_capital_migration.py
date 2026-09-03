"""Native migration for adjudicated v1.6 capital/ownership delta events.

These records have stable event ids, exact dates, exact controlled organization subjects,
source references, event types and explicit claim boundaries. They do not carry native
Event evidence_state or verification_state fields, so migration uses explicit sentinel
states that preserve that absence instead of inventing substantive verification.
"""

from __future__ import annotations

from typing import Any

from .observatory_event_migration import (
    ObservatoryEventMigrationError,
    exact_entity_name_index,
    resolve_exact_entity_name,
)
from .observatory_graph import GRAPH_BOUNDARY, KIND_RESOLVED_ENTITY_REFERENCE, build_event, validate_graph_object
from .temporal import TIME_VALUE_BOUNDARY, parse_time_value
from .util import canonical_json_bytes, sha256_bytes

DELTA_CAPITAL_BOUNDARY = (
    "Adjudicated v1.6 capital-event migration. Exact ids, dates, event types, controlled organization subjects, "
    "source references and predecessor claim boundaries are preserved. Evidence/verification sentinel states "
    "mean the predecessor did not govern those native fields; they are not substantive evidence judgments. "
    "No valuation, control, authorization, performance, conformance or publication authority is inferred."
)
PREDECESSOR_EVIDENCE_STATE_UNSPECIFIED = "PREDECESSOR_EVIDENCE_STATE_UNSPECIFIED"
PREDECESSOR_VERIFICATION_STATE_UNSPECIFIED = "PREDECESSOR_VERIFICATION_STATE_UNSPECIFIED"


class DeltaCapitalMigrationError(ValueError):
    """Raised when a v1.6 capital delta cannot be migrated without invention."""


def _record_digest(record: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(record))


def _resolved(entity_id: str) -> dict[str, Any]:
    return {
        "kind": KIND_RESOLVED_ENTITY_REFERENCE,
        "entity_id": entity_id,
        "boundary": GRAPH_BOUNDARY,
    }


def _date(value: Any) -> dict[str, Any]:
    if not isinstance(value, str) or not value.strip():
        raise DeltaCapitalMigrationError("v1.6 capital event requires an explicit date")
    text = value.strip()
    return parse_time_value({"value": text, "precision": "DATE", "boundary": TIME_VALUE_BOUNDARY})


def verify_delta_capital_event(
    event: dict[str, Any],
    trace: dict[str, Any],
    *,
    entity_index: dict[str, dict[str, Any]],
    known_source_ids: set[str],
) -> list[str]:
    """Verify every mapped Event field against the exact adjudicated predecessor record."""
    errors: list[str] = []
    predecessor = trace.get("predecessor_record")
    if not isinstance(predecessor, dict):
        return ["predecessor_record must be an object"]
    if trace.get("predecessor_record_sha256") != _record_digest(predecessor):
        errors.append("predecessor_record_sha256 mismatch")
    if trace.get("role") != "DELTA16" or trace.get("family") != "capital_and_ownership_events":
        errors.append("delta-capital migration role/family mismatch")
    if trace.get("native_object_class") != "Event" or trace.get("native_authority") is not False:
        errors.append("delta-capital trace authority/class mismatch")
    if trace.get("boundary") != DELTA_CAPITAL_BOUNDARY:
        errors.append("delta-capital trace boundary mismatch")

    event_id = predecessor.get("event_id")
    if event.get("event_id") != event_id or trace.get("native_object_id") != event_id:
        errors.append("event_id binding mismatch")
    if event.get("event_type") != predecessor.get("event_type"):
        errors.append("event_type binding mismatch")
    if event.get("source_ids") != predecessor.get("source_ids"):
        errors.append("source_ids binding mismatch")
    source_ids = predecessor.get("source_ids")
    if not isinstance(source_ids, list) or any(not isinstance(item, str) or not item for item in source_ids):
        errors.append("predecessor source_ids must be non-empty strings")
    else:
        missing = sorted(set(source_ids) - known_source_ids)
        if missing:
            errors.append(f"delta-capital event references missing Sources {missing}")
    if event.get("claim_boundary") != predecessor.get("boundary"):
        errors.append("claim_boundary binding mismatch")
    if event.get("evidence_state") != PREDECESSOR_EVIDENCE_STATE_UNSPECIFIED:
        errors.append("evidence_state sentinel mismatch")
    if event.get("verification_state") != PREDECESSOR_VERIFICATION_STATE_UNSPECIFIED:
        errors.append("verification_state sentinel mismatch")
    if event.get("observation_ids") != [] or event.get("objects") != []:
        errors.append("delta-capital migration must not invent observations or counterparties")
    if event.get("boundary") != DELTA_CAPITAL_BOUNDARY:
        errors.append("Event migration boundary mismatch")

    subject_name = predecessor.get("subject")
    subject = event.get("subject")
    subject_id = subject.get("entity_id") if isinstance(subject, dict) else None
    entity = entity_index.get(str(subject_id)) if isinstance(subject_id, str) else None
    if not isinstance(subject_name, str) or not subject_name.strip():
        errors.append("predecessor subject is missing")
    elif entity is None or entity.get("canonical_label") != subject_name.strip():
        errors.append("subject exact-label Entity binding mismatch")
    if trace.get("subject_entity_id") != subject_id:
        errors.append("trace subject Entity binding mismatch")

    raw_date = predecessor.get("date")
    occurred = event.get("occurred_at")
    if not isinstance(raw_date, str) or not raw_date.strip():
        errors.append("predecessor date is missing")
    elif (
        not isinstance(occurred, dict)
        or occurred.get("precision") != "DATE"
        or occurred.get("value") != raw_date.strip()
    ):
        errors.append("occurred_at date binding mismatch")

    schema_errors = validate_graph_object(
        {key: value for key, value in event.items() if key != "canonical_sha256"},
        "Event",
    )
    errors.extend(f"schema: {error}" for error in schema_errors)
    return sorted(set(errors))


def materialize_delta16_capital_events(
    delta16: dict[str, Any],
    *,
    entities: list[dict[str, Any]],
    known_source_ids: set[str],
) -> dict[str, Any]:
    """Materialize the complete adjudicated v1.6 capital-event delta or fail closed."""
    records = delta16.get("capital_and_ownership_events")
    if not isinstance(records, list):
        raise DeltaCapitalMigrationError("Expected delta16 capital_and_ownership_events array")
    try:
        name_index = exact_entity_name_index(entities)
    except ObservatoryEventMigrationError as exc:
        raise DeltaCapitalMigrationError(str(exc)) from exc
    entity_index = {str(entity["entity_id"]): entity for entity in entities}
    events: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    seen: set[str] = set()

    for index, raw in enumerate(records):
        if not isinstance(raw, dict):
            raise DeltaCapitalMigrationError(f"delta16 capital event {index} must be an object")
        required = ("event_id", "event_type", "subject", "boundary")
        missing = [field for field in required if not isinstance(raw.get(field), str) or not str(raw[field]).strip()]
        if missing:
            raise DeltaCapitalMigrationError(f"delta16 capital event missing required fields: {missing}")
        refs = raw.get("source_ids")
        if not isinstance(refs, list) or any(not isinstance(item, str) or not item for item in refs):
            raise DeltaCapitalMigrationError("delta16 capital event source_ids are invalid")
        missing_sources = sorted(set(refs) - known_source_ids)
        if missing_sources:
            raise DeltaCapitalMigrationError(f"delta16 capital event references missing Sources {missing_sources}")
        try:
            subject_id = resolve_exact_entity_name(raw["subject"], name_index)
        except ObservatoryEventMigrationError as exc:
            raise DeltaCapitalMigrationError(str(exc)) from exc
        event_id = str(raw["event_id"])
        if event_id in seen:
            raise DeltaCapitalMigrationError(f"duplicate delta16 capital event id {event_id}")
        seen.add(event_id)
        event = build_event(
            event_id=event_id,
            event_type=str(raw["event_type"]),
            subject=_resolved(subject_id),
            objects=[],
            occurred_at=_date(raw.get("date")),
            source_ids=list(refs),
            observation_ids=[],
            evidence_state=PREDECESSOR_EVIDENCE_STATE_UNSPECIFIED,
            verification_state=PREDECESSOR_VERIFICATION_STATE_UNSPECIFIED,
            claim_boundary=str(raw["boundary"]),
            boundary=DELTA_CAPITAL_BOUNDARY,
        )
        trace = {
            "role": "DELTA16",
            "family": "capital_and_ownership_events",
            "record_index": index,
            "native_object_class": "Event",
            "native_object_id": event_id,
            "subject_entity_id": subject_id,
            "predecessor_record_sha256": _record_digest(raw),
            "predecessor_record": raw,
            "migration_generated_fields": {
                "evidence_state": PREDECESSOR_EVIDENCE_STATE_UNSPECIFIED,
                "verification_state": PREDECESSOR_VERIFICATION_STATE_UNSPECIFIED,
                "observation_ids": [],
                "objects": [],
            },
            "native_authority": False,
            "boundary": DELTA_CAPITAL_BOUNDARY,
        }
        errors = verify_delta_capital_event(
            event,
            trace,
            entity_index=entity_index,
            known_source_ids=known_source_ids,
        )
        if errors:
            raise DeltaCapitalMigrationError(f"generated delta-capital Event is invalid: {errors}")
        events.append(event)
        traces.append(trace)

    return {
        "state": "NONCANONICAL_CANDIDATE",
        "release_authorized": False,
        "input_record_count": len(records),
        "object_count": len(events),
        "predecessor_trace_count": len(traces),
        "events": events,
        "predecessor_traces": traces,
        "migration_generated_metadata": {
            "evidence_state": PREDECESSOR_EVIDENCE_STATE_UNSPECIFIED,
            "verification_state": PREDECESSOR_VERIFICATION_STATE_UNSPECIFIED,
            "observation_ids": [],
            "objects": [],
            "boundary": DELTA_CAPITAL_BOUNDARY,
        },
        "boundary": DELTA_CAPITAL_BOUNDARY,
    }
