from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from neuroai_workbench.benchmark_manifests import (
    DEV_TUNING_BOUNDARY,
    BenchmarkManifestError,
    manifest_identity_sha256,
    validate_freeze_manifest,
    validate_held_out_run_manifest,
)
from neuroai_workbench.evaluation_benchmarks import (
    APPROVED_D1_CANONICAL_SHA256,
    BENCHMARK_KINDS,
    BINARY_PROJECTION_ID,
    REQUIRED_STRATA,
    canonical_json_bytes,
)

EVALUATION_PLAN_SCHEMA_VERSION = "0.1"
EVIDENCE_BINDING_SCHEMA_VERSION = "0.3"
EVALUATION_PLAN_TYPE = "BENCHMARK_EVALUATION_PLAN"
FREEZE_BINDING_TYPE = "BENCHMARK_FREEZE_EVALUATION_BINDING"
RUN_BINDING_TYPE = "HELD_OUT_EVALUATION_COMPONENT_BINDING"

POPULATION_PROBABILITY_AUDIT = "POPULATION_PROBABILITY_AUDIT"
CHALLENGE_CONSTRUCT_COVERAGE = "CHALLENGE_CONSTRUCT_COVERAGE"
EVIDENCE_ROLES = frozenset({POPULATION_PROBABILITY_AUDIT, CHALLENGE_CONSTRUCT_COVERAGE})

PROBABILITY_SAMPLING_DESIGN = "PROBABILITY"
CHALLENGE_SAMPLING_DESIGN = "NONPROBABILITY_CHALLENGE"
NO_CROSS_ROLE_POOLING = "NO_CROSS_ROLE_POOLING"
AGGREGATE_ONLY = "AGGREGATE_ONLY"

POPULATION_METRIC_FAMILIES = frozenset(
    {
        "BINARY_CLASSIFICATION",
        "FOUR_WAY_ROUTING",
        "ABSTENTION",
        "SUBGROUP_DIAGNOSTIC",
        "CALIBRATION",
        "PREVALENCE",
        "RETRIEVAL_RECALL",
    }
)
CHALLENGE_METRIC_FAMILIES = frozenset(
    {
        "BINARY_CLASSIFICATION",
        "FOUR_WAY_ROUTING",
        "ABSTENTION",
        "SUBGROUP_DIAGNOSTIC",
        "CALIBRATION",
    }
)
POPULATION_ONLY_METRIC_FAMILIES = frozenset({"PREVALENCE", "RETRIEVAL_RECALL"})

_PLAN_FIELDS = frozenset(
    {
        "schema_version",
        "plan_type",
        "plan_id",
        "benchmark_kind",
        "benchmark_id",
        "d1_canonical_json_sha256",
        "binary_projection_id",
        "required_strata",
        "components",
        "component_pooling_policy",
        "development_tuning_boundary",
        "s3_design_custody",
        "g2_passed",
        "canonical_s2_authority",
        "publication_authority",
        "assessment_effect",
    }
)

_POPULATION_COMPONENT_FIELDS = frozenset(
    {
        "component_id",
        "evidence_role",
        "population_generalizable",
        "metric_families",
        "population_estimands",
        "denominator_semantics",
        "sampling_design_type",
        "target_population_frame_id",
        "target_population_frame_sha256",
        "sampling_design_id",
        "sampling_design_sha256",
        "inclusion_probability_manifest_sha256",
        "estimator_id",
        "estimator_sha256",
        "uncertainty_method_id",
        "uncertainty_method_sha256",
        "certainty_cells_allowed",
        "challenge_enrichment",
        "s3_design_custody",
    }
)

_CHALLENGE_COMPONENT_FIELDS = frozenset(
    {
        "component_id",
        "evidence_role",
        "population_generalizable",
        "metric_families",
        "diagnostic_targets",
        "sampling_design_type",
        "required_strata",
        "challenge_enrichment",
        "population_frame_id",
        "inclusion_probability_manifest_sha256",
        "estimator_id",
        "uncertainty_method_id",
        "prevalence_reporting_allowed",
        "population_recall_reporting_allowed",
        "s3_design_custody",
    }
)

_FREEZE_BINDING_FIELDS = frozenset(
    {
        "schema_version",
        "binding_type",
        "binding_id",
        "benchmark_kind",
        "benchmark_id",
        "freeze_manifest_sha256",
        "evaluation_plan_sha256",
        "bound_at",
        "g2_passed",
        "canonical_s2_authority",
        "publication_authority",
        "assessment_effect",
    }
)

