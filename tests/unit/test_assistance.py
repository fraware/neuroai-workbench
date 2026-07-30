from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench.assistance import (
    create_assistance_request,
    dispose_assistance_response,
    record_assistance_response,
    scan_sensitive_text,
    verify_assistance_record,
)

REPO = Path(__file__).resolve().parents[2]
PRIMA = REPO / "examples" / "assessments" / "PRIMA_Controlled_Assessment_v4.2.1.native.json"


def _import_prima(workspace) -> None:
    workspace.import_case(PRIMA, case_id="prima")


def _valid_output() -> dict:
    return {
        "task_type": "DRAFT_FINDING",
        "summary": "A bounded wording suggestion is supplied for human review.",
        "suggestions": [
            {
                "target_path": "/requirement_findings/NK-01-R01/finding",
                "proposed_text": "The trial configuration is reconstructable; the current commercial configuration remains unresolved.",
                "evidence_ids": ["EV-PR-001", "EV-PR-006"],
                "confidence": "HIGH",
                "limitations": ["No current commercial configuration or conformance conclusion follows."],
            }
        ],
        "warnings": ["Human domain review is required."],
    }


def test_assistance_round_trip_preserves_human_authority(workspace, tmp_path: Path) -> None:
    _import_prima(workspace)
    created = create_assistance_request(
        workspace,
        "prima",
        "DRAFT_FINDING",
        "Draft bounded wording for NK-01-R01 using only the selected evidence.",
        evidence_ids=["EV-PR-001", "EV-PR-006"],
        requirement_ids=["NK-01-R01"],
        actor="reviewer",
    )
    request = created["request"]
    assert request["network_execution"] == "NOT_PERFORMED_BY_WORKBENCH"
    assert request["human_authority"] == "REQUIRED_FOR_ANY_USE"

    response_file = tmp_path / "response.json"
    response_file.write_text(json.dumps(_valid_output()), encoding="utf-8")
    recorded = record_assistance_response(
        workspace,
        "prima",
        request["request_id"],
        response_file,
        provider="manual",
        model="gpt-compatible-test",
        actor="reviewer",
    )
    assert recorded["response"]["contract_valid"] is True
    assert recorded["response"]["disposition_state"] == "PENDING_REVIEW"

    disposed = dispose_assistance_response(
        workspace,
        "prima",
        request["request_id"],
        "ACCEPTED_AS_DRAFT",
        "Accepted as draft wording only; no automatic assessment mutation.",
        actor="domain-reviewer",
    )
    assert disposed["disposition"]["assessment_mutation"] == "NONE_PERFORMED_BY_DISPOSITION_RECORD"
    assert verify_assistance_record(workspace, "prima", request["request_id"])["valid"] is True


def test_sensitive_prompt_and_unknown_references_are_blocked(workspace) -> None:
    _import_prima(workspace)
    assert scan_sensitive_text("api_key=supersecretvalue")
    with pytest.raises(ValueError, match="sensitive-data guard"):
        create_assistance_request(workspace, "prima", "SUMMARIZE_EVIDENCE", "api_key=supersecretvalue")
    with pytest.raises(ValueError, match="Unknown evidence IDs"):
        create_assistance_request(
            workspace,
            "prima",
            "SUMMARIZE_EVIDENCE",
            "Summarize the selected evidence.",
            evidence_ids=["EV-DOES-NOT-EXIST"],
        )


def test_invalid_model_output_and_tampering_are_detected(workspace, tmp_path: Path) -> None:
    _import_prima(workspace)
    created = create_assistance_request(
        workspace,
        "prima",
        "DRAFT_FINDING",
        "Draft bounded wording.",
        evidence_ids=["EV-PR-001"],
        requirement_ids=["NK-01-R01"],
    )
    request_id = created["request"]["request_id"]

    invalid = _valid_output()
    invalid["suggestions"][0]["evidence_ids"] = ["EV-MISSING"]
    response_file = tmp_path / "invalid.json"
    response_file.write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown IDs"):
        record_assistance_response(workspace, "prima", request_id, response_file, provider="test", model="test")

    response_file.write_text(json.dumps(_valid_output()), encoding="utf-8")
    recorded = record_assistance_response(workspace, "prima", request_id, response_file, provider="test", model="test")
    response_path = Path(recorded["path"])
    response = json.loads(response_path.read_text(encoding="utf-8"))
    response["output"]["summary"] = "tampered"
    response_path.write_text(json.dumps(response), encoding="utf-8")
    verification = verify_assistance_record(workspace, "prima", request_id)
    assert verification["valid"] is False
    assert "response hash mismatch" in verification["errors"]
