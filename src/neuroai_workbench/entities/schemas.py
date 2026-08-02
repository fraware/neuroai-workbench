from __future__ import annotations

import json
from importlib.resources import files
from typing import Any, cast

from jsonschema import Draft202012Validator

ENTITIES_RESOURCE_PACKAGE = "neuroai_workbench.resources.entities"
ENTITY_SCHEMA = "ENTITY.schema.json"
ALIAS_SCHEMA = "ALIAS.schema.json"
IDENTIFIER_SCHEMA = "IDENTIFIER.schema.json"
ENTITY_EVENT_SCHEMA = "ENTITY_EVENT.schema.json"
REGISTRY_SCHEMA = "ENTITY_REGISTRY.schema.json"


def _schema(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(ENTITIES_RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8")),
    )


def schema_errors(value: Any, schema_name: str) -> list[dict[str, Any]]:
    validator = Draft202012Validator(_schema(schema_name))
    return [
        {
            "code": "SCHEMA_ERROR",
            "path": ".".join(str(part) for part in error.absolute_path),
            "message": error.message,
        }
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    ]


def validate_entity(value: Any) -> list[dict[str, Any]]:
    return schema_errors(value, ENTITY_SCHEMA)


def validate_alias(value: Any) -> list[dict[str, Any]]:
    return schema_errors(value, ALIAS_SCHEMA)


def validate_identifier(value: Any) -> list[dict[str, Any]]:
    return schema_errors(value, IDENTIFIER_SCHEMA)


def validate_entity_event(value: Any) -> list[dict[str, Any]]:
    return schema_errors(value, ENTITY_EVENT_SCHEMA)


def validate_registry_container(value: Any) -> list[dict[str, Any]]:
    return schema_errors(value, REGISTRY_SCHEMA)
