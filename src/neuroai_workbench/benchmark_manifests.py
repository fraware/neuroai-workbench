from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from neuroai_workbench.evaluation_benchmarks import (
    BENCHMARK_KINDS,
    COMMITMENT_SCHEME,
    BenchmarkContractError,
    canonical_json_bytes,
)

MANIFEST_SCHEMA_VERSION = "0.1"
FREEZE_MANIFEST_TYPE = "BENCHMARK_FREEZE"
RUN_MANIFEST_TYPE = "HELD_OUT_EVALUATION_RUN"
FREEZE_LINEAGE_STATES = frozenset({"ROOT", "SUCCESSOR"})
CLEAN_CONTAMINATION_STATE = "NO_KNOWN_CONTAMINATION_REVIEWED"
DEV_TUNING_BOUNDARY = "HELD_OUT_NOT_USED_FOR_TUNING"
EXPORT_POLICY = "AGGREGATE_ONLY"

FREEZE_FIELDS = frozenset(
    {
        "schema_version",
        "manifest_type",
        "manifest_id",
        "benchmark_kind",
        "benchmark_id",
        "g1_disposition_id",
        "g1_disposition_sha256",
        "membership_commitment",
        "label_commitment",
        "commitment_scheme",
        "s3_custody",
        "strata_contract_version",
        "adjudication_protocol_version",
        "frozen_at",
        "lineage_state",
        "predecessor_manifest_sha256",
        "contamination_status",
        "exposure_register_ref",
        "g2_passed",
        "canonical_s2_authority",
        "publication_authority",
        "assessment_effect",
    }
)

RUN_FIELDS = frozenset(
    {
        "schema_version",
        "manifest_type",
        "run_id",
        "benchmark_kind",
        "freeze_manifest_id",
        "freeze_manifest_sha256",
        "workbench_commit_sha",
        "pipeline_id",
        "pipeline_artifact_sha256",
        "config_sha256",
        "threshold_policy_id",
        "threshold_policy_sha256",
        "abstention_policy_id",
        "abstention_policy_sha256",
        "development_tuning_boundary",
        "subgroup_plan_id",
        "subgroup_plan_sha256",
        "metric_schema_version",
        "observed_at",
        "operator_role_ref",
        "contamination_status",
        "exposure_register_ref",
        "prediction_artifact_sha256",
        "aggregate_result_sha256",
        "export_policy",
        "g2_passed",
        "canonical_s2_authority",
        "publication_authority",
        "assessment_effect",
    }
)


class BenchmarkManifestError(BenchmarkContractError):
    """Raised when a PRE-G2 freeze or held-out run manifest is invalid."""


def manifest_identity_sha256(manifest: Mapping[str, Any]) -> str:
    """Return the deterministic identity digest of an exact manifest payload."""

    return hashlib.sha256(canonical_json_bytes(manifest)).hexdigest()


def _require_exact_fields(manifest: Mapping[str, Any], allowed: frozenset[str]) -> None:
    missing = allowed - set(manifest)
    unexpected = set(manifest) - allowed
    if missing:
        raise BenchmarkManifestError(f"Manifest is missing required fields: {sorted(missing)}")
    if unexpected:
        raise BenchmarkManifestError(f"Manifest contains unsupported fields: {sorted(unexpected)}")


def _require_nonempty_string(manifest: Mapping[str, Any], field: str) -> str:
    value = manifest.get(field)
    if not isinstance(value, str) or not value.strip():
        raise BenchmarkManifestError(f"{field} must be a non-empty string")
    return value


def _is_hex_digest(value: Any, length: int) -> bool:
    if not isinstance(value, str) or len(value) != length:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _require_sha256(manifest: Mapping[str, Any], field: str) -> str:
    value = manifest.get(field)
    if not isinstance(value, str) or not _is_hex_digest(value, 64):
        raise BenchmarkManifestError(f"{field} must be a 64-character SHA-256 hex digest")
    return value


def _require_utc_timestamp(manifest: Mapping[str, Any], field: str) -> None:
    value = _require_nonempty_string(manifest, field)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BenchmarkManifestError(f"{field} must be an RFC 3339 timestamp") from exc
    offset = parsed.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise BenchmarkManifestError(f"{field} must be expressed in UTC")


def _require_no_authority_escalation(manifest: Mapping[str, Any]) -> None:
    if manifest.get("g2_passed") is not False:
        raise BenchmarkManifestError("g2_passed must remain false in PRE-G2 manifests")
    if manifest.get("canonical_s2_authority") is not False:
        raise BenchmarkManifestError("canonical_s2_authority must remain false")
    if manifest.get("publication_authority") is not False:
        raise BenchmarkManifestError("publication_authority must remain false")
    if manifest.get("assessment_effect") != "NONE":
        raise BenchmarkManifestError("assessment_effect must be NONE")


def _require_clean_contamination_review(manifest: Mapping[str, Any]) -> None:
    if manifest.get("contamination_status") != CLEAN_CONTAMINATION_STATE:
        raise BenchmarkManifestError("Manifest cannot proceed with known or unresolved held-out contamination")
    _require_nonempty_string(manifest, "exposure_register_ref")


