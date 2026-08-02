from __future__ import annotations

import json
from importlib.resources import files
from typing import Any, cast

from jsonschema import Draft202012Validator

COLLECTOR_RESOURCE_PACKAGE = "neuroai_workbench.resources.collector"

REQUEST_SCHEMA = "collection-request.schema.json"
RESULT_SCHEMA = "collection-result.schema.json"
FAILURE_SCHEMA = "collection-failure.schema.json"
QUARANTINE_SCHEMA = "quarantine-record.schema.json"


def _schema(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(COLLECTOR_RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8")),
    )


def schema_errors(value: Any, schema_name: str) -> list[str]:
    validator = Draft202012Validator(_schema(schema_name))
    return sorted(
        f"{'.'.join(str(part) for part in error.absolute_path)}: {error.message}"
        for error in validator.iter_errors(value)
    )


def validate_or_raise(value: Any, schema_name: str) -> None:
    errors = schema_errors(value, schema_name)
    if errors:
        raise ValueError(f"{schema_name} validation failed: {'; '.join(errors)}")
