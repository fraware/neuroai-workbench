from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

import neuroai_workbench.validation_study as study
from neuroai_workbench.validation_study import (
    AMENDMENT_BOUNDARY,
    CASE_BOUNDARY,
    DECISION_STATE_COMPATIBILITY,
    PARAMETER_BOUNDARY,
    REQUIRED_ESTIMAND_FAMILIES,
    case_manifest_sha256,
    current_v42_normative_identity,
    finalize_case_manifest,
    finalize_protocol_amendment,
    finalize_study_parameter_set,
    load_case_manifests,
    load_validation_record,
    protocol_amendment_sha256,
    study_parameter_set_sha256,
    validate_case_manifest,
    validate_case_manifest_file,
    validate_protocol_amendment,
    validate_protocol_amendment_file,
    validate_study_parameter_set,
    validate_study_parameter_set_file,
)

COMMIT = "a0ab966679187c50fb5adccd7f0cc31dff7ac2d1"


def _ref(name: str, digest: str = "a" * 64, *, protected: bool = False) -> dict[str, str]:
    prefix = "protected-ref:" if protected else "public-ref:"
    return {"reference": prefix + name, "sha256": digest}


def _case(case_id: str, stratum: str, *, protected: bool = False) -> dict[str, Any]:
    evidence_ref = "protected-ref:case/evidence" if protected else "public-ref:case/evidence"
    value: dict[str, Any] = {
        "schema_version": "1",
        "manifest_id": f"VALCASE-{case_id}",
        "study_wave_id": "VAL-WAVE-1",
        "case_id": case_id,
        "case_class_id": stratum,
        "calibration_status": "HELD_OUT",
        "normative_identity": current_v42_normative_identity(COMMIT),
        "case_instructions": _ref(f"cases/{case_id}/instructions", "b" * 64),
        "evidence_manifest": _ref(f"cases/{case_id}/evidence-manifest", "c" * 64),
        "evidence_objects": [
            {
                "evidence_id": f"EVID-{case_id}-1",
                "access": "PROTECTED" if protected else "PUBLIC",
                "reference": evidence_ref,
                "sha256": "d" * 64,
            }
        ],
        "evidence_access_rules": "TEST FIXTURE ONLY. Use only the frozen evidence universe.",
        "public_private_boundary": "MIXED_WITH_PROTECTED_REFERENCES" if protected else "PUBLIC_ONLY",
        "boundary": CASE_BOUNDARY,
    }
    return finalize_case_manifest(value)


def _estimands() -> list[dict[str, Any]]:
    rows = []
    for family in sorted(REQUIRED_ESTIMAND_FAMILIES):
        row: dict[str, Any] = {
            "field_family": family,
            "population": "TEST FIXTURE ONLY. Frozen assigned judgments.",
            "primary_estimate": "TEST FIXTURE ONLY. Prespecified agreement estimate.",
            "robustness_estimate": "TEST FIXTURE ONLY. Prespecified robustness estimate.",
            "distance_or_weights": "TEST FIXTURE ONLY. Frozen distance function.",
            "structural_state_handling": "TEST FIXTURE ONLY. Structural states remain categorical.",
            "clustering_units": ["CASE", "ASSESSOR"],
            "uncertainty_method": "TEST FIXTURE ONLY. Multiway case and assessor cluster bootstrap.",
        }
        if family == "REQUIREMENT_FINDING":
            row["excluded_structural_states"] = ["NOT ASSESSED"]
        rows.append(row)
    return rows


