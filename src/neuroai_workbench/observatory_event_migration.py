"""Loss-aware migration for predecessor capital and ownership events.

The v1.4 capital-event family can be materialized when its subject name resolves by
exact canonical label to exactly one already materialized Entity and all source ids are
present in the materialized Source set. Counterparties that lack controlled entity ids
remain UNRESOLVED_LITERAL references. Predecessor event fields without native Event
slots remain in the exact predecessor trace.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from . import __version__
from .observatory_graph import (
    GRAPH_BOUNDARY,
    KIND_RESOLVED_ENTITY_REFERENCE,
    KIND_UNRESOLVED_LITERAL,
    build_event,
    validate_graph_object,
)
from .temporal import TIME_VALUE_BOUNDARY, parse_time_value
from .util import atomic_write_bytes, atomic_write_json, canonical_json_bytes, sha256_bytes

EVENT_MIGRATION_BOUNDARY = (
    "Predecessor capital/ownership event migration. Exact controlled subjects and source ids are preserved; "
    "unresolved counterparties remain literals. MIGRATED_PREDECESSOR_STATE is migration verification metadata, "
    "not a claim that predecessor verification occurred. YEAR/DATE/null event time is preserved without "
    "fabricating precision. Amount, currency, ownership-effect and other fields without native Event slots "
    "remain exact trace state. No substantive truth or release authority is inferred."
)
MIGRATED_PREDECESSOR_VERIFICATION_STATE = "MIGRATED_PREDECESSOR_STATE"
_YEAR_RE = re.compile(r"^\d{4}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ObservatoryEventMigrationError(ValueError):
    """Raised when a predecessor event cannot be materialized without identity or semantic invention."""


def _require_hex(value: Any, *, length: int, field: str) -> str:
    if not isinstance(value, str) or len(value) != length or any(char not in "0123456789abcdef" for char in value):
        raise ObservatoryEventMigrationError(
            f"{field} must be a lowercase {length}-character hexadecimal identity"
        )
    return value


def _record_digest(record: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(record))


def predecessor_event_time_value(value: Any) -> dict[str, Any] | None:
    """Preserve predecessor event time at YEAR/DATE/TIMESTAMP precision or remain absent."""
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ObservatoryEventMigrationError("capital-event date must be a string or null")
    text = value.strip()
    if _YEAR_RE.fullmatch(text):
        precision = "YEAR"
    elif _DATE_RE.fullmatch(text):
        precision = "DATE"
    elif "T" in text:
        precision = "TIMESTAMP"
    else:
        raise ObservatoryEventMigrationError(f"unsupported capital-event temporal literal {value!r}")
    return parse_time_value({"value": text, "precision": precision, "boundary": TIME_VALUE_BOUNDARY})


def _resolved(entity_id: str) -> dict[str, Any]:
    return {
        "kind": KIND_RESOLVED_ENTITY_REFERENCE,
        "entity_id": entity_id,
        "boundary": GRAPH_BOUNDARY,
    }


def _unresolved(value: str) -> dict[str, Any]:
    return {
        "kind": KIND_UNRESOLVED_LITERAL,
        "value": value,
        "boundary": GRAPH_BOUNDARY,
    }


def exact_entity_name_index(entities: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Index exact canonical labels without assuming global name uniqueness."""
    index: dict[str, list[str]] = defaultdict(list)
    for entity in entities:
        if not isinstance(entity, dict):
            raise ObservatoryEventMigrationError("Entity index contains a non-object")
        entity_id = entity.get("entity_id")
        label = entity.get("canonical_label")
        if not isinstance(entity_id, str) or not entity_id or not isinstance(label, str) or not label:
            raise ObservatoryEventMigrationError("Entity index requires non-empty entity_id and canonical_label")
        index[label].append(entity_id)
    return {label: sorted(ids) for label, ids in index.items()}


def resolve_exact_entity_name(name: Any, index: dict[str, list[str]]) -> str:
    """Resolve only an exact unique controlled canonical label."""
    if not isinstance(name, str) or not name.strip():
        raise ObservatoryEventMigrationError("event subject name must be a non-empty string")
    text = name.strip()
    matches = index.get(text, [])
    if not matches:
        raise ObservatoryEventMigrationError(f"event subject {text!r} has no exact materialized Entity match")
    if len(matches) != 1:
        raise ObservatoryEventMigrationError(f"event subject {text!r} is ambiguous across Entity ids {matches}")
    return matches[0]


