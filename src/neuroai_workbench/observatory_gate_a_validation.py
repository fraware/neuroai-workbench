"""Candidate-wide typed referential and temporal validation for Gate-A migration."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .observatory_gate_a_migration import verify_gate_a_migration_checkpoint
from .observatory_graph import parse_identity_ref, validate_graph_object
from .observatory_graph.digest import assert_digest
from .temporal import parse_time_value

ID_FIELDS = {
    "Entity": "entity_id",
    "Source": "source_id",
    "Observation": "observation_id",
    "Assertion": "assertion_id",
    "Relationship": "relationship_id",
    "Event": "event_id",
    "Candidate": "candidate_id",
    "ReopeningDecision": "reopening_decision_id",
}
TIME_FIELDS = {
    "publication_or_record_date",
    "observed_at",
    "occurred_at",
    "valid_from",
    "valid_until",
    "decided_at",
}


class ObservatoryGateAValidationError(ValueError):
    """Raised when typed candidate validation cannot be performed."""


def _resolved_entity_id(ref: Any) -> str | None:
    parsed = parse_identity_ref(ref)
    if parsed["kind"] == "RESOLVED_ENTITY_REFERENCE":
        entity_id = parsed.get("entity_id")
        return str(entity_id) if isinstance(entity_id, str) else None
    return None


def _time_bounds(value: dict[str, Any]) -> tuple[datetime, datetime] | None:
    parsed = parse_time_value(value)
    precision = parsed["precision"]
    raw = parsed["value"]
    if precision == "UNKNOWN":
        return None
    if not isinstance(raw, str):
        return None
    if precision == "YEAR":
        year = int(raw)
        return (
            datetime(year, 1, 1, tzinfo=timezone.utc),
            datetime(year, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc),
        )
    if precision == "DATE":
        day = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return (day, day.replace(hour=23, minute=59, second=59, microsecond=999999))
    text = raw.replace("Z", "+00:00")
    instant = datetime.fromisoformat(text)
    return (instant, instant)


def validate_gate_a_native_graph(
    checkpoint: dict[str, Any],
    *,
    delta16: dict[str, Any],
) -> dict[str, Any]:
    """Validate native candidate objects using class-qualified references and precision-safe time semantics."""
    gate_report = verify_gate_a_migration_checkpoint(checkpoint, delta16=delta16)
    errors = [f"checkpoint: {error}" for error in gate_report["errors"]]
    candidate = checkpoint.get("candidate")
    if not isinstance(candidate, dict):
        return {"valid": False, "errors": errors + ["candidate is missing"]}
    objects = candidate.get("native_objects")
    if not isinstance(objects, list):
        return {"valid": False, "errors": errors + ["candidate native_objects must be an array"]}

    ids_by_class: dict[str, set[str]] = {name: set() for name in ID_FIELDS}
    id_classes: dict[str, set[str]] = {}
    class_counts: dict[str, int] = {}
    for index, record in enumerate(objects):
        if not isinstance(record, dict):
            errors.append(f"native object {index} must be an object")
            continue
        object_class = record.get("object_class")
        if object_class not in ID_FIELDS:
            errors.append(f"native object {index} has unsupported class {object_class!r}")
            continue
        id_field = ID_FIELDS[object_class]
        object_id = record.get(id_field)
        if not isinstance(object_id, str) or not object_id:
            errors.append(f"{object_class} object {index} lacks {id_field}")
            continue
        if object_id in ids_by_class[object_class]:
            errors.append(f"duplicate typed identity {object_class}:{object_id}")
        ids_by_class[object_class].add(object_id)
        id_classes.setdefault(object_id, set()).add(object_class)
        class_counts[object_class] = class_counts.get(object_class, 0) + 1

    cross_class_collisions = {
        object_id: sorted(classes) for object_id, classes in sorted(id_classes.items()) if len(classes) > 1
    }
    typed_reference_checks = 0
    temporal_values_checked = 0

    def require_ids(owner: str, values: Any, target_class: str, field: str) -> None:
        nonlocal typed_reference_checks
        if not isinstance(values, list):
            errors.append(f"{owner}.{field} must be an array")
            return
        for value in values:
            typed_reference_checks += 1
            if not isinstance(value, str) or value not in ids_by_class[target_class]:
                errors.append(f"{owner}.{field} references missing {target_class} {value!r}")

    def check_ref(owner: str, ref: Any, field: str) -> None:
        nonlocal typed_reference_checks
        typed_reference_checks += 1
        try:
            entity_id = _resolved_entity_id(ref)
        except Exception as exc:
            errors.append(f"{owner}.{field} malformed identity reference: {exc}")
            return
        if entity_id is not None and entity_id not in ids_by_class["Entity"]:
            errors.append(f"{owner}.{field} references missing Entity {entity_id!r}")

    for record in objects:
        if not isinstance(record, dict):
            continue
        object_class = record.get("object_class")
        if object_class not in ID_FIELDS:
            continue
        object_id = str(record.get(ID_FIELDS[object_class]) or "")
        owner = f"{object_class}:{object_id}"
        schema_errors = validate_graph_object(
            {key: value for key, value in record.items() if key != "canonical_sha256"},
            object_class,
        )
        errors.extend(f"{owner}: {error}" for error in schema_errors)
        try:
            assert_digest(record)
        except ValueError as exc:
            errors.append(f"{owner}: {exc}")

        for field in TIME_FIELDS:
            if field in record:
                temporal_values_checked += 1
                try:
                    parse_time_value(record[field])
                except Exception as exc:
                    errors.append(f"{owner}.{field}: {exc}")

        if object_class == "Entity":
            lineage = record.get("lineage")
            if isinstance(lineage, dict):
                require_ids(owner, lineage.get("predecessor_entity_ids"), "Entity", "lineage.predecessor_entity_ids")
                require_ids(owner, lineage.get("successor_entity_ids"), "Entity", "lineage.successor_entity_ids")
        elif object_class == "Observation":
            source_id = record.get("source_id")
            typed_reference_checks += 1
            if source_id not in ids_by_class["Source"]:
                errors.append(f"{owner}.source_id references missing Source {source_id!r}")
        elif object_class in {"Event", "Relationship", "Assertion"}:
            require_ids(owner, record.get("source_ids"), "Source", "source_ids")
            require_ids(owner, record.get("observation_ids"), "Observation", "observation_ids")
            check_ref(owner, record.get("subject"), "subject")
            if object_class == "Event":
                values = record.get("objects")
                if not isinstance(values, list):
                    errors.append(f"{owner}.objects must be an array")
                else:
                    for index, ref in enumerate(values):
                        check_ref(owner, ref, f"objects[{index}]")
            elif object_class == "Relationship":
                check_ref(owner, record.get("object_ref"), "object_ref")
            else:
                if record.get("object_ref") is not None:
                    check_ref(owner, record.get("object_ref"), "object_ref")
                require_ids(owner, record.get("supersedes_assertion_ids"), "Assertion", "supersedes_assertion_ids")
        elif object_class == "ReopeningDecision":
            check_ref(owner, record.get("subject"), "subject")
            require_ids(owner, record.get("trigger_assertion_ids"), "Assertion", "trigger_assertion_ids")
            require_ids(owner, record.get("trigger_event_ids"), "Event", "trigger_event_ids")
        elif object_class == "Candidate":
            payload = record.get("payload")
            if isinstance(payload, dict) and "source_ids" in payload:
                require_ids(owner, payload.get("source_ids"), "Source", "payload.source_ids")

        if "valid_from" in record and "valid_until" in record:
            try:
                start = _time_bounds(record["valid_from"])
                end = _time_bounds(record["valid_until"])
            except Exception as exc:
                errors.append(f"{owner}: temporal interval cannot be parsed: {exc}")
            else:
                if start is not None and end is not None and end[1] < start[0]:
                    errors.append(f"{owner}: valid_until definitely precedes valid_from")

    return {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "object_count": len(objects),
        "class_counts": dict(sorted(class_counts.items())),
        "typed_reference_checks": typed_reference_checks,
        "temporal_values_checked": temporal_values_checked,
        "cross_class_id_collisions": cross_class_collisions,
        "typed_reference_semantics": "CLASS_QUALIFIED",
        "temporal_semantics": "PRECISION_PRESERVING_INTERVAL_BOUNDS",
    }
