"""Temporal graph compiler: referential/temporal integrity and release projections.

Derived loaders and website/database projections are never authority. Canonical state
lives in release artifacts produced by the candidate release compiler.
"""

from __future__ import annotations

from typing import Any

from ..temporal.time_value import TemporalValueError, parse_time_value
from .digest import object_digest
from .objects import OBJECT_CLASSES, persistable
from .schemas import validate_graph_object

COMPILER_BOUNDARY = (
    "The temporal graph compiler validates and projects observatory-graph objects for a "
    "candidate release. It does not authorize publication, mutate assessments, or grant "
    "authority to derived databases or search indexes."
)

ID_FIELDS = {
    "Entity": "entity_id",
    "Source": "source_id",
    "Observation": "observation_id",
    "Assertion": "assertion_id",
    "Event": "event_id",
    "Relationship": "relationship_id",
    "Candidate": "candidate_id",
    "ReopeningDecision": "reopening_decision_id",
}


def _index(objects: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for record in objects:
        object_class = str(record.get("object_class"))
        field = ID_FIELDS.get(object_class)
        if not field:
            continue
        object_id = str(record.get(field, ""))
        if object_id:
            index[object_id] = record
    return index


def _time_order_key(value: Any) -> tuple[str, str]:
    if value is None:
        return ("", "")
    parsed = parse_time_value(value)
    return (str(parsed["precision"]), str(parsed["value"] or ""))


def validate_temporal_integrity(objects: list[dict[str, Any]]) -> list[str]:
    """Return mechanical integrity errors. Does not establish substantive truth."""
    errors: list[str] = []
    index = _index(objects)
    seen: set[str] = set()
    for record in objects:
        object_class = str(record.get("object_class"))
        if object_class not in OBJECT_CLASSES:
            errors.append(f"Unknown object_class {object_class!r}")
            continue
        field = ID_FIELDS[object_class]
        object_id = str(record.get(field, ""))
        if not object_id:
            errors.append(f"{object_class} missing {field}")
            continue
        if object_id in seen:
            errors.append(f"Duplicate id {object_id}")
        seen.add(object_id)
        schema_errors = validate_graph_object(
            {key: value for key, value in record.items() if key != "canonical_sha256"},
            object_class,
        )
        errors.extend(f"{object_id}: {item}" for item in schema_errors)

        for ref_field in ("source_ids", "observation_ids", "supersedes_assertion_ids", "trigger_assertion_ids"):
            for ref in record.get(ref_field) or []:
                if str(ref) not in index:
                    errors.append(f"{object_id}.{ref_field}->{ref} dangling")
        if object_class == "Observation" and record.get("source_id") and str(record["source_id"]) not in index:
            errors.append(f"{object_id}.source_id->{record['source_id']} dangling")

        for time_field in ("valid_from", "valid_until", "observed_at"):
            if record.get(time_field) is None:
                continue
            try:
                parse_time_value(record[time_field])
            except (TypeError, TemporalValueError) as exc:
                errors.append(f"{object_id}.{time_field}: {exc}")
        if record.get("valid_from") and record.get("valid_until"):
            if _time_order_key(record["valid_until"]) < _time_order_key(record["valid_from"]):
                errors.append(f"{object_id}: valid_until precedes valid_from")
    return errors


def compile_temporal_graph(objects: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate and persistably normalize objects for release compilation."""
    persisted = [persistable(record) for record in objects]
    errors = validate_temporal_integrity(persisted)
    digests = {str(record[ID_FIELDS[str(record["object_class"])]]): object_digest(record) for record in persisted}
    return {
        "objects": persisted,
        "object_count": len(persisted),
        "digests": digests,
        "integrity_errors": errors,
        "mechanical_pass": not errors,
        "release_authorized": False,
        "boundary": COMPILER_BOUNDARY,
    }


def state_as_of_release(objects: list[dict[str, Any]]) -> dict[str, Any]:
    """Projection: full object set belonging to one release snapshot."""
    compiled = compile_temporal_graph(objects)
    by_class: dict[str, list[dict[str, Any]]] = {name: [] for name in OBJECT_CLASSES}
    for record in compiled["objects"]:
        by_class[str(record["object_class"])].append(record)
    return {
        "projection": "STATE_AS_OF_RELEASE",
        "by_class": by_class,
        "object_count": compiled["object_count"],
        "integrity_errors": compiled["integrity_errors"],
        "authoritative": True,
        "authority_note": "Release artifact objects are authoritative only when a separate publication authority attaches.",
        "release_authorized": False,
        "boundary": COMPILER_BOUNDARY,
    }


def _assertion_valid_at(record: dict[str, Any], as_of: dict[str, Any]) -> bool:
    as_of_key = _time_order_key(as_of)
    valid_from = record.get("valid_from")
    valid_until = record.get("valid_until")
    if valid_from is not None and _time_order_key(valid_from) > as_of_key:
        return False
    if valid_until is not None and _time_order_key(valid_until) < as_of_key:
        return False
    return True


def state_valid_at(objects: list[dict[str, Any]], *, as_of: dict[str, Any]) -> dict[str, Any]:
    """Projection: assertions whose valid_from/valid_until window covers as_of."""
    parsed_as_of = parse_time_value(as_of)
    compiled = compile_temporal_graph(objects)
    selected = [
        record
        for record in compiled["objects"]
        if str(record.get("object_class")) != "Assertion" or _assertion_valid_at(record, parsed_as_of)
    ]
    return {
        "projection": "STATE_VALID_AT",
        "as_of": parsed_as_of,
        "objects": selected,
        "object_count": len(selected),
        "integrity_errors": compiled["integrity_errors"],
        "authoritative": False,
        "authority_note": "Temporal projections are derived views over release objects; they are not a second authority.",
        "release_authorized": False,
        "boundary": COMPILER_BOUNDARY,
    }


def predecessor_successor_diff(
    predecessor: list[dict[str, Any]],
    successor: list[dict[str, Any]],
) -> dict[str, Any]:
    pred_index = _index(predecessor)
    succ_index = _index(successor)
    added = sorted(set(succ_index) - set(pred_index))
    removed = sorted(set(pred_index) - set(succ_index))
    changed = sorted(
        object_id
        for object_id in set(pred_index) & set(succ_index)
        if object_digest(pred_index[object_id]) != object_digest(succ_index[object_id])
    )
    return {
        "added_ids": added,
        "removed_ids": removed,
        "changed_ids": changed,
        "predecessor_count": len(pred_index),
        "successor_count": len(succ_index),
        "boundary": COMPILER_BOUNDARY,
    }