def verify_capital_event_trace(
    trace: dict[str, Any],
    *,
    expected_event_id: str | None = None,
    expected_subject_entity_id: str | None = None,
) -> list[str]:
    """Verify exact predecessor bytes and native Event/subject trace binding."""
    errors: list[str] = []
    record = trace.get("predecessor_record")
    if not isinstance(record, dict):
        return ["predecessor_record must be an object"]
    if trace.get("predecessor_record_sha256") != _record_digest(record):
        errors.append("predecessor_record_sha256 mismatch")
    if trace.get("role") != "V14" or trace.get("family") != "capital_and_ownership_events":
        errors.append("capital-event migration role/family mismatch")
    if trace.get("native_object_class") != "Event":
        errors.append("capital-event trace must bind native Event")
    if trace.get("native_authority") is not False:
        errors.append("native_authority must remain false")
    if trace.get("boundary") != EVENT_MIGRATION_BOUNDARY:
        errors.append("capital-event migration boundary mismatch")
    if not isinstance(trace.get("record_index"), int) or int(trace["record_index"]) < 0:
        errors.append("record_index must be a non-negative integer")
    if trace.get("native_object_id") != record.get("event_id"):
        errors.append("native Event id must equal predecessor event_id")
    if expected_event_id is not None and trace.get("native_object_id") != expected_event_id:
        errors.append("native event id binding mismatch")
    if expected_subject_entity_id is not None and trace.get("subject_entity_id") != expected_subject_entity_id:
        errors.append("subject Entity binding mismatch")
    expected_generated = {
        "verification_state": MIGRATED_PREDECESSOR_VERIFICATION_STATE,
        "observation_ids": [],
    }
    if trace.get("migration_generated_fields") != expected_generated:
        errors.append("capital-event migration-generated field declaration mismatch")
    return sorted(set(errors))


def verify_materialized_capital_event(
    event: dict[str, Any],
    trace: dict[str, Any],
    *,
    entity_index: dict[str, dict[str, Any]],
    known_source_ids: set[str],
) -> list[str]:
    """Verify every mapped Event field against predecessor state and controlled object bindings."""
    errors: list[str] = []
    event_id = str(event.get("event_id") or "")
    subject = event.get("subject")
    subject_id = str(subject.get("entity_id") or "") if isinstance(subject, dict) else ""
    errors.extend(
        verify_capital_event_trace(
            trace,
            expected_event_id=event_id,
            expected_subject_entity_id=subject_id,
        )
    )
    predecessor = trace.get("predecessor_record")
    if not isinstance(predecessor, dict):
        return sorted(set(errors + ["predecessor_record must be an object"]))

    if event.get("event_type") != predecessor.get("event_type"):
        errors.append("event_type binding mismatch")
    entity = entity_index.get(subject_id)
    if entity is None:
        errors.append(f"resolved subject Entity {subject_id!r} is missing")
    elif entity.get("canonical_label") != predecessor.get("subject"):
        errors.append("subject binding does not preserve exact predecessor canonical label")

    counterparties = predecessor.get("counterparties") or []
    if not isinstance(counterparties, list):
        errors.append("predecessor counterparties must be an array")
        counterparties = []
    expected_objects = [_unresolved(str(value).strip()) for value in counterparties]
    if event.get("objects") != expected_objects:
        errors.append("counterparty unresolved-literal binding mismatch")

    try:
        expected_time = predecessor_event_time_value(predecessor.get("date"))
        if expected_time is None:
            if "occurred_at" in event:
                errors.append("null predecessor date must remain absent in native Event")
        elif event.get("occurred_at") != expected_time:
            errors.append("occurred_at precision/value binding mismatch")
    except (ObservatoryEventMigrationError, ValueError) as exc:
        errors.append(str(exc))

    predecessor_sources = predecessor.get("source_ids")
    if event.get("source_ids") != predecessor_sources:
        errors.append("source_ids binding mismatch")
    if isinstance(predecessor_sources, list):
        missing_sources = sorted(str(item) for item in predecessor_sources if str(item) not in known_source_ids)
        if missing_sources:
            errors.append(f"references missing Sources {missing_sources}")
    else:
        errors.append("predecessor source_ids must be an array")

    if event.get("observation_ids") != []:
        errors.append("migration-generated observation_ids must remain empty")
    if event.get("evidence_state") != predecessor.get("evidence_state"):
        errors.append("evidence_state binding mismatch")
    if event.get("verification_state") != MIGRATED_PREDECESSOR_VERIFICATION_STATE:
        errors.append("migration verification_state mismatch")
    if event.get("claim_boundary") != predecessor.get("boundary"):
        errors.append("claim_boundary binding mismatch")
    if event.get("boundary") != EVENT_MIGRATION_BOUNDARY:
        errors.append("Event migration boundary mismatch")

    schema_errors = validate_graph_object(
        {key: value for key, value in event.items() if key != "canonical_sha256"},
        "Event",
    )
    errors.extend(f"schema: {error}" for error in schema_errors)
    return sorted(set(errors))