def validate_freeze_manifest(manifest: Mapping[str, Any]) -> None:
    """Validate structural evidence for a benchmark freeze after an external G1 approval."""

    _require_exact_fields(manifest, FREEZE_FIELDS)
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise BenchmarkManifestError(f"schema_version must be {MANIFEST_SCHEMA_VERSION}")
    if manifest.get("manifest_type") != FREEZE_MANIFEST_TYPE:
        raise BenchmarkManifestError(f"manifest_type must be {FREEZE_MANIFEST_TYPE}")
    _require_nonempty_string(manifest, "manifest_id")
    if manifest.get("benchmark_kind") not in BENCHMARK_KINDS:
        raise BenchmarkManifestError(f"benchmark_kind must be one of {sorted(BENCHMARK_KINDS)}")
    _require_nonempty_string(manifest, "benchmark_id")
    _require_nonempty_string(manifest, "g1_disposition_id")
    _require_sha256(manifest, "g1_disposition_sha256")
    _require_sha256(manifest, "membership_commitment")
    _require_sha256(manifest, "label_commitment")
    if manifest.get("commitment_scheme") != COMMITMENT_SCHEME:
        raise BenchmarkManifestError(f"commitment_scheme must be {COMMITMENT_SCHEME}")
    if manifest.get("s3_custody") is not True:
        raise BenchmarkManifestError("s3_custody must be true")
    _require_nonempty_string(manifest, "strata_contract_version")
    _require_nonempty_string(manifest, "adjudication_protocol_version")
    _require_utc_timestamp(manifest, "frozen_at")

    lineage_state = manifest.get("lineage_state")
    if lineage_state not in FREEZE_LINEAGE_STATES:
        raise BenchmarkManifestError(f"lineage_state must be one of {sorted(FREEZE_LINEAGE_STATES)}")
    predecessor = manifest.get("predecessor_manifest_sha256")
    if lineage_state == "ROOT":
        if predecessor is not None:
            raise BenchmarkManifestError("ROOT freeze manifests cannot name a predecessor")
    elif not _is_hex_digest(predecessor, 64):
        raise BenchmarkManifestError("SUCCESSOR freeze manifests require predecessor_manifest_sha256")

    _require_clean_contamination_review(manifest)
    _require_no_authority_escalation(manifest)


def validate_held_out_run_manifest(
    manifest: Mapping[str, Any],
    *,
    freeze_manifest: Mapping[str, Any],
) -> None:
    """Validate a held-out run binding against an exact structurally valid freeze manifest."""

    _require_exact_fields(manifest, RUN_FIELDS)
    validate_freeze_manifest(freeze_manifest)
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise BenchmarkManifestError(f"schema_version must be {MANIFEST_SCHEMA_VERSION}")
    if manifest.get("manifest_type") != RUN_MANIFEST_TYPE:
        raise BenchmarkManifestError(f"manifest_type must be {RUN_MANIFEST_TYPE}")
    _require_nonempty_string(manifest, "run_id")
    if manifest.get("benchmark_kind") != freeze_manifest.get("benchmark_kind"):
        raise BenchmarkManifestError("Run benchmark_kind must match its freeze manifest")
    if manifest.get("freeze_manifest_id") != freeze_manifest.get("manifest_id"):
        raise BenchmarkManifestError("freeze_manifest_id does not match the supplied freeze manifest")
    if manifest.get("freeze_manifest_sha256") != manifest_identity_sha256(freeze_manifest):
        raise BenchmarkManifestError("freeze_manifest_sha256 does not bind the supplied freeze manifest")

    workbench_commit_sha = manifest.get("workbench_commit_sha")
    if not _is_hex_digest(workbench_commit_sha, 40):
        raise BenchmarkManifestError("workbench_commit_sha must be a 40-character Git SHA")
    _require_nonempty_string(manifest, "pipeline_id")
    _require_sha256(manifest, "pipeline_artifact_sha256")
    _require_sha256(manifest, "config_sha256")
    _require_nonempty_string(manifest, "threshold_policy_id")
    _require_sha256(manifest, "threshold_policy_sha256")
    _require_nonempty_string(manifest, "abstention_policy_id")
    _require_sha256(manifest, "abstention_policy_sha256")
    if manifest.get("development_tuning_boundary") != DEV_TUNING_BOUNDARY:
        raise BenchmarkManifestError(
            "development_tuning_boundary must declare that held-out data was not used for tuning"
        )
    _require_nonempty_string(manifest, "subgroup_plan_id")
    _require_sha256(manifest, "subgroup_plan_sha256")
    _require_nonempty_string(manifest, "metric_schema_version")
    _require_utc_timestamp(manifest, "observed_at")
    _require_nonempty_string(manifest, "operator_role_ref")
    _require_clean_contamination_review(manifest)
    _require_sha256(manifest, "prediction_artifact_sha256")
    _require_sha256(manifest, "aggregate_result_sha256")
    if manifest.get("export_policy") != EXPORT_POLICY:
        raise BenchmarkManifestError(f"export_policy must be {EXPORT_POLICY}")
    _require_no_authority_escalation(manifest)