def _consequential() -> list[dict[str, Any]]:
    interval = "TEST FIXTURE ONLY. Case/assessor clustered interval."
    return [
        {
            "rule_id": "REQ-PASS-FAIL",
            "field_family": "REQUIREMENT_FINDING",
            "comparison_mode": "STATE_PAIR",
            "left_state": "PASS",
            "right_state": "FAIL",
            "denominator": "Requirements jointly substantively assessed by the compared assessors.",
            "interval_method": interval,
        },
        {
            "rule_id": "CLAIM-SUPPORTED-UNSUPPORTED",
            "field_family": "CLAIM_STATUS",
            "comparison_mode": "STATE_PAIR",
            "left_state": "SUPPORTED WITHIN BOUNDED SCOPE",
            "right_state": "UNSUPPORTED",
            "denominator": "Claims jointly reviewable by the compared assessors.",
            "interval_method": interval,
        },
        {
            "rule_id": "CLAIM-SUPPORTED-CONTRADICTED",
            "field_family": "CLAIM_STATUS",
            "comparison_mode": "STATE_PAIR",
            "left_state": "SUPPORTED WITHIN BOUNDED SCOPE",
            "right_state": "CONTRADICTED",
            "denominator": "Claims jointly reviewable by the compared assessors.",
            "interval_method": interval,
        },
        {
            "rule_id": "AUTHORIZATION",
            "field_family": "TYPED_DECISION",
            "decision_object_type": "LEGAL OR REGULATORY AUTHORIZATION",
            "comparison_mode": "STATE_PAIR",
            "left_state": "AUTHORIZED WITHIN BOUNDED SCOPE",
            "right_state": "NOT AUTHORIZED",
            "denominator": "Cases where legal or regulatory authorization is genuinely in study scope.",
            "interval_method": interval,
        },
        {
            "rule_id": "CONFORMANCE",
            "field_family": "TYPED_DECISION",
            "decision_object_type": "CONFORMANCE DECISION",
            "comparison_mode": "STATE_PAIR",
            "left_state": "CONFORMS FOR BOUNDED SCOPE",
            "right_state": "NO CONFORMANCE DECISION — BLOCKED",
            "denominator": "Cases where conformance decision is in scope.",
            "interval_method": interval,
        },
        {
            "rule_id": "PROHIBITED-PRESENCE",
            "field_family": "TYPED_DECISION",
            "decision_object_type": "PROHIBITED-USE DECISION",
            "comparison_mode": "PRESENCE_ABSENCE",
            "left_state": "PROHIBITED OR DISPROPORTIONATE USE",
            "denominator": "Cases where prohibited-use evaluation is required by the frozen case design.",
            "interval_method": interval,
        },
        {
            "rule_id": "REOPENING-PRESENCE",
            "field_family": "TYPED_DECISION",
            "decision_object_type": "REOPENING DECISION",
            "comparison_mode": "PRESENCE_ABSENCE",
            "left_state": "REOPENED",
            "denominator": "Cases containing a frozen reopening trigger condition.",
            "interval_method": interval,
        },
    ]


