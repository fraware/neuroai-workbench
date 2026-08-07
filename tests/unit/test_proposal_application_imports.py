from __future__ import annotations

from pathlib import Path

import neuroai_workbench._review_records as review_records
import neuroai_workbench.review as review
from neuroai_workbench.proposal_application import apply_review_proposal, assessment_edit_authority_assignments

REPO = Path(__file__).resolve().parents[2]
PRIMA = REPO / "examples" / "assessments" / "PRIMA_Controlled_Assessment_v4.2.1.native.json"


def test_review_compatibility_exports_use_hardened_implementations() -> None:
    assert review.apply_review_proposal is apply_review_proposal
    assert review.assessment_edit_authority_assignments is assessment_edit_authority_assignments
    assert review_records.apply_review_proposal is apply_review_proposal
    assert review_records.assessment_edit_authority_assignments is assessment_edit_authority_assignments


def test_review_facade_private_fallbacks() -> None:
    assert review.__getattr__("apply_review_proposal") is apply_review_proposal
    assert review.__getattr__("assessment_edit_authority_assignments") is assessment_edit_authority_assignments
    assert review.__getattr__("REVIEW_ROLES") is review.REVIEW_ROLES


def test_review_timestamp_hook_covers_assignment_and_statement(workspace, monkeypatch) -> None:
    workspace.import_case(PRIMA, case_id="clock-case")
    fixed = "2026-08-07T12:34:56.000000Z"
    monkeypatch.setattr(review, "_review_timestamp", lambda: fixed)

    assignment = review.create_review_assignment(
        workspace,
        "clock-case",
        "reviewer-1",
        "DOMAIN_REVIEWER",
        ["FINDING:NK-01-R01"],
        actor="assigner-1",
    )["assignment"]
    statement = review.submit_review_statement(
        workspace,
        "clock-case",
        "reviewer-1",
        "FINDING",
        "NK-01-R01",
        "AGREE",
        "Timestamp bridge regression guard.",
    )["statement"]

    assert assignment["assigned_at"] == fixed
    assert statement["submitted_at"] == fixed
