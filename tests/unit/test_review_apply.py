from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench.events import load_events
from neuroai_workbench.review import (
    REVIEW_PROPOSAL_APPLIED_EVENT,
    apply_review_proposal,
    create_review_assignment,
    dispose_review_statement,
    submit_review_statement,
)
from neuroai_workbench.util import sha256_file

REPO = Path(__file__).resolve().parents[2]
PRIMA = REPO / "examples" / "assessments" / "PRIMA_Controlled_Assessment_v4.2.1.native.json"
TARGET = "/requirement_findings/NK-01-R01/finding"
SECOND_TARGET = "/requirement_findings/NK-01-R01/strongest_supported_claim"
TEXT = "Exact accepted proposal text."


def _prepare_review(workspace, *, disposition="ACCEPTED"):
    workspace.import_case(PRIMA, case_id="review-case")
    create_review_assignment(
        workspace,
        "review-case",
        "reviewer-1",
        "DOMAIN_REVIEWER",
        ["FINDING:NK-01-R01"],
        actor="assigner-1",
    )
    create_review_assignment(
        workspace,
        "review-case",
        "lead-1",
        "LEAD_ASSESSOR",
        ["FINDING:NK-01-R01"],
        actor="assigner-1",
    )
    statement = submit_review_statement(
        workspace,
        "review-case",
        "reviewer-1",
        "FINDING",
        "NK-01-R01",
        "DISAGREE",
        "Keep the finding bounded.",
        evidence_ids=["EV-PR-001"],
        proposed_change=TEXT,
    )["statement"]
    dispose_review_statement(
        workspace,
        "review-case",
        statement["statement_id"],
        disposition,
        "Human disposition.",
        actor="lead-1",
    )
    return statement["statement_id"], sha256_file(workspace.case_path("review-case") / "assessment.json")


def test_review_apply_exact_text_and_related_event(workspace) -> None:
    statement_id, before_sha = _prepare_review(workspace)
    root = workspace.case_path("review-case") / "reviews"
    source_paths = [
        root / "statements" / f"{statement_id}.json",
        root / "dispositions" / f"{statement_id}.json",
    ]
    source_bytes = [path.read_bytes() for path in source_paths]
    result = apply_review_proposal(
        workspace,
        "review-case",
        statement_id,
        actor="lead-1",
        expected_assessment_sha256=before_sha,
        field_patches=[{"target_path": TARGET, "value": TEXT}],
    )
    assert [path.read_bytes() for path in source_paths] == source_bytes
    assert result["application"]["authority_assignments"]
    events = load_events(workspace.case_path("review-case") / "events.jsonl")
    saved = [event for event in events if event.get("action") == "ASSESSMENT_SAVED"][-1]
    assert saved["payload"]["related_events"][0]["action"] == REVIEW_PROPOSAL_APPLIED_EVENT


def test_review_apply_refuses_changed_text(workspace) -> None:
    statement_id, before_sha = _prepare_review(workspace)
    with pytest.raises(ValueError, match="differs from the accepted"):
        apply_review_proposal(
            workspace,
            "review-case",
            statement_id,
            actor="lead-1",
            expected_assessment_sha256=before_sha,
            field_patches=[{"target_path": TARGET, "value": "Different wording."}],
        )


def test_review_apply_refuses_ambiguous_partial_acceptance(workspace) -> None:
    statement_id, before_sha = _prepare_review(workspace, disposition="PARTIALLY_ACCEPTED")
    with pytest.raises(ValueError, match="ambiguous"):
        apply_review_proposal(
            workspace,
            "review-case",
            statement_id,
            actor="lead-1",
            expected_assessment_sha256=before_sha,
            field_patches=[{"target_path": TARGET, "value": TEXT}],
        )


def _review_paths(workspace, statement_id: str):
    root = workspace.case_path("review-case") / "reviews"
    return (
        root / "statements" / f"{statement_id}.json",
        root / "dispositions" / f"{statement_id}.json",
        root / "applications" / f"{statement_id}.json",
    )


