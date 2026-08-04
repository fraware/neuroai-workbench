from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench.review import (
    _hash_record,
    create_review_assignment,
    dispose_review_statement,
    render_review_markdown,
    submit_review_statement,
    verify_review_records,
)
from neuroai_workbench.workspace import Workspace

PRIMA = Path("examples/assessments/PRIMA_Controlled_Assessment_v4.2.1.native.json")


def _workspace(tmp_path: Path) -> tuple[Workspace, str]:
    workspace = Workspace.initialize(tmp_path / "workspace")
    workspace.import_case(PRIMA, case_id="PRIMA-REVIEW")
    return workspace, "PRIMA-REVIEW"


def test_review_lifecycle_is_attributable_and_non_mutating(tmp_path: Path) -> None:
    workspace, case_id = _workspace(tmp_path)
    before = (workspace.case_path(case_id) / "assessment.json").read_bytes()
    assessment = workspace.load_case(case_id)
    finding_id = assessment["requirement_findings"][0]["requirement_id"]
    evidence_id = assessment["evidence_register"][0]["evidence_id"]

    create_review_assignment(
        workspace, case_id, "reviewer-1", "DOMAIN_REVIEWER", [f"FINDING:{finding_id}"], actor="lead-1"
    )
    create_review_assignment(workspace, case_id, "lead-1", "LEAD_ASSESSOR", ["ASSESSMENT:*"], actor="assigner-1")
    statement = submit_review_statement(
        workspace,
        case_id,
        "reviewer-1",
        "FINDING",
        finding_id,
        "DISAGREE",
        "The public record supports a narrower formulation.",
        evidence_ids=[evidence_id],
        proposed_change="Narrow the strongest supported claim.",
    )["statement"]
    dispose_review_statement(
        workspace,
        case_id,
        statement["statement_id"],
        "PARTIALLY_ACCEPTED",
        "The claim boundary will be reviewed in a separate assessment edit.",
        actor="lead-1",
    )

    report = verify_review_records(workspace, case_id)
    assert report["valid"] is True
    assert report["counts"] == {
        "assignments": 2,
        "statements": 1,
        "dispositions": 1,
        "open_statements": 0,
        "disagreements": 1,
        "stale_statements": 0,
    }
    assert (workspace.case_path(case_id) / "assessment.json").read_bytes() == before
    markdown = render_review_markdown(workspace, case_id)
    assert "DISAGREE" in markdown
    assert "PARTIALLY_ACCEPTED" in markdown


def test_review_requires_covering_assignment_and_known_evidence(tmp_path: Path) -> None:
    workspace, case_id = _workspace(tmp_path)
    finding_id = workspace.load_case(case_id)["requirement_findings"][0]["requirement_id"]
    with pytest.raises(ValueError, match="no active assignment"):
        submit_review_statement(
            workspace, case_id, "reviewer-1", "FINDING", finding_id, "AGREE", "Supported as written."
        )
    create_review_assignment(
        workspace, case_id, "reviewer-1", "DOMAIN_REVIEWER", [f"FINDING:{finding_id}"], actor="lead-1"
    )
    with pytest.raises(ValueError, match="Unknown evidence IDs"):
        submit_review_statement(
            workspace,
            case_id,
            "reviewer-1",
            "FINDING",
            finding_id,
            "AGREE",
            "Supported as written.",
            evidence_ids=["EV-NOT-THERE"],
        )


def test_disposition_requires_decision_role_and_is_single_use(tmp_path: Path) -> None:
    workspace, case_id = _workspace(tmp_path)
    finding_id = workspace.load_case(case_id)["requirement_findings"][0]["requirement_id"]
    create_review_assignment(
        workspace, case_id, "reviewer-1", "DOMAIN_REVIEWER", [f"FINDING:{finding_id}"], actor="lead-1"
    )
    statement_id = submit_review_statement(
        workspace, case_id, "reviewer-1", "FINDING", finding_id, "AGREE", "Supported as written."
    )["statement"]["statement_id"]
    with pytest.raises(ValueError, match="no active decision role"):
        dispose_review_statement(
            workspace, case_id, statement_id, "ACCEPTED", "Accepted after review.", actor="reviewer-1"
        )
    create_review_assignment(workspace, case_id, "lead-1", "DECISION_AUTHORITY", ["ASSESSMENT:*"], actor="assigner-1")
    dispose_review_statement(workspace, case_id, statement_id, "ACCEPTED", "Accepted after review.", actor="lead-1")
    with pytest.raises(ValueError, match="already recorded"):
        dispose_review_statement(
            workspace, case_id, statement_id, "REJECTED", "A second disposition is forbidden.", actor="lead-1"
        )