def materialize_v14_capital_event(
    record: dict[str, Any],
    *,
    record_index: int,
    entity_name_index: dict[str, list[str]],
    known_source_ids: set[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Materialize one v1.4 capital/ownership event using only exact controlled identity resolution."""
    required_strings = ("event_id", "event_type", "subject", "evidence_state", "boundary")
    missing = [
        field
        for field in required_strings
        if not isinstance(record.get(field), str) or not str(record[field]).strip()
    ]
    if missing:
        raise ObservatoryEventMigrationError(f"capital event missing required predecessor fields: {missing}")
    source_ids = record.get("source_ids")
    if not isinstance(source_ids, list) or any(not isinstance(item, str) or not item for item in source_ids):
        raise ObservatoryEventMigrationError("capital event source_ids must be an array of non-empty strings")
    missing_sources = sorted(set(source_ids) - known_source_ids)
    if missing_sources:
        raise ObservatoryEventMigrationError(f"capital event references non-materialized Sources {missing_sources}")

    subject_entity_id = resolve_exact_entity_name(record["subject"], entity_name_index)
    counterparties = record.get("counterparties") or []
    if not isinstance(counterparties, list) or any(not isinstance(item, str) or not item.strip() for item in counterparties):
        raise ObservatoryEventMigrationError("capital event counterparties must be an array of non-empty strings")
    occurred_at = predecessor_event_time_value(record.get("date"))

    event = build_event(
        event_id=str(record["event_id"]),
        event_type=str(record["event_type"]),
        subject=_resolved(subject_entity_id),
        objects=[_unresolved(item.strip()) for item in counterparties],
        occurred_at=occurred_at,
        source_ids=list(source_ids),
        observation_ids=[],
        evidence_state=str(record["evidence_state"]),
        verification_state=MIGRATED_PREDECESSOR_VERIFICATION_STATE,
        claim_boundary=str(record["boundary"]),
        boundary=EVENT_MIGRATION_BOUNDARY,
    )
    trace = {
        "role": "V14",
        "family": "capital_and_ownership_events",
        "record_index": record_index,
        "native_object_class": "Event",
        "native_object_id": str(event["event_id"]),
        "subject_entity_id": subject_entity_id,
        "predecessor_record_sha256": _record_digest(record),
        "predecessor_record": record,
        "migration_generated_fields": {
            "verification_state": MIGRATED_PREDECESSOR_VERIFICATION_STATE,
            "observation_ids": [],
        },
        "native_authority": False,
        "boundary": EVENT_MIGRATION_BOUNDARY,
    }
    entity_index = {
        subject_entity_id: {
            "entity_id": subject_entity_id,
            "canonical_label": str(record["subject"]),
        }
    }
    verification_errors = verify_materialized_capital_event(
        event,
        trace,
        entity_index=entity_index,
        known_source_ids=known_source_ids,
    )
    if verification_errors:
        raise ObservatoryEventMigrationError(
            f"generated capital Event/trace is invalid: {verification_errors}"
        )
    return event, trace


def materialize_v14_capital_events(
    v14_release: dict[str, Any],
    *,
    entities: list[dict[str, Any]],
    known_source_ids: set[str],
) -> dict[str, Any]:
    """Materialize the complete v1.4 capital/ownership-event family or fail closed."""
    records = v14_release.get("capital_and_ownership_events")
    if not isinstance(records, list):
        raise ObservatoryEventMigrationError("Expected v1.4 capital_and_ownership_events array")
    name_index = exact_entity_name_index(entities)
    entity_index = {str(entity["entity_id"]): entity for entity in entities}

    events: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(records):
        if not isinstance(raw, dict):
            raise ObservatoryEventMigrationError(f"v1.4 capital event {index} must be an object")
        event, trace = materialize_v14_capital_event(
            raw,
            record_index=index,
            entity_name_index=name_index,
            known_source_ids=known_source_ids,
        )
        event_id = str(event["event_id"])
        if event_id in seen_ids:
            raise ObservatoryEventMigrationError(f"duplicate predecessor capital event id {event_id}")
        seen_ids.add(event_id)
        verification_errors = verify_materialized_capital_event(
            event,
            trace,
            entity_index=entity_index,
            known_source_ids=known_source_ids,
        )
        if verification_errors:
            raise ObservatoryEventMigrationError(
                f"capital Event {event_id} fails composed verification: {verification_errors}"
            )
        events.append(event)
        traces.append(trace)

    return {
        "state": "NONCANONICAL_CANDIDATE",
        "release_authorized": False,
        "object_class": "Event",
        "input_record_count": len(records),
        "object_count": len(events),
        "predecessor_trace_count": len(traces),
        "events": events,
        "predecessor_traces": traces,
        "migration_generated_metadata": {
            "verification_state": MIGRATED_PREDECESSOR_VERIFICATION_STATE,
            "observation_ids": [],
            "counterparty_identity": "UNRESOLVED_LITERAL_UNLESS_SEPARATELY_RESOLVED",
            "temporal_precision": "PRESERVE_YEAR_DATE_TIMESTAMP_OR_ABSENT",
            "boundary": EVENT_MIGRATION_BOUNDARY,
        },
        "boundary": EVENT_MIGRATION_BOUNDARY,
    }


def _jsonl_bytes(records: list[dict[str, Any]]) -> bytes:
    lines = [json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for record in records]
    return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")


def write_capital_event_migration_package(
    result: dict[str, Any],
    output_dir: Path,
    *,
    entities: list[dict[str, Any]],
    known_source_ids: set[str],
    v14_input_sha256: str,
    producer_commit: str,
    runtime_execution_pin: str,
    s2_predecessor_commit: str,
    observatory_graph_schema_version: str = "1",
) -> dict[str, Any]:
    """Write a deterministic noncanonical package for the complete v1.4 capital-event family."""
    if result.get("state") != "NONCANONICAL_CANDIDATE" or result.get("release_authorized") is not False:
        raise ObservatoryEventMigrationError("capital-event migration package must remain noncanonical")
    events = result.get("events")
    traces = result.get("predecessor_traces")
    if not isinstance(events, list) or not isinstance(traces, list) or len(events) != len(traces):
        raise ObservatoryEventMigrationError("capital-event package requires one trace per Event")
    if result.get("input_record_count") != len(events):
        raise ObservatoryEventMigrationError("capital-event package requires complete family materialization")
    entity_index = {str(entity["entity_id"]): entity for entity in entities}
    for event, trace in zip(events, traces, strict=True):
        if not isinstance(event, dict) or not isinstance(trace, dict):
            raise ObservatoryEventMigrationError("capital-event package entries must be objects")
        errors = verify_materialized_capital_event(
            event,
            trace,
            entity_index=entity_index,
            known_source_ids=known_source_ids,
        )
        if errors:
            raise ObservatoryEventMigrationError(f"capital-event verification failed: {errors}")

    input_v14 = _require_hex(v14_input_sha256, length=64, field="v14_input_sha256")
    producer = _require_hex(producer_commit, length=40, field="producer_commit")
    runtime_pin = _require_hex(runtime_execution_pin, length=40, field="runtime_execution_pin")
    s2_commit = _require_hex(s2_predecessor_commit, length=40, field="s2_predecessor_commit")
    if not isinstance(observatory_graph_schema_version, str) or not observatory_graph_schema_version.strip():
        raise ObservatoryEventMigrationError("observatory_graph_schema_version must be non-empty")

    output_dir.mkdir(parents=True, exist_ok=True)
    event_bytes = _jsonl_bytes(events)
    trace_bytes = _jsonl_bytes(traces)
    atomic_write_bytes(output_dir / "events.jsonl", event_bytes)
    atomic_write_bytes(output_dir / "predecessor-traces.jsonl", trace_bytes)
    file_digests = {
        "events.jsonl": sha256_bytes(event_bytes),
        "predecessor-traces.jsonl": sha256_bytes(trace_bytes),
    }
    descriptor = {
        "schema_version": "1",
        "package_type": "OBSERVATORY_V2_PREDECESSOR_CAPITAL_EVENT_MIGRATION",
        "state": "NONCANONICAL_CANDIDATE",
        "release_authorized": False,
        "object_count": len(events),
        "workbench_compatibility_version": __version__,
        "producer_workbench_commit": producer,
        "runtime_execution_pin": runtime_pin,
        "observatory_graph_schema_version": observatory_graph_schema_version,
        "s2_predecessor_commit": s2_commit,
        "inputs": {"V14": input_v14},
        "migration_generated_metadata": result.get("migration_generated_metadata"),
        "boundary": EVENT_MIGRATION_BOUNDARY,
    }
    manifest = {
        "files": [{"path": path, "sha256": digest} for path, digest in sorted(file_digests.items())],
        "descriptor_sha256": sha256_bytes(canonical_json_bytes(descriptor)),
        "release_authorized": False,
        "boundary": EVENT_MIGRATION_BOUNDARY,
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    atomic_write_json(output_dir / "descriptor.json", descriptor)
    atomic_write_json(output_dir / "manifest.json", manifest)
    return {"descriptor": descriptor, "manifest": manifest}