def _parameter(cases: dict[str, dict[str, Any]]) -> dict[str, Any]:
    case_rows = [
        {
            "case_id": case_id,
            "case_class_id": manifest["case_class_id"],
            "manifest_reference": f"public-ref:validation/cases/{case_id}.json",
            "manifest_sha256": manifest["manifest_sha256"],
            "calibration_status": manifest["calibration_status"],
        }
        for case_id, manifest in sorted(cases.items())
    ]
    counts: dict[str, int] = {"STRATUM-A": 0, "STRATUM-B": 0}
    for row in case_rows:
        counts[row["case_class_id"]] += 1
    value: dict[str, Any] = {
        "schema_version": "1",
        "parameter_set_id": "VALPARAM-WAVE-1",
        "study_wave_id": "VAL-WAVE-1",
        "frozen_at": "2026-08-18T00:00:00Z",
        "outcome_access_state": "NO_OUTCOME_DATA_ACCESSED",
        "protocol_reference": _ref("docs/evaluation/assessment-validation-protocol.md", "e" * 64),
        "normative_identity": current_v42_normative_identity(COMMIT),
        "analysis_identity": {
            "code_reference": _ref("validation/analysis-code", "f" * 64),
            "environment_reference": _ref("validation/environment", "1" * 64),
            "random_seeds": [17, 29],
        },
        "case_strata": [
            {
                "stratum_id": "STRATUM-A",
                "rationale": "TEST FIXTURE ONLY. First materially distinct context class.",
                "inclusion_criteria": ["TEST FIXTURE ONLY. Meets stratum A definition."],
                "exclusion_criteria": ["TEST FIXTURE ONLY. Fails evidence-freeze requirements."],
            },
            {
                "stratum_id": "STRATUM-B",
                "rationale": "TEST FIXTURE ONLY. Second materially distinct context class.",
                "inclusion_criteria": ["TEST FIXTURE ONLY. Meets stratum B definition."],
                "exclusion_criteria": ["TEST FIXTURE ONLY. Fails evidence-freeze requirements."],
            },
        ],
        "cases": case_rows,
        "assessor_design": {
            "final_assessors_per_case": 3,
            "eligibility_criteria": ["TEST FIXTURE ONLY. Meets frozen domain-experience criterion."],
            "training_reference": _ref("validation/assessor-training", "2" * 64),
            "conflict_rules": ["TEST FIXTURE ONLY. No material case conflict."],
            "prior_familiarity_rule": "TEST FIXTURE ONLY. Prior case involvement is declared before assignment.",
            "evidence_access_rule": "TEST FIXTURE ONLY. Access only the frozen case universe.",
            "independent_first_pass": True,
            "adjudication_after_freeze": True,
        },
        "reliability_estimands": _estimands(),
        "decision_state_compatibility": {key: list(states) for key, states in DECISION_STATE_COMPATIBILITY.items()},
        "consequential_disagreements": _consequential(),
        "precision_plan": {
            "method": "SIMULATION",
            "planning_assumptions": ["TEST FIXTURE ONLY. Planning inputs are not observed study outcomes."],
            "target_precision": "TEST FIXTURE ONLY. Frozen interval-width target.",
            "clustering_model": "TEST FIXTURE ONLY. Cases and assessors are crossed clustering units.",
            "simulation_code_reference": _ref("validation/precision-simulation", "3" * 64),
            "case_counts_by_stratum": [
                {"stratum_id": stratum, "case_count": count} for stratum, count in sorted(counts.items())
            ],
            "assessor_allocation": "TEST FIXTURE ONLY. Three independent assessors per case.",
            "disagreement_prevalence_sensitivity": [0.05, 0.15, 0.30],
        },
        "stopping_rules": {
            "recruitment_target": "TEST FIXTURE ONLY. Complete the frozen case and assessor allocation.",
            "outcome_adaptive_stopping": False,
            "interim_outcome_access": False,
            "under_recruitment_rule": "TEST FIXTURE ONLY. Record deviation; do not replace with outcome-adaptive stopping.",
        },
        "decision_usefulness": {
            "comparator_reference": _ref("validation/comparator-workflow", "4" * 64),
            "primary_outcome_definition": "TEST FIXTURE ONLY. Prespecified critical assessment defect rate.",
            "critical_defect_taxonomy": [
                "Unsupported decision wording with a decision consequence",
                "Omitted blocking evidence or unresolved dependency",
            ],
            "assignment_strategy": "TEST FIXTURE ONLY. Balanced assignment across assessors and cases.",
            "counterbalancing": "TEST FIXTURE ONLY. Each case appears in both workflows across different assessors.",
            "period_learning_controls": "TEST FIXTURE ONLY. Case order is balanced and training is excluded.",
            "outcome_adjudicator_blinding": True,
        },
        "accessibility": {
            "representative_user_strata": ["TEST FIXTURE ONLY. Representative keyboard and screen-reader user stratum."],
            "assistive_technology_matrix": ["TEST FIXTURE ONLY. Screen reader plus browser and keyboard workflow."],
            "critical_tasks": [
                {
                    "task_id": "TASK-EVIDENCE",
                    "definition": "Locate and inspect decision-relevant evidence state.",
                    "critical_failure_definition": "Cannot reach or materially misinterprets the evidence state without out-of-protocol assistance.",
                }
            ],
            "primary_outcomes": ["Critical-task success", "Critical-task failure"],
        },
        "linguistic_validation": {
            "proposed_non_english_publication_locales": [],
            "locale_parameters": [],
        },
        "missingness_and_exclusions": {
            "structural_states_are_observed": True,
            "missingness_rule": "TEST FIXTURE ONLY. Unsubmitted assigned records are true missingness.",
            "exclusion_rules": ["TEST FIXTURE ONLY. Exclude only frozen protocol-defined ineligible records."],
            "post_outcome_exclusion_rule": "TEST FIXTURE ONLY. Record a deviation and sensitivity analysis.",
        },
        "multiplicity": "TEST FIXTURE ONLY. One confirmatory usefulness primary contrast; secondary analyses remain labeled.",
        "blinding_and_data_access": {
            "independent_assessor_blinding_rule": "TEST FIXTURE ONLY. No case-specific feedback before first-pass freeze.",
            "adjudicator_blinding_rule": "TEST FIXTURE ONLY. Blind workflow assignment where artifact presentation permits.",
            "amendment_outcome_access_recorded": True,
        },
        "amendment_policy": "TEST FIXTURE ONLY. Changes after freeze are append-only amendments with outcome-access disclosure.",
        "public_protected_boundary": "TEST FIXTURE ONLY. Public digests and safe metadata only; protected bytes remain outside public Git.",
        "boundary": PARAMETER_BOUNDARY,
    }
    return finalize_study_parameter_set(value)


def _two_cases() -> dict[str, dict[str, Any]]:
    return {
        "CASE-A": _case("CASE-A", "STRATUM-A"),
        "CASE-B": _case("CASE-B", "STRATUM-B", protected=True),
    }


def _amendment(predecessor: dict[str, Any], successor: dict[str, Any]) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema_version": "1",
        "amendment_id": "VALAMD-001",
        "recorded_at": "2026-08-19T00:00:00Z",
        "predecessor_parameter_set_id": predecessor["parameter_set_id"],
        "predecessor_parameter_set_sha256": predecessor["parameter_set_sha256"],
        "successor_parameter_set_id": successor["parameter_set_id"],
        "successor_parameter_set_sha256": successor["parameter_set_sha256"],
        "rationale": "TEST FIXTURE ONLY. Freeze a declared design correction.",
        "changed_fields": ["stopping_rules.recruitment_target"],
        "affected_cases": [],
        "affected_outcomes": ["primary usefulness outcome analysis"],
        "affected_analyses": ["decision-usefulness primary contrast"],
        "outcome_data_access_state": "NO_OUTCOME_DATA_ACCESSED",
        "analysis_class_impact": ["PRIMARY"],
        "boundary": AMENDMENT_BOUNDARY,
    }
    return finalize_protocol_amendment(value)


