from __future__ import annotations

import json
from pathlib import Path

from neuroai_workbench.programme_adapter import (
    _access_state,
    _claim_status,
    _decision_state,
    _evidence_state,
    adapt_programme_assessment,
    detect_programme_assessment,
)
from neuroai_workbench.validation import validate_assessment
from neuroai_workbench.workspace import Workspace

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
    assert result.report["preservation"]["preservation_verified"] is True
    assert result.report["no_reappraisal"]["reappraisal_performed"] is False
    assert all(result.report["preservation"]["checks"].values())


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
    assert "FAIL" not in counts
    assert all(item["historical_finding_preserved"] for item in assessment["requirement_findings"])


def test_adapter_documents_gap_link_and_classification_loss() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    result = adapt_programme_assessment(source)
    assert all(item["linked_requirement_ids"] == [] for item in result.assessment["gap_register"])
    assert any("linked_requirement_ids" in item for item in result.report["loss_boundaries"])
    assert any("sc_01" in item for item in result.report["loss_boundaries"])
    assert any(
        "provisional" in warning.lower() or "sc_01" in warning
        for warning in result.assessment["migration_provenance"]["migration_warnings"]
    )
    classification = result.assessment["system_profile"]["classification"]
    for key in (f"sc_{index:02d}" for index in range(1, 13)):
        assert classification[key]["certainty"] == "PROVISIONAL"


def test_claim_status_unmatched_is_not_reviewable() -> None:
    assert _claim_status("TOTALLY_NOVEL_STATE") == "NOT REVIEWABLE"
    assert _claim_status("") == "NOT REVIEWABLE"
    assert _claim_status("SUPPORTED_PRIMARY_STUDY") == "SUPPORTED WITHIN BOUNDED SCOPE"
    assert _claim_status("COMPANY_ANNOUNCEMENT_CORROBORATED") == "PARTIALLY SUPPORTED"


def test_adapter_mappings_fail_closed_on_unknown_and_private_phrases() -> None:
    assert _evidence_state({"evidence_class": "UNKNOWN_CLASS", "publication_state": ""}) == "NOT AVAILABLE"
    assert _evidence_state({"evidence_class": "WEIRD_THING", "publication_state": "X"}) == "NOT AVAILABLE"
    assert _access_state({"retrieval_state": "PRIVATE FULL RECORD"}) == "KNOWN PRIVATE RECORD REQUIRED"
    assert _access_state({"retrieval_state": "PRIVATE_CONTENT_AVAILABLE"}) == "KNOWN PRIVATE RECORD REQUIRED"
    assert _access_state({"retrieval_state": "MYSTERIOUS_STATE"}) == "EVALUATION NOT EXECUTED"
    assert (
        _decision_state({"decision_class": "CONFORMANCE", "decision": "WEIRD_CONFORMANCE"})
        == "NO CONFORMANCE DECISION — BLOCKED"
    )
    assert (
        _decision_state({"decision_class": "REGULATORY_STATE", "decision": "UNKNOWN_AUTH"})
        == "AUTHORIZATION NOT ASSESSED"
    )
    assert (
        _decision_state({"decision_class": "SYSTEM_ASSESSMENT", "decision": "WEIRD_CLAIM_LIKE"})
        == "ASSESSMENT INCOMPLETE"
    )


def test_export_import_round_trip_preserves_governed_fields(tmp_path: Path) -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    native = adapt_programme_assessment(source).assessment
    workspace = Workspace.initialize(tmp_path / "workspace", name="Adapter round trip")
    case_id = native["assessment_metadata"]["assessment_id"]
    export_path = tmp_path / "prima.native.json"
    export_path.write_text(json.dumps(native, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    workspace.import_case(export_path, case_id=case_id, actor="test")
    reloaded = workspace.load_case(case_id)
    governed = (
        "assessment_metadata",
        "system_profile",
        "claim_register",
        "evidence_register",
        "endpoint_register",
        "denominator_register",
        "requirement_findings",
        "gap_register",
        "decision_register",
        "migration_provenance",
    )
    for field in governed:
        assert reloaded[field] == native[field]
    assert validate_assessment(reloaded).valid is True
    assert reloaded["migration_provenance"]["preservation_verified"] is True


def test_adapter_rejects_unrelated_json() -> None:
    try:
        adapt_programme_assessment({"metadata": {}})
    except ValueError as exc:
        assert "supported programme" in str(exc)
    else:
        raise AssertionError("Expected unrelated JSON to be rejected")
