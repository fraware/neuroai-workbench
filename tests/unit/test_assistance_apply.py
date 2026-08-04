from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench.assistance import (
    ASSISTANCE_PROPOSAL_APPLIED_EVENT,
    apply_assistance_proposal,
    create_assistance_request,
    dispose_assistance_response,
    record_assistance_response,
)
from neuroai_workbench.errors import WorkspaceError
from neuroai_workbench.events import load_events
from neuroai_workbench.exporter import export_case_bundle
from neuroai_workbench.util import sha256_file

REPO = Path(__file__).resolve().parents[2]
PRIMA = REPO / "examples" / "assessments" / "PRIMA_Controlled_Assessment_v4.2.1.native.json"
TARGET = "/requirement_findings/NK-01-R01/finding"
PROPOSED = "The trial configuration is reconstructable; the current commercial configuration remains unresolved."


def _import_prima(workspace) -> None:
    workspace.import_case(PRIMA, case_id="prima")


def _valid_output(text: str = PROPOSED) -> dict:
    return {
        "task_type": "DRAFT_FINDING",
        "summary": "A bounded wording suggestion is supplied for human review.",
        "suggestions": [
            {
                "target_path": TARGET,
                "proposed_text": text,
                "evidence_ids": ["EV-PR-001", "EV-PR-006"],
                "confidence": "HIGH",
                "limitations": ["No current commercial configuration or conformance conclusion follows."],
            }
        ],
        "warnings": ["Human domain review is required."],
    }


def _prepare_disposed(
    workspace,
    tmp_path: Path,
    *,
    disposition: str = "ACCEPTED_AS_DRAFT",
    case_id: str = "prima",
) -> tuple[str, str]:
    if not (workspace.case_path(case_id) / "assessment.json").is_file():
        workspace.import_case(PRIMA, case_id=case_id)
    created = create_assistance_request(
        workspace,
        case_id,
        "DRAFT_FINDING",
        "Draft bounded wording for NK-01-R01 using only the selected evidence.",
        evidence_ids=["EV-PR-001", "EV-PR-006"],
        requirement_ids=["NK-01-R01"],
        actor="reviewer",
    )
    request_id = created["request"]["request_id"]
    response_file = tmp_path / f"response-{request_id}.json"
    response_file.write_text(json.dumps(_valid_output()), encoding="utf-8")
    record_assistance_response(
        workspace,
        case_id,
        request_id,
        response_file,
        provider="manual",
        model="gpt-compatible-test",
        actor="reviewer",
    )
    if disposition:
        dispose_assistance_response(
            workspace,
            case_id,
            request_id,
            disposition,
            "Disposition recorded; apply separately.",
            actor="domain-reviewer",
        )
    sha = sha256_file(workspace.case_path(case_id) / "assessment.json")
    return request_id, sha


def test_apply_assistance_success_preserves_prior_and_bytes(workspace, tmp_path: Path) -> None:
    request_id, sha = _prepare_disposed(workspace, tmp_path)
    root = workspace.case_path("prima") / "assistance"
    before_request = (root / "requests" / f"{request_id}.json").read_bytes()
    before_response = (root / "responses" / f"{request_id}.json").read_bytes()
    before_disposition = (root / "dispositions" / f"{request_id}.json").read_bytes()
    prior_finding = workspace.load_case("prima")["requirement_findings"][0]["finding"]

    result = apply_assistance_proposal(
        workspace,
        "prima",
        request_id,
        actor="domain-reviewer",
        expected_assessment_sha256=sha,
        field_patches=[{"target_path": TARGET, "value": PROPOSED}],
    )
    assert result["application"]["model_invocation"] == "NONE"
    assert result["application"]["before_assessment_sha256"] == sha
    assert result["save"]["after_sha256"] == result["application"]["after_assessment_sha256"]
    assert workspace.load_case("prima")["requirement_findings"][0]["finding"] == PROPOSED

    history = workspace.load_assessment_history("prima", sha)
    assert history["requirement_findings"][0]["finding"] == prior_finding

    assert (root / "requests" / f"{request_id}.json").read_bytes() == before_request
    assert (root / "responses" / f"{request_id}.json").read_bytes() == before_response
    assert (root / "dispositions" / f"{request_id}.json").read_bytes() == before_disposition

    events = load_events(workspace.case_path("prima") / "events.jsonl")
    applied = [event for event in events if event.get("action") == ASSISTANCE_PROPOSAL_APPLIED_EVENT]
    assert len(applied) == 1
    payload = applied[0]["payload"]
    assert payload["proposal_id"] == request_id
    assert payload["disposition_sha256"] == result["application"]["disposition_sha256"]
    assert payload["before_assessment_sha256"] == sha
    assert payload["after_assessment_sha256"] == result["application"]["after_assessment_sha256"]
    assert payload["model_invocation"] == "NONE"

    saved = [event for event in events if event.get("action") == "ASSESSMENT_SAVED"][-1]
    assert saved["payload"]["apply_provenance"]["proposal_id"] == request_id
    assert "prior_history" in saved["payload"]


