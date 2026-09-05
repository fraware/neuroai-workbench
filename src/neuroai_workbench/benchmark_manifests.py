from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from neuroai_workbench.evaluation_benchmarks import (
    APPROVED_D1_CANONICAL_SHA256,
    BENCHMARK_KINDS,
    BINARY_PROJECTION_ID,
    BOUNDARY_DISPOSITIONS,
    COMMITMENT_SCHEME,
    REQUIRED_BOUNDARY_DISPOSITIONS,
    BenchmarkContractError,
    canonical_json_bytes,
    validate_public_benchmark_contract,
)
from neuroai_workbench.evaluation_benchmarks import (
    SCHEMA_VERSION as EVALUATION_SCHEMA_VERSION,
)

MANIFEST_SCHEMA_VERSION = "0.2"
FREEZE_MANIFEST_TYPE = "BENCHMARK_FREEZE"
RUN_MANIFEST_TYPE = "HELD_OUT_EVALUATION_RUN"
FREEZE_LINEAGE_STATES = frozenset({"ROOT", "SUCCESSOR"})
CLEAN_CONTAMINATION_STATE = "NO_KNOWN_CONTAMINATION_REVIEWED"
DEV_TUNING_BOUNDARY = "HELD_OUT_NOT_USED_FOR_TUNING"
EXPORT_POLICY = "AGGREGATE_ONLY"
RIGHTS_CONTAINMENT_STATE = "S3_CONTROLLED_NO_REDISTRIBUTION_AUTHORITY_CLAIMED"
UNRESOLVED_COUNT_KEY = "UNRESOLVED_ADJUDICATION"

APPROVED_G1_DISPOSITION_ID = "HUMAN_G1_DISPOSITION_2026-09-05_D1_D2_v0.1"
APPROVED_G1_DISPOSITION_SHA256 = "ed6489fe1085b5aec1b594970dd1c574b57bd6bbd25a659643e9bd1b7b72d8ef"
HUMAN_REVIEW_REQUIRED_FIELDS = frozenset(
    {
        "decision",
        "rationale",
        "adjudicator_role",
        "timestamp",
        "exact_object_binding",
    }
)
BOUNDARY_COUNT_KEYS = frozenset({*BOUNDARY_DISPOSITIONS, UNRESOLVED_COUNT_KEY})

FREEZE_FIELDS = frozenset(
    {
        "schema_version",
        "manifest_type",
        "manifest_id",
        "benchmark_kind",
        "benchmark_id",
        "public_contract_schema_version",
        "public_contract_sha256",
        "d1_canonical_json_sha256",
        "binary_projection_id",
        "g1_disposition_id",
        "g1_disposition_sha256",
        "membership_commitment",
        "label_commitment",
        "commitment_scheme",
        "s3_custody",
        "required_boundary_dispositions",
        "boundary_disposition_counts",
        "boundary_coverage_report_sha256",
        "required_strata",
        "strata_coverage_report_sha256",
        "sampling_protocol_id",
        "sampling_protocol_sha256",
        "human_review_required_fields",
        "human_review_provenance_sha256",
        "adjudication_protocol_id",
        "adjudication_protocol_sha256",
        "adjudication_accounting_sha256",
        "double_label_subset_count",
        "rights_containment_status",
        "rights_review_ref",
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
        "public_contract_sha256",
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
        "binary_projection_id",
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


def _require_exact_string_set(value: Any, expected: frozenset[str], field: str) -> None:
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) for item in value)
        or len(value) != len(set(value))
        or set(value) != expected
    ):
        raise BenchmarkManifestError(f"{field} must contain exactly {sorted(expected)}")


def _require_positive_int(manifest: Mapping[str, Any], field: str) -> int:
    value = manifest.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise BenchmarkManifestError(f"{field} must be a positive integer")
    return value


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


