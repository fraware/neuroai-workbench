from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from neuroai_workbench import cli
from neuroai_workbench.events import load_events
from neuroai_workbench.review import (
    _hash_record,
    create_review_assignment,
    dispose_review_appeal,
    dispose_review_statement,
    file_review_appeal,
    list_review_appeals,
    render_review_markdown,
    revoke_review_assignment,
    submit_review_statement,
    verify_review_records,
)
from neuroai_workbench.util import sha256_file
from neuroai_workbench.workspace import Workspace

PRIMA = Path("examples/assessments/PRIMA_Controlled_Assessment_v4.2.1.native.json")


def _workspace(tmp_path: Path) -> tuple[Workspace, str, str, str]:
    workspace = Workspace.initialize(tmp_path / "workspace")
    workspace.import_case(PRIMA, case_id="PRIMA-APPEAL")
    case_id = "PRIMA-APPEAL"
    assessment = workspace.load_case(case_id)
    finding_id = str(assessment["requirement_findings"][0]["requirement_id"])
    evidence_id = str(assessment["evidence_register"][0]["evidence_id"])
    return workspace, case_id, finding_id, evidence_id


def _seed_statement(
    workspace: Workspace,
    case_id: str,
    finding_id: str,
    *,
    position: str = "DISAGREE",
    dispose: bool = False,
) -> dict[str, object]:
    create_review_assignment(
        workspace,
        case_id,
        "reviewer-1",
        "DOMAIN_REVIEWER",
        [f"FINDING:{finding_id}"],
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
        finding_id,
        position,
        "The claim should remain bounded.",
    )["statement"]
    if dispose:
        dispose_review_statement(
            workspace,
            case_id,
            str(statement["statement_id"]),
            "ACCEPTED",
            "Accepted for local workflow; dissent may still be appealed.",
            actor="lead-1",
        )
    return statement


def test_appeal_after_statement_disposition_preserves_dissent(tmp_path: Path) -> None:
    workspace, case_id, finding_id, _evidence_id = _workspace(tmp_path)
    before = (workspace.case_path(case_id) / "assessment.json").read_bytes()
    statement = _seed_statement(workspace, case_id, finding_id, dispose=True)
    statement_path = workspace.case_path(case_id) / "reviews" / "statements" / f"{statement['statement_id']}.json"
    statement_bytes = statement_path.read_bytes()

    appeal = file_review_appeal(
        workspace,
        case_id,
        str(statement["statement_id"]),
        "MINORITY_REPORT",
        "The minority disagreement remains material after acceptance.",
        "Preserve the original disagreement in the final local record.",
        appellant_id="reviewer-1",
    )["appeal"]
    assert statement_path.read_bytes() == statement_bytes

    disposition = dispose_review_appeal(
        workspace,
        case_id,
        str(appeal["appeal_id"]),
        "DENIED",
        "The statement disposition stands; the minority report remains recorded.",
        actor="lead-1",
    )["appeal_disposition"]
    appeal_path = Path(workspace.case_path(case_id) / "reviews" / "appeals" / f"{appeal['appeal_id']}.json")
    appeal_bytes = appeal_path.read_bytes()
    assert appeal_path.read_bytes() == appeal_bytes
    assert statement_path.read_bytes() == statement_bytes
    assert (workspace.case_path(case_id) / "assessment.json").read_bytes() == before

    report = verify_review_records(workspace, case_id)
    assert report["valid"] is True
    assert report["counts"]["appeals"] == 1
    assert report["counts"]["appeal_dispositions"] == 1
    assert report["counts"]["open_appeals"] == 0

    listing = list_review_appeals(workspace, case_id)
    assert listing["counts"]["disposed_appeals"] == 1
    assert listing["appeals"][0]["source_position"] == "DISAGREE"
    assert listing["appeals"][0]["outcome"] == "DENIED"

    markdown = render_review_markdown(workspace, case_id)
    assert "DISAGREE" in markdown
    assert "MINORITY_REPORT" in markdown
    assert "DENIED" in markdown
    assert disposition["assessment_mutation"] == "NONE_PERFORMED_BY_APPEAL_DISPOSITION"
    assert (
        "institutional" not in disposition["authority_boundary"].lower()
        or "does not establish" in disposition["authority_boundary"]
    )