def test_current_normative_identity_and_bad_commit() -> None:
    identity = current_v42_normative_identity(COMMIT)
    assert identity["object_model_version"] == "v4.2"
    assert all(len(identity[key]) == 64 for key in identity if key.endswith("sha256"))
    with pytest.raises(ValueError, match="commit SHA"):
        current_v42_normative_identity("bad")


def test_case_manifest_valid_and_digest_changes() -> None:
    case = _case("CASE-A", "STRATUM-A")
    report = validate_case_manifest(case)
    assert report["valid"] is True
    assert report["canonical_sha256"] == case["manifest_sha256"] == case_manifest_sha256(case)
    changed = deepcopy(case)
    changed["evidence_access_rules"] += " Changed."
    assert case_manifest_sha256(changed) != case["manifest_sha256"]


def test_case_manifest_protected_and_public_boundary_checks() -> None:
    protected = _case("CASE-P", "STRATUM-A", protected=True)
    report = validate_case_manifest(protected)
    assert report["valid"] is True
    assert report["protected_evidence_count"] == 1

    bad = deepcopy(protected)
    bad["public_private_boundary"] = "PUBLIC_ONLY"
    bad = finalize_case_manifest(bad)
    report = validate_case_manifest(bad)
    assert any(error["code"] == "PUBLIC_PRIVATE_MISMATCH" for error in report["errors"])

    bad = _case("CASE-P2", "STRATUM-A")
    bad["public_private_boundary"] = "MIXED_WITH_PROTECTED_REFERENCES"
    bad = finalize_case_manifest(bad)
    report = validate_case_manifest(bad)
    assert any(error["code"] == "PUBLIC_PRIVATE_MISMATCH" for error in report["errors"])


def test_case_manifest_duplicate_evidence_access_reference_and_digest_fail() -> None:
    case = _case("CASE-A", "STRATUM-A")
    duplicate = deepcopy(case["evidence_objects"][0])
    case["evidence_objects"].append(duplicate)
    case = finalize_case_manifest(case)
    report = validate_case_manifest(case)
    assert any(error["code"] == "DUPLICATE_EVIDENCE_ID" for error in report["errors"])

    case = _case("CASE-BADREF", "STRATUM-A")
    case["evidence_objects"][0]["reference"] = "protected-ref:secret"
    case = finalize_case_manifest(case)
    report = validate_case_manifest(case)
    assert any(error["code"] == "ACCESS_REFERENCE_MISMATCH" for error in report["errors"])

    case = _case("CASE-BADDIGEST", "STRATUM-A")
    case["evidence_objects"][0]["sha256"] = "bad"
    case = finalize_case_manifest(case)
    report = validate_case_manifest(case)
    assert any(error["code"] in {"SCHEMA_ERROR", "INVALID_DIGEST"} for error in report["errors"])


def test_case_manifest_rejects_unbounded_reference_normative_boundary_and_hash() -> None:
    case = _case("CASE-A", "STRATUM-A")
    case["case_instructions"] = {"reference": "/private/path", "sha256": "b" * 64}
    case["evidence_manifest"] = {"reference": "file:///private/evidence", "sha256": "c" * 64}
    case["normative_identity"] = dict(case["normative_identity"])
    case["normative_identity"]["controlled_vocabularies_sha256"] = "0" * 64
    case["boundary"] = "wrong"
    report = validate_case_manifest(case)
    codes = {error["code"] for error in report["errors"]}
    assert {"INVALID_REFERENCE", "NORMATIVE_IDENTITY_MISMATCH", "BOUNDARY_MISMATCH", "HASH_MISMATCH"} <= codes


def test_case_manifest_access_ref_direction_for_protected() -> None:
    case = _case("CASE-A", "STRATUM-A", protected=True)
    case["evidence_objects"][0]["reference"] = "public-ref:wrong"
    case = finalize_case_manifest(case)
    report = validate_case_manifest(case)
    assert any(error["code"] == "ACCESS_REFERENCE_MISMATCH" for error in report["errors"])


def test_study_parameter_set_valid() -> None:
    cases = _two_cases()
    params = _parameter(cases)
    report = validate_study_parameter_set(params, case_manifests=cases)
    assert report["valid"] is True
    assert report["case_count"] == 2
    assert report["stratum_count"] == 2
    assert report["canonical_sha256"] == params["parameter_set_sha256"] == study_parameter_set_sha256(params)