def test_review_verification_detects_tampering(tmp_path: Path) -> None:
    workspace, case_id = _workspace(tmp_path)
    finding_id = workspace.load_case(case_id)["requirement_findings"][0]["requirement_id"]
    create_review_assignment(
        workspace, case_id, "reviewer-1", "DOMAIN_REVIEWER", [f"FINDING:{finding_id}"], actor="lead-1"
    )
    result = submit_review_statement(
        workspace, case_id, "reviewer-1", "FINDING", finding_id, "ABSTAIN", "Outside my competence."
    )
    path = Path(result["path"])
    record = json.loads(path.read_text(encoding="utf-8"))
    record["rationale"] = "Tampered"
    path.write_text(json.dumps(record), encoding="utf-8")
    report = verify_review_records(workspace, case_id)
    assert report["valid"] is False
    assert any("hash mismatch" in error for error in report["errors"])


def test_tampered_assignment_cannot_authorize_new_statement(tmp_path: Path) -> None:
    workspace, case_id = _workspace(tmp_path)
    finding_id = workspace.load_case(case_id)["requirement_findings"][0]["requirement_id"]
    assignment = create_review_assignment(
        workspace, case_id, "reviewer-1", "DOMAIN_REVIEWER", [f"FINDING:{finding_id}"], actor="lead-1"
    )
    path = Path(assignment["path"])
    record = json.loads(path.read_text(encoding="utf-8"))
    record["scope"] = ["ASSESSMENT:*"]
    path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid hash"):
        submit_review_statement(
            workspace, case_id, "reviewer-1", "FINDING", finding_id, "AGREE", "Supported as written."
        )


def test_review_statement_becomes_stale_without_becoming_invalid(tmp_path: Path) -> None:
    workspace, case_id = _workspace(tmp_path)
    assessment = workspace.load_case(case_id)
    finding_id = assessment["requirement_findings"][0]["requirement_id"]
    create_review_assignment(
        workspace, case_id, "reviewer-1", "DOMAIN_REVIEWER", [f"FINDING:{finding_id}"], actor="lead-1"
    )
    submit_review_statement(workspace, case_id, "reviewer-1", "FINDING", finding_id, "AGREE", "Supported as written.")

    assessment["assessment_metadata"]["title"] = "Updated title after review"
    workspace.save_case(case_id, assessment, actor="lead-1", require_valid=True)
    report = verify_review_records(workspace, case_id)

    assert report["valid"] is True
    assert report["counts"]["stale_statements"] == 1
    assert any("assessment has changed" in warning for warning in report["warnings"])
    assert "earlier assessment hash: 1" in render_review_markdown(workspace, case_id)


def test_dispose_refuses_stale_statement_hash(tmp_path: Path) -> None:
    workspace, case_id = _workspace(tmp_path)
    assessment = workspace.load_case(case_id)
    finding_id = assessment["requirement_findings"][0]["requirement_id"]
    create_review_assignment(
        workspace, case_id, "reviewer-1", "DOMAIN_REVIEWER", [f"FINDING:{finding_id}"], actor="lead-1"
    )
    create_review_assignment(workspace, case_id, "lead-1", "LEAD_ASSESSOR", ["ASSESSMENT:*"], actor="assigner-1")
    statement_id = submit_review_statement(
        workspace, case_id, "reviewer-1", "FINDING", finding_id, "AGREE", "Supported as written."
    )["statement"]["statement_id"]
    assessment["assessment_metadata"]["title"] = "Updated after statement"
    workspace.save_case(case_id, assessment, actor="lead-1", require_valid=True)
    with pytest.raises(ValueError, match="stale"):
        dispose_review_statement(
            workspace,
            case_id,
            statement_id,
            "ACCEPTED",
            "Should be refused.",
            actor="lead-1",
        )


def test_decision_role_self_assignment_is_refused(tmp_path: Path) -> None:
    workspace, case_id = _workspace(tmp_path)
    with pytest.raises(ValueError, match="Self-assignment"):
        create_review_assignment(workspace, case_id, "lead-1", "LEAD_ASSESSOR", ["ASSESSMENT:*"], actor="lead-1")
    assignment = create_review_assignment(
        workspace, case_id, "lead-1", "LEAD_ASSESSOR", ["ASSESSMENT:*"], actor="assigner-1"
    )
    assert assignment["assignment"]["authority_profile"] == "LOCAL_UNAUTHENTICATED_ATTRIBUTION"