def test_abstention_clarification_is_preserved(tmp_path: Path) -> None:
    workspace, case_id, finding_id, _evidence_id = _workspace(tmp_path)
    statement = _seed_statement(workspace, case_id, finding_id, position="ABSTAIN")
    appeal = file_review_appeal(
        workspace,
        case_id,
        str(statement["statement_id"]),
        "ABSTENTION_CLARIFICATION",
        "Abstention was for scope insufficiency, not agreement.",
        "Clarify that abstention is not tacit acceptance.",
        appellant_id="reviewer-1",
    )["appeal"]
    dispose_review_appeal(
        workspace,
        case_id,
        str(appeal["appeal_id"]),
        "UPHELD",
        "Record the clarification as local workflow metadata.",
        actor="lead-1",
    )
    markdown = render_review_markdown(workspace, case_id)
    assert "ABSTAIN" in markdown
    assert "ABSTENTION_CLARIFICATION" in markdown
    assert "UPHELD" in markdown


def test_duplicate_appeal_is_refused(tmp_path: Path) -> None:
    workspace, case_id, finding_id, _evidence_id = _workspace(tmp_path)
    statement = _seed_statement(workspace, case_id, finding_id)
    file_review_appeal(
        workspace,
        case_id,
        str(statement["statement_id"]),
        "RECONSIDERATION",
        "Please reconsider the finding boundary.",
        "Reopen the local disposition path.",
        appellant_id="reviewer-1",
    )
    with pytest.raises(ValueError, match="already recorded"):
        file_review_appeal(
            workspace,
            case_id,
            str(statement["statement_id"]),
            "PROCEDURAL_OBJECTION",
            "Second appeal must be refused.",
            "No silent successor.",
            appellant_id="reviewer-1",
        )


def test_unauthorized_and_stale_scope_disposition_refused(tmp_path: Path) -> None:
    workspace, case_id, finding_id, _evidence_id = _workspace(tmp_path)
    statement = _seed_statement(workspace, case_id, finding_id)
    appeal = file_review_appeal(
        workspace,
        case_id,
        str(statement["statement_id"]),
        "PROCEDURAL_OBJECTION",
        "Procedure omitted a covering decision role check.",
        "Require a covering decision disposition.",
        appellant_id="reviewer-1",
    )["appeal"]

    with pytest.raises(ValueError, match="no active decision role"):
        dispose_review_appeal(
            workspace,
            case_id,
            str(appeal["appeal_id"]),
            "UPHELD",
            "Reviewer cannot dispose their own appeal.",
            actor="reviewer-1",
        )

    create_review_assignment(
        workspace,
        case_id,
        "narrow-lead",
        "LEAD_ASSESSOR",
        ["CLAIM:*"],
        actor="assigner-1",
    )
    with pytest.raises(ValueError, match="no active decision role covering"):
        dispose_review_appeal(
            workspace,
            case_id,
            str(appeal["appeal_id"]),
            "DENIED",
            "Insufficient scope must refuse disposal.",
            actor="narrow-lead",
        )

    lead_assignment = next(
        path
        for path in (workspace.case_path(case_id) / "reviews" / "assignments").glob("*.json")
        if json.loads(path.read_text(encoding="utf-8")).get("reviewer_id") == "lead-1"
    )
    lead_id = json.loads(lead_assignment.read_text(encoding="utf-8"))["assignment_id"]
    revoke_review_assignment(
        workspace,
        case_id,
        lead_id,
        "Lead availability ended.",
        actor="lead-1",
    )
    with pytest.raises(ValueError, match="no active decision role"):
        dispose_review_appeal(
            workspace,
            case_id,
            str(appeal["appeal_id"]),
            "DEFERRED",
            "Revoked lead must not dispose.",
            actor="lead-1",
        )


