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
from neuroai_workbench.events import load_events
from neuroai_workbench.review import create_review_assignment
from neuroai_workbench.util import sha256_file

REPO = Path(__file__).resolve().parents[2]
PRIMA = REPO / "examples" / "assessments" / "PRIMA_Controlled_Assessment_v4.2.1.native.json"
TARGET = "/requirement_findings/NK-01-R01/finding"
SECOND_TARGET = "/requirement_findings/NK-01-R01/strongest_supported_claim"
TEXT = "Exact accepted proposal text."
SECOND_TEXT = "Exact accepted bounded claim."


def _suggestion(path: str, text: str) -> dict[str, object]:
    return {
        "target_path": path,
        "proposed_text": text,
        "evidence_ids": ["EV-PR-001"],
        "confidence": "HIGH",
        "limitations": [],
    }


def _prepare_assistance(
    workspace,
    tmp_path: Path,
    *,
    disposition: str = "ACCEPTED_AS_DRAFT",
    suggestions=None,
):
    workspace.import_case(PRIMA, case_id="prima")
    create_review_assignment(
        workspace,
        "prima",
        "lead-1",
        "LEAD_ASSESSOR",
        ["FINDING:NK-01-R01"],
        actor="assigner-1",
    )
    request = create_assistance_request(
        workspace,
        "prima",
        "DRAFT_FINDING",
        "Draft bounded finding text.",
        requirement_ids=["NK-01-R01"],
        actor="requester-1",
    )["request"]
    output = {
        "task_type": "DRAFT_FINDING",
        "summary": "Bounded proposal.",
        "suggestions": suggestions or [_suggestion(TARGET, TEXT)],
        "warnings": [],
    }
    output_path = tmp_path / "output.json"
    output_path.write_text(json.dumps(output), encoding="utf-8")
    record_assistance_response(
        workspace,
        "prima",
        request["request_id"],
        output_path,
        provider="fixture",
        model="fixture",
        actor="recorder-1",
    )
    dispose_assistance_response(
        workspace,
        "prima",
        request["request_id"],
        disposition,
        "Human disposition.",
        actor="reviewer-1",
    )
    return request["request_id"], sha256_file(workspace.case_path("prima") / "assessment.json")


def test_assistance_apply_exact_authority_and_immutability(workspace, tmp_path: Path) -> None:
    request_id, before_sha = _prepare_assistance(workspace, tmp_path)
    root = workspace.case_path("prima") / "assistance"
    source_paths = [
        root / "requests" / f"{request_id}.json",
        root / "responses" / f"{request_id}.json",
        root / "dispositions" / f"{request_id}.json",
    ]
    source_bytes = [path.read_bytes() for path in source_paths]
    prior = workspace.load_case("prima")["requirement_findings"][0]["finding"]

    result = apply_assistance_proposal(
        workspace,
        "prima",
        request_id,
        actor="lead-1",
        expected_assessment_sha256=before_sha,
        field_patches=[{"target_path": TARGET, "value": TEXT}],
    )

    assert workspace.load_case("prima")["requirement_findings"][0]["finding"] == TEXT
    assert workspace.load_assessment_history("prima", before_sha)["requirement_findings"][0]["finding"] == prior
    assert [path.read_bytes() for path in source_paths] == source_bytes
    assert result["application"]["authority_assignments"]
    assert result["application"]["field_patches"][0]["expected_value"] == prior
    events = load_events(workspace.case_path("prima") / "events.jsonl")
    saved = [event for event in events if event.get("action") == "ASSESSMENT_SAVED"][-1]
    assert saved["payload"]["related_events"][0]["action"] == ASSISTANCE_PROPOSAL_APPLIED_EVENT
    assert all(event.get("action") != ASSISTANCE_PROPOSAL_APPLIED_EVENT for event in events)


def test_assistance_apply_refuses_unassigned_actor(workspace, tmp_path: Path) -> None:
    request_id, before_sha = _prepare_assistance(workspace, tmp_path)
    with pytest.raises(ValueError, match="assessment-edit decision role"):
        apply_assistance_proposal(
            workspace,
            "prima",
            request_id,
            actor="unassigned-intruder",
            expected_assessment_sha256=before_sha,
            field_patches=[{"target_path": TARGET, "value": TEXT}],
        )


def test_assistance_apply_refuses_arbitrary_text(workspace, tmp_path: Path) -> None:
    request_id, before_sha = _prepare_assistance(workspace, tmp_path)
    with pytest.raises(ValueError, match="exactly bound"):
        apply_assistance_proposal(
            workspace,
            "prima",
            request_id,
            actor="lead-1",
            expected_assessment_sha256=before_sha,
            field_patches=[{"target_path": TARGET, "value": "Unrelated replacement."}],
        )


@pytest.mark.parametrize(
    ("disposition", "suggestions", "patches", "message"),
    [
        (
            "ACCEPTED_AS_DRAFT",
            [_suggestion(TARGET, TEXT), _suggestion(SECOND_TARGET, SECOND_TEXT)],
            [{"target_path": TARGET, "value": TEXT}],
            "must apply every",
        ),
        (
            "PARTIALLY_USED",
            [_suggestion(TARGET, TEXT)],
            [{"target_path": TARGET, "value": TEXT}],
            "proper subset",
        ),
    ],
)
def test_assistance_apply_enforces_full_and_partial_semantics(
    workspace, tmp_path: Path, disposition, suggestions, patches, message
) -> None:
    request_id, before_sha = _prepare_assistance(
        workspace,
        tmp_path,
        disposition=disposition,
        suggestions=suggestions,
    )
    with pytest.raises(ValueError, match=message):
        apply_assistance_proposal(
            workspace,
            "prima",
            request_id,
            actor="lead-1",
            expected_assessment_sha256=before_sha,
            field_patches=patches,
        )


def test_assistance_partial_subset_succeeds(workspace, tmp_path: Path) -> None:
    request_id, before_sha = _prepare_assistance(
        workspace,
        tmp_path,
        disposition="PARTIALLY_USED",
        suggestions=[_suggestion(TARGET, TEXT), _suggestion(SECOND_TARGET, SECOND_TEXT)],
    )
    result = apply_assistance_proposal(
        workspace,
        "prima",
        request_id,
        actor="lead-1",
        expected_assessment_sha256=before_sha,
        field_patches=[{"target_path": TARGET, "value": TEXT}],
    )
    assert result["application"]["disposition"] == "PARTIALLY_USED"


def test_assistance_apply_cli_uses_hardened_path(workspace, tmp_path: Path) -> None:
    from neuroai_workbench import cli

    request_id, before_sha = _prepare_assistance(workspace, tmp_path)
    patches = tmp_path / "patches.json"
    patches.write_text(
        json.dumps([{"target_path": TARGET, "value": TEXT}]),
        encoding="utf-8",
    )
    assert (
        cli.main(
            [
                "assist-apply",
                str(workspace.root),
                "prima",
                request_id,
                "--expected-assessment-sha256",
                before_sha,
                "--patches-file",
                str(patches),
                "--actor",
                "lead-1",
            ]
        )
        == 0
    )