def test_review_input_and_integrity_error_branches(tmp_path: Path) -> None:
    workspace, case_id = _workspace(tmp_path)
    assessment = workspace.load_case(case_id)
    finding_id = assessment["requirement_findings"][0]["requirement_id"]

    with pytest.raises(ValueError, match="Unsupported review role"):
        create_review_assignment(workspace, case_id, "reviewer-x", "OWNER", ["ASSESSMENT:*"], actor="lead-1")
    with pytest.raises(ValueError, match="Review scope"):
        create_review_assignment(workspace, case_id, "reviewer-x", "OBSERVER", [], actor="lead-1")
    with pytest.raises(ValueError, match="Invalid actor ID"):
        create_review_assignment(workspace, case_id, "reviewer-x", "OBSERVER", ["ASSESSMENT:*"], actor="not valid")
    with pytest.raises(ValueError, match="Unsupported scope target type"):
        create_review_assignment(workspace, case_id, "reviewer-x", "OBSERVER", ["MODEL:*"], actor="lead-1")
    with pytest.raises(ValueError, match="Unknown finding target"):
        create_review_assignment(workspace, case_id, "reviewer-x", "OBSERVER", ["FINDING:NOPE"], actor="lead-1")

    create_review_assignment(
        workspace, case_id, "reviewer-x", "DOMAIN_REVIEWER", [f"FINDING:{finding_id}"], actor="lead-1"
    )
    with pytest.raises(ValueError, match="Unsupported review position"):
        submit_review_statement(workspace, case_id, "reviewer-x", "FINDING", finding_id, "MAYBE", "Rationale")
    with pytest.raises(ValueError, match="must not be empty"):
        submit_review_statement(workspace, case_id, "reviewer-x", "FINDING", finding_id, "AGREE", " ")
    with pytest.raises(ValueError, match="actor must match"):
        submit_review_statement(
            workspace, case_id, "reviewer-x", "FINDING", finding_id, "AGREE", "Rationale", actor="other"
        )
    with pytest.raises(ValueError, match="Unsupported target type"):
        submit_review_statement(workspace, case_id, "reviewer-x", "MODEL", finding_id, "AGREE", "Rationale")

    with pytest.raises(ValueError, match="Unsupported review disposition"):
        dispose_review_statement(workspace, case_id, "RS-NOT-THERE", "OVERRULED", "Rationale", actor="lead-1")
    with pytest.raises(ValueError, match="must not be empty"):
        dispose_review_statement(workspace, case_id, "RS-NOT-THERE", "DEFERRED", " ", actor="lead-1")
    with pytest.raises(FileNotFoundError, match="Unknown review statement"):
        dispose_review_statement(workspace, case_id, "RS-NOT-THERE", "DEFERRED", "Rationale", actor="lead-1")


def test_duplicate_timestamp_records_are_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, case_id = _workspace(tmp_path)
    finding_id = workspace.load_case(case_id)["requirement_findings"][0]["requirement_id"]
    monkeypatch.setattr("neuroai_workbench.review._review_timestamp", lambda: "2026-07-30T12:00:00Z")

    create_review_assignment(
        workspace, case_id, "reviewer-1", "DOMAIN_REVIEWER", [f"FINDING:{finding_id}"], actor="lead-1"
    )
    with pytest.raises(ValueError, match="identical review assignment"):
        create_review_assignment(
            workspace,
            case_id,
            "reviewer-1",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            actor="lead-1",
        )

    submit_review_statement(workspace, case_id, "reviewer-1", "FINDING", finding_id, "AGREE", "Supported as written.")
    with pytest.raises(ValueError, match="identical review statement"):
        submit_review_statement(
            workspace, case_id, "reviewer-1", "FINDING", finding_id, "AGREE", "Supported as written."
        )


def test_disposition_rejects_tampered_statement(tmp_path: Path) -> None:
    workspace, case_id = _workspace(tmp_path)
    finding_id = workspace.load_case(case_id)["requirement_findings"][0]["requirement_id"]
    create_review_assignment(
        workspace, case_id, "reviewer-1", "DOMAIN_REVIEWER", [f"FINDING:{finding_id}"], actor="lead-1"
    )
    create_review_assignment(workspace, case_id, "lead-1", "LEAD_ASSESSOR", ["ASSESSMENT:*"], actor="assigner-1")
    result = submit_review_statement(
        workspace, case_id, "reviewer-1", "FINDING", finding_id, "AGREE", "Supported as written."
    )
    statement = result["statement"]
    path = Path(result["path"])
    record = json.loads(path.read_text(encoding="utf-8"))
    record["rationale"] = "Changed without rehashing"
    path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="statement hash is invalid"):
        dispose_review_statement(
            workspace,
            case_id,
            statement["statement_id"],
            "ACCEPTED",
            "Accepted after review.",
            actor="lead-1",
        )


