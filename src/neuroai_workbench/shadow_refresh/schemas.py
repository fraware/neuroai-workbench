from __future__ import annotations

import json
from importlib.resources import files
from typing import Any, cast

from jsonschema import Draft202012Validator

SHADOW_REFRESH_RESOURCE_PACKAGE = "neuroai_workbench.resources.shadow_refresh"
COHORT_SCHEMA = "SHADOW_REFRESH_COHORT.schema.json"
FREEZE_MANIFEST_SCHEMA = "SHADOW_REFRESH_FREEZE_MANIFEST.schema.json"
GO_NO_GO_METRICS_SCHEMA = "SHADOW_REFRESH_GO_NO_GO_METRICS.schema.json"
RUN_RESULTS_SCHEMA = "SHADOW_REFRESH_RUN_RESULTS.schema.json"

SHADOW_EVALUATION_STATUS = "SHADOW_EVALUATION_NOT_CANONICAL"

SHADOW_REFRESH_BOUNDARY = (
    "Shadow refresh evaluation records operational rehearsal metrics only. "
    "They do not establish canonical observatory state, substantive findings, regulatory authorization, "
    "clinical effectiveness, conformance, or an assessment decision."
)

DEFAULT_GO_NO_GO_THRESHOLDS: dict[str, float | int] = {
    "minimum_retrieval_success_rate": 0.85,
    "maximum_unsupported_candidate_rate": 0.10,
    "minimum_candidate_precision": 0.80,
    "minimum_reopening_precision": 0.85,
    "maximum_reopening_false_positive_rate": 0.10,
    "minimum_provenance_closure_rate": 1.0,
    "maximum_publication_reconciliation_errors": 0,
}


def _load_schema(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(SHADOW_REFRESH_RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8")),
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


def validate_shadow_refresh_cohort(value: Any) -> list[dict[str, Any]]:
    return schema_errors(value, COHORT_SCHEMA)


def validate_shadow_refresh_freeze_manifest(value: Any) -> list[dict[str, Any]]:
    return schema_errors(value, FREEZE_MANIFEST_SCHEMA)


def validate_shadow_refresh_go_no_go_metrics(value: Any) -> list[dict[str, Any]]:
    return schema_errors(value, GO_NO_GO_METRICS_SCHEMA)


def validate_shadow_refresh_run_results(value: Any) -> list[dict[str, Any]]:
    return schema_errors(value, RUN_RESULTS_SCHEMA)


def validate_shadow_artifact_status(value: dict[str, Any]) -> list[dict[str, Any]]:
    """Ensure shadow evaluation artifacts remain explicitly non-canonical."""
    errors: list[dict[str, Any]] = []
    metadata = value.get("metadata")
    if not isinstance(metadata, dict):
        errors.append({"code": "METADATA_REQUIRED", "path": "metadata", "message": "metadata object is required"})
        return errors
    status = metadata.get("status")
    if status != SHADOW_EVALUATION_STATUS:
        errors.append(
            {
                "code": "INVALID_STATUS",
                "path": "metadata.status",
                "message": f"Shadow evaluation artifacts must use status {SHADOW_EVALUATION_STATUS!r}",
            }
        )
    return errors