def _validate_current_public_contract(public_contract: Mapping[str, Any]) -> None:
    try:
        validate_public_benchmark_contract(public_contract)
    except BenchmarkContractError as exc:
        raise BenchmarkManifestError(f"Supplied public benchmark contract is invalid: {exc}") from exc

    if public_contract.get("schema_version") != EVALUATION_SCHEMA_VERSION:
        raise BenchmarkManifestError(
            f"Current freeze requires public benchmark contract schema {EVALUATION_SCHEMA_VERSION}"
        )
    if public_contract.get("state") != "FROZEN_COMMITMENTS_ONLY":
        raise BenchmarkManifestError("A freeze manifest requires a FROZEN_COMMITMENTS_ONLY public contract")
    if public_contract.get("g1_disposition_id") != APPROVED_G1_DISPOSITION_ID:
        raise BenchmarkManifestError("Public contract does not bind the exact approved G1 disposition id")
    if public_contract.get("g1_disposition_sha256") != APPROVED_G1_DISPOSITION_SHA256:
        raise BenchmarkManifestError("Public contract does not bind the exact approved G1 disposition digest")

    semantics = public_contract.get("boundary_semantics")
    if not isinstance(semantics, Mapping):
        raise BenchmarkManifestError("Public contract boundary_semantics must be an object")
    if semantics.get("source_d1_canonical_json_sha256") != APPROVED_D1_CANONICAL_SHA256:
        raise BenchmarkManifestError("Public contract does not bind the exact approved D1 digest")
    projection = semantics.get("binary_projection")
    if not isinstance(projection, Mapping) or projection.get("projection_id") != BINARY_PROJECTION_ID:
        raise BenchmarkManifestError("Public contract does not bind the current binary projection")


def _validate_boundary_counts(manifest: Mapping[str, Any]) -> int:
    counts = manifest.get("boundary_disposition_counts")
    if not isinstance(counts, Mapping) or set(counts) != BOUNDARY_COUNT_KEYS:
        raise BenchmarkManifestError(f"boundary_disposition_counts must contain exactly {sorted(BOUNDARY_COUNT_KEYS)}")

    total = 0
    for key in sorted(BOUNDARY_COUNT_KEYS):
        value = counts.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise BenchmarkManifestError(f"boundary_disposition_counts[{key}] must be a non-negative integer")
        total += value

    if total < 1:
        raise BenchmarkManifestError("boundary_disposition_counts cannot describe an empty benchmark")
    for required in REQUIRED_BOUNDARY_DISPOSITIONS:
        if counts.get(required, 0) < 1:
            raise BenchmarkManifestError(f"Required G2 boundary disposition {required} has zero frozen cases")
    return total


