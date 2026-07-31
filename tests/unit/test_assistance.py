from __future__ import annotations

import json
import uuid
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


def test_stale_assistance_response_is_rejected(workspace, tmp_path: Path) -> None:
    _import_prima(workspace)
    created = create_assistance_request(
        workspace,
        "prima",
        "DRAFT_FINDING",
        "Draft bounded wording.",
        evidence_ids=["EV-PR-001"],
        requirement_ids=["NK-01-R01"],
    )
    assert created["request"]["disclosure_policy"] == "ATTESTATION_PLUS_SECRET_SCAN_ONLY"
    assessment = workspace.load_case("prima")
    assessment["assessment_metadata"]["title"] = "Changed after request"
    workspace.save_case("prima", assessment, actor="reviewer", require_valid=True)
    response_file = tmp_path / "response.json"
    response_file.write_text(json.dumps(_valid_output()), encoding="utf-8")
    with pytest.raises(ValueError, match="stale"):
        record_assistance_response(
            workspace,
            "prima",
            created["request"]["request_id"],
            response_file,
            provider="manual",
            model="test",
        )


def test_dispose_rejects_assessment_drift(workspace, tmp_path: Path) -> None:
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
    response_file = tmp_path / "response.json"
    response_file.write_text(json.dumps(_valid_output()), encoding="utf-8")
    record_assistance_response(workspace, "prima", request_id, response_file, provider="test", model="test")
    assessment = workspace.load_case("prima")
    assessment["assessment_metadata"]["title"] = "Changed after response"
    workspace.save_case("prima", assessment, actor="reviewer", require_valid=True)
    with pytest.raises(ValueError, match="ASSESSMENT_DRIFT"):
        dispose_assistance_response(
            workspace,
            "prima",
            request_id,
            "REJECTED",
            "Rejected after drift.",
            actor="domain-reviewer",
        )
    verification = verify_assistance_record(workspace, "prima", request_id)
    assert verification["valid"] is False
    assert "ASSESSMENT_DRIFT" in verification["errors"]


def test_pending_review_is_not_a_final_disposition(workspace, tmp_path: Path) -> None:
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
    response_file = tmp_path / "response.json"
    response_file.write_text(json.dumps(_valid_output()), encoding="utf-8")
    record_assistance_response(workspace, "prima", request_id, response_file, provider="test", model="test")
    with pytest.raises(ValueError, match="Unsupported disposition"):
        dispose_assistance_response(
            workspace,
            "prima",
            request_id,
            "PENDING_REVIEW",
            "Not a final disposition.",
            actor="domain-reviewer",
        )


def test_model_output_secret_patterns_are_rejected(workspace, tmp_path: Path) -> None:
    _import_prima(workspace)
    created = create_assistance_request(
        workspace,
        "prima",
        "DRAFT_FINDING",
        "Draft bounded wording.",
        evidence_ids=["EV-PR-001"],
        requirement_ids=["NK-01-R01"],
    )
    poisoned = _valid_output()
    poisoned["summary"] = "Contains api_key=supersecretvalue which must be blocked."
    response_file = tmp_path / "poisoned.json"
    response_file.write_text(json.dumps(poisoned), encoding="utf-8")
    with pytest.raises(ValueError, match="sensitive-data guard"):
        record_assistance_response(
            workspace,
            "prima",
            created["request"]["request_id"],
            response_file,
            provider="test",
            model="test",
        )


def test_request_id_uses_uuid_and_refuses_collision(workspace, monkeypatch) -> None:
    _import_prima(workspace)
    fixed = uuid.UUID("12345678-1234-5678-1234-567812345678")
    monkeypatch.setattr("neuroai_workbench.assistance.uuid.uuid4", lambda: fixed)
    first = create_assistance_request(
        workspace,
        "prima",
        "DRAFT_FINDING",
        "Draft bounded wording.",
        evidence_ids=["EV-PR-001"],
        requirement_ids=["NK-01-R01"],
    )
    assert first["request"]["request_id"] == f"AI-{fixed.hex}"
    with pytest.raises(ValueError, match="already exists"):
        create_assistance_request(
            workspace,
            "prima",
            "DRAFT_FINDING",
            "Draft bounded wording again.",
            evidence_ids=["EV-PR-001"],
            requirement_ids=["NK-01-R01"],
        )


