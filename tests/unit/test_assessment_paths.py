from __future__ import annotations

import pytest

from neuroai_workbench.assessment_paths import (
    apply_field_patches,
    get_at_path,
    normalize_target_path,
    path_within_review_target,
)


def test_normalize_and_get_paths() -> None:
    assessment = {
        "assessment_metadata": {"title": "T", "assessment_id": "C1"},
        "requirement_findings": [{"requirement_id": "NK-01-R01", "finding": "old", "owner": "a"}],
        "claim_register": [{"claim_id": "CL-1", "statement": "s"}],
        "decision_register": [{"decision_id": "D-1", "status": "OPEN"}],
        "gap_register": [{"gap_id": "G-1", "description": "gap"}],
        "evidence_register": [{"evidence_id": "EV-1", "title": "e"}],
    }
    assert normalize_target_path("/requirement_findings/NK-01-R01/finding") == (
        "/requirement_findings/NK-01-R01/finding"
    )
    assert get_at_path(assessment, "/assessment_metadata/title") == "T"
    assert get_at_path(assessment, "/requirement_findings/NK-01-R01/finding") == "old"
    assert get_at_path(assessment, "/claim_register/CL-1/statement") == "s"
    assert path_within_review_target("/requirement_findings/NK-01-R01/finding", "FINDING", "NK-01-R01")
    assert path_within_review_target("/claim_register/CL-1/statement", "CLAIM", "CL-1")
    assert path_within_review_target("/decision_register/D-1/status", "DECISION", "D-1")
    assert path_within_review_target("/gap_register/G-1/description", "GAP", "G-1")
    assert path_within_review_target("/assessment_metadata/title", "ASSESSMENT", "C1")
    assert not path_within_review_target("/requirement_findings/NK-01-R01/finding", "FINDING", "OTHER")

    patched = apply_field_patches(
        assessment,
        [
            {"target_path": "/requirement_findings/NK-01-R01/finding", "value": "new"},
            {"target_path": "/assessment_metadata/title", "value": "NT"},
        ],
    )
    assert patched["requirement_findings"][0]["finding"] == "new"
    assert patched["assessment_metadata"]["title"] == "NT"
    assert assessment["requirement_findings"][0]["finding"] == "old"


def test_path_refusals() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        normalize_target_path("")
    with pytest.raises(ValueError, match="start with"):
        normalize_target_path("requirement_findings/x")
    with pytest.raises(ValueError, match="\\.\\."):
        normalize_target_path("/a/../b")
    with pytest.raises(ValueError, match="segment"):
        normalize_target_path("/bad path/x")
    with pytest.raises(ValueError, match="At least one"):
        apply_field_patches({"assessment_metadata": {"title": "t"}}, [])
    with pytest.raises(ValueError, match="identity field"):
        apply_field_patches(
            {"requirement_findings": [{"requirement_id": "NK-01-R01", "finding": "x"}]},
            [{"target_path": "/requirement_findings/NK-01-R01/requirement_id", "value": "OTHER"}],
        )
    with pytest.raises(ValueError, match="Unknown collection member"):
        apply_field_patches(
            {"requirement_findings": [{"requirement_id": "NK-01-R01", "finding": "x"}]},
            [{"target_path": "/requirement_findings/MISSING/finding", "value": "x"}],
        )
    with pytest.raises(ValueError, match="unknown field"):
        apply_field_patches(
            {"assessment_metadata": {"title": "t"}},
            [{"target_path": "/assessment_metadata/missing", "value": "x"}],
        )