_RUN_BINDING_FIELDS = frozenset(
    {
        "schema_version",
        "binding_type",
        "binding_id",
        "run_manifest_sha256",
        "freeze_evaluation_binding_sha256",
        "evaluation_plan_sha256",
        "component_id",
        "evidence_role",
        "aggregate_result_sha256",
        "population_generalizable",
        "cross_role_pooling",
        "export_policy",
        "bound_at",
        "g2_passed",
        "canonical_s2_authority",
        "publication_authority",
        "assessment_effect",
    }
)


class EvaluationEvidenceRoleError(BenchmarkManifestError):
    """Raised when an evaluation plan or evidence-role binding is invalid."""


def evaluation_plan_identity_sha256(plan: Mapping[str, Any]) -> str:
    """Return a deterministic digest for an exact evaluation plan."""

    return hashlib.sha256(canonical_json_bytes(plan)).hexdigest()


def evidence_binding_identity_sha256(binding: Mapping[str, Any]) -> str:
    """Return a deterministic digest for an exact evidence-role binding."""

    return hashlib.sha256(canonical_json_bytes(binding)).hexdigest()


def _require_exact_fields(value: Mapping[str, Any], expected: frozenset[str], name: str) -> None:
    missing = expected - set(value)
    unexpected = set(value) - expected
    if missing:
        raise EvaluationEvidenceRoleError(f"{name} is missing required fields: {sorted(missing)}")
    if unexpected:
        raise EvaluationEvidenceRoleError(f"{name} contains unsupported fields: {sorted(unexpected)}")


def _require_nonempty_string(value: Mapping[str, Any], field: str) -> str:
    item = value.get(field)
    if not isinstance(item, str) or not item.strip():
        raise EvaluationEvidenceRoleError(f"{field} must be a non-empty string")
    return item


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _require_sha256(value: Mapping[str, Any], field: str) -> str:
    item = value.get(field)
    if not _is_sha256(item):
        raise EvaluationEvidenceRoleError(f"{field} must be a 64-character SHA-256 hex digest")
    assert isinstance(item, str)
    return item