def test_assistance_error_paths_and_verify_failures(workspace, tmp_path: Path) -> None:
    from neuroai_workbench.assistance import _case_assistance_dir
    from neuroai_workbench.errors import WorkspaceError

    workspace.create_case("CASE-001", "Case")
    with pytest.raises(WorkspaceError, match="Unknown case"):
        create_assistance_request(workspace, "MISSING", "DRAFT_FINDING", "prompt")
    (workspace.case_path("CASE-001") / "assessment.json").unlink()
    with pytest.raises(ValueError, match="Unknown case"):
        _case_assistance_dir(workspace, "CASE-001")
    _import_prima(workspace)
    with pytest.raises(ValueError, match="Unsupported task"):
        create_assistance_request(workspace, "prima", "NOT_A_TASK", "prompt")
    with pytest.raises(ValueError, match="must not be empty"):
        create_assistance_request(workspace, "prima", "DRAFT_FINDING", "   ")
    with pytest.raises(ValueError, match="Unknown requirement IDs"):
        create_assistance_request(
            workspace,
            "prima",
            "DRAFT_FINDING",
            "Draft.",
            evidence_ids=["EV-PR-001"],
            requirement_ids=["NK-DOES-NOT-EXIST"],
        )
    # Sensitive context guard: inject a secret into selected structured context.
    assessment = workspace.load_case("prima")
    for item in assessment["evidence_register"]:
        if item.get("evidence_id") == "EV-PR-001":
            item["title"] = "api_key=supersecretvalue"
            break
    workspace.save_case("prima", assessment, actor="reviewer", require_valid=False)
    with pytest.raises(ValueError, match="sensitive-data guard"):
        create_assistance_request(
            workspace,
            "prima",
            "DRAFT_FINDING",
            "Draft.",
            evidence_ids=["EV-PR-001"],
            requirement_ids=["NK-01-R01"],
        )
    assessment = workspace.load_case("prima")
    for item in assessment["evidence_register"]:
        if item.get("evidence_id") == "EV-PR-001":
            item["title"] = "Restored title"
            break
    workspace.save_case("prima", assessment, actor="reviewer", require_valid=False)
    created = create_assistance_request(
        workspace,
        "prima",
        "DRAFT_FINDING",
        "Draft bounded wording.",
        evidence_ids=["EV-PR-001"],
        requirement_ids=["NK-01-R01"],
    )
    request_id = created["request"]["request_id"]
    request_path = Path(created["path"])
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["prompt"] = "tampered"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    response_file = tmp_path / "response.json"
    response_file.write_text(json.dumps(_valid_output()), encoding="utf-8")
    with pytest.raises(ValueError, match="hash is invalid"):
        record_assistance_response(workspace, "prima", request_id, response_file, provider="t", model="t")

    # Restore a valid request and exercise output contract / duplicate response / dispose paths.
    fresh = create_assistance_request(
        workspace,
        "prima",
        "DRAFT_FINDING",
        "Draft bounded wording again.",
        evidence_ids=["EV-PR-001"],
        requirement_ids=["NK-01-R01"],
    )
    request_id = fresh["request"]["request_id"]
    bad_outputs = [
        "not-an-object",
        {"task_type": "WRONG", "summary": "x", "suggestions": [], "warnings": []},
        {"task_type": "DRAFT_FINDING", "summary": " ", "suggestions": [], "warnings": []},
        {"task_type": "DRAFT_FINDING", "summary": "ok", "suggestions": "bad", "warnings": []},
        {"task_type": "DRAFT_FINDING", "summary": "ok", "suggestions": [], "warnings": "bad"},
        {
            "task_type": "DRAFT_FINDING",
            "summary": "ok",
            "suggestions": ["bad"],
            "warnings": [],
        },
        {
            "task_type": "DRAFT_FINDING",
            "summary": "ok",
            "suggestions": [
                {"target_path": "", "proposed_text": "", "evidence_ids": "x", "confidence": "NO", "limitations": "x"}
            ],
            "warnings": [],
        },
    ]
    for bad in bad_outputs:
        response_file.write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(ValueError, match="contract validation|Model output"):
            record_assistance_response(workspace, "prima", request_id, response_file, provider="t", model="t")

    response_file.write_text(json.dumps(_valid_output()), encoding="utf-8")
    record_assistance_response(workspace, "prima", request_id, response_file, provider="t", model="t")
    with pytest.raises(ValueError, match="already recorded"):
        record_assistance_response(workspace, "prima", request_id, response_file, provider="t", model="t")
    with pytest.raises(ValueError, match="Unsupported disposition"):
        dispose_assistance_response(workspace, "prima", request_id, "NOPE", "notes")
    disposed = dispose_assistance_response(workspace, "prima", request_id, "REJECTED", "notes")
    assert disposed["disposition"]["disposition"] == "REJECTED"
    with pytest.raises(ValueError, match="already recorded"):
        dispose_assistance_response(workspace, "prima", request_id, "REJECTED", "again")

    # Verify failure branches via tampered disposition and missing response linkage.
    other = create_assistance_request(
        workspace,
        "prima",
        "IDENTIFY_GAPS",
        "Identify gaps.",
        evidence_ids=["EV-PR-001"],
        requirement_ids=["NK-01-R01"],
    )
    other_id = other["request"]["request_id"]
    response_file.write_text(json.dumps({**_valid_output(), "task_type": "IDENTIFY_GAPS"}), encoding="utf-8")
    recorded = record_assistance_response(workspace, "prima", other_id, response_file, provider="t", model="t")
    dispose_assistance_response(workspace, "prima", other_id, "PARTIALLY_USED", "partial")
    disposition_path = Path(recorded["path"]).parent.parent / "dispositions" / f"{other_id}.json"
    disposition = json.loads(disposition_path.read_text(encoding="utf-8"))
    disposition["notes"] = "tampered"
    disposition_path.write_text(json.dumps(disposition), encoding="utf-8")
    verification = verify_assistance_record(workspace, "prima", other_id)
    assert verification["valid"] is False
    assert "disposition hash mismatch" in verification["errors"]


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
