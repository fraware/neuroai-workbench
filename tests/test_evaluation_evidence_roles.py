from __future__ import annotations

import copy

import pytest

from neuroai_workbench.benchmark_manifests import (
    APPROVED_G1_DISPOSITION_ID,
    APPROVED_G1_DISPOSITION_SHA256,
    HUMAN_REVIEW_REQUIRED_FIELDS,
    RIGHTS_CONTAINMENT_STATE,
    manifest_identity_sha256,
)
from neuroai_workbench.benchmark_packaging import load_packaged_public_contract
from neuroai_workbench.evaluation_benchmarks import (
    APPROVED_D1_CANONICAL_SHA256,
    BINARY_PROJECTION_ID,
    REQUIRED_BOUNDARY_DISPOSITIONS,
)
from neuroai_workbench.evaluation_evidence_roles import (
    CHALLENGE_CONSTRUCT_COVERAGE,
    CHALLENGE_SAMPLING_DESIGN,
    EVALUATION_PLAN_TYPE,
    FREEZE_BINDING_TYPE,
    NO_CROSS_ROLE_POOLING,
    POPULATION_PROBABILITY_AUDIT,
    PROBABILITY_SAMPLING_DESIGN,
    RUN_BINDING_TYPE,
    EvaluationEvidenceRoleError,
    evidence_binding_identity_sha256,
    evaluation_plan_identity_sha256,
    validate_component_run_binding,
    validate_evaluation_plan,
    validate_freeze_evaluation_binding,
)


def _public_contract(kind: str = "PATENT") -> dict[str, object]:
    contract = copy.deepcopy(load_packaged_public_contract(kind))
    contract["state"] = "FROZEN_COMMITMENTS_ONLY"
    contract["membership_commitment"] = "2" * 64
    contract["label_commitment"] = "3" * 64
    return contract


def _freeze(contract: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "0.2",
        "manifest_type": "BENCHMARK_FREEZE",
        "manifest_id": f"{contract['benchmark_kind']}-FREEZE-EVIDENCE-ROLE-SYNTHETIC",
        "benchmark_kind": contract["benchmark_kind"],
        "benchmark_id": contract["benchmark_id"],
        "public_contract_schema_version": "0.2",
        "public_contract_sha256": manifest_identity_sha256(contract),
        "d1_canonical_json_sha256": APPROVED_D1_CANONICAL_SHA256,
        "binary_projection_id": BINARY_PROJECTION_ID,
        "g1_disposition_id": APPROVED_G1_DISPOSITION_ID,
        "g1_disposition_sha256": APPROVED_G1_DISPOSITION_SHA256,
        "membership_commitment": contract["membership_commitment"],
        "label_commitment": contract["label_commitment"],
        "commitment_scheme": "HMAC_SHA256_DOMAIN_CANONICAL_JSON_V1",
        "s3_custody": True,
        "required_boundary_dispositions": sorted(REQUIRED_BOUNDARY_DISPOSITIONS),
        "boundary_disposition_counts": {
            "INCLUDE": 3,
            "EXCLUDE": 3,
            "BORDERLINE": 2,
            "ABSTAIN": 1,
            "UNRESOLVED_ADJUDICATION": 1,
        },
        "boundary_coverage_report_sha256": "4" * 64,
        "required_strata": sorted(contract["required_strata"]),
        "strata_coverage_report_sha256": "5" * 64,
        "sampling_protocol_id": "SAMPLE-PROTOCOL-EVIDENCE-ROLE-SYNTHETIC",
        "sampling_protocol_sha256": "6" * 64,
        "human_review_required_fields": sorted(HUMAN_REVIEW_REQUIRED_FIELDS),
        "human_review_provenance_sha256": "7" * 64,
        "adjudication_protocol_id": "ADJUDICATION-EVIDENCE-ROLE-SYNTHETIC",
        "adjudication_protocol_sha256": "8" * 64,
        "adjudication_accounting_sha256": "9" * 64,
        "double_label_subset_count": 4,
        "rights_containment_status": RIGHTS_CONTAINMENT_STATE,
        "rights_review_ref": "S3-RIGHTS-REVIEW-SYNTHETIC",
        "frozen_at": "2026-09-08T02:00:00Z",
        "lineage_state": "ROOT",
        "predecessor_manifest_sha256": None,
        "contamination_status": "NO_KNOWN_CONTAMINATION_REVIEWED",
        "exposure_register_ref": "S3-EXPOSURE-REGISTER-SYNTHETIC",
        "g2_passed": False,
        "canonical_s2_authority": False,
        "publication_authority": False,
        "assessment_effect": "NONE",
    }