def test_parameter_set_requires_case_objects_and_bounded_references() -> None:
    cases = _two_cases()
    params = _parameter(cases)
    report = validate_study_parameter_set(params)
    assert any(error["code"] == "CASE_MANIFESTS_REQUIRED" for error in report["errors"])

    params = _parameter(cases)
    params["cases"][0]["manifest_reference"] = "/private/case.json"
    params = finalize_study_parameter_set(params)
    report = validate_study_parameter_set(params, case_manifests=cases)
    assert any(error["code"] == "INVALID_REFERENCE" for error in report["errors"])


def test_parameter_set_hash_boundary_normative_and_compatibility_fail_closed() -> None:
    cases = _two_cases()
    params = _parameter(cases)
    params["boundary"] = "wrong"
    params["normative_identity"] = dict(params["normative_identity"])
    params["normative_identity"]["assessment_schema_sha256"] = "0" * 64
    params["decision_state_compatibility"] = {}
    report = validate_study_parameter_set(params, case_manifests=cases)
    codes = {error["code"] for error in report["errors"]}
    assert {"BOUNDARY_MISMATCH", "HASH_MISMATCH", "NORMATIVE_IDENTITY_MISMATCH", "DECISION_COMPATIBILITY_MISMATCH"} <= codes


def test_parameter_set_duplicate_and_unknown_strata_cases_and_manifests() -> None:
    cases = _two_cases()
    params = _parameter(cases)
    params["case_strata"].append(deepcopy(params["case_strata"][0]))
    params["cases"].append(deepcopy(params["cases"][0]))
    params = finalize_study_parameter_set(params)
    report = validate_study_parameter_set(params, case_manifests=cases)
    codes = {error["code"] for error in report["errors"]}
    assert "DUPLICATE_STRATUM_ID" in codes
    assert "DUPLICATE_CASE_ID" in codes
    assert "DUPLICATE_CASE_MANIFEST" in codes

    params = _parameter(cases)
    params["cases"][0]["case_class_id"] = "UNKNOWN"
    params = finalize_study_parameter_set(params)
    report = validate_study_parameter_set(params, case_manifests=cases)
    assert any(error["code"] == "UNKNOWN_CASE_STRATUM" for error in report["errors"])


def test_parameter_set_empty_stratum_and_case_count_mismatch() -> None:
    cases = _two_cases()
    params = _parameter(cases)
    params["cases"][1]["case_class_id"] = "STRATUM-A"
    params["precision_plan"]["case_counts_by_stratum"] = [
        {"stratum_id": "STRATUM-A", "case_count": 2},
        {"stratum_id": "STRATUM-B", "case_count": 1},
    ]
    params = finalize_study_parameter_set(params)
    report = validate_study_parameter_set(params, case_manifests=cases)
    codes = {error["code"] for error in report["errors"]}
    assert "EMPTY_CASE_STRATUM" in codes
    assert "CASE_COUNT_MISMATCH" in codes


def test_parameter_set_assessor_seed_and_sensitivity_rules() -> None:
    cases = _two_cases()
    params = _parameter(cases)
    params["assessor_design"]["final_assessors_per_case"] = 2
    params["analysis_identity"]["random_seeds"] = [17, 17]
    params["precision_plan"]["disagreement_prevalence_sensitivity"] = [0.1, 0.1]
    params = finalize_study_parameter_set(params)
    report = validate_study_parameter_set(params, case_manifests=cases)
    codes = {error["code"] for error in report["errors"]}
    assert {"ASSESSOR_COUNT_UNJUSTIFIED", "DUPLICATE_RANDOM_SEED", "DUPLICATE_SENSITIVITY_POINT"} <= codes

    params = _parameter(cases)
    params["assessor_design"]["final_assessors_per_case"] = 2
    params["assessor_design"]["precision_override_justification"] = "TEST FIXTURE ONLY. Pre-outcome precision analysis supports two."
    params = finalize_study_parameter_set(params)
    assert not any(
        error["code"] == "ASSESSOR_COUNT_UNJUSTIFIED"
        for error in validate_study_parameter_set(params, case_manifests=cases)["errors"]
    )