def _rehash(path: Path, field: str) -> None:
    from neuroai_workbench.review import _hash_record

    record = json.loads(path.read_text(encoding="utf-8"))
    record[field] = _hash_record(record, field)
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def test_authority_refuses_empty_targets(workspace) -> None:
    workspace.import_case(PRIMA, case_id="review-case")
    from neuroai_workbench.review import assessment_edit_authority_assignments

    with pytest.raises(ValueError, match="At least one"):
        assessment_edit_authority_assignments(workspace, "review-case", "lead-1", [])


def test_authority_refuses_correspondence_error(workspace, monkeypatch) -> None:
    workspace.import_case(PRIMA, case_id="review-case")
    create_review_assignment(
        workspace,
        "review-case",
        "lead-1",
        "LEAD_ASSESSOR",
        ["FINDING:NK-01-R01"],
        actor="assigner-1",
    )
    import neuroai_workbench.review as review_module
    from neuroai_workbench.review import assessment_edit_authority_assignments

    monkeypatch.setattr(review_module, "_verify_assignment_event_correspondence", lambda *_: ["bad link"])
    with pytest.raises(ValueError, match="correspondence failed"):
        assessment_edit_authority_assignments(
            workspace,
            "review-case",
            "lead-1",
            [("FINDING", "NK-01-R01")],
        )