def _run(freeze: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "0.2",
        "manifest_type": "HELD_OUT_EVALUATION_RUN",
        "run_id": "D3-RUN-EVIDENCE-ROLE-SYNTHETIC",
        "benchmark_kind": freeze["benchmark_kind"],
        "freeze_manifest_id": freeze["manifest_id"],
        "freeze_manifest_sha256": manifest_identity_sha256(freeze),
        "public_contract_sha256": freeze["public_contract_sha256"],
        "workbench_commit_sha": "a" * 40,
        "pipeline_id": "PIPELINE-SYNTHETIC",
        "pipeline_artifact_sha256": "b" * 64,
        "config_sha256": "c" * 64,
        "threshold_policy_id": "THRESHOLD-SYNTHETIC",
        "threshold_policy_sha256": "d" * 64,
        "abstention_policy_id": "ABSTENTION-SYNTHETIC",
        "abstention_policy_sha256": "e" * 64,
        "development_tuning_boundary": "HELD_OUT_NOT_USED_FOR_TUNING",
        "subgroup_plan_id": "SUBGROUP-SYNTHETIC",
        "subgroup_plan_sha256": "f" * 64,
        "metric_schema_version": "0.2",
        "binary_projection_id": BINARY_PROJECTION_ID,
        "observed_at": "2026-09-08T02:30:00Z",
        "operator_role_ref": "CONTROLLED_EVALUATION_OPERATOR",
        "contamination_status": "NO_KNOWN_CONTAMINATION_REVIEWED",
        "exposure_register_ref": "S3-EXPOSURE-REGISTER-SYNTHETIC",
        "prediction_artifact_sha256": "1" * 64,
        "aggregate_result_sha256": "a" * 64,
        "export_policy": "AGGREGATE_ONLY",
        "g2_passed": False,
        "canonical_s2_authority": False,
        "publication_authority": False,
        "assessment_effect": "NONE",
    }


def _challenge_component(contract: dict[str, object]) -> dict[str, object]:
    return {
        "component_id": "CHALLENGE-SYNTHETIC",
        "evidence_role": CHALLENGE_CONSTRUCT_COVERAGE,
        "population_generalizable": False,
        "metric_families": [
            "ABSTENTION",
            "BINARY_CLASSIFICATION",
            "FOUR_WAY_ROUTING",
            "SUBGROUP_DIAGNOSTIC",
        ],
        "diagnostic_targets": ["failure_mode_coverage", "routing_error_profile"],
        "sampling_design_type": CHALLENGE_SAMPLING_DESIGN,
        "required_strata": sorted(contract["required_strata"]),
        "challenge_enrichment": True,
        "population_frame_id": None,
        "inclusion_probability_manifest_sha256": None,
        "estimator_id": None,
        "uncertainty_method_id": None,
        "prevalence_reporting_allowed": False,
        "population_recall_reporting_allowed": False,
        "s3_design_custody": True,
    }


def _population_component() -> dict[str, object]:
    return {
        "component_id": "POPULATION-AUDIT-SYNTHETIC",
        "evidence_role": POPULATION_PROBABILITY_AUDIT,
        "population_generalizable": True,
        "metric_families": ["BINARY_CLASSIFICATION", "PREVALENCE", "RETRIEVAL_RECALL"],
        "population_estimands": [
            "include_prevalence_under_declared_frame",
            "query_retrieval_recall_under_declared_frame",
        ],
        "denominator_semantics": "Declared finite population frame bound by digest",
        "sampling_design_type": PROBABILITY_SAMPLING_DESIGN,
        "target_population_frame_id": "FRAME-SYNTHETIC",
        "target_population_frame_sha256": "1" * 64,
        "sampling_design_id": "PROBABILITY-DESIGN-SYNTHETIC",
        "sampling_design_sha256": "2" * 64,
        "inclusion_probability_manifest_sha256": "3" * 64,
        "estimator_id": "ESTIMATOR-SYNTHETIC",
        "estimator_sha256": "4" * 64,
        "uncertainty_method_id": "UNCERTAINTY-SYNTHETIC",
        "uncertainty_method_sha256": "5" * 64,
        "certainty_cells_allowed": True,
        "challenge_enrichment": False,
        "s3_design_custody": True,
    }


def _plan(contract: dict[str, object], *, include_population: bool = True) -> dict[str, object]:
    components: list[dict[str, object]] = [_challenge_component(contract)]
    if include_population:
        components.insert(0, _population_component())
    return {
        "schema_version": "0.1",
        "plan_type": EVALUATION_PLAN_TYPE,
        "plan_id": f"{contract['benchmark_kind']}-EVALUATION-PLAN-SYNTHETIC",
        "benchmark_kind": contract["benchmark_kind"],
        "benchmark_id": contract["benchmark_id"],
        "d1_canonical_json_sha256": APPROVED_D1_CANONICAL_SHA256,
        "binary_projection_id": BINARY_PROJECTION_ID,
        "required_strata": sorted(contract["required_strata"]),
        "components": components,
        "component_pooling_policy": NO_CROSS_ROLE_POOLING,
        "development_tuning_boundary": "HELD_OUT_NOT_USED_FOR_TUNING",
        "s3_design_custody": True,
        "g2_passed": False,
        "canonical_s2_authority": False,
        "publication_authority": False,
        "assessment_effect": "NONE",
    }


