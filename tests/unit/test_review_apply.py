from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench.errors import WorkspaceError
from neuroai_workbench.events import load_events
from neuroai_workbench.reports import write_assessment_markdown
from neuroai_workbench.review import (
    REVIEW_PROPOSAL_APPLIED_EVENT,
    apply_review_proposal,
    create_review_assignment,
    dispose_review_statement,
    render_review_markdown,
    submit_review_statement,
)
from neuroai_workbench.util import sha256_file

REPO = Path(__file__).resolve().parents[2]
PRIMA = REPO / "examples" / "assessments" / "PRIMA_Controlled_Assessment_v4.2.1.native.json"
TARGET = "/requirement_findings/NK-01-R01/finding"
PROPOSED = "Bounded finding text after accepted review proposal."


def _setup_accepted(workspace, *, disposition: str = "ACCEPTED", case_id: str = "prima-review") -> tuple[str, str]:
    workspace.import_case(PRIMA, case_id=case_id)
    create_review_assignment(
        workspace,
        case_id,
        "reviewer-1",
        "DOMAIN_REVIEWER",
        ["FINDING:NK-01-R01"],
        actor="lead-1",
    )
    create_review_assignment(
        workspace,
        case_id,
        "lead-1",
        "LEAD_ASSESSOR",
        ["ASSESSMENT:*"],
        actor="assigner-1",
    )
    statement = submit_review_statement(
        workspace,
        case_id,
        "reviewer-1",
        "FINDING",
        "NK-01-R01",
        "DISAGREE",
        "The claim should remain bounded.",
        evidence_ids=["EV-PR-001"],
        proposed_change=PROPOSED,
    )["statement"]
    dispose_review_statement(
        workspace,
        case_id,
        statement["statement_id"],
        disposition,
        "Accepted for separate ordinary edit.",
        actor="lead-1",
    )
    sha = sha256_file(workspace.case_path(case_id) / "assessment.json")
    return statement["statement_id"], sha


def test_apply_review_proposal_success_and_report(workspace, tmp_path: Path) -> None:
    statement_id, sha = _setup_accepted(workspace)
    root = workspace.case_path("prima-review") / "reviews"
    before_statement = (root / "statements" / f"{statement_id}.json").read_bytes()
    before_disposition = (root / "dispositions" / f"{statement_id}.json").read_bytes()
    prior = workspace.load_case("prima-review")["requirement_findings"][0]["finding"]

    result = apply_review_proposal(
        workspace,
        "prima-review",
        statement_id,
        actor="lead-1",
        expected_assessment_sha256=sha,
        field_patches=[{"target_path": TARGET, "value": PROPOSED}],
    )
    assert result["application"]["model_invocation"] == "NONE"
    assert workspace.load_case("prima-review")["requirement_findings"][0]["finding"] == PROPOSED
    assert workspace.load_assessment_history("prima-review", sha)["requirement_findings"][0]["finding"] == prior
    assert (root / "statements" / f"{statement_id}.json").read_bytes() == before_statement
    assert (root / "dispositions" / f"{statement_id}.json").read_bytes() == before_disposition

    events = load_events(workspace.case_path("prima-review") / "events.jsonl")
    assert any(event.get("action") == REVIEW_PROPOSAL_APPLIED_EVENT for event in events)

    report = render_review_markdown(workspace, "prima-review")
    assert statement_id in report
    markdown = tmp_path / "assessment.md"
    write_assessment_markdown(workspace.load_case("prima-review"), markdown)
    assert PROPOSED in markdown.read_text(encoding="utf-8")


def test_apply_review_rejects_rejected_disposition(workspace) -> None:
    statement_id, sha = _setup_accepted(workspace, disposition="REJECTED")
    with pytest.raises(ValueError, match="cannot be applied"):
        apply_review_proposal(
            workspace,
            "prima-review",
            statement_id,
            actor="lead-1",
            expected_assessment_sha256=sha,
            field_patches=[{"target_path": TARGET, "value": PROPOSED}],
        )


def test_apply_review_proposal_authority_and_scope_refusals(workspace) -> None:
    statement_id, sha = _setup_accepted(workspace)
    with pytest.raises(ValueError, match="assessment-edit decision role"):
        apply_review_proposal(
            workspace,
            "prima-review",
            statement_id,
            actor="reviewer-1",
            expected_assessment_sha256=sha,
            field_patches=[{"target_path": TARGET, "value": PROPOSED}],
        )
    with pytest.raises(ValueError, match="outside proposal"):
        apply_review_proposal(
            workspace,
            "prima-review",
            statement_id,
            actor="lead-1",
            expected_assessment_sha256=sha,
            field_patches=[{"target_path": "/requirement_findings/NK-02-R01/finding", "value": "x"}],
        )
    with pytest.raises(ValueError, match="Explicit field_patches"):
        apply_review_proposal(
            workspace,
            "prima-review",
            statement_id,
            actor="lead-1",
            expected_assessment_sha256=sha,
            field_patches=[],
        )


def test_apply_review_cli(workspace, tmp_path: Path) -> None:
    from neuroai_workbench import cli

    statement_id, sha = _setup_accepted(workspace)
    patches = tmp_path / "patches.json"
    patches.write_text(json.dumps([{"target_path": TARGET, "value": PROPOSED}]), encoding="utf-8")
    assert (
        cli.main(
            [
                "review-apply",
                str(workspace.root),
                "prima-review",
                statement_id,
                "--expected-assessment-sha256",
                sha,
                "--patches-file",
                str(patches),
                "--actor",
                "lead-1",
            ]
        )
        == 0
    )


def test_apply_review_optimistic_conflict(workspace) -> None:
    statement_id, sha = _setup_accepted(workspace)
    apply_review_proposal(
        workspace,
        "prima-review",
        statement_id,
        actor="lead-1",
        expected_assessment_sha256=sha,
        field_patches=[{"target_path": TARGET, "value": PROPOSED}],
    )
    with pytest.raises((ValueError, WorkspaceError), match="already|expected|digest|Optimistic"):
        apply_review_proposal(
            workspace,
            "prima-review",
            statement_id,
            actor="lead-1",
            expected_assessment_sha256=sha,
            field_patches=[{"target_path": TARGET, "value": PROPOSED}],
        )