def test_parameter_set_estimand_coverage_clustering_and_structural_state() -> None:
    cases = _two_cases()
    params = _parameter(cases)
    params["reliability_estimands"] = params["reliability_estimands"][:-1]
    params = finalize_study_parameter_set(params)
    assert any(
        error["code"] == "ESTIMAND_COVERAGE"
        for error in validate_study_parameter_set(params, case_manifests=cases)["errors"]
    )

    params = _parameter(cases)
    params["reliability_estimands"][0]["clustering_units"] = ["CASE", "CASE"]
    finding = next(item for item in params["reliability_estimands"] if item["field_family"] == "REQUIREMENT_FINDING")
    finding["excluded_structural_states"] = []
    params = finalize_study_parameter_set(params)
    codes = {error["code"] for error in validate_study_parameter_set(params, case_manifests=cases)["errors"]}
    assert {"CLUSTERING_REQUIRED", "STRUCTURAL_STATE_COLLAPSE"} <= codes


def test_consequential_rules_reject_bad_domain_state_presence_and_interval() -> None:
    cases = _two_cases()
    params = _parameter(cases)
    params["consequential_disagreements"][0]["decision_object_type"] = "CONFORMANCE DECISION"
    params["consequential_disagreements"][1]["left_state"] = "PASS"
    params["consequential_disagreements"][2]["interval_method"] = ""
    params["consequential_disagreements"][5]["right_state"] = "NOT APPLICABLE"
    params = finalize_study_parameter_set(params)
    report = validate_study_parameter_set(params, case_manifests=cases)
    codes = {error["code"] for error in report["errors"]}
    assert {"UNEXPECTED_DECISION_TYPE", "INVALID_RULE_STATE", "MISSING_INTERVAL_METHOD", "INVALID_PRESENCE_RULE"} <= codes
    assert "MISSING_CONSEQUENTIAL_RULE" in codes


def test_consequential_rules_duplicate_invalid_type_and_pair() -> None:
    cases = _two_cases()
    params = _parameter(cases)
    params["consequential_disagreements"].append(deepcopy(params["consequential_disagreements"][0]))
    params["consequential_disagreements"][3]["decision_object_type"] = "BAD TYPE"
    params["consequential_disagreements"][4]["right_state"] = params["consequential_disagreements"][4]["left_state"]
    params = finalize_study_parameter_set(params)
    codes = {error["code"] for error in validate_study_parameter_set(params, case_manifests=cases)["errors"]}
    assert {"DUPLICATE_RULE_ID", "INVALID_RULE_DOMAIN", "INVALID_RULE_STATE"} <= codes


def test_linguistic_locale_and_accessibility_usefulness_duplicates() -> None:
    cases = _two_cases()
    params = _parameter(cases)
    params["linguistic_validation"] = {
        "proposed_non_english_publication_locales": ["fr-FR", "fr-FR", "en-US"],
        "locale_parameters": [
            {
                "locale": "fr-FR",
                "terminology_review": "TEST FIXTURE ONLY.",
                "comprehension_test": "TEST FIXTURE ONLY.",
                "decision_critical_terms": ["TEST"],
            }
        ],
    }
    params["accessibility"]["critical_tasks"].append(deepcopy(params["accessibility"]["critical_tasks"][0]))
    params["decision_usefulness"]["critical_defect_taxonomy"].append(
        params["decision_usefulness"]["critical_defect_taxonomy"][0]
    )
    params = finalize_study_parameter_set(params)
    codes = {error["code"] for error in validate_study_parameter_set(params, case_manifests=cases)["errors"]}
    assert {
        "DUPLICATE_LOCALE",
        "ENGLISH_IN_NON_ENGLISH_SET",
        "LOCALE_PARAMETER_MISMATCH",
        "DUPLICATE_ACCESSIBILITY_TASK",
        "DUPLICATE_CRITICAL_DEFECT",
    } <= codes


def test_linguistic_matching_non_english_locale_can_validate() -> None:
    cases = _two_cases()
    params = _parameter(cases)
    params["linguistic_validation"] = {
        "proposed_non_english_publication_locales": ["fr-FR"],
        "locale_parameters": [
            {
                "locale": "fr-FR",
                "terminology_review": "TEST FIXTURE ONLY. Subject-matter terminology review.",
                "comprehension_test": "TEST FIXTURE ONLY. Decision-critical task comprehension.",
                "decision_critical_terms": ["evidence state"],
            }
        ],
    }
    params = finalize_study_parameter_set(params)
    assert validate_study_parameter_set(params, case_manifests=cases)["valid"] is True