def _freeze_binding(freeze: dict[str, object], plan: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "0.3",
        "binding_type": FREEZE_BINDING_TYPE,
        "binding_id": "FREEZE-EVALUATION-BINDING-SYNTHETIC",
        "benchmark_kind": freeze["benchmark_kind"],
        "benchmark_id": freeze["benchmark_id"],
        "freeze_manifest_sha256": manifest_identity_sha256(freeze),
        "evaluation_plan_sha256": evaluation_plan_identity_sha256(plan),
        "bound_at": "2026-09-08T02:15:00Z",
        "g2_passed": False,
        "canonical_s2_authority": False,
        "publication_authority": False,
        "assessment_effect": "NONE",
    }


def _run_binding(
    run: dict[str, object],
    freeze_binding: dict[str, object],
    plan: dict[str, object],
    *,
    component_id: str,
) -> dict[str, object]:
    component = next(item for item in plan["components"] if item["component_id"] == component_id)
    return {
        "schema_version": "0.3",
        "binding_type": RUN_BINDING_TYPE,
        "binding_id": f"RUN-BINDING-{component_id}",
        "run_manifest_sha256": manifest_identity_sha256(run),
        "freeze_evaluation_binding_sha256": evidence_binding_identity_sha256(freeze_binding),
        "evaluation_plan_sha256": evaluation_plan_identity_sha256(plan),
        "component_id": component_id,
        "evidence_role": component["evidence_role"],
        "aggregate_result_sha256": run["aggregate_result_sha256"],
        "population_generalizable": component["population_generalizable"],
        "cross_role_pooling": False,
        "export_policy": "AGGREGATE_ONLY",
        "bound_at": "2026-09-08T02:45:00Z",
        "g2_passed": False,
        "canonical_s2_authority": False,
        "publication_authority": False,
        "assessment_effect": "NONE",
    }


@pytest.mark.parametrize("kind", ["PATENT", "PRODUCT"])
def test_challenge_only_plan_is_valid_for_both_benchmark_kinds(kind: str) -> None:
    contract = _public_contract(kind)
    validate_evaluation_plan(_plan(contract, include_population=False))


def test_probability_and_challenge_components_are_valid_when_explicitly_separated() -> None:
    contract = _public_contract("PATENT")
    validate_evaluation_plan(_plan(contract))


def test_population_generalization_requires_complete_probability_design_binding() -> None:
    contract = _public_contract()
    for field in (
        "target_population_frame_sha256",
        "sampling_design_sha256",
        "inclusion_probability_manifest_sha256",
        "estimator_sha256",
        "uncertainty_method_sha256",
    ):
        plan = _plan(contract)
        population = plan["components"][0]
        population[field] = None
        with pytest.raises(EvaluationEvidenceRoleError, match=field):
            validate_evaluation_plan(plan)


def test_probability_component_cannot_use_challenge_enrichment() -> None:
    contract = _public_contract()
    plan = _plan(contract)
    plan["components"][0]["challenge_enrichment"] = True
    with pytest.raises(EvaluationEvidenceRoleError, match="challenge-enriched"):
        validate_evaluation_plan(plan)


def test_challenge_component_cannot_claim_population_generalizability() -> None:
    contract = _public_contract()
    plan = _plan(contract, include_population=False)
    plan["components"][0]["population_generalizable"] = True
    with pytest.raises(EvaluationEvidenceRoleError, match="population_generalizable=false"):
        validate_evaluation_plan(plan)


def test_challenge_component_cannot_smuggle_population_inference_fields() -> None:
    contract = _public_contract()
    for field, value in (
        ("population_frame_id", "FRAME-ILLEGAL"),
        ("inclusion_probability_manifest_sha256", "1" * 64),
        ("estimator_id", "ESTIMATOR-ILLEGAL"),
        ("uncertainty_method_id", "UNCERTAINTY-ILLEGAL"),
    ):
        plan = _plan(contract, include_population=False)
        plan["components"][0][field] = value
        with pytest.raises(EvaluationEvidenceRoleError, match=field):
            validate_evaluation_plan(plan)


