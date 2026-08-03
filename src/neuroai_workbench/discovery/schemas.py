from __future__ import annotations

import json
from importlib.resources import files
from typing import Any, cast

from jsonschema import Draft202012Validator

DISCOVERY_RESOURCE_PACKAGE = "neuroai_workbench.resources.discovery"

QUERY_SCHEMA = "DISCOVERY_QUERY.schema.json"
RUN_SCHEMA = "DISCOVERY_RUN.schema.json"
PROPOSAL_SCHEMA = "CANDIDATE_SOURCE_PROPOSAL.schema.json"
ADJUDICATION_SCHEMA = "DISCOVERY_ADJUDICATION.schema.json"
SUCCESSOR_SCHEMA = "REGISTRY_SUCCESSOR_PROPOSAL.schema.json"
FIXTURES_NAME = "DISCOVERY_QUERY_FIXTURES.json"


def _schema(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(DISCOVERY_RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8")),
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


def load_fixture_bundle() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(DISCOVERY_RESOURCE_PACKAGE).joinpath(FIXTURES_NAME).read_text(encoding="utf-8")),
    )
