from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from neuroai_workbench.cli import build_parser
from neuroai_workbench.events import load_events
from neuroai_workbench.review import (
    _hash_record,
    create_review_assignment,
    render_review_markdown,
    revoke_review_assignment,
    submit_review_statement,
    supersede_review_assignment,
    verify_review_records,
)
from neuroai_workbench.workspace import Workspace


def _workspace(tmp_path: Path) -> tuple[Workspace, str, str]:
    workspace = Workspace.initialize(tmp_path / "workspace")
    assessment = workspace.create_case("CASE-REVIEW", "Review assignment lineage")
    finding_id = str(assessment["requirement_findings"][0]["requirement_id"])
    return workspace, "CASE-REVIEW", finding_id


def test_revoke_is_append_only_and_blocks_future_statements(tmp_path: Path) -> None:
    workspace, case_id, finding_id = _workspace(tmp_path)
    assessment_path = workspace.case_path(case_id) / "assessment.json"
    before_assessment = assessment_path.read_bytes()
    created = create_review_assignment(
        workspace,
        case_id,
        "reviewer-1",
        "DOMAIN_REVIEWER",
        [f"FINDING:{finding_id}"],
        actor="lead-1",
    )
    original_path = Path(created["path"])
    original_bytes = original_path.read_bytes()
    statement = submit_review_statement(
        workspace,
        case_id,
        "reviewer-1",
        "FINDING",
        finding_id,
        "DISAGREE",
        "The claim boundary should remain narrower.",
    )["statement"]

    revoked = revoke_review_assignment(
        workspace,
        case_id,
        created["assignment"]["assignment_id"],
        "Reviewer availability ended.",
        actor="reviewer-1",
    )["assignment"]

    assert original_path.read_bytes() == original_bytes
    assert revoked["state"] == "REVOKED"
    assert revoked["transition"] == "REVOKES"
    assert revoked["predecessor_assignment_id"] == created["assignment"]["assignment_id"]
    assert revoked["assessment_mutation"] == "NONE_PERFORMED_BY_ASSIGNMENT_TRANSITION"
    assert assessment_path.read_bytes() == before_assessment

    with pytest.raises(ValueError, match="no active assignment"):
        submit_review_statement(
            workspace,
            case_id,
            "reviewer-1",
            "FINDING",
            finding_id,
            "AGREE",
            "A post-revocation statement must be refused.",
        )

    report = verify_review_records(workspace, case_id)
    assert report["valid"] is True
    assert report["assignment_summary"] == {
        "active": 0,
        "supersessions": 0,
        "revocations": 1,
        "records": 2,
    }
    assert report["counts"]["statements"] == 1
    assert statement["statement_id"] in render_review_markdown(workspace, case_id)
    assert "REVIEW_ASSIGNMENT_REVOKED" in {
        event["action"] for event in load_events(workspace.case_path(case_id) / "events.jsonl")
    }


def test_supersede_transfers_authority_without_overwriting_history(tmp_path: Path) -> None:
    workspace, case_id, finding_id = _workspace(tmp_path)
    created = create_review_assignment(
        workspace,
        case_id,
        "reviewer-1",
        "DOMAIN_REVIEWER",
        [f"FINDING:{finding_id}"],
        actor="lead-1",
    )
    original_path = Path(created["path"])
    original_bytes = original_path.read_bytes()

    successor = supersede_review_assignment(
        workspace,
        case_id,
        created["assignment"]["assignment_id"],
        "reviewer-2",
        "METHODS_REVIEWER",
        [f"FINDING:{finding_id}"],
        "Transfer the review to the methods track.",
        actor="lead-1",
    )["assignment"]

    assert original_path.read_bytes() == original_bytes
    assert successor["transition"] == "SUPERSEDES"
    assert successor["state"] == "ACTIVE"
    assert successor["predecessor_assignment_sha256"] == created["assignment"]["assignment_sha256"]

    with pytest.raises(ValueError, match="no active assignment"):
        submit_review_statement(
            workspace,
            case_id,
            "reviewer-1",
            "FINDING",
            finding_id,
            "AGREE",
            "The predecessor assignment is no longer effective.",
        )
    submitted = submit_review_statement(
        workspace,
        case_id,
        "reviewer-2",
        "FINDING",
        finding_id,
        "AGREE_WITH_CONDITIONS",
        "Support is conditional on a narrower methods statement.",
    )["statement"]
    assert submitted["assignment_ids"] == [successor["assignment_id"]]

    report = verify_review_records(workspace, case_id)
    assert report["valid"] is True
    assert report["assignment_summary"] == {
        "active": 1,
        "supersessions": 1,
        "revocations": 0,
        "records": 2,
    }
    markdown = render_review_markdown(workspace, case_id)
    assert "SUPERSEDED" in markdown
    assert successor["assignment_id"] in markdown
    assert created["assignment"]["assignment_id"] in markdown