def test_apply_assistance_rejects_rejected_disposition(workspace, tmp_path: Path) -> None:
    request_id, sha = _prepare_disposed(workspace, tmp_path, disposition="REJECTED")
    with pytest.raises(ValueError, match="cannot be applied"):
        apply_assistance_proposal(
            workspace,
            "prima",
            request_id,
            actor="domain-reviewer",
            expected_assessment_sha256=sha,
            field_patches=[{"target_path": TARGET, "value": PROPOSED}],
        )


def test_apply_assistance_refusal_matrix(workspace, tmp_path: Path) -> None:
    request_id, _sha = _prepare_disposed(workspace, tmp_path, disposition="")
    # Manual path: prepare without dispose when disposition falsy - but dispose was skipped
    root = workspace.case_path("prima") / "assistance"
    assert not (root / "dispositions" / f"{request_id}.json").is_file()
    current = sha256_file(workspace.case_path("prima") / "assessment.json")
    with pytest.raises(ValueError, match="No disposition"):
        apply_assistance_proposal(
            workspace,
            "prima",
            request_id,
            actor="domain-reviewer",
            expected_assessment_sha256=current,
            field_patches=[{"target_path": TARGET, "value": PROPOSED}],
        )

    dispose_assistance_response(workspace, "prima", request_id, "PARTIALLY_USED", "partial", actor="domain-reviewer")
    with pytest.raises(ValueError, match="Stale assessment|expected_assessment_sha256"):
        apply_assistance_proposal(
            workspace,
            "prima",
            request_id,
            actor="domain-reviewer",
            expected_assessment_sha256="0" * 64,
            field_patches=[{"target_path": TARGET, "value": PROPOSED}],
        )
    with pytest.raises(ValueError, match="outside proposal"):
        apply_assistance_proposal(
            workspace,
            "prima",
            request_id,
            actor="domain-reviewer",
            expected_assessment_sha256=current,
            field_patches=[{"target_path": "/requirement_findings/NK-01-R01/owner", "value": "x"}],
        )
    with pytest.raises(ValueError, match="Explicit field_patches"):
        apply_assistance_proposal(
            workspace,
            "prima",
            request_id,
            actor="domain-reviewer",
            expected_assessment_sha256=current,
            field_patches=[],
        )

    apply_assistance_proposal(
        workspace,
        "prima",
        request_id,
        actor="domain-reviewer",
        expected_assessment_sha256=current,
        field_patches=[{"target_path": TARGET, "value": PROPOSED}],
    )
    with pytest.raises(ValueError, match="already been applied"):
        apply_assistance_proposal(
            workspace,
            "prima",
            request_id,
            actor="domain-reviewer",
            expected_assessment_sha256=sha256_file(workspace.case_path("prima") / "assessment.json"),
            field_patches=[{"target_path": TARGET, "value": PROPOSED}],
        )


def test_apply_assistance_no_model_call(workspace, tmp_path: Path, monkeypatch) -> None:
    request_id, sha = _prepare_disposed(workspace, tmp_path)
    calls: list[str] = []

    def blocked(*_args, **_kwargs):
        calls.append("network")
        raise AssertionError("external model call must not occur")

    monkeypatch.setattr("urllib.request.urlopen", blocked)
    apply_assistance_proposal(
        workspace,
        "prima",
        request_id,
        actor="domain-reviewer",
        expected_assessment_sha256=sha,
        field_patches=[{"target_path": TARGET, "value": PROPOSED}],
    )
    assert calls == []


def test_apply_assistance_optimistic_conflict(workspace, tmp_path: Path) -> None:
    request_id, sha = _prepare_disposed(workspace, tmp_path)
    apply_assistance_proposal(
        workspace,
        "prima",
        request_id,
        actor="domain-reviewer",
        expected_assessment_sha256=sha,
        field_patches=[{"target_path": TARGET, "value": PROPOSED}],
    )
    with pytest.raises((ValueError, WorkspaceError), match="already|expected|digest|Optimistic"):
        apply_assistance_proposal(
            workspace,
            "prima",
            request_id,
            actor="domain-reviewer",
            expected_assessment_sha256=sha,
            field_patches=[{"target_path": TARGET, "value": PROPOSED}],
        )


