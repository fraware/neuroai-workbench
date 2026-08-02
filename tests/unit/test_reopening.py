from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench.observatory import load_release
from neuroai_workbench.reopening import (
    analyze_observatory_delta,
    confirm_reopening_recommendation,
    extract_delta_operations,
    load_observatory_delta,
    recommend_reopening,
    reconcile_with_observatory_decisions,
    summarize_reopening_analysis,
)

ROOT = Path(__file__).resolve().parents[2]
SUCCESSOR = ROOT / "examples" / "observatory" / "canonical_successor_snapshot_v1.7.json"
REGRESSION = ROOT / "tests" / "fixtures" / "reopening" / "prima_v17_regression.json"


def test_extract_delta_operations_from_v17():
    operations = extract_delta_operations(load_observatory_delta(SUCCESSOR))
    assert len(operations) == 9
    assert any(item["operation_id"] == "REG-16-001" for item in operations)


def test_unrelated_change_produces_no_effect_for_pilots():
    recommendations = analyze_observatory_delta(load_observatory_delta(SUCCESSOR))
    summary = summarize_reopening_analysis(recommendations)
    assert summary["strongest_rule_effect_by_assessment"]["PILOT-05-BRAIN2QWERTY-v4.1.3"] == "NO_EFFECT"
    assert summary["strongest_rule_effect_by_assessment"]["PILOT-01-BRAINGATE2-T15-v4.1.5"] == "NO_EFFECT"
    assert summary["strongest_rule_effect_by_assessment"]["PILOT-02-FDA-ADBS-v4.1.4"] == "NO_EFFECT"


def test_prima_regulatory_change_produces_review_required():
    recommendations = analyze_observatory_delta(load_observatory_delta(SUCCESSOR))
    summary = summarize_reopening_analysis(recommendations)
    assert summary["strongest_rule_effect_by_assessment"]["PRIMA-PUBLIC-2026-001"] == "REVIEW_REQUIRED"
    prima_reg = [
        item
        for item in recommendations
        if item["assessment_id"] == "PRIMA-PUBLIC-2026-001" and item["operation_id"] == "REG-16-001"
    ]
    assert len(prima_reg) == 1
    assert prima_reg[0]["rule_reopening_effect"] == "REVIEW_REQUIRED"
    assert prima_reg[0]["suggested_observatory_decision"] == "REOPEN_REQUIRED"


def test_prima_v17_locked_regression_fixture():
    fixture = json.loads(REGRESSION.read_text(encoding="utf-8"))
    recommendations = analyze_observatory_delta(load_observatory_delta(SUCCESSOR))
    summary = summarize_reopening_analysis(recommendations)
    assert summary["strongest_rule_effect_by_assessment"] == fixture["strongest_rule_effect_by_assessment"]


def test_human_confirmation_separate_from_rule_result():
    operations = extract_delta_operations(load_observatory_delta(SUCCESSOR))
    reg_op = next(item for item in operations if item["operation_id"] == "REG-16-001")
    from neuroai_workbench.assessment_dependencies import load_reference_manifest

    manifest = load_reference_manifest("PRIMA-PUBLIC-2026-001", ROOT)
    recommendation = recommend_reopening(reg_op, assessment_id="PRIMA-PUBLIC-2026-001", manifest=manifest)
    confirmation = confirm_reopening_recommendation(
        recommendation,
        human_reopening_effect="PARTIAL_REASSESSMENT_REQUIRED",
        human_rationale="Human reviewer narrowed scope to regulatory deployment metadata only.",
        confirmed_by="local-reviewer",
        authority_claim={
            "name_or_role": "Programme reopening reviewer",
            "organization": "Local workflow",
            "accountability_state": "CLAIMED LOCAL IDENTITY ONLY",
        },
        observatory_decision="REOPENING_EXECUTED_RECORD_UPDATED_OPEN_CONDITIONS",
    )
    assert confirmation["rule_reopening_effect"] == "REVIEW_REQUIRED"
    assert confirmation["human_reopening_effect"] == "PARTIAL_REASSESSMENT_REQUIRED"
    assert confirmation["assessment_mutation_performed"] is False


def test_reconcile_with_observatory_decisions():
    release = load_release(SUCCESSOR)
    recommendations = analyze_observatory_delta(release["delta"])
    report = reconcile_with_observatory_decisions(recommendations, release["reopening_decisions"])
    prima_rows = [row for row in report["rows"] if row["assessment_id"] == "PRIMA-PUBLIC-2026-001"]
    assert prima_rows
    assert any(row["operation_id"] == "REG-16-001" for row in prima_rows)


def test_confirm_rejects_empty_rationale():
    operations = extract_delta_operations(load_observatory_delta(SUCCESSOR))
    reg_op = next(item for item in operations if item["operation_id"] == "REG-16-001")
    from neuroai_workbench.assessment_dependencies import load_reference_manifest

    manifest = load_reference_manifest("PRIMA-PUBLIC-2026-001", ROOT)
    recommendation = recommend_reopening(reg_op, assessment_id="PRIMA-PUBLIC-2026-001", manifest=manifest)
    with pytest.raises(ValueError, match="Human rationale is required"):
        confirm_reopening_recommendation(
            recommendation,
            human_reopening_effect="DECLINED",
            human_rationale="   ",
            confirmed_by="local-reviewer",
            authority_claim={
                "name_or_role": "Reviewer",
                "accountability_state": "CLAIMED LOCAL IDENTITY ONLY",
            },
        )