def validate_freeze_manifest(
    manifest: Mapping[str, Any],
    *,
    public_contract: Mapping[str, Any],
) -> None:
    """Validate a post-#291 PRE-G2 freeze against the exact public contract.

    The function validates structural identity and control bindings only. It
    does not read private item-level evidence, establish label truth, prove
    reviewer independence, establish licence rights, or pass G2.
    """

    _require_exact_fields(manifest, FREEZE_FIELDS)
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise BenchmarkManifestError(f"schema_version must be {MANIFEST_SCHEMA_VERSION}")
    if manifest.get("manifest_type") != FREEZE_MANIFEST_TYPE:
        raise BenchmarkManifestError(f"manifest_type must be {FREEZE_MANIFEST_TYPE}")

    _validate_current_public_contract(public_contract)
    _require_nonempty_string(manifest, "manifest_id")

    benchmark_kind = manifest.get("benchmark_kind")
    if benchmark_kind not in BENCHMARK_KINDS:
        raise BenchmarkManifestError(f"benchmark_kind must be one of {sorted(BENCHMARK_KINDS)}")
    if benchmark_kind != public_contract.get("benchmark_kind"):
        raise BenchmarkManifestError("Freeze benchmark_kind must match the supplied public contract")
    if manifest.get("benchmark_id") != public_contract.get("benchmark_id"):
        raise BenchmarkManifestError("Freeze benchmark_id must match the supplied public contract")

    if manifest.get("public_contract_schema_version") != EVALUATION_SCHEMA_VERSION:
        raise BenchmarkManifestError(f"public_contract_schema_version must be {EVALUATION_SCHEMA_VERSION}")
    expected_contract_sha256 = manifest_identity_sha256(public_contract)
    if manifest.get("public_contract_sha256") != expected_contract_sha256:
        raise BenchmarkManifestError("public_contract_sha256 does not bind the supplied public contract")
    if manifest.get("d1_canonical_json_sha256") != APPROVED_D1_CANONICAL_SHA256:
        raise BenchmarkManifestError("d1_canonical_json_sha256 must bind the exact approved D1")
    if manifest.get("binary_projection_id") != BINARY_PROJECTION_ID:
        raise BenchmarkManifestError("binary_projection_id must bind the current controlled projection")

    if manifest.get("g1_disposition_id") != APPROVED_G1_DISPOSITION_ID:
        raise BenchmarkManifestError("g1_disposition_id must bind the exact approved G1 disposition")
    if manifest.get("g1_disposition_sha256") != APPROVED_G1_DISPOSITION_SHA256:
        raise BenchmarkManifestError("g1_disposition_sha256 must bind the exact approved G1 disposition")
    if manifest.get("g1_disposition_id") != public_contract.get("g1_disposition_id"):
        raise BenchmarkManifestError("Freeze G1 disposition id does not match the supplied public contract")
    if manifest.get("g1_disposition_sha256") != public_contract.get("g1_disposition_sha256"):
        raise BenchmarkManifestError("Freeze G1 disposition digest does not match the supplied public contract")

    membership_commitment = _require_sha256(manifest, "membership_commitment")
    label_commitment = _require_sha256(manifest, "label_commitment")
    if membership_commitment != public_contract.get("membership_commitment"):
        raise BenchmarkManifestError("membership_commitment does not match the supplied public contract")
    if label_commitment != public_contract.get("label_commitment"):
        raise BenchmarkManifestError("label_commitment does not match the supplied public contract")
    if manifest.get("commitment_scheme") != COMMITMENT_SCHEME:
        raise BenchmarkManifestError(f"commitment_scheme must be {COMMITMENT_SCHEME}")
    if manifest.get("commitment_scheme") != public_contract.get("commitment_scheme"):
        raise BenchmarkManifestError("Freeze commitment_scheme does not match the supplied public contract")
    if manifest.get("s3_custody") is not True:
        raise BenchmarkManifestError("s3_custody must be true")

    semantics = public_contract["boundary_semantics"]
    assert isinstance(semantics, Mapping)
    expected_required_dispositions = frozenset(semantics["required_g2_coverage_dispositions"])
    _require_exact_string_set(
        manifest.get("required_boundary_dispositions"),
        REQUIRED_BOUNDARY_DISPOSITIONS,
        "required_boundary_dispositions",
    )
    if expected_required_dispositions != REQUIRED_BOUNDARY_DISPOSITIONS:
        raise BenchmarkManifestError("Public contract required boundary dispositions do not match current D1 semantics")

    member_count = _validate_boundary_counts(manifest)
    _require_sha256(manifest, "boundary_coverage_report_sha256")

    expected_strata = frozenset(str(item) for item in public_contract["required_strata"])
    _require_exact_string_set(manifest.get("required_strata"), expected_strata, "required_strata")
    _require_sha256(manifest, "strata_coverage_report_sha256")
    _require_nonempty_string(manifest, "sampling_protocol_id")
    _require_sha256(manifest, "sampling_protocol_sha256")

    _require_exact_string_set(
        manifest.get("human_review_required_fields"),
        HUMAN_REVIEW_REQUIRED_FIELDS,
        "human_review_required_fields",
    )
    _require_sha256(manifest, "human_review_provenance_sha256")
    _require_nonempty_string(manifest, "adjudication_protocol_id")
    _require_sha256(manifest, "adjudication_protocol_sha256")
    _require_sha256(manifest, "adjudication_accounting_sha256")
    double_label_subset_count = _require_positive_int(manifest, "double_label_subset_count")
    if double_label_subset_count > member_count:
        raise BenchmarkManifestError("double_label_subset_count cannot exceed the frozen member count")

    if manifest.get("rights_containment_status") != RIGHTS_CONTAINMENT_STATE:
        raise BenchmarkManifestError(
            f"rights_containment_status must be {RIGHTS_CONTAINMENT_STATE} in this PRE-G2 contract"
        )
    _require_nonempty_string(manifest, "rights_review_ref")
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
    public_contract: Mapping[str, Any],
) -> None:
    """Validate a held-out run against an exact current freeze/public contract pair."""

    _require_exact_fields(manifest, RUN_FIELDS)
    validate_freeze_manifest(freeze_manifest, public_contract=public_contract)
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
    if manifest.get("public_contract_sha256") != freeze_manifest.get("public_contract_sha256"):
        raise BenchmarkManifestError("Run public_contract_sha256 must match the freeze manifest binding")

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
    if manifest.get("metric_schema_version") != EVALUATION_SCHEMA_VERSION:
        raise BenchmarkManifestError(f"metric_schema_version must be {EVALUATION_SCHEMA_VERSION}")
    if manifest.get("binary_projection_id") != BINARY_PROJECTION_ID:
        raise BenchmarkManifestError("Run binary_projection_id must bind the current controlled projection")
    _require_utc_timestamp(manifest, "observed_at")
    _require_nonempty_string(manifest, "operator_role_ref")
    _require_clean_contamination_review(manifest)
    _require_sha256(manifest, "prediction_artifact_sha256")
    _require_sha256(manifest, "aggregate_result_sha256")
    if manifest.get("export_policy") != EXPORT_POLICY:
        raise BenchmarkManifestError(f"export_policy must be {EXPORT_POLICY}")
    _require_no_authority_escalation(manifest)