def test_cross_record_missing_digest_wave_normative_class_and_calibration() -> None:
    cases = _two_cases()
    params = _parameter(cases)

    report = validate_study_parameter_set(params, case_manifests={"CASE-A": cases["CASE-A"]})
    assert any(error["code"] == "CASE_MANIFEST_MISSING" for error in report["errors"])

    wrong = deepcopy(cases)
    wrong["CASE-A"] = deepcopy(wrong["CASE-A"])
    wrong["CASE-A"]["evidence_access_rules"] += " changed"
    report = validate_study_parameter_set(params, case_manifests=wrong)
    assert any(error["code"] in {"CASE_MANIFEST_INVALID", "CASE_MANIFEST_DIGEST_MISMATCH"} for error in report["errors"])

    for field, code, changed in (
        ("study_wave_id", "CASE_WAVE_MISMATCH", "OTHER"),
        ("case_class_id", "CASE_CLASS_MISMATCH", "STRATUM-B"),
        ("calibration_status", "CASE_CALIBRATION_MISMATCH", "CALIBRATION_DERIVED"),
    ):
        wrong = deepcopy(cases)
        wrong["CASE-A"] = deepcopy(wrong["CASE-A"])
        wrong["CASE-A"][field] = changed
        wrong["CASE-A"] = finalize_case_manifest(wrong["CASE-A"])
        report = validate_study_parameter_set(params, case_manifests=wrong)
        assert any(error["code"] == code for error in report["errors"])

    wrong = deepcopy(cases)
    wrong["CASE-A"] = deepcopy(wrong["CASE-A"])
    wrong["CASE-A"]["normative_identity"] = current_v42_normative_identity("1" * 40)
    wrong["CASE-A"] = finalize_case_manifest(wrong["CASE-A"])
    report = validate_study_parameter_set(params, case_manifests=wrong)
    assert any(error["code"] == "CASE_NORMATIVE_MISMATCH" for error in report["errors"])


def test_cross_record_extra_case_is_warning() -> None:
    cases = _two_cases()
    params = _parameter(cases)
    supplied = dict(cases)
    supplied["CASE-C"] = _case("CASE-C", "STRATUM-A")
    report = validate_study_parameter_set(params, case_manifests=supplied)
    assert report["valid"] is True
    assert report["warnings"][0]["code"] == "UNREFERENCED_CASE_MANIFESTS"


def test_reference_objects_fail_closed_when_malformed() -> None:
    cases = _two_cases()
    params = _parameter(cases)
    params["protocol_reference"] = "bad"
    params["analysis_identity"]["code_reference"] = {"reference": "public-ref:", "sha256": "f" * 64}
    params["analysis_identity"]["environment_reference"] = {"reference": "public-ref:x", "sha256": "bad"}
    params = finalize_study_parameter_set(params)
    report = validate_study_parameter_set(params, case_manifests=cases)
    assert sum(error["code"] in {"INVALID_REFERENCE", "INVALID_DIGEST"} for error in report["errors"]) >= 3


def test_amendment_valid_with_exact_parameter_lineage() -> None:
    cases = _two_cases()
    predecessor = _parameter(cases)
    successor = deepcopy(predecessor)
    successor.pop("parameter_set_sha256")
    successor["parameter_set_id"] = "VALPARAM-WAVE-1-A1"
    successor["stopping_rules"]["recruitment_target"] += " Amended."
    successor = finalize_study_parameter_set(successor)
    amendment = _amendment(predecessor, successor)
    report = validate_protocol_amendment(
        amendment,
        parameter_sets={predecessor["parameter_set_id"]: predecessor, successor["parameter_set_id"]: successor},
    )
    assert report["valid"] is True
    assert report["canonical_sha256"] == amendment["amendment_sha256"] == protocol_amendment_sha256(amendment)


def test_amendment_without_objects_warns_but_keeps_digest_record() -> None:
    cases = _two_cases()
    predecessor = _parameter(cases)
    successor = deepcopy(predecessor)
    successor.pop("parameter_set_sha256")
    successor["parameter_set_id"] = "VALPARAM-WAVE-1-A1"
    successor["multiplicity"] += " Amended."
    successor = finalize_study_parameter_set(successor)
    report = validate_protocol_amendment(_amendment(predecessor, successor))
    assert report["valid"] is True
    assert report["warnings"][0]["code"] == "PARAMETER_SETS_NOT_PROVIDED"


def test_amendment_semantic_failures() -> None:
    cases = _two_cases()
    predecessor = _parameter(cases)
    successor = deepcopy(predecessor)
    successor.pop("parameter_set_sha256")
    successor["parameter_set_id"] = "VALPARAM-WAVE-1-A1"
    successor["multiplicity"] += " Amended."
    successor = finalize_study_parameter_set(successor)
    amendment = _amendment(predecessor, successor)
    amendment["successor_parameter_set_id"] = amendment["predecessor_parameter_set_id"]
    amendment["successor_parameter_set_sha256"] = amendment["predecessor_parameter_set_sha256"]
    amendment["changed_fields"].append(amendment["changed_fields"][0])
    amendment["analysis_class_impact"] = ["PRIMARY", "NO_ANALYSIS_IMPACT"]
    amendment["affected_outcomes"] = []
    amendment["affected_analyses"] = []
    amendment["boundary"] = "wrong"
    report = validate_protocol_amendment(amendment)
    codes = {error["code"] for error in report["errors"]}
    assert {
        "SELF_REFERENTIAL_AMENDMENT",
        "UNCHANGED_PARAMETER_DIGEST",
        "DUPLICATE_CHANGED_FIELD",
        "ANALYSIS_IMPACT_CONFLICT",
        "AMENDMENT_EFFECT_UNSPECIFIED",
        "BOUNDARY_MISMATCH",
        "HASH_MISMATCH",
    } <= codes


