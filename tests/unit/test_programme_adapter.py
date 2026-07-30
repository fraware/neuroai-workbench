from __future__ import annotations

import json
from pathlib import Path

from neuroai_workbench.programme_adapter import adapt_programme_assessment, detect_programme_assessment
from neuroai_workbench.validation import validate_assessment

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "examples" / "programme" / "PRIMA_COMPLETED_ASSESSMENT_v4.2.1.programme.json"
NATIVE = REPO / "examples" / "assessments" / "PRIMA_Controlled_Assessment_v4.2.1.native.json"


def test_detect_and_adapt_programme_assessment() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    assert detect_programme_assessment(source) is True
    result = adapt_programme_assessment(source)
    assert result.report["validation"]["valid"] is True
    assert result.report["preserved_counts"] == {
        "claims": 14,
        "evidence_objects": 15,
        "endpoints": 11,
        "denominators": 8,
        "requirement_findings": 78,
        "gaps": 22,
        "decisions": 4,
        "safety_event_notes": 11,
    }
    assert result.assessment["assessment_metadata"]["assessment_id"] == "PRIMA-PUBLIC-2026-001"
    assert result.assessment["profile_selection"]["final_profile_id"] == "AP-3"
    assert result.assessment["migration_provenance"]["preservation_verified"] is True


def test_checked_in_native_projection_matches_adapter() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    expected = adapt_programme_assessment(source).assessment
    checked_in = json.loads(NATIVE.read_text(encoding="utf-8"))
    # Migration date is derived from the execution date. The controlled checked-in
    # projection is expected to remain byte-equivalent for the same release day.
    assert checked_in == expected
    assert validate_assessment(checked_in).valid is True


def test_adapter_preserves_requirement_status_counts() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    assessment = adapt_programme_assessment(source).assessment
    counts: dict[str, int] = {}
    for item in assessment["requirement_findings"]:
        counts[item["finding_status"]] = counts.get(item["finding_status"], 0) + 1
    assert counts == {"PARTIAL": 42, "NOT ASSESSED": 21, "PASS": 15}
    assert all(item["historical_finding_preserved"] for item in assessment["requirement_findings"])


def test_adapter_rejects_unrelated_json() -> None:
    try:
        adapt_programme_assessment({"metadata": {}})
    except ValueError as exc:
        assert "supported programme" in str(exc)
    else:
        raise AssertionError("Expected unrelated JSON to be rejected")
