"""Temporal graph compiler: referential/temporal integrity and release projections.

Derived loaders and website/database projections are never authority. Canonical state
lives in separately authorized release artifacts, not in compiler output.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

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

TemporalRelation = Literal["BEFORE", "AFTER", "EQUAL", "OVERLAPS", "INDETERMINATE"]


def _ids_by_class(objects: list[dict[str, Any]]) -> dict[str, set[str]]:
    index: dict[str, set[str]] = {object_class: set() for object_class in ID_FIELDS}
    for record in objects:
        object_class = str(record.get("object_class"))
        field = ID_FIELDS.get(object_class)
        if not field:
            continue
        object_id = str(record.get(field, ""))
        if object_id:
            index[object_class].add(object_id)
    return index


def _object_index(objects: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """Index records without allowing an id from one class to shadow another class."""
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for record in objects:
        object_class = str(record.get("object_class"))
        field = ID_FIELDS.get(object_class)
        if not field:
            continue
        object_id = str(record.get(field, ""))
        if object_id:
            index[(object_class, object_id)] = record
    return index


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _temporal_relation(left: Any, right: Any) -> TemporalRelation:
    """Compare TimeValues without manufacturing finer precision.

    Equal-precision values are compared directly. For mixed precision, a coarser
    YEAR or DATE is treated as overlapping a finer value inside the same calendar
    envelope; values outside that envelope have a definite order. UNKNOWN remains
    indeterminate. This is a mechanical consistency relation, not a fabricated
    timestamp for partial dates.
    """
    lhs = parse_time_value(left)
    rhs = parse_time_value(right)
    lp = str(lhs["precision"])
    rp = str(rhs["precision"])
    if "UNKNOWN" in {lp, rp}:
        return "INDETERMINATE"

    lv = str(lhs["value"])
    rv = str(rhs["value"])
    if lp == rp:
        if lp == "YEAR":
            left_value: Any = int(lv)
            right_value: Any = int(rv)
        elif lp == "DATE":
            left_value = datetime.strptime(lv, "%Y-%m-%d").date()
            right_value = datetime.strptime(rv, "%Y-%m-%d").date()
        else:
            left_value = _timestamp(lv)
            right_value = _timestamp(rv)
        if left_value < right_value:
            return "BEFORE"
        if left_value > right_value:
            return "AFTER"
        return "EQUAL"

    # Compare calendar envelopes conservatively when precisions differ. A value
    # inside the coarser envelope overlaps it; no instant/date is invented.
    def year_of(precision: str, value: str) -> int:
        if precision == "YEAR":
            return int(value)
        if precision == "DATE":
            return datetime.strptime(value, "%Y-%m-%d").year
        return _timestamp(value).year

    left_year = year_of(lp, lv)
    right_year = year_of(rp, rv)
    if left_year < right_year:
        return "BEFORE"
    if left_year > right_year:
        return "AFTER"
    if "YEAR" in {lp, rp}:
        return "OVERLAPS"

    # Remaining mixed case is DATE versus TIMESTAMP in the same represented year.
    def date_of(precision: str, value: str):
        if precision == "DATE":
            return datetime.strptime(value, "%Y-%m-%d").date()
        return _timestamp(value).date()

    left_date = date_of(lp, lv)
    right_date = date_of(rp, rv)
    if left_date < right_date:
        return "BEFORE"
    if left_date > right_date:
        return "AFTER"
    return "OVERLAPS"


def _resolved_entity_ref_error(
    *,
    object_id: str,
    field: str,
    ref: Any,
    entity_ids: set[str],
) -> str | None:
    if not isinstance(ref, dict) or ref.get("kind") != "RESOLVED_ENTITY_REFERENCE":
        return None
    entity_id = str(ref.get("entity_id") or "")
    if entity_id and entity_id not in entity_ids:
        return f"{object_id}.{field}->{entity_id} dangling"
    return None


def validate_temporal_integrity(objects: list[dict[str, Any]]) -> list[str]:
    """Return mechanical graph/temporal integrity errors. Does not establish substantive truth."""
    errors: list[str] = []
    ids = _ids_by_class(objects)
    seen: set[tuple[str, str]] = set()
    typed_list_refs = {
        "source_ids": "Source",
        "observation_ids": "Observation",
        "supersedes_assertion_ids": "Assertion",
        "trigger_assertion_ids": "Assertion",
        "trigger_event_ids": "Event",
    }

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
        identity = (object_class, object_id)
        if identity in seen:
            errors.append(f"Duplicate {object_class} id {object_id}")
        seen.add(identity)
        schema_errors = validate_graph_object(
            {key: value for key, value in record.items() if key != "canonical_sha256"},
            object_class,
        )
        errors.extend(f"{object_id}: {item}" for item in schema_errors)

        for ref_field, expected_class in typed_list_refs.items():
            for ref in record.get(ref_field) or []:
                if str(ref) not in ids[expected_class]:
                    errors.append(f"{object_id}.{ref_field}->{ref} dangling")
        if object_class == "Observation" and record.get("source_id"):
            source_id = str(record["source_id"])
            if source_id not in ids["Source"]:
                errors.append(f"{object_id}.source_id->{source_id} dangling")

        for ref_field in ("subject", "object_ref"):
            missing = _resolved_entity_ref_error(
                object_id=object_id,
                field=ref_field,
                ref=record.get(ref_field),
                entity_ids=ids["Entity"],
            )
            if missing:
                errors.append(missing)

        if object_class == "Event":
            for position, ref in enumerate(record.get("objects") or []):
                missing = _resolved_entity_ref_error(
                    object_id=object_id,
                    field=f"objects[{position}]",
                    ref=ref,
                    entity_ids=ids["Entity"],
                )
                if missing:
                    errors.append(missing)

        if object_class == "Entity":
            lineage = record.get("lineage") or {}
            if isinstance(lineage, dict):
                for lineage_field in ("predecessor_entity_ids", "successor_entity_ids"):
                    for ref in lineage.get(lineage_field) or []:
                        if str(ref) not in ids["Entity"]:
                            errors.append(f"{object_id}.lineage.{lineage_field}->{ref} dangling")

        for time_field in ("valid_from", "valid_until", "observed_at", "occurred_at", "decided_at"):
            if record.get(time_field) is None:
                continue
            try:
                parse_time_value(record[time_field])
            except (TypeError, TemporalValueError) as exc:
                errors.append(f"{object_id}.{time_field}: {exc}")
        if record.get("valid_from") and record.get("valid_until"):
            try:
                if _temporal_relation(record["valid_until"], record["valid_from"]) == "BEFORE":
                    errors.append(f"{object_id}: valid_until definitely precedes valid_from")
            except (TypeError, TemporalValueError) as exc:
                errors.append(f"{object_id}.valid_interval: {exc}")
    return sorted(set(errors))


def compile_temporal_graph(objects: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate and persistably normalize objects for candidate release compilation."""
    persisted = [persistable(record) for record in objects]
    errors = validate_temporal_integrity(persisted)
    digests = {
        f"{record['object_class']}:{record[ID_FIELDS[str(record['object_class'])]]}": object_digest(record)
        for record in persisted
    }
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
    """Projection: full object set belonging to one candidate/release snapshot."""
    compiled = compile_temporal_graph(objects)
    by_class: dict[str, list[dict[str, Any]]] = {name: [] for name in OBJECT_CLASSES}
    for record in compiled["objects"]:
        by_class[str(record["object_class"])].append(record)
    return {
        "projection": "STATE_AS_OF_RELEASE",
        "by_class": by_class,
        "object_count": compiled["object_count"],
        "integrity_errors": compiled["integrity_errors"],
        "authoritative": False,
        "authority_note": "Authority requires a separate authorized S2 publication; compiler projections are noncanonical.",
        "release_authorized": False,
        "boundary": COMPILER_BOUNDARY,
    }