def test_reviewer_may_relinquish_but_may_not_appoint_successor(tmp_path: Path) -> None:
    workspace, case_id, finding_id = _workspace(tmp_path)
    created = create_review_assignment(
        workspace,
        case_id,
        "reviewer-1",
        "DOMAIN_REVIEWER",
        [f"FINDING:{finding_id}"],
        actor="lead-1",
    )["assignment"]

    with pytest.raises(ValueError, match="not authorized to supersede"):
        supersede_review_assignment(
            workspace,
            case_id,
            created["assignment_id"],
            "reviewer-2",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            "A reviewer cannot appoint a successor.",
            actor="reviewer-1",
        )

    revoked = revoke_review_assignment(
        workspace,
        case_id,
        created["assignment_id"],
        "The reviewer relinquishes the assignment.",
        actor="reviewer-1",
    )["assignment"]
    assert revoked["transition_by"] == "reviewer-1"


def test_decision_role_may_control_covering_assignment(tmp_path: Path) -> None:
    workspace, case_id, finding_id = _workspace(tmp_path)
    target = create_review_assignment(
        workspace,
        case_id,
        "reviewer-1",
        "DOMAIN_REVIEWER",
        [f"FINDING:{finding_id}"],
        actor="assigner-1",
    )["assignment"]
    create_review_assignment(
        workspace,
        case_id,
        "lead-1",
        "LEAD_ASSESSOR",
        ["ASSESSMENT:*"],
        actor="assigner-1",
    )

    successor = supersede_review_assignment(
        workspace,
        case_id,
        target["assignment_id"],
        "reviewer-2",
        "SECURITY_REVIEWER",
        [f"FINDING:{finding_id}"],
        "The lead reassigns the bounded review.",
        actor="lead-1",
    )["assignment"]
    assert successor["assigned_by"] == "lead-1"


def test_lineage_tampering_is_detected_and_cannot_authorize(tmp_path: Path) -> None:
    workspace, case_id, finding_id = _workspace(tmp_path)
    created = create_review_assignment(
        workspace,
        case_id,
        "reviewer-1",
        "DOMAIN_REVIEWER",
        [f"FINDING:{finding_id}"],
        actor="lead-1",
    )
    successor = supersede_review_assignment(
        workspace,
        case_id,
        created["assignment"]["assignment_id"],
        "reviewer-2",
        "DOMAIN_REVIEWER",
        [f"FINDING:{finding_id}"],
        "Legitimate transfer.",
        actor="lead-1",
    )
    successor_path = Path(successor["path"])
    record = json.loads(successor_path.read_text(encoding="utf-8"))
    record["predecessor_assignment_sha256"] = "0" * 64
    record["assignment_sha256"] = _hash_record(record, "assignment_sha256")
    successor_path.write_text(json.dumps(record), encoding="utf-8")

    report = verify_review_records(workspace, case_id)
    assert report["valid"] is False
    assert any("predecessor hash mismatch" in error for error in report["errors"])
    with pytest.raises(ValueError, match="predecessor hash mismatch"):
        submit_review_statement(
            workspace,
            case_id,
            "reviewer-2",
            "FINDING",
            finding_id,
            "AGREE",
            "Tampered lineage must not authorize a statement.",
        )


def test_assignment_transition_is_single_successor_under_concurrency(tmp_path: Path) -> None:
    workspace, case_id, finding_id = _workspace(tmp_path)
    assignment = create_review_assignment(
        workspace,
        case_id,
        "reviewer-1",
        "DOMAIN_REVIEWER",
        [f"FINDING:{finding_id}"],
        actor="lead-1",
    )["assignment"]

    def revoke(reason: str) -> str:
        result = revoke_review_assignment(
            workspace,
            case_id,
            assignment["assignment_id"],
            reason,
            actor="lead-1",
        )
        return str(result["assignment"]["assignment_id"])

    outcomes: list[str] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(revoke, f"reason-{index}") for index in range(2)]
        for future in futures:
            try:
                outcomes.append(future.result())
            except ValueError as exc:
                errors.append(str(exc))

    assert len(outcomes) == 1
    assert len(errors) == 1
    assert "not an active lineage tip" in errors[0]
    report = verify_review_records(workspace, case_id)
    assert report["valid"] is True
    assert report["assignment_summary"]["revocations"] == 1


def test_cli_exposes_revocation_and_supersession_commands() -> None:
    parser = build_parser()
    revoke = parser.parse_args(
        [
            "review-revoke",
            "WORKSPACE",
            "CASE",
            "RA-1",
            "--rationale",
            "End assignment",
            "--actor",
            "lead-1",
        ]
    )
    assert revoke.command == "review-revoke"
    supersede = parser.parse_args(
        [
            "review-supersede",
            "WORKSPACE",
            "CASE",
            "RA-1",
            "reviewer-2",
            "DOMAIN_REVIEWER",
            "--scope",
            "ASSESSMENT:*",
            "--rationale",
            "Transfer assignment",
            "--actor",
            "lead-1",
        ]
    )
    assert supersede.command == "review-supersede"