def test_source_statement_and_appeal_digest_tampering_detected(tmp_path: Path) -> None:
    workspace, case_id, finding_id, _evidence_id = _workspace(tmp_path)
    statement = _seed_statement(workspace, case_id, finding_id)
    appeal = file_review_appeal(
        workspace,
        case_id,
        str(statement["statement_id"]),
        "RECONSIDERATION",
        "Grounds for reconsideration.",
        "Reconsider the local disposition.",
        appellant_id="reviewer-1",
    )["appeal"]

    statement_path = workspace.case_path(case_id) / "reviews" / "statements" / f"{statement['statement_id']}.json"
    mutated = json.loads(statement_path.read_text(encoding="utf-8"))
    mutated["rationale"] = "Tampered rationale"
    mutated["statement_sha256"] = _hash_record(mutated, "statement_sha256")
    statement_path.write_text(json.dumps(mutated, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = verify_review_records(workspace, case_id)
    assert report["valid"] is False
    assert any("source statement hash mismatch" in error for error in report["errors"])

    with pytest.raises(ValueError, match="source-statement digest"):
        dispose_review_appeal(
            workspace,
            case_id,
            str(appeal["appeal_id"]),
            "DENIED",
            "Must refuse when source digest drifted.",
            actor="lead-1",
        )

    # Restore statement bytes from original appeal binding is not available; recreate clean case path for appeal hash.
    workspace2, case_id2, finding_id2, _ = _workspace(tmp_path / "second")
    statement2 = _seed_statement(workspace2, case_id2, finding_id2)
    appeal2 = file_review_appeal(
        workspace2,
        case_id2,
        str(statement2["statement_id"]),
        "MINORITY_REPORT",
        "Preserve minority grounds.",
        "Keep dissent visible.",
        appellant_id="reviewer-1",
    )
    appeal_path = Path(appeal2["path"])
    tampered = json.loads(appeal_path.read_text(encoding="utf-8"))
    tampered["grounds"] = "Tampered grounds"
    appeal_path.write_text(json.dumps(tampered, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report2 = verify_review_records(workspace2, case_id2)
    assert report2["valid"] is False
    assert any("appeal" in error and "hash mismatch" in error for error in report2["errors"])


def test_missing_source_statement_and_missing_event_fail_closed(tmp_path: Path) -> None:
    workspace, case_id, finding_id, _evidence_id = _workspace(tmp_path)
    statement = _seed_statement(workspace, case_id, finding_id)
    with pytest.raises(FileNotFoundError, match="Unknown review statement"):
        file_review_appeal(
            workspace,
            case_id,
            "RS-MISSING",
            "RECONSIDERATION",
            "Missing statement must fail.",
            "Refuse filing.",
            appellant_id="reviewer-1",
        )

    appeal = file_review_appeal(
        workspace,
        case_id,
        str(statement["statement_id"]),
        "RECONSIDERATION",
        "Valid appeal for event deletion test.",
        "Detect missing event.",
        appellant_id="reviewer-1",
    )["appeal"]
    events_path = workspace.case_path(case_id) / "events.jsonl"
    kept = [line for line in events_path.read_text(encoding="utf-8").splitlines() if "REVIEW_APPEAL_FILED" not in line]
    events_path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    report = verify_review_records(workspace, case_id)
    assert report["valid"] is False
    assert any("missing matching REVIEW_APPEAL_FILED" in error for error in report["errors"])
    assert appeal["appeal_id"]


def test_assessment_bytes_unchanged_through_appeal_lifecycle(tmp_path: Path) -> None:
    workspace, case_id, finding_id, evidence_id = _workspace(tmp_path)
    assessment_path = workspace.case_path(case_id) / "assessment.json"
    before = assessment_path.read_bytes()
    digest_before = sha256_file(assessment_path)
    statement = _seed_statement(workspace, case_id, finding_id, dispose=True)
    appeal = file_review_appeal(
        workspace,
        case_id,
        str(statement["statement_id"]),
        "MINORITY_REPORT",
        "Dissent remains after acceptance.",
        "Do not mutate assessment through appeal.",
        appellant_id="reviewer-1",
        evidence_ids=[evidence_id],
    )["appeal"]
    dispose_review_appeal(
        workspace,
        case_id,
        str(appeal["appeal_id"]),
        "PARTIALLY_UPHELD",
        "Record partial local recognition without assessment edit.",
        actor="lead-1",
    )
    assert assessment_path.read_bytes() == before
    assert sha256_file(assessment_path) == digest_before
    assert appeal["assessment_mutation"] == "NONE_PERFORMED_BY_APPEAL_RECORD"


def test_appeal_disposition_concurrency_is_single_writer(tmp_path: Path) -> None:
    workspace, case_id, finding_id, _evidence_id = _workspace(tmp_path)
    statement = _seed_statement(workspace, case_id, finding_id)
    appeal = file_review_appeal(
        workspace,
        case_id,
        str(statement["statement_id"]),
        "RECONSIDERATION",
        "Concurrent disposition must serialize.",
        "Only one disposition may persist.",
        appellant_id="reviewer-1",
    )["appeal"]

    def dispose(reason: str) -> str:
        result = dispose_review_appeal(
            workspace,
            case_id,
            str(appeal["appeal_id"]),
            "DENIED",
            reason,
            actor="lead-1",
        )
        return str(result["appeal_disposition"]["appeal_disposition_sha256"])

    outcomes: list[str] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(dispose, f"reason-{index}") for index in range(2)]
        for future in futures:
            try:
                outcomes.append(future.result())
            except ValueError as exc:
                errors.append(str(exc))

    assert len(outcomes) == 1
    assert len(errors) == 1
    assert any("already recorded" in error for error in errors)
    assert len(list((workspace.case_path(case_id) / "reviews" / "appeal_dispositions").glob("*.json"))) == 1
    assert verify_review_records(workspace, case_id)["valid"] is True


def test_appeal_cli_execution(tmp_path: Path) -> None:
    workspace_path = tmp_path / "cli-workspace"
    assert cli.main(["init", str(workspace_path), "--name", "CLI appeal"]) == 0
    assert (
        cli.main(
            [
                "case-import",
                str(workspace_path),
                str(PRIMA),
                "--case-id",
                "CASE-APPEAL",
            ]
        )
        == 0
    )
    workspace = Workspace(workspace_path)
    finding_id = str(workspace.load_case("CASE-APPEAL")["requirement_findings"][0]["requirement_id"])
    assert (
        cli.main(
            [
                "review-assign",
                str(workspace_path),
                "CASE-APPEAL",
                "reviewer-1",
                "DOMAIN_REVIEWER",
                "--scope",
                f"FINDING:{finding_id}",
                "--actor",
                "lead-1",
            ]
        )
        == 0
    )
    assert (
        cli.main(
            [
                "review-assign",
                str(workspace_path),
                "CASE-APPEAL",
                "lead-1",
                "LEAD_ASSESSOR",
                "--scope",
                "ASSESSMENT:*",
                "--actor",
                "assigner-1",
            ]
        )
        == 0
    )
    submit_out = tmp_path / "statement.json"
    assert (
        cli.main(
            [
                "review-submit",
                str(workspace_path),
                "CASE-APPEAL",
                "reviewer-1",
                "FINDING",
                finding_id,
                "DISAGREE",
                "--rationale",
                "CLI dissent statement.",
                "--out",
                str(submit_out),
            ]
        )
        == 0
    )
    statement_id = json.loads(submit_out.read_text(encoding="utf-8"))["statement"]["statement_id"]
    appeal_out = tmp_path / "appeal.json"
    assert (
        cli.main(
            [
                "review-appeal-file",
                str(workspace_path),
                "CASE-APPEAL",
                statement_id,
                "MINORITY_REPORT",
                "--grounds",
                "CLI minority report grounds.",
                "--requested-resolution",
                "Preserve dissent in reports.",
                "--appellant-id",
                "reviewer-1",
                "--out",
                str(appeal_out),
            ]
        )
        == 0
    )
    appeal_id = json.loads(appeal_out.read_text(encoding="utf-8"))["appeal"]["appeal_id"]
    assert (
        cli.main(
            [
                "review-appeal-dispose",
                str(workspace_path),
                "CASE-APPEAL",
                appeal_id,
                "DENIED",
                "--rationale",
                "CLI disposition keeps dissent visible.",
                "--actor",
                "lead-1",
            ]
        )
        == 0
    )
    list_out = tmp_path / "appeals.json"
    assert cli.main(["review-appeal-list", str(workspace_path), "CASE-APPEAL", "--out", str(list_out)]) == 0
    listing = json.loads(list_out.read_text(encoding="utf-8"))
    assert listing["counts"]["disposed_appeals"] == 1
    assert listing["appeals"][0]["outcome"] == "DENIED"
    assert cli.main(["review-verify", str(workspace_path), "CASE-APPEAL"]) == 0
    report_path = tmp_path / "review.md"
    assert (
        cli.main(
            [
                "review-report",
                str(workspace_path),
                "CASE-APPEAL",
                "--output",
                str(report_path),
            ]
        )
        == 0
    )
    text = report_path.read_text(encoding="utf-8")
    assert "MINORITY_REPORT" in text
    assert "DENIED" in text
    assert "DISAGREE" in text
    events = load_events(workspace.case_path("CASE-APPEAL") / "events.jsonl")
    actions = {event.get("action") for event in events}
    assert "REVIEW_APPEAL_FILED" in actions
    assert "REVIEW_APPEAL_DISPOSED" in actions


def test_appeal_validation_and_verification_matrix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, case_id, finding_id, _evidence_id = _workspace(tmp_path)
    statement = _seed_statement(workspace, case_id, finding_id)
    statement_id = str(statement["statement_id"])

    with pytest.raises(ValueError, match="Unsupported appeal type"):
        file_review_appeal(
            workspace,
            case_id,
            statement_id,
            "NOT_A_TYPE",
            "grounds",
            "resolution",
            appellant_id="reviewer-1",
        )
    with pytest.raises(ValueError, match="grounds must not be empty"):
        file_review_appeal(
            workspace,
            case_id,
            statement_id,
            "RECONSIDERATION",
            "   ",
            "resolution",
            appellant_id="reviewer-1",
        )
    with pytest.raises(ValueError, match="Requested resolution must not be empty"):
        file_review_appeal(
            workspace,
            case_id,
            statement_id,
            "RECONSIDERATION",
            "grounds",
            "  ",
            appellant_id="reviewer-1",
        )
    with pytest.raises(ValueError, match="must match appellant_id"):
        file_review_appeal(
            workspace,
            case_id,
            statement_id,
            "RECONSIDERATION",
            "grounds",
            "resolution",
            appellant_id="reviewer-1",
            actor="other-actor",
        )
    with pytest.raises(ValueError, match="no active assignment covering"):
        file_review_appeal(
            workspace,
            case_id,
            statement_id,
            "RECONSIDERATION",
            "grounds",
            "resolution",
            appellant_id="stranger",
        )
    with pytest.raises(ValueError, match="Unknown evidence IDs"):
        file_review_appeal(
            workspace,
            case_id,
            statement_id,
            "RECONSIDERATION",
            "grounds",
            "resolution",
            appellant_id="reviewer-1",
            evidence_ids=["EV-MISSING"],
        )

    statement_path = workspace.case_path(case_id) / "reviews" / "statements" / f"{statement_id}.json"
    original_statement = statement_path.read_text(encoding="utf-8")
    broken = json.loads(original_statement)
    broken["rationale"] = "Broken without rehash"
    statement_path.write_text(json.dumps(broken, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Source review statement hash is invalid"):
        file_review_appeal(
            workspace,
            case_id,
            statement_id,
            "RECONSIDERATION",
            "grounds",
            "resolution",
            appellant_id="reviewer-1",
        )
    statement_path.write_text(original_statement, encoding="utf-8")

    fixed_time = "2026-08-04T12:00:00.000000Z"
    monkeypatch.setattr("neuroai_workbench.review._review_timestamp", lambda: fixed_time)
    first = file_review_appeal(
        workspace,
        case_id,
        statement_id,
        "RECONSIDERATION",
        "grounds for duplicate-path collision",
        "resolution",
        appellant_id="reviewer-1",
    )
    # Remove the duplicate-source guard by deleting the appeal file while keeping the path collision ready.
    Path(first["path"]).unlink()
    with pytest.raises(ValueError, match="identical review appeal already exists"):
        # Recreate the deleted file so output.exists() trips before rewrite.
        Path(first["path"]).write_text("{}", encoding="utf-8")
        file_review_appeal(
            workspace,
            case_id,
            statement_id,
            "RECONSIDERATION",
            "grounds for duplicate-path collision",
            "resolution",
            appellant_id="reviewer-1",
        )
    Path(first["path"]).unlink(missing_ok=True)
    monkeypatch.undo()

    appeal = file_review_appeal(
        workspace,
        case_id,
        statement_id,
        "RECONSIDERATION",
        "Valid grounds after collision cleanup.",
        "Valid resolution.",
        appellant_id="reviewer-1",
    )["appeal"]
    appeal_id = str(appeal["appeal_id"])

    with pytest.raises(ValueError, match="Unsupported appeal outcome"):
        dispose_review_appeal(workspace, case_id, appeal_id, "NOPE", "rationale", actor="lead-1")
    with pytest.raises(ValueError, match="rationale must not be empty"):
        dispose_review_appeal(workspace, case_id, appeal_id, "DENIED", "  ", actor="lead-1")
    with pytest.raises(FileNotFoundError, match="Unknown review appeal"):
        dispose_review_appeal(workspace, case_id, "RAP-MISSING", "DENIED", "missing", actor="lead-1")

    appeal_path = workspace.case_path(case_id) / "reviews" / "appeals" / f"{appeal_id}.json"
    original_appeal = appeal_path.read_text(encoding="utf-8")
    broken_appeal = json.loads(original_appeal)
    broken_appeal["grounds"] = "Broken without rehash"
    appeal_path.write_text(json.dumps(broken_appeal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Review appeal hash is invalid"):
        dispose_review_appeal(workspace, case_id, appeal_id, "DENIED", "hash invalid", actor="lead-1")
    appeal_path.write_text(original_appeal, encoding="utf-8")

    statement_path.unlink()
    with pytest.raises(FileNotFoundError, match="Unknown review statement"):
        dispose_review_appeal(workspace, case_id, appeal_id, "DENIED", "statement gone", actor="lead-1")
    statement_path.write_text(original_statement, encoding="utf-8")

    dispose_review_appeal(
        workspace,
        case_id,
        appeal_id,
        "WITHDRAWN",
        "Withdrawn by decision role for coverage.",
        actor="lead-1",
    )

    from neuroai_workbench.review import _verify_appeal_event_correspondence

    workspace2, case_id2, finding_id2, _ = _workspace(tmp_path / "verify-matrix")
    statement2 = _seed_statement(workspace2, case_id2, finding_id2)
    appeal2 = file_review_appeal(
        workspace2,
        case_id2,
        str(statement2["statement_id"]),
        "MINORITY_REPORT",
        "Event mismatch grounds.",
        "Detect mismatches.",
        appellant_id="reviewer-1",
    )["appeal"]
    dispose_review_appeal(
        workspace2,
        case_id2,
        str(appeal2["appeal_id"]),
        "DENIED",
        "Disposition for event mismatch coverage.",
        actor="lead-1",
    )
    appeals_map = {str(appeal2["appeal_id"]): appeal2}
    dispositions_map = {
        str(appeal2["appeal_id"]): json.loads(
            (
                workspace2.case_path(case_id2) / "reviews" / "appeal_dispositions" / f"{appeal2['appeal_id']}.json"
            ).read_text(encoding="utf-8")
        )
    }
    fake_events = [
        {
            "action": "REVIEW_APPEAL_FILED",
            "actor": "wrong",
            "payload": {
                "appeal_id": appeal2["appeal_id"],
                "appeal_sha256": "0" * 64,
                "source_statement_id": "RS-WRONG",
                "source_statement_sha256": "1" * 64,
                "appeal_type": "RECONSIDERATION",
            },
        },
        {
            "action": "REVIEW_APPEAL_FILED",
            "actor": "wrong",
            "payload": {"appeal_id": appeal2["appeal_id"], "appeal_sha256": "0" * 64},
        },
        {
            "action": "REVIEW_APPEAL_DISPOSED",
            "actor": "wrong",
            "payload": {
                "appeal_id": appeal2["appeal_id"],
                "appeal_disposition_sha256": "2" * 64,
                "appeal_sha256": "3" * 64,
                "outcome": "UPHELD",
            },
        },
        {
            "action": "REVIEW_APPEAL_DISPOSED",
            "actor": "wrong",
            "payload": {"appeal_id": appeal2["appeal_id"], "appeal_disposition_sha256": "2" * 64},
        },
        {"action": "REVIEW_APPEAL_FILED", "actor": "ghost", "payload": {"appeal_id": "RAP-ORPHAN"}},
        {"action": "REVIEW_APPEAL_DISPOSED", "actor": "ghost", "payload": {}},
    ]
    correspondence_errors = _verify_appeal_event_correspondence(appeals_map, dispositions_map, fake_events)
    assert any("duplicate appeal filed" in error for error in correspondence_errors)
    assert any("duplicate appeal disposition" in error for error in correspondence_errors)
    assert any("orphan appeal event" in error for error in correspondence_errors)

    missing_disp_errors = _verify_appeal_event_correspondence(appeals_map, dispositions_map, [fake_events[0]])
    assert any("missing matching REVIEW_APPEAL_DISPOSED" in error for error in missing_disp_errors)

    single_mismatch = _verify_appeal_event_correspondence(
        appeals_map,
        dispositions_map,
        [fake_events[0], fake_events[2]],
    )
    assert any("event appeal digest mismatch" in error for error in single_mismatch)
    assert any("event outcome mismatch" in error for error in single_mismatch)

    # Record-level verification defects on the primary workspace.
    appeal_record = json.loads(appeal_path.read_text(encoding="utf-8"))
    appeal_record["appeal_type"] = "NOT_VALID"
    appeal_record["actor"] = "not-appellant"
    appeal_record["evidence_ids"] = ["EV-UNKNOWN"]
    appeal_record["assessment_sha256"] = "0" * 64
    appeal_record["assignment_ids"] = []
    appeal_record["appeal_sha256"] = _hash_record(appeal_record, "appeal_sha256")
    appeal_path.write_text(json.dumps(appeal_record, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    second = dict(appeal_record)
    second["appeal_id"] = "RAP-DUPLICATE-SOURCE"
    second["appeal_sha256"] = _hash_record(second, "appeal_sha256")
    (workspace.case_path(case_id) / "reviews" / "appeals" / "RAP-DUPLICATE-SOURCE.json").write_text(
        json.dumps(second, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    orphan_appeal = dict(appeal_record)
    orphan_appeal["appeal_id"] = "RAP-NO-SOURCE"
    orphan_appeal["source_statement_id"] = "RS-GONE"
    orphan_appeal["appeal_sha256"] = _hash_record(orphan_appeal, "appeal_sha256")
    (workspace.case_path(case_id) / "reviews" / "appeals" / "RAP-NO-SOURCE.json").write_text(
        json.dumps(orphan_appeal, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    broken_hash_appeal = dict(appeal_record)
    broken_hash_appeal["appeal_id"] = "RAP-BAD-HASH"
    broken_hash_appeal["source_statement_id"] = "RS-GONE-2"
    broken_hash_appeal["appeal_sha256"] = "bad"
    (workspace.case_path(case_id) / "reviews" / "appeals" / "RAP-BAD-HASH.json").write_text(
        json.dumps(broken_hash_appeal, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    disposition_path = workspace.case_path(case_id) / "reviews" / "appeal_dispositions" / f"{appeal_id}.json"
    disposition = json.loads(disposition_path.read_text(encoding="utf-8"))
    disposition["outcome"] = "NOT_VALID"
    disposition["appeal_sha256"] = "9" * 64
    disposition["appeal_disposition_sha256"] = _hash_record(disposition, "appeal_disposition_sha256")
    disposition_path.write_text(json.dumps(disposition, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    duplicate_disposition = dict(disposition)
    (workspace.case_path(case_id) / "reviews" / "appeal_dispositions" / f"{appeal_id}-dup.json").write_text(
        json.dumps(duplicate_disposition, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    orphan_disposition = {
        "schema_version": "1",
        "appeal_id": "RAP-NO-APPEAL",
        "appeal_sha256": "8" * 64,
        "outcome": "DENIED",
        "rationale": "orphan",
        "actor": "lead-1",
        "decision_assignment_ids": [],
        "recorded_at": "2026-08-04T12:00:00Z",
        "assessment_mutation": "NONE_PERFORMED_BY_APPEAL_DISPOSITION",
        "authority_profile": "LOCAL_UNAUTHENTICATED_ATTRIBUTION",
        "authority_boundary": "local only",
    }
    orphan_disposition["appeal_disposition_sha256"] = _hash_record(orphan_disposition, "appeal_disposition_sha256")
    (workspace.case_path(case_id) / "reviews" / "appeal_dispositions" / "RAP-NO-APPEAL.json").write_text(
        json.dumps(orphan_disposition, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report = verify_review_records(workspace, case_id)
    assert report["valid"] is False
    joined = " | ".join(report["errors"] + report["warnings"])
    assert "unsupported appeal type" in joined
    assert "actor does not match appellant" in joined
    assert "duplicate appeal for statement" in joined
    assert "source statement missing" in joined
    assert "unknown evidence IDs" in joined
    assert "assessment has changed since filing" in joined
    assert "no valid covering assignment at filing time" in joined
    assert "unsupported outcome" in joined
    assert "appeal hash mismatch" in joined
    assert "hash mismatch" in joined
    assert "duplicate appeal disposition" in joined
    assert "appeal missing" in joined

    disposition["appeal_disposition_sha256"] = "bad"
    disposition_path.write_text(json.dumps(disposition, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report2 = verify_review_records(workspace, case_id)
    assert any("appeal disposition" in error and "hash mismatch" in error for error in report2["errors"])
    assert any("no valid covering decision assignment at disposition time" in error for error in report2["errors"])