def test_review_apply_input_and_record_refusals(workspace) -> None:
    statement_id, before_sha = _prepare_review(workspace)
    statement_path, disposition_path, _ = _review_paths(workspace, statement_id)

    with pytest.raises(ValueError, match="expected_assessment"):
        apply_review_proposal(
            workspace,
            "review-case",
            statement_id,
            actor="lead-1",
            expected_assessment_sha256="",
            field_patches=[{"target_path": TARGET, "value": TEXT}],
        )
    with pytest.raises(ValueError, match="field_patches"):
        apply_review_proposal(
            workspace,
            "review-case",
            statement_id,
            actor="lead-1",
            expected_assessment_sha256=before_sha,
            field_patches=[],
        )
    with pytest.raises(FileNotFoundError):
        apply_review_proposal(
            workspace,
            "review-case",
            "RS-UNKNOWN",
            actor="lead-1",
            expected_assessment_sha256=before_sha,
            field_patches=[{"target_path": TARGET, "value": TEXT}],
        )

    disposition_bytes = disposition_path.read_bytes()
    disposition_path.unlink()
    with pytest.raises(ValueError, match="No disposition"):
        apply_review_proposal(
            workspace,
            "review-case",
            statement_id,
            actor="lead-1",
            expected_assessment_sha256=before_sha,
            field_patches=[{"target_path": TARGET, "value": TEXT}],
        )
    disposition_path.write_bytes(disposition_bytes)

    statement = json.loads(statement_path.read_text(encoding="utf-8"))
    statement["rationale"] = "tampered"
    statement_path.write_text(json.dumps(statement, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="statement hash"):
        apply_review_proposal(
            workspace,
            "review-case",
            statement_id,
            actor="lead-1",
            expected_assessment_sha256=before_sha,
            field_patches=[{"target_path": TARGET, "value": TEXT}],
        )


def test_review_apply_disposition_integrity_refusals(workspace) -> None:
    statement_id, before_sha = _prepare_review(workspace)
    _, disposition_path, _ = _review_paths(workspace, statement_id)
    disposition = json.loads(disposition_path.read_text(encoding="utf-8"))
    disposition["rationale"] = "tampered"
    disposition_path.write_text(json.dumps(disposition, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="disposition hash"):
        apply_review_proposal(
            workspace,
            "review-case",
            statement_id,
            actor="lead-1",
            expected_assessment_sha256=before_sha,
            field_patches=[{"target_path": TARGET, "value": TEXT}],
        )


def test_review_apply_reference_and_state_refusals(workspace) -> None:
    statement_id, before_sha = _prepare_review(workspace)
    statement_path, disposition_path, _ = _review_paths(workspace, statement_id)
    disposition = json.loads(disposition_path.read_text(encoding="utf-8"))
    disposition["statement_sha256"] = "0" * 64
    disposition_path.write_text(json.dumps(disposition, indent=2) + "\n", encoding="utf-8")
    _rehash(disposition_path, "disposition_sha256")
    with pytest.raises(ValueError, match="does not reference"):
        apply_review_proposal(
            workspace,
            "review-case",
            statement_id,
            actor="lead-1",
            expected_assessment_sha256=before_sha,
            field_patches=[{"target_path": TARGET, "value": TEXT}],
        )

    disposition = json.loads(disposition_path.read_text(encoding="utf-8"))
    statement = json.loads(statement_path.read_text(encoding="utf-8"))
    disposition["statement_sha256"] = statement["statement_sha256"]
    disposition["disposition"] = "REJECTED"
    disposition_path.write_text(json.dumps(disposition, indent=2) + "\n", encoding="utf-8")
    _rehash(disposition_path, "disposition_sha256")
    with pytest.raises(ValueError, match="cannot be applied"):
        apply_review_proposal(
            workspace,
            "review-case",
            statement_id,
            actor="lead-1",
            expected_assessment_sha256=before_sha,
            field_patches=[{"target_path": TARGET, "value": TEXT}],
        )


def test_review_apply_stale_and_shape_refusals(workspace) -> None:
    statement_id, before_sha = _prepare_review(workspace)
    with pytest.raises(ValueError, match="Stale assessment"):
        apply_review_proposal(
            workspace,
            "review-case",
            statement_id,
            actor="lead-1",
            expected_assessment_sha256="0" * 64,
            field_patches=[{"target_path": TARGET, "value": TEXT}],
        )
    with pytest.raises(ValueError, match="exactly one"):
        apply_review_proposal(
            workspace,
            "review-case",
            statement_id,
            actor="lead-1",
            expected_assessment_sha256=before_sha,
            field_patches=[
                {"target_path": TARGET, "value": TEXT},
                {"target_path": SECOND_TARGET, "value": TEXT},
            ],
        )
    with pytest.raises(ValueError, match="must be an object"):
        apply_review_proposal(
            workspace,
            "review-case",
            statement_id,
            actor="lead-1",
            expected_assessment_sha256=before_sha,
            field_patches=["bad"],
        )
    with pytest.raises(ValueError, match="requires target_path"):
        apply_review_proposal(
            workspace,
            "review-case",
            statement_id,
            actor="lead-1",
            expected_assessment_sha256=before_sha,
            field_patches=[{"target_path": TARGET}],
        )
    with pytest.raises(ValueError, match="outside proposal target"):
        apply_review_proposal(
            workspace,
            "review-case",
            statement_id,
            actor="lead-1",
            expected_assessment_sha256=before_sha,
            field_patches=[{"target_path": "/assessment_metadata/title", "value": TEXT}],
        )


def test_review_apply_refuses_missing_proposed_change(workspace) -> None:
    statement_id, before_sha = _prepare_review(workspace)
    statement_path, disposition_path, _ = _review_paths(workspace, statement_id)
    statement = json.loads(statement_path.read_text(encoding="utf-8"))
    statement["proposed_change"] = None
    statement_path.write_text(json.dumps(statement, indent=2) + "\n", encoding="utf-8")
    _rehash(statement_path, "statement_sha256")
    statement = json.loads(statement_path.read_text(encoding="utf-8"))
    disposition = json.loads(disposition_path.read_text(encoding="utf-8"))
    disposition["statement_sha256"] = statement["statement_sha256"]
    disposition_path.write_text(json.dumps(disposition, indent=2) + "\n", encoding="utf-8")
    _rehash(disposition_path, "disposition_sha256")
    with pytest.raises(ValueError, match="no exact proposed_change"):
        apply_review_proposal(
            workspace,
            "review-case",
            statement_id,
            actor="lead-1",
            expected_assessment_sha256=before_sha,
            field_patches=[{"target_path": TARGET, "value": TEXT}],
        )


def test_review_apply_refuses_statement_assessment_drift(workspace) -> None:
    statement_id, before_sha = _prepare_review(workspace)
    statement_path, disposition_path, _ = _review_paths(workspace, statement_id)
    statement = json.loads(statement_path.read_text(encoding="utf-8"))
    statement["assessment_sha256"] = "f" * 64
    statement_path.write_text(json.dumps(statement, indent=2) + "\n", encoding="utf-8")
    _rehash(statement_path, "statement_sha256")
    disposition = json.loads(disposition_path.read_text(encoding="utf-8"))
    disposition["statement_sha256"] = json.loads(statement_path.read_text(encoding="utf-8"))[
        "statement_sha256"
    ]
    disposition_path.write_text(json.dumps(disposition, indent=2) + "\n", encoding="utf-8")
    _rehash(disposition_path, "disposition_sha256")
    with pytest.raises(ValueError, match="statement is stale"):
        apply_review_proposal(
            workspace,
            "review-case",
            statement_id,
            actor="lead-1",
            expected_assessment_sha256=before_sha,
            field_patches=[{"target_path": TARGET, "value": TEXT}],
        )


def test_review_apply_refuses_authority_change_inside_save(workspace, monkeypatch) -> None:
    statement_id, before_sha = _prepare_review(workspace)
    import neuroai_workbench.proposal_application as module

    real = module.assessment_edit_authority_assignments
    calls = 0

    def changed(*args, **kwargs):
        nonlocal calls
        calls += 1
        records = real(*args, **kwargs)
        if calls > 1:
            records = [dict(records[0], assignment_sha256="0" * 64)]
        return records

    monkeypatch.setattr(module, "assessment_edit_authority_assignments", changed)
    with pytest.raises(ValueError, match="authority changed"):
        apply_review_proposal(
            workspace,
            "review-case",
            statement_id,
            actor="lead-1",
            expected_assessment_sha256=before_sha,
            field_patches=[{"target_path": TARGET, "value": TEXT}],
        )


def test_review_apply_refuses_field_change_inside_save(workspace, monkeypatch) -> None:
    statement_id, before_sha = _prepare_review(workspace)
    original_save = workspace.save_case

    def changed(*args, **kwargs):
        current = workspace.load_case("review-case")
        current["requirement_findings"][0]["finding"] = "concurrent change"
        from neuroai_workbench.util import atomic_write_json

        atomic_write_json(workspace.case_path("review-case") / "assessment.json", current)
        return original_save(*args, **kwargs)

    monkeypatch.setattr(workspace, "save_case", changed)
    with pytest.raises(ValueError, match="Field value changed"):
        apply_review_proposal(
            workspace,
            "review-case",
            statement_id,
            actor="lead-1",
            expected_assessment_sha256=before_sha,
            field_patches=[{"target_path": TARGET, "value": TEXT}],
        )


def test_authority_refuses_invalid_event_chain(workspace, monkeypatch) -> None:
    _prepare_review(workspace)
    import neuroai_workbench.proposal_application as module

    monkeypatch.setattr(module, "verify_chain", lambda _path: {"valid": False, "trailer_valid": False})
    with pytest.raises(ValueError, match="Event chain is invalid"):
        module.assessment_edit_authority_assignments(
            workspace,
            "review-case",
            "lead-1",
            [("FINDING", "NK-01-R01")],
        )


def test_review_apply_refuses_duplicate_application(workspace) -> None:
    statement_id, before_sha = _prepare_review(workspace)
    apply_review_proposal(
        workspace,
        "review-case",
        statement_id,
        actor="lead-1",
        expected_assessment_sha256=before_sha,
        field_patches=[{"target_path": TARGET, "value": TEXT}],
    )
    with pytest.raises(ValueError, match="already been applied"):
        apply_review_proposal(
            workspace,
            "review-case",
            statement_id,
            actor="lead-1",
            expected_assessment_sha256=sha256_file(
                workspace.case_path("review-case") / "assessment.json"
            ),
            field_patches=[{"target_path": TARGET, "value": TEXT}],
        )


def test_review_apply_cli_uses_hardened_path(workspace, tmp_path: Path) -> None:
    from neuroai_workbench import cli

    statement_id, before_sha = _prepare_review(workspace)
    patches = tmp_path / "patches.json"
    patches.write_text(
        json.dumps([{"target_path": TARGET, "value": TEXT}]),
        encoding="utf-8",
    )
    assert (
        cli.main(
            [
                "review-apply",
                str(workspace.root),
                "review-case",
                statement_id,
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