def test_amendment_cross_record_missing_and_digest_mismatch() -> None:
    cases = _two_cases()
    predecessor = _parameter(cases)
    successor = deepcopy(predecessor)
    successor.pop("parameter_set_sha256")
    successor["parameter_set_id"] = "VALPARAM-WAVE-1-A1"
    successor["multiplicity"] += " Amended."
    successor = finalize_study_parameter_set(successor)
    amendment = _amendment(predecessor, successor)

    report = validate_protocol_amendment(amendment, parameter_sets={})
    assert any(error["code"] == "AMENDMENT_PARAMETER_SET_MISSING" for error in report["errors"])

    bad = deepcopy(amendment)
    bad["predecessor_parameter_set_sha256"] = "0" * 64
    bad["successor_parameter_set_sha256"] = "1" * 64
    bad = finalize_protocol_amendment(bad)
    report = validate_protocol_amendment(
        bad,
        parameter_sets={predecessor["parameter_set_id"]: predecessor, successor["parameter_set_id"]: successor},
    )
    codes = {error["code"] for error in report["errors"]}
    assert {"PREDECESSOR_DIGEST_MISMATCH", "SUCCESSOR_DIGEST_MISMATCH"} <= codes


def test_load_record_and_file_helpers(tmp_path: Path) -> None:
    cases = _two_cases()
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    for case_id, value in cases.items():
        (case_dir / f"{case_id}.json").write_text(json.dumps(value), encoding="utf-8")
    loaded = load_case_manifests(case_dir)
    assert set(loaded) == set(cases)
    assert validate_case_manifest_file(case_dir / "CASE-A.json")["valid"] is True

    params = _parameter(cases)
    param_path = tmp_path / "parameters.json"
    param_path.write_text(json.dumps(params), encoding="utf-8")
    assert validate_study_parameter_set_file(param_path, case_manifest_dir=case_dir)["valid"] is True

    successor = deepcopy(params)
    successor.pop("parameter_set_sha256")
    successor["parameter_set_id"] = "VALPARAM-WAVE-1-A1"
    successor["multiplicity"] += " Amended."
    successor = finalize_study_parameter_set(successor)
    amendment = _amendment(params, successor)
    amendment_path = tmp_path / "amendment.json"
    amendment_path.write_text(json.dumps(amendment), encoding="utf-8")
    assert validate_protocol_amendment_file(amendment_path)["valid"] is True


def test_load_record_rejects_non_object_and_duplicate_case_ids(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a JSON object"):
        load_validation_record(bad)

    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    first = _case("CASE-A", "STRATUM-A")
    second = deepcopy(first)
    second["manifest_id"] = "VALCASE-OTHER"
    second = finalize_case_manifest(second)
    (case_dir / "a.json").write_text(json.dumps(first), encoding="utf-8")
    (case_dir / "b.json").write_text(json.dumps(second), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate validation case_id"):
        load_case_manifests(case_dir)


def test_load_case_manifests_rejects_missing_case_id(tmp_path: Path) -> None:
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    (case_dir / "bad.json").write_text(json.dumps({"schema_version": "1"}), encoding="utf-8")
    with pytest.raises(ValueError, match="has no case_id"):
        load_case_manifests(case_dir)


def test_internal_compatibility_matrix_uses_controlled_vocab(monkeypatch: pytest.MonkeyPatch) -> None:
    assert study._compatibility_is_controlled() is True
    monkeypatch.setattr(study, "DECISION_STATE_COMPATIBILITY", {"BAD": ("BAD",)})
    assert study._compatibility_is_controlled() is False


def test_schema_and_defensive_type_errors_are_reported() -> None:
    report = validate_case_manifest({"schema_version": "1"})
    assert report["valid"] is False
    assert any(error["code"] == "SCHEMA_ERROR" for error in report["errors"])

    cases = _two_cases()
    params = _parameter(cases)
    params["reliability_estimands"] = "bad"
    params["consequential_disagreements"] = "bad"
    params = finalize_study_parameter_set(params)
    report = validate_study_parameter_set(params, case_manifests=cases)
    assert any(error["code"] == "CONSEQUENTIAL_RULES_INVALID" for error in report["errors"])
