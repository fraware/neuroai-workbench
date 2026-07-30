from __future__ import annotations

import copy

from neuroai_workbench.resource_loader import read_resource_bytes
from neuroai_workbench.validation import EXPECTED_REQUIREMENTS, validate_assessment
import json


def test_blank_instance_is_structurally_valid():
    instance = json.loads(read_resource_bytes("BLANK_UNIVERSAL_ASSESSMENT_INSTANCE_v4.2.json"))
    report = validate_assessment(instance)
    assert report.valid
    assert report.counts["requirements"] == 78
    assert report.counts["p0_blockers"] == 52


def test_every_example_is_valid(example_assessment):
    report = validate_assessment(example_assessment)
    assert report.valid, report.to_dict()
    assert report.counts["requirements"] == 78


def test_all_requirement_ids_are_exact(example_assessment):
    ids = [row["requirement_id"] for row in example_assessment["requirement_findings"]]
    assert len(ids) == 78
    assert len(set(ids)) == 78
    assert set(ids) == EXPECTED_REQUIREMENTS


def test_duplicate_requirement_is_rejected(example_assessment):
    altered = copy.deepcopy(example_assessment)
    altered["requirement_findings"][1]["requirement_id"] = altered["requirement_findings"][0]["requirement_id"]
    report = validate_assessment(altered)
    assert not report.valid
    assert any(issue.code == "REQ-COVERAGE" for issue in report.semantic_issues)


def test_dangling_claim_evidence_is_rejected(example_assessment):
    altered = copy.deepcopy(example_assessment)
    altered["claim_register"][0]["evidence_ids"].append("EV-DOES-NOT-EXIST")
    report = validate_assessment(altered)
    assert not report.valid
    assert any(issue.code == "DANGLING-EVIDENCE" for issue in report.semantic_issues)


def test_inapplicable_requirement_needs_rationale(example_assessment):
    altered = copy.deepcopy(example_assessment)
    row = altered["requirement_findings"][0]
    row["applicability"] = "NOT APPLICABLE WITH RATIONALE"
    row["applicability_rationale"] = ""
    report = validate_assessment(altered)
    assert not report.valid
    assert any(issue.code == "MISSING-RATIONALE" for issue in report.semantic_issues)


def test_pass_without_finding_is_rejected(example_assessment):
    altered = copy.deepcopy(example_assessment)
    row = altered["requirement_findings"][0]
    row["finding_status"] = "PASS"
    row["finding"] = ""
    report = validate_assessment(altered)
    assert not report.valid
    assert any(issue.code == "MISSING-FINDING" for issue in report.semantic_issues)


def test_claim_and_conformance_decisions_are_required(example_assessment):
    altered = copy.deepcopy(example_assessment)
    altered["decision_register"] = [
        row for row in altered["decision_register"] if row["decision_object_type"] != "CONFORMANCE DECISION"
    ]
    report = validate_assessment(altered)
    assert not report.valid
    assert any(issue.code == "DECISION-SEPARATION" for issue in report.semantic_issues)


def test_frozen_status_requires_freeze_id(example_assessment):
    altered = copy.deepcopy(example_assessment)
    altered["assessment_metadata"]["assessment_status"] = "DECISION READY"
    altered["assessment_metadata"]["evidence_freeze_id"] = ""
    report = validate_assessment(altered)
    assert not report.valid
    assert any(issue.code == "FREEZE-REQUIRED" for issue in report.semantic_issues)


def test_schema_rejects_wrong_instrument_version(example_assessment):
    altered = copy.deepcopy(example_assessment)
    altered["assessment_metadata"]["instrument_version"] = "v9.9"
    report = validate_assessment(altered)
    assert not report.valid
    assert report.schema_issues