def test_challenge_component_rejects_population_only_metrics() -> None:
    contract = _public_contract()
    plan = _plan(contract, include_population=False)
    plan["components"][0]["metric_families"] = ["BINARY_CLASSIFICATION", "PREVALENCE"]
    with pytest.raises(EvaluationEvidenceRoleError, match="unsupported"):
        validate_evaluation_plan(plan)


def test_cross_role_pooling_policy_is_fail_closed() -> None:
    contract = _public_contract()
    plan = _plan(contract)
    plan["component_pooling_policy"] = "POOL_ALL_RESULTS"
    with pytest.raises(EvaluationEvidenceRoleError, match=NO_CROSS_ROLE_POOLING):
        validate_evaluation_plan(plan)


def test_freeze_binding_is_exactly_bound_to_plan_and_freeze() -> None:
    contract = _public_contract()
    freeze = _freeze(contract)
    plan = _plan(contract)
    binding = _freeze_binding(freeze, plan)
    validate_freeze_evaluation_binding(
        binding,
        freeze_manifest=freeze,
        public_contract=contract,
        evaluation_plan=plan,
    )

    changed = copy.deepcopy(plan)
    changed["plan_id"] = "CHANGED-PLAN"
    with pytest.raises(EvaluationEvidenceRoleError, match="evaluation_plan_sha256"):
        validate_freeze_evaluation_binding(
            binding,
            freeze_manifest=freeze,
            public_contract=contract,
            evaluation_plan=changed,
        )


def test_component_run_binding_cannot_switch_role_or_component_after_freeze() -> None:
    contract = _public_contract()
    freeze = _freeze(contract)
    run = _run(freeze)
    plan = _plan(contract)
    freeze_binding = _freeze_binding(freeze, plan)
    run_binding = _run_binding(
        run,
        freeze_binding,
        plan,
        component_id="CHALLENGE-SYNTHETIC",
    )
    validate_component_run_binding(
        run_binding,
        run_manifest=run,
        freeze_manifest=freeze,
        freeze_evaluation_binding=freeze_binding,
        public_contract=contract,
        evaluation_plan=plan,
    )

    run_binding["evidence_role"] = POPULATION_PROBABILITY_AUDIT
    with pytest.raises(EvaluationEvidenceRoleError, match="evidence_role"):
        validate_component_run_binding(
            run_binding,
            run_manifest=run,
            freeze_manifest=freeze,
            freeze_evaluation_binding=freeze_binding,
            public_contract=contract,
            evaluation_plan=plan,
        )


def test_component_run_binding_rejects_cross_role_pooling_and_authority_escalation() -> None:
    contract = _public_contract()
    freeze = _freeze(contract)
    run = _run(freeze)
    plan = _plan(contract)
    freeze_binding = _freeze_binding(freeze, plan)

    binding = _run_binding(run, freeze_binding, plan, component_id="POPULATION-AUDIT-SYNTHETIC")
    binding["cross_role_pooling"] = True
    with pytest.raises(EvaluationEvidenceRoleError, match="cross_role_pooling"):
        validate_component_run_binding(
            binding,
            run_manifest=run,
            freeze_manifest=freeze,
            freeze_evaluation_binding=freeze_binding,
            public_contract=contract,
            evaluation_plan=plan,
        )

    binding = _run_binding(run, freeze_binding, plan, component_id="POPULATION-AUDIT-SYNTHETIC")
    binding["g2_passed"] = True
    with pytest.raises(EvaluationEvidenceRoleError, match="g2_passed"):
        validate_component_run_binding(
            binding,
            run_manifest=run,
            freeze_manifest=freeze,
            freeze_evaluation_binding=freeze_binding,
            public_contract=contract,
            evaluation_plan=plan,
        )


def test_component_run_binding_requires_aggregate_result_identity() -> None:
    contract = _public_contract()
    freeze = _freeze(contract)
    run = _run(freeze)
    plan = _plan(contract)
    freeze_binding = _freeze_binding(freeze, plan)
    binding = _run_binding(run, freeze_binding, plan, component_id="CHALLENGE-SYNTHETIC")
    binding["aggregate_result_sha256"] = "0" * 64
    with pytest.raises(EvaluationEvidenceRoleError, match="aggregate_result_sha256"):
        validate_component_run_binding(
            binding,
            run_manifest=run,
            freeze_manifest=freeze,
            freeze_evaluation_binding=freeze_binding,
            public_contract=contract,
            evaluation_plan=plan,
        )


def test_evidence_role_identities_are_deterministic() -> None:
    contract = _public_contract()
    plan = _plan(contract)
    assert evaluation_plan_identity_sha256(plan) == evaluation_plan_identity_sha256(copy.deepcopy(plan))

    freeze = _freeze(contract)
    binding = _freeze_binding(freeze, plan)
    assert evidence_binding_identity_sha256(binding) == evidence_binding_identity_sha256(copy.deepcopy(binding))