def test_apply_assistance_integrity_refusals(workspace, tmp_path: Path) -> None:
    request_id, sha = _prepare_disposed(workspace, tmp_path)
    root = workspace.case_path("prima") / "assistance"

    with pytest.raises(ValueError, match="expected_assessment_sha256"):
        apply_assistance_proposal(
            workspace,
            "prima",
            request_id,
            actor="domain-reviewer",
            expected_assessment_sha256="",
            field_patches=[{"target_path": TARGET, "value": PROPOSED}],
        )
    with pytest.raises(ValueError, match="field_patches"):
        apply_assistance_proposal(
            workspace,
            "prima",
            request_id,
            actor="domain-reviewer",
            expected_assessment_sha256=sha,
            field_patches=[{"target_path": TARGET}],  # type: ignore[list-item]
        )

    request_path = root / "requests" / f"{request_id}.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["prompt"] = "tampered"
    request_path.write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="request hash"):
        apply_assistance_proposal(
            workspace,
            "prima",
            request_id,
            actor="domain-reviewer",
            expected_assessment_sha256=sha,
            field_patches=[{"target_path": TARGET, "value": PROPOSED}],
        )


def test_apply_assistance_assessment_drift(workspace, tmp_path: Path) -> None:
    request_id, sha = _prepare_disposed(workspace, tmp_path)
    assessment = workspace.load_case("prima")
    assessment["assessment_metadata"]["title"] = "Drifted title"
    workspace.save_case("prima", assessment, require_valid=False)
    with pytest.raises(ValueError, match="Stale assessment"):
        apply_assistance_proposal(
            workspace,
            "prima",
            request_id,
            actor="domain-reviewer",
            expected_assessment_sha256=sha,
            field_patches=[{"target_path": TARGET, "value": PROPOSED}],
        )
    current = sha256_file(workspace.case_path("prima") / "assessment.json")
    with pytest.raises(ValueError, match="ASSESSMENT_DRIFT"):
        apply_assistance_proposal(
            workspace,
            "prima",
            request_id,
            actor="domain-reviewer",
            expected_assessment_sha256=current,
            field_patches=[{"target_path": TARGET, "value": PROPOSED}],
        )


def test_apply_assistance_record_tamper_refusals(workspace, tmp_path: Path) -> None:
    request_id, sha = _prepare_disposed(workspace, tmp_path)
    root = workspace.case_path("prima") / "assistance"
    response_path = root / "responses" / f"{request_id}.json"
    disposition_path = root / "dispositions" / f"{request_id}.json"

    response_path.unlink()
    with pytest.raises(FileNotFoundError, match="No response"):
        apply_assistance_proposal(
            workspace,
            "prima",
            request_id,
            actor="domain-reviewer",
            expected_assessment_sha256=sha,
            field_patches=[{"target_path": TARGET, "value": PROPOSED}],
        )

    request_id, sha = _prepare_disposed(workspace, tmp_path, case_id="prima2")
    root = workspace.case_path("prima2") / "assistance"
    response_path = root / "responses" / f"{request_id}.json"
    disposition_path = root / "dispositions" / f"{request_id}.json"
    response = json.loads(response_path.read_text(encoding="utf-8"))
    response["provider"] = "tampered"
    response_path.write_text(json.dumps(response, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="response hash"):
        apply_assistance_proposal(
            workspace,
            "prima2",
            request_id,
            actor="domain-reviewer",
            expected_assessment_sha256=sha,
            field_patches=[{"target_path": TARGET, "value": PROPOSED}],
        )

    request_id, sha = _prepare_disposed(workspace, tmp_path, case_id="prima3")
    root = workspace.case_path("prima3") / "assistance"
    disposition_path = root / "dispositions" / f"{request_id}.json"
    disposition = json.loads(disposition_path.read_text(encoding="utf-8"))
    disposition["notes"] = "tampered"
    disposition_path.write_text(json.dumps(disposition, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="disposition hash"):
        apply_assistance_proposal(
            workspace,
            "prima3",
            request_id,
            actor="domain-reviewer",
            expected_assessment_sha256=sha,
            field_patches=[{"target_path": TARGET, "value": PROPOSED}],
        )


def test_apply_assistance_cli_and_export(workspace, tmp_path: Path) -> None:
    from neuroai_workbench import cli

    request_id, sha = _prepare_disposed(workspace, tmp_path)
    patches = tmp_path / "patches.json"
    patches.write_text(json.dumps([{"target_path": TARGET, "value": PROPOSED}]), encoding="utf-8")
    assert (
        cli.main(
            [
                "assist-apply",
                str(workspace.root),
                "prima",
                request_id,
                "--expected-assessment-sha256",
                sha,
                "--patches-file",
                str(patches),
                "--actor",
                "domain-reviewer",
            ]
        )
        == 0
    )
    bundle = tmp_path / "bundle.zip"
    export_case_bundle(workspace, "prima", bundle)
    assert bundle.is_file()
    assert sha256_file(workspace.case_path("prima") / "assessment.json") != sha