def test_review_verifier_detects_reference_and_event_errors(tmp_path: Path) -> None:
    workspace, case_id = _workspace(tmp_path)
    finding_id = workspace.load_case(case_id)["requirement_findings"][0]["requirement_id"]
    assignment = create_review_assignment(
        workspace, case_id, "reviewer-1", "DOMAIN_REVIEWER", [f"FINDING:{finding_id}"], actor="lead-1"
    )
    statement = submit_review_statement(
        workspace, case_id, "reviewer-1", "FINDING", finding_id, "AGREE_WITH_CONDITIONS", "Conditioned agreement."
    )
    assignment_path = Path(assignment["path"])
    assignment_record = json.loads(assignment_path.read_text(encoding="utf-8"))
    assignment_record["role"] = "UNKNOWN"
    assignment_path.write_text(json.dumps(assignment_record), encoding="utf-8")
    event_path = workspace.case_path(case_id) / "events.jsonl"
    lines = event_path.read_text(encoding="utf-8").splitlines()
    event = json.loads(lines[-1])
    event["payload"]["position"] = "TAMPERED"
    lines[-1] = json.dumps(event)
    event_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = verify_review_records(workspace, case_id)
    assert report["valid"] is False
    assert any("unsupported role" in error for error in report["errors"])
    assert any("event chain" in error for error in report["errors"])
    assert Path(statement["path"]).is_file()


def test_review_verifier_reports_semantic_record_corruption(tmp_path: Path) -> None:
    workspace, case_id = _workspace(tmp_path)
    assessment = workspace.load_case(case_id)
    finding_id = assessment["requirement_findings"][0]["requirement_id"]
    evidence_id = assessment["evidence_register"][0]["evidence_id"]
    assignment = create_review_assignment(
        workspace, case_id, "reviewer-1", "DOMAIN_REVIEWER", [f"FINDING:{finding_id}"], actor="lead-1"
    )
    create_review_assignment(workspace, case_id, "lead-1", "LEAD_ASSESSOR", ["ASSESSMENT:*"], actor="assigner-1")
    statement = submit_review_statement(
        workspace,
        case_id,
        "reviewer-1",
        "FINDING",
        finding_id,
        "AGREE",
        "Supported as written.",
        evidence_ids=[evidence_id],
    )
    disposition = dispose_review_statement(
        workspace,
        case_id,
        statement["statement"]["statement_id"],
        "ACCEPTED",
        "Accepted after review.",
        actor="lead-1",
    )

    assignment_path = Path(assignment["path"])
    assignment_record = json.loads(assignment_path.read_text(encoding="utf-8"))
    assignment_record["state"] = "SUSPENDED"
    assignment_record["scope"] = ["BAD", "MODEL:*", "FINDING:UNKNOWN"]
    assignment_record["assignment_sha256"] = _hash_record(assignment_record, "assignment_sha256")
    assignment_path.write_text(json.dumps(assignment_record), encoding="utf-8")

    statement_path = Path(statement["path"])
    statement_record = json.loads(statement_path.read_text(encoding="utf-8"))
    statement_record["target_id"] = "UNKNOWN"
    statement_record["position"] = "MAYBE"
    statement_record["actor"] = "someone-else"
    statement_record["evidence_ids"] = ["EV-UNKNOWN"]
    statement_record["assignment_ids"] = []
    statement_record["statement_sha256"] = _hash_record(statement_record, "statement_sha256")
    statement_path.write_text(json.dumps(statement_record), encoding="utf-8")

    disposition_path = Path(disposition["path"])
    disposition_record = json.loads(disposition_path.read_text(encoding="utf-8"))
    disposition_record["statement_sha256"] = "0" * 64
    disposition_record["disposition"] = "OVERRULED"
    disposition_record["assignment_ids"] = []
    disposition_record["disposition_sha256"] = _hash_record(disposition_record, "disposition_sha256")
    disposition_path.write_text(json.dumps(disposition_record), encoding="utf-8")

    report = verify_review_records(workspace, case_id)
    assert report["valid"] is False
    expected = (
        "unsupported state",
        "invalid scope entry",
        "unsupported scope target type",
        "unresolved scope target",
        "unresolved target",
        "unsupported position",
        "actor does not match reviewer",
        "unknown evidence IDs",
        "no valid covering assignment",
        "statement hash mismatch",
        "unsupported disposition",
        "no valid covering decision assignment",
    )
    for fragment in expected:
        assert any(fragment in error for error in report["errors"]), fragment