def _require_utc_timestamp(value: Mapping[str, Any], field: str) -> None:
    item = _require_nonempty_string(value, field)
    try:
        parsed = datetime.fromisoformat(item.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvaluationEvidenceRoleError(f"{field} must be an RFC 3339 timestamp") from exc
    offset = parsed.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise EvaluationEvidenceRoleError(f"{field} must be expressed in UTC")


def _require_string_list(value: Any, field: str, *, nonempty: bool = True) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise EvaluationEvidenceRoleError(f"{field} must be a list of non-empty strings")
    if len(value) != len(set(value)):
        raise EvaluationEvidenceRoleError(f"{field} must not contain duplicates")
    if nonempty and not value:
        raise EvaluationEvidenceRoleError(f"{field} must not be empty")
    return value


def _require_exact_string_set(value: Any, expected: frozenset[str], field: str) -> None:
    items = _require_string_list(value, field)
    if set(items) != expected:
        raise EvaluationEvidenceRoleError(f"{field} must contain exactly {sorted(expected)}")


def _require_no_authority_escalation(value: Mapping[str, Any]) -> None:
    if value.get("g2_passed") is not False:
        raise EvaluationEvidenceRoleError("g2_passed must remain false in PRE-G2 evidence-role contracts")
    if value.get("canonical_s2_authority") is not False:
        raise EvaluationEvidenceRoleError("canonical_s2_authority must remain false")
    if value.get("publication_authority") is not False:
        raise EvaluationEvidenceRoleError("publication_authority must remain false")
    if value.get("assessment_effect") != "NONE":
        raise EvaluationEvidenceRoleError("assessment_effect must be NONE")


def _validate_metric_families(value: Any, *, role: str) -> None:
    items = set(_require_string_list(value, "metric_families"))
    allowed = POPULATION_METRIC_FAMILIES if role == POPULATION_PROBABILITY_AUDIT else CHALLENGE_METRIC_FAMILIES
    unsupported = items - allowed
    if unsupported:
        raise EvaluationEvidenceRoleError(
            f"metric_families contains metrics unsupported for {role}: {sorted(unsupported)}"
        )
    if role == CHALLENGE_CONSTRUCT_COVERAGE and items & POPULATION_ONLY_METRIC_FAMILIES:
        raise EvaluationEvidenceRoleError(
            "Challenge components cannot report prevalence or population retrieval recall"
        )


def _validate_population_component(component: Mapping[str, Any]) -> None:
    _require_exact_fields(component, _POPULATION_COMPONENT_FIELDS, "population component")
    _require_nonempty_string(component, "component_id")
    if component.get("evidence_role") != POPULATION_PROBABILITY_AUDIT:
        raise EvaluationEvidenceRoleError(f"population component evidence_role must be {POPULATION_PROBABILITY_AUDIT}")
    if component.get("population_generalizable") is not True:
        raise EvaluationEvidenceRoleError(
            "Probability-audit components must explicitly set population_generalizable=true"
        )
    _validate_metric_families(component.get("metric_families"), role=POPULATION_PROBABILITY_AUDIT)
    _require_string_list(component.get("population_estimands"), "population_estimands")
    _require_nonempty_string(component, "denominator_semantics")
    if component.get("sampling_design_type") != PROBABILITY_SAMPLING_DESIGN:
        raise EvaluationEvidenceRoleError(f"sampling_design_type must be {PROBABILITY_SAMPLING_DESIGN}")
    _require_nonempty_string(component, "target_population_frame_id")
    _require_sha256(component, "target_population_frame_sha256")
    _require_nonempty_string(component, "sampling_design_id")
    _require_sha256(component, "sampling_design_sha256")
    _require_sha256(component, "inclusion_probability_manifest_sha256")
    _require_nonempty_string(component, "estimator_id")
    _require_sha256(component, "estimator_sha256")
    _require_nonempty_string(component, "uncertainty_method_id")
    _require_sha256(component, "uncertainty_method_sha256")
    if not isinstance(component.get("certainty_cells_allowed"), bool):
        raise EvaluationEvidenceRoleError("certainty_cells_allowed must be a boolean")
    if component.get("challenge_enrichment") is not False:
        raise EvaluationEvidenceRoleError("Population probability-audit components cannot be challenge-enriched")
    if component.get("s3_design_custody") is not True:
        raise EvaluationEvidenceRoleError("Population sampling/weight evidence must remain in controlled S3")


def _validate_challenge_component(component: Mapping[str, Any], *, benchmark_kind: str) -> None:
    _require_exact_fields(component, _CHALLENGE_COMPONENT_FIELDS, "challenge component")
    _require_nonempty_string(component, "component_id")
    if component.get("evidence_role") != CHALLENGE_CONSTRUCT_COVERAGE:
        raise EvaluationEvidenceRoleError(f"challenge component evidence_role must be {CHALLENGE_CONSTRUCT_COVERAGE}")
    if component.get("population_generalizable") is not False:
        raise EvaluationEvidenceRoleError("Challenge components must explicitly set population_generalizable=false")
    _validate_metric_families(component.get("metric_families"), role=CHALLENGE_CONSTRUCT_COVERAGE)
    _require_string_list(component.get("diagnostic_targets"), "diagnostic_targets")
    if component.get("sampling_design_type") != CHALLENGE_SAMPLING_DESIGN:
        raise EvaluationEvidenceRoleError(f"sampling_design_type must be {CHALLENGE_SAMPLING_DESIGN}")
    _require_exact_string_set(component.get("required_strata"), REQUIRED_STRATA[benchmark_kind], "required_strata")
    if component.get("challenge_enrichment") is not True:
        raise EvaluationEvidenceRoleError("Challenge components must explicitly declare challenge_enrichment=true")
    for field in (
        "population_frame_id",
        "inclusion_probability_manifest_sha256",
        "estimator_id",
        "uncertainty_method_id",
    ):
        if component.get(field) is not None:
            raise EvaluationEvidenceRoleError(f"Challenge component {field} must be null")
    if component.get("prevalence_reporting_allowed") is not False:
        raise EvaluationEvidenceRoleError("Challenge components cannot authorize prevalence reporting")
    if component.get("population_recall_reporting_allowed") is not False:
        raise EvaluationEvidenceRoleError("Challenge components cannot authorize population recall reporting")
    if component.get("s3_design_custody") is not True:
        raise EvaluationEvidenceRoleError("Challenge membership/design evidence must remain in controlled S3")


def validate_evaluation_plan(plan: Mapping[str, Any]) -> None:
    """Validate a PRE-G2 evaluation plan without reading private benchmark evidence.

    Structural validation proves only that population-generalized claims are
    bound to a declared probability design and that challenge evidence is
    explicitly non-generalizable. It does not validate an estimator, sampling
    probabilities, human labels, benchmark adequacy, or scientific truth.
    """

    _require_exact_fields(plan, _PLAN_FIELDS, "evaluation plan")
    if plan.get("schema_version") != EVALUATION_PLAN_SCHEMA_VERSION:
        raise EvaluationEvidenceRoleError(f"schema_version must be {EVALUATION_PLAN_SCHEMA_VERSION}")
    if plan.get("plan_type") != EVALUATION_PLAN_TYPE:
        raise EvaluationEvidenceRoleError(f"plan_type must be {EVALUATION_PLAN_TYPE}")
    _require_nonempty_string(plan, "plan_id")

    benchmark_kind = plan.get("benchmark_kind")
    if benchmark_kind not in BENCHMARK_KINDS:
        raise EvaluationEvidenceRoleError(f"benchmark_kind must be one of {sorted(BENCHMARK_KINDS)}")
    assert isinstance(benchmark_kind, str)
    _require_nonempty_string(plan, "benchmark_id")
    if plan.get("d1_canonical_json_sha256") != APPROVED_D1_CANONICAL_SHA256:
        raise EvaluationEvidenceRoleError("Evaluation plan must bind the exact approved D1 canonical digest")
    if plan.get("binary_projection_id") != BINARY_PROJECTION_ID:
        raise EvaluationEvidenceRoleError("Evaluation plan must bind the current controlled binary projection")
    _require_exact_string_set(plan.get("required_strata"), REQUIRED_STRATA[benchmark_kind], "required_strata")

    components = plan.get("components")
    if not isinstance(components, list) or not components:
        raise EvaluationEvidenceRoleError("components must be a non-empty list")
    ids: set[str] = set()
    for component in components:
        if not isinstance(component, Mapping):
            raise EvaluationEvidenceRoleError("Every evaluation component must be an object")
        role = component.get("evidence_role")
        if role not in EVIDENCE_ROLES:
            raise EvaluationEvidenceRoleError(f"evidence_role must be one of {sorted(EVIDENCE_ROLES)}")
        if role == POPULATION_PROBABILITY_AUDIT:
            _validate_population_component(component)
        else:
            _validate_challenge_component(component, benchmark_kind=benchmark_kind)
        component_id = component["component_id"]
        assert isinstance(component_id, str)
        if component_id in ids:
            raise EvaluationEvidenceRoleError("component_id values must be unique")
        ids.add(component_id)

    if plan.get("component_pooling_policy") != NO_CROSS_ROLE_POOLING:
        raise EvaluationEvidenceRoleError(f"component_pooling_policy must be {NO_CROSS_ROLE_POOLING}")
    if plan.get("development_tuning_boundary") != DEV_TUNING_BOUNDARY:
        raise EvaluationEvidenceRoleError("development_tuning_boundary must preserve held-out isolation from tuning")
    if plan.get("s3_design_custody") is not True:
        raise EvaluationEvidenceRoleError("Evaluation design evidence must remain in controlled S3")
    _require_no_authority_escalation(plan)


def _component_by_id(plan: Mapping[str, Any], component_id: str) -> Mapping[str, Any]:
    components = plan.get("components")
    assert isinstance(components, list)
    for component in components:
        if isinstance(component, Mapping) and component.get("component_id") == component_id:
            return component
    raise EvaluationEvidenceRoleError("component_id is not present in the bound evaluation plan")


def validate_freeze_evaluation_binding(
    binding: Mapping[str, Any],
    *,
    freeze_manifest: Mapping[str, Any],
    public_contract: Mapping[str, Any],
    evaluation_plan: Mapping[str, Any],
) -> None:
    """Bind an exact v0.2 freeze to an exact predeclared evaluation plan."""

    _require_exact_fields(binding, _FREEZE_BINDING_FIELDS, "freeze evaluation binding")
    validate_freeze_manifest(freeze_manifest, public_contract=public_contract)
    validate_evaluation_plan(evaluation_plan)
    if binding.get("schema_version") != EVIDENCE_BINDING_SCHEMA_VERSION:
        raise EvaluationEvidenceRoleError(f"schema_version must be {EVIDENCE_BINDING_SCHEMA_VERSION}")
    if binding.get("binding_type") != FREEZE_BINDING_TYPE:
        raise EvaluationEvidenceRoleError(f"binding_type must be {FREEZE_BINDING_TYPE}")
    _require_nonempty_string(binding, "binding_id")
    if binding.get("benchmark_kind") != freeze_manifest.get("benchmark_kind"):
        raise EvaluationEvidenceRoleError("Freeze binding benchmark_kind must match the freeze manifest")
    if binding.get("benchmark_id") != freeze_manifest.get("benchmark_id"):
        raise EvaluationEvidenceRoleError("Freeze binding benchmark_id must match the freeze manifest")
    if evaluation_plan.get("benchmark_kind") != freeze_manifest.get("benchmark_kind"):
        raise EvaluationEvidenceRoleError("Evaluation plan benchmark_kind must match the freeze manifest")
    if evaluation_plan.get("benchmark_id") != freeze_manifest.get("benchmark_id"):
        raise EvaluationEvidenceRoleError("Evaluation plan benchmark_id must match the freeze manifest")
    if binding.get("freeze_manifest_sha256") != manifest_identity_sha256(freeze_manifest):
        raise EvaluationEvidenceRoleError("freeze_manifest_sha256 does not bind the supplied freeze manifest")
    if binding.get("evaluation_plan_sha256") != evaluation_plan_identity_sha256(evaluation_plan):
        raise EvaluationEvidenceRoleError("evaluation_plan_sha256 does not bind the supplied evaluation plan")
    _require_utc_timestamp(binding, "bound_at")
    _require_no_authority_escalation(binding)


def validate_component_run_binding(
    binding: Mapping[str, Any],
    *,
    run_manifest: Mapping[str, Any],
    freeze_manifest: Mapping[str, Any],
    freeze_evaluation_binding: Mapping[str, Any],
    public_contract: Mapping[str, Any],
    evaluation_plan: Mapping[str, Any],
) -> None:
    """Bind one aggregate held-out result to one explicit evidence role."""

    _require_exact_fields(binding, _RUN_BINDING_FIELDS, "component run binding")
    validate_held_out_run_manifest(
        run_manifest,
        freeze_manifest=freeze_manifest,
        public_contract=public_contract,
    )
    validate_freeze_evaluation_binding(
        freeze_evaluation_binding,
        freeze_manifest=freeze_manifest,
        public_contract=public_contract,
        evaluation_plan=evaluation_plan,
    )
    if binding.get("schema_version") != EVIDENCE_BINDING_SCHEMA_VERSION:
        raise EvaluationEvidenceRoleError(f"schema_version must be {EVIDENCE_BINDING_SCHEMA_VERSION}")
    if binding.get("binding_type") != RUN_BINDING_TYPE:
        raise EvaluationEvidenceRoleError(f"binding_type must be {RUN_BINDING_TYPE}")
    _require_nonempty_string(binding, "binding_id")
    if binding.get("run_manifest_sha256") != manifest_identity_sha256(run_manifest):
        raise EvaluationEvidenceRoleError("run_manifest_sha256 does not bind the supplied run manifest")
    if binding.get("freeze_evaluation_binding_sha256") != evidence_binding_identity_sha256(freeze_evaluation_binding):
        raise EvaluationEvidenceRoleError(
            "freeze_evaluation_binding_sha256 does not bind the supplied freeze evaluation binding"
        )
    if binding.get("evaluation_plan_sha256") != evaluation_plan_identity_sha256(evaluation_plan):
        raise EvaluationEvidenceRoleError("Run evaluation_plan_sha256 does not match the bound evaluation plan")

    component_id = _require_nonempty_string(binding, "component_id")
    component = _component_by_id(evaluation_plan, component_id)
    evidence_role = component.get("evidence_role")
    if binding.get("evidence_role") != evidence_role:
        raise EvaluationEvidenceRoleError("Run evidence_role must match the selected evaluation-plan component")
    if binding.get("population_generalizable") is not component.get("population_generalizable"):
        raise EvaluationEvidenceRoleError(
            "Run population_generalizable must match the selected evaluation-plan component"
        )
    if binding.get("aggregate_result_sha256") != run_manifest.get("aggregate_result_sha256"):
        raise EvaluationEvidenceRoleError("aggregate_result_sha256 must match the underlying held-out run")
    if binding.get("cross_role_pooling") is not False:
        raise EvaluationEvidenceRoleError("cross_role_pooling must remain false")
    if binding.get("export_policy") != AGGREGATE_ONLY:
        raise EvaluationEvidenceRoleError(f"export_policy must be {AGGREGATE_ONLY}")
    _require_utc_timestamp(binding, "bound_at")
    _require_no_authority_escalation(binding)
