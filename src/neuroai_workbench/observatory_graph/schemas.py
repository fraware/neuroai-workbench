from __future__ import annotations

import json
from importlib.resources import files
from typing import Any, cast

from jsonschema import Draft202012Validator

from ..temporal.time_value import TemporalValueError, parse_time_value
from .identity import (
    IdentityError,
    UnresolvedLiteralError,
    parse_identity_ref,
    require_resolved_entity_id,
)

GRAPH_RESOURCE_PACKAGE = "neuroai_workbench.resources.observatory_graph"
TEMPORAL_RESOURCE_PACKAGE = "neuroai_workbench.resources.temporal"

OBJECT_SCHEMAS = {
    "Entity": "ENTITY.schema.json",
    "Source": "SOURCE.schema.json",
    "Observation": "OBSERVATION.schema.json",
    "Assertion": "ASSERTION.schema.json",
    "Event": "EVENT.schema.json",
    "Relationship": "RELATIONSHIP.schema.json",
    "Candidate": "CANDIDATE.schema.json",
    "ReopeningDecision": "REOPENING_DECISION.schema.json",
}

RESOLVED_SUBJECT_CLASSES = frozenset({"Assertion", "Relationship", "Event", "ReopeningDecision"})
TIME_FIELDS = ("valid_from", "valid_until", "observed_at", "occurred_at", "publication_or_record_date")


def _load(package: str, name: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(files(package).joinpath(name).read_text(encoding="utf-8")))


def schema_errors(value: Any, schema_name: str, *, package: str = GRAPH_RESOURCE_PACKAGE) -> list[dict[str, Any]]:
    validator = Draft202012Validator(_load(package, schema_name))
    return [
        {
            "code": "SCHEMA_ERROR",
            "path": ".".join(str(part) for part in error.absolute_path),
            "message": error.message,
        }
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    ]


def _reject_mixed_provenance(record: dict[str, Any]) -> None:
    for field in TIME_FIELDS:
        if field in record and f"{field}_timestamp" in record:
            raise TemporalValueError(
                f"Invalid mixed provenance: {field} and {field}_timestamp must not both be present"
            )
        if field in record and f"{field}_iso" in record:
            raise TemporalValueError(f"Invalid mixed provenance: {field} and {field}_iso must not both be present")


def _parse_times(record: dict[str, Any]) -> None:
    for field in TIME_FIELDS:
        if field not in record or record[field] is None:
            continue
        parse_time_value(record[field])


def validate_graph_object(value: Any, object_class: str) -> list[dict[str, Any]]:
    schema_name = OBJECT_SCHEMAS.get(object_class)
    if schema_name is None:
        raise ValueError(f"Unknown observatory-graph object class {object_class!r}")
    errors = schema_errors(value, schema_name)
    if not isinstance(value, dict):
        return errors or [{"code": "SCHEMA_ERROR", "path": "", "message": "object must be an object"}]
    try:
        _reject_mixed_provenance(value)
        _parse_times(value)
    except TemporalValueError as exc:
        errors.append({"code": "TEMPORAL_ERROR", "path": "", "message": str(exc)})

    if object_class in RESOLVED_SUBJECT_CLASSES and "subject" in value:
        try:
            require_resolved_entity_id(value["subject"], field="subject")
        except (IdentityError, UnresolvedLiteralError) as exc:
            errors.append({"code": "UNRESOLVED_LITERAL", "path": "subject", "message": str(exc)})
    if object_class == "Assertion" and "subject" not in value and "subject_id" in value:
        errors.append(
            {
                "code": "UNRESOLVED_LITERAL",
                "path": "subject",
                "message": "Assertion subject must be a RESOLVED_ENTITY_REFERENCE object, not a bare subject_id literal",
            }
        )
    if "subject" in value and object_class not in RESOLVED_SUBJECT_CLASSES:
        try:
            parse_identity_ref(value["subject"])
        except IdentityError as exc:
            errors.append({"code": "IDENTITY_ERROR", "path": "subject", "message": str(exc)})
    return errors


def validate_or_raise(value: Any, object_class: str) -> None:
    errors = validate_graph_object(value, object_class)
    if errors:
        raise ValueError(f"{object_class} validation failed: {errors}")
