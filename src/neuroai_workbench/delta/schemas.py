from __future__ import annotations

import json
from importlib.resources import files
from typing import Any, cast

from jsonschema import Draft202012Validator

DELTA_RESOURCE_PACKAGE = "neuroai_workbench.resources.delta"
ADJUDICATED_DELTA_SCHEMA = "ADJUDICATED_DELTA.schema.json"
DELTA_OPERATION_SCHEMA = "DELTA_OPERATION.schema.json"

OPERATION_TYPES = frozenset(
    {
        "ADD_RECORD",
        "ADD_RELATIONSHIP",
        "UPDATE_FIELD_WITH_PREDECESSOR",
        "ADD_EVENT",
        "SUPERSEDE_RECORD",
        "ADD_ALIAS",
        "RECORD_SOURCE_INACCESSIBILITY",
        "QUEUE_ASSESSMENT_REVIEW",
        "ADD_ENTITY",
        "ADD_SOURCE",
        "ADD_OBSERVATION",
        "ADD_ASSERTION",
        "SUPERSEDE_ASSERTION",
        "SUPERSEDE_ENTITY",
        "RECORD_SOURCE_SUCCESSOR_ROUTE",
        "RECORD_REOPENING_DECISION",
        "RECORD_NO_CHANGE_COMPARISON",
    }
)

# Explicit mapping only. Do not silently rename historical ADD_RECORD / SUPERSEDE_RECORD ops.
LEGACY_OPERATION_MAPPING: dict[str, str] = {
    "ADD_RECORD": "ADD_RECORD",
    "SUPERSEDE_RECORD": "SUPERSEDE_RECORD",
}

GRAPH_NATIVE_ADD_OPS = frozenset({"ADD_ENTITY", "ADD_SOURCE", "ADD_OBSERVATION", "ADD_ASSERTION"})
GRAPH_NATIVE_SUPERSEDE_OPS = frozenset({"SUPERSEDE_ASSERTION", "SUPERSEDE_ENTITY"})

DISPOSITION_DECISIONS = frozenset({"ACCEPT", "REJECT", "DEFER", "DUPLICATE", "NEEDS_EVIDENCE"})

DECISION_TO_REGISTER: dict[str, str] = {
    "ACCEPT": "accepted",
    "REJECT": "rejected",
    "DEFER": "deferred",
    "DUPLICATE": "duplicate",
    "NEEDS_EVIDENCE": "needs_evidence",
}

DELTA_BOUNDARY = (
    "An adjudicated delta records proposed canonical changes supported by human decisions. "
    "It is not a canonical successor release and does not establish substantive correctness. "
    "Unrestricted RFC-6902 JSON Patch is forbidden."
)


def _load_schema(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(DELTA_RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8")),
    )


def schema_errors(value: Any, schema_name: str) -> list[dict[str, Any]]:
    validator = Draft202012Validator(_load_schema(schema_name))
    return [
        {
            "code": "SCHEMA_ERROR",
            "path": ".".join(str(part) for part in error.absolute_path),
            "message": error.message,
        }
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    ]


def validate_delta_operation(value: Any) -> list[dict[str, Any]]:
    return schema_errors(value, DELTA_OPERATION_SCHEMA)


def validate_adjudicated_delta(value: Any) -> list[dict[str, Any]]:
    errors = schema_errors(value, ADJUDICATED_DELTA_SCHEMA)
    if not isinstance(value, dict):
        return errors
    operations = value.get("operations")
    if isinstance(operations, list):
        for index, operation in enumerate(operations):
            for op_error in validate_delta_operation(operation):
                op_error["path"] = (
                    f"operations[{index}].{op_error['path']}" if op_error["path"] else f"operations[{index}]"
                )
                errors.append(op_error)
    return errors


def validate_adjudicated_delta_semantics(value: dict[str, Any]) -> list[dict[str, Any]]:
    """Reject unrestricted patch-like operations and enforce deterministic ordering."""
    errors: list[dict[str, Any]] = []
    operations = value.get("operations")
    if not isinstance(operations, list):
        return errors

    seen_operation_ids: set[str] = set()
    previous_id: str | None = None
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            continue
        operation_type = operation.get("operation_type")
        if operation_type not in OPERATION_TYPES:
            errors.append(
                {
                    "code": "UNSUPPORTED_OPERATION",
                    "path": f"operations[{index}].operation_type",
                    "message": f"Unsupported operation type {operation_type!r}",
                }
            )
        operation_id = operation.get("operation_id")
        if isinstance(operation_id, str):
            if operation_id in seen_operation_ids:
                errors.append(
                    {
                        "code": "DUPLICATE_OPERATION_ID",
                        "path": f"operations[{index}].operation_id",
                        "message": f"Duplicate operation_id {operation_id!r}",
                    }
                )
            seen_operation_ids.add(operation_id)
            if previous_id is not None and operation_id <= previous_id:
                errors.append(
                    {
                        "code": "NON_DETERMINISTIC_ORDER",
                        "path": f"operations[{index}].operation_id",
                        "message": "Operations must be sorted by operation_id",
                    }
                )
            previous_id = operation_id

    metadata = value.get("metadata")
    if isinstance(metadata, dict) and metadata.get("status") != "NON_CANONICAL":
        errors.append(
            {
                "code": "INVALID_STATUS",
                "path": "metadata.status",
                "message": "Adjudicated delta packages must be NON_CANONICAL",
            }
        )
    return errors