def _assertion_valid_at(record: dict[str, Any], as_of: dict[str, Any]) -> bool:
    valid_from = record.get("valid_from")
    valid_until = record.get("valid_until")
    if valid_from is not None and _temporal_relation(as_of, valid_from) == "BEFORE":
        return False
    if valid_until is not None and _temporal_relation(as_of, valid_until) == "AFTER":
        return False
    return True


def state_valid_at(objects: list[dict[str, Any]], *, as_of: dict[str, Any]) -> dict[str, Any]:
    """Projection: assertions not definitely outside their valid-time window at ``as_of``.

    Mixed-precision overlap is retained instead of manufacturing a finer instant.
    """
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
    pred_index = _object_index(predecessor)
    succ_index = _object_index(successor)
    added_keys = sorted(set(succ_index) - set(pred_index))
    removed_keys = sorted(set(pred_index) - set(succ_index))
    changed_keys = sorted(
        key
        for key in set(pred_index) & set(succ_index)
        if object_digest(pred_index[key]) != object_digest(succ_index[key])
    )

    def display(keys: list[tuple[str, str]]) -> list[str]:
        ids = [object_id for _, object_id in keys]
        # Preserve the legacy id-only surface when unambiguous; qualify collisions.
        counts = {object_id: ids.count(object_id) for object_id in set(ids)}
        return [object_id if counts[object_id] == 1 else f"{object_class}:{object_id}" for object_class, object_id in keys]

    return {
        "added_ids": display(added_keys),
        "removed_ids": display(removed_keys),
        "changed_ids": display(changed_keys),
        "predecessor_count": len(pred_index),
        "successor_count": len(succ_index),
        "boundary": COMPILER_BOUNDARY,
    }
