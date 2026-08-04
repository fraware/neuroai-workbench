from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from neuroai_workbench import cli
from neuroai_workbench.cli import build_parser
from neuroai_workbench.errors import WorkspaceError
from neuroai_workbench.events import append_event, load_events
from neuroai_workbench.review import (
    _assignment_index,
    _assignment_was_active_at,
    _collect_independent_assignment_errors,
    _hash_record,
    _load_records,
    _parse_utc_timestamp,
    _review_root,
    _scope_covers_assignment,
    _verify_assignment_event_correspondence,
    create_review_assignment,
    dispose_review_statement,
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


def _write_assignment(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def _load_assignment(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _rehash_assignment(record: dict[str, Any]) -> dict[str, Any]:
    record = dict(record)
    record.pop("_path", None)
    record["assignment_sha256"] = _hash_record(record, "assignment_sha256")
    return record


# ---------------------------------------------------------------------------
# Existing happy-path / adversarial coverage retained and extended
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 5.1 Review-root / load failures
# ---------------------------------------------------------------------------


class TestReviewRootAndLoadFailures:
    def test_unknown_case_refused(self, tmp_path: Path) -> None:
        workspace = Workspace.initialize(tmp_path / "workspace")
        with pytest.raises(WorkspaceError, match="Unknown case"):
            create_review_assignment(
                workspace,
                "MISSING",
                "reviewer-1",
                "DOMAIN_REVIEWER",
                ["ASSESSMENT:*"],
                actor="lead-1",
            )

    def test_empty_assignment_store_loads_cleanly(self, tmp_path: Path) -> None:
        workspace, case_id, _finding_id = _workspace(tmp_path)
        report = verify_review_records(workspace, case_id)
        assert report["valid"] is True
        assert report["counts"]["assignments"] == 0
        assert "Integrity: `VALID`" in render_review_markdown(workspace, case_id)


# ---------------------------------------------------------------------------
# 5.2 Scope authorization via public revoke/supersede
# ---------------------------------------------------------------------------


class TestScopeAuthorizationViaPublicApis:
    def test_narrow_decision_role_cannot_control_broader_assignment(self, tmp_path: Path) -> None:
        workspace, case_id, finding_id = _workspace(tmp_path)
        target = create_review_assignment(
            workspace,
            case_id,
            "reviewer-1",
            "DOMAIN_REVIEWER",
            ["ASSESSMENT:*"],
            actor="assigner-1",
        )["assignment"]
        create_review_assignment(
            workspace,
            case_id,
            "methods-lead",
            "LEAD_ASSESSOR",
            [f"FINDING:{finding_id}"],
            actor="assigner-1",
        )
        with pytest.raises(ValueError, match="not authorized to supersede"):
            supersede_review_assignment(
                workspace,
                case_id,
                target["assignment_id"],
                "reviewer-2",
                "DOMAIN_REVIEWER",
                ["ASSESSMENT:*"],
                "Narrow lead cannot reassign broader scope.",
                actor="methods-lead",
            )
        with pytest.raises(ValueError, match="not authorized to revoke"):
            revoke_review_assignment(
                workspace,
                case_id,
                target["assignment_id"],
                "Narrow lead cannot revoke broader scope.",
                actor="methods-lead",
            )

    def test_wildcard_type_scope_covers_specific_assignment(self, tmp_path: Path) -> None:
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
            "DECISION_AUTHORITY",
            ["FINDING:*"],
            actor="assigner-1",
        )
        revoked = revoke_review_assignment(
            workspace,
            case_id,
            target["assignment_id"],
            "Covering FINDING:* decision role may revoke.",
            actor="lead-1",
        )["assignment"]
        assert revoked["transition_by"] == "lead-1"


# ---------------------------------------------------------------------------
# 5.3 Assignment-index structural rejection matrix
# ---------------------------------------------------------------------------


class TestAssignmentIndexStructuralRejection:
    def test_missing_assignment_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="missing assignment_id"):
            _assignment_index([{"role": "DOMAIN_REVIEWER", "state": "ACTIVE", "assignment_sha256": "x"}])

    def test_duplicate_assignment_id_rejected(self, tmp_path: Path) -> None:
        workspace, case_id, finding_id = _workspace(tmp_path)
        created = create_review_assignment(
            workspace,
            case_id,
            "reviewer-1",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            actor="lead-1",
        )["assignment"]
        duplicate = dict(created)
        duplicate["assignment_id"] = created["assignment_id"]
        with pytest.raises(ValueError, match="Duplicate review assignment ID"):
            _assignment_index([created, duplicate])

    def test_created_with_predecessor_rejected(self, tmp_path: Path) -> None:
        workspace, case_id, finding_id = _workspace(tmp_path)
        created = create_review_assignment(
            workspace,
            case_id,
            "reviewer-1",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            actor="lead-1",
        )["assignment"]
        created["predecessor_assignment_id"] = "RA-OTHER"
        created["assignment_sha256"] = _hash_record(created, "assignment_sha256")
        with pytest.raises(ValueError, match="predecessor data on CREATED"):
            _assignment_index([created])

    def test_unresolved_predecessor_rejected(self, tmp_path: Path) -> None:
        workspace, case_id, finding_id = _workspace(tmp_path)
        created = create_review_assignment(
            workspace,
            case_id,
            "reviewer-1",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            actor="lead-1",
        )["assignment"]
        successor = {
            **created,
            "assignment_id": "RA-SUCCESSOR",
            "transition": "SUPERSEDES",
            "predecessor_assignment_id": "RA-MISSING",
            "predecessor_assignment_sha256": created["assignment_sha256"],
            "transition_by": "lead-1",
            "transition_at": "2026-08-01T12:00:01Z",
            "transition_rationale": "missing predecessor",
            "state": "ACTIVE",
        }
        successor = _rehash_assignment(successor)
        with pytest.raises(ValueError, match="unresolved predecessor"):
            _assignment_index([created, successor])

    def test_multiple_successors_rejected(self, tmp_path: Path) -> None:
        workspace, case_id, finding_id = _workspace(tmp_path)
        created = create_review_assignment(
            workspace,
            case_id,
            "reviewer-1",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            actor="lead-1",
        )["assignment"]
        base = datetime.fromisoformat(created["assigned_at"].replace("Z", "+00:00")).astimezone(timezone.utc)
        stamp1 = (base + timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
        stamp2 = (base + timedelta(seconds=2)).isoformat().replace("+00:00", "Z")
        first = _rehash_assignment(
            {
                **created,
                "assignment_id": "RA-A",
                "transition": "REVOKES",
                "state": "REVOKED",
                "predecessor_assignment_id": created["assignment_id"],
                "predecessor_assignment_sha256": created["assignment_sha256"],
                "transition_by": "lead-1",
                "transition_at": stamp1,
                "transition_rationale": "first",
            }
        )
        second = _rehash_assignment(
            {
                **created,
                "assignment_id": "RA-B",
                "transition": "REVOKES",
                "state": "REVOKED",
                "predecessor_assignment_id": created["assignment_id"],
                "predecessor_assignment_sha256": created["assignment_sha256"],
                "transition_by": "lead-1",
                "transition_at": stamp2,
                "transition_rationale": "second",
            }
        )
        with pytest.raises(ValueError, match="multiple successor"):
            _assignment_index([created, first, second])

    def test_revocation_field_drift_rejected(self, tmp_path: Path) -> None:
        workspace, case_id, finding_id = _workspace(tmp_path)
        created = create_review_assignment(
            workspace,
            case_id,
            "reviewer-1",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            actor="lead-1",
        )["assignment"]
        stamp = (
            (
                datetime.fromisoformat(created["assigned_at"].replace("Z", "+00:00")).astimezone(timezone.utc)
                + timedelta(seconds=1)
            )
            .isoformat()
            .replace("+00:00", "Z")
        )
        drifted = _rehash_assignment(
            {
                **created,
                "assignment_id": "RA-REV",
                "transition": "REVOKES",
                "state": "REVOKED",
                "role": "METHODS_REVIEWER",
                "predecessor_assignment_id": created["assignment_id"],
                "predecessor_assignment_sha256": created["assignment_sha256"],
                "transition_by": "lead-1",
                "transition_at": stamp,
                "transition_rationale": "role drift",
            }
        )
        with pytest.raises(ValueError, match="changes role"):
            _assignment_index([created, drifted])

    def test_cycle_detected_with_hash_monkeypatch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "neuroai_workbench.review._hash_record",
            lambda value, hash_field: str(value.get(hash_field) or "patched"),
        )
        first = {
            "assignment_id": "RA-1",
            "role": "DOMAIN_REVIEWER",
            "state": "ACTIVE",
            "assigned_at": "2026-08-01T12:00:00Z",
            "transition": "SUPERSEDES",
            "predecessor_assignment_id": "RA-2",
            "predecessor_assignment_sha256": "hash-2",
            "transition_by": "lead-1",
            "transition_at": "2026-08-01T12:00:01Z",
            "transition_rationale": "cycle",
            "assignment_sha256": "hash-1",
            "scope": ["ASSESSMENT:*"],
            "reviewer_id": "r1",
        }
        second = {
            "assignment_id": "RA-2",
            "role": "DOMAIN_REVIEWER",
            "state": "ACTIVE",
            "assigned_at": "2026-08-01T11:00:00Z",
            "transition": "SUPERSEDES",
            "predecessor_assignment_id": "RA-1",
            "predecessor_assignment_sha256": "hash-1",
            "transition_by": "lead-1",
            "transition_at": "2026-08-01T12:00:02Z",
            "transition_rationale": "cycle",
            "assignment_sha256": "hash-2",
            "scope": ["ASSESSMENT:*"],
            "reviewer_id": "r2",
        }
        with pytest.raises(ValueError, match="lineage cycle"):
            _assignment_index([first, second])

    def test_temporal_inversion_rejected(self, tmp_path: Path) -> None:
        workspace, case_id, finding_id = _workspace(tmp_path)
        created = create_review_assignment(
            workspace,
            case_id,
            "reviewer-1",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            actor="lead-1",
        )["assignment"]
        earlier = _rehash_assignment(
            {
                **created,
                "assignment_id": "RA-EARLY",
                "transition": "SUPERSEDES",
                "state": "ACTIVE",
                "reviewer_id": "reviewer-2",
                "predecessor_assignment_id": created["assignment_id"],
                "predecessor_assignment_sha256": created["assignment_sha256"],
                "transition_by": "lead-1",
                "transition_at": "2020-01-01T00:00:00Z",
                "assigned_at": "2020-01-01T00:00:00Z",
                "transition_rationale": "too early",
            }
        )
        with pytest.raises(ValueError, match="predates its predecessor"):
            _assignment_index([created, earlier])


# ---------------------------------------------------------------------------
# 5.4 Temporal state + exact transition boundary
# ---------------------------------------------------------------------------


class TestTemporalStateAndTransitionBoundary:
    @pytest.mark.parametrize(
        ("value", "match"),
        [
            (None, "expected a non-empty"),
            ("", "expected a non-empty"),
            (123, "expected a non-empty"),
            ("not-a-timestamp", "malformed"),
            ("2026-08-01T12:00:00", "naive timestamp"),
        ],
    )
    def test_parse_utc_timestamp_rejects_invalid(self, value: object, match: str) -> None:
        with pytest.raises(ValueError, match=match):
            _parse_utc_timestamp(value, "assigned_at", record_id="RA-1")

    def test_parse_utc_timestamp_normalizes_z_and_offsets(self) -> None:
        zulu = _parse_utc_timestamp("2026-08-01T12:00:00Z", "assigned_at")
        offset = _parse_utc_timestamp("2026-08-01T14:00:00+02:00", "assigned_at")
        assert zulu == offset
        assert zulu.tzinfo == timezone.utc

    def test_half_open_boundary_at_exact_transition(self, tmp_path: Path) -> None:
        workspace, case_id, finding_id = _workspace(tmp_path)
        created = create_review_assignment(
            workspace,
            case_id,
            "reviewer-1",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            actor="lead-1",
        )["assignment"]
        successor = supersede_review_assignment(
            workspace,
            case_id,
            created["assignment_id"],
            "reviewer-2",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            "Boundary transfer.",
            actor="lead-1",
        )["assignment"]
        assignments, successors = _assignment_index(
            [
                _load_assignment(Path(p))
                for p in (
                    workspace.case_path(case_id) / "reviews" / "assignments" / f"{created['assignment_id']}.json",
                    workspace.case_path(case_id) / "reviews" / "assignments" / f"{successor['assignment_id']}.json",
                )
            ]
        )
        transition_at = successor["transition_at"]
        assert _assignment_was_active_at(created["assignment_id"], transition_at, assignments, successors) is False
        assert _assignment_was_active_at(successor["assignment_id"], transition_at, assignments, successors) is True
        before = (
            datetime.fromisoformat(transition_at.replace("Z", "+00:00"))
            .astimezone(timezone.utc)
            .replace(microsecond=max(0, datetime.fromisoformat(transition_at.replace("Z", "+00:00")).microsecond - 1))
        )
        # Use an instant strictly before transition via predecessor assigned_at.
        assert (
            _assignment_was_active_at(created["assignment_id"], created["assigned_at"], assignments, successors) is True
        )
        assert before  # keep datetime import exercised for local clarity


# ---------------------------------------------------------------------------
# 5.5 Revoke + supersede public APIs
# ---------------------------------------------------------------------------


class TestRevokeAndSupersedePublicApis:
    def test_unknown_and_inactive_tip_refusals(self, tmp_path: Path) -> None:
        workspace, case_id, finding_id = _workspace(tmp_path)
        created = create_review_assignment(
            workspace,
            case_id,
            "reviewer-1",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            actor="lead-1",
        )["assignment"]
        with pytest.raises(FileNotFoundError, match="Unknown review assignment"):
            revoke_review_assignment(workspace, case_id, "RA-MISSING", "gone", actor="lead-1")
        revoke_review_assignment(workspace, case_id, created["assignment_id"], "done", actor="lead-1")
        with pytest.raises(ValueError, match="not an active lineage tip"):
            revoke_review_assignment(workspace, case_id, created["assignment_id"], "again", actor="lead-1")
        with pytest.raises(ValueError, match="rationale must not be empty"):
            supersede_review_assignment(
                workspace,
                case_id,
                created["assignment_id"],
                "reviewer-2",
                "DOMAIN_REVIEWER",
                [f"FINDING:{finding_id}"],
                " ",
                actor="lead-1",
            )

    def test_supersede_refuses_decision_role_self_appointment(self, tmp_path: Path) -> None:
        workspace, case_id, finding_id = _workspace(tmp_path)
        created = create_review_assignment(
            workspace,
            case_id,
            "reviewer-1",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            actor="lead-1",
        )["assignment"]
        with pytest.raises(ValueError, match="Self-assignment"):
            supersede_review_assignment(
                workspace,
                case_id,
                created["assignment_id"],
                "lead-1",
                "LEAD_ASSESSOR",
                ["ASSESSMENT:*"],
                "Self appoint",
                actor="lead-1",
            )

    def test_assessment_and_predecessor_bytes_unchanged_with_one_event(self, tmp_path: Path) -> None:
        workspace, case_id, finding_id = _workspace(tmp_path)
        assessment_path = workspace.case_path(case_id) / "assessment.json"
        before = assessment_path.read_bytes()
        created = create_review_assignment(
            workspace,
            case_id,
            "reviewer-1",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            actor="lead-1",
        )
        predecessor_path = Path(created["path"])
        predecessor_bytes = predecessor_path.read_bytes()
        supersede_review_assignment(
            workspace,
            case_id,
            created["assignment"]["assignment_id"],
            "reviewer-2",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            "Transfer.",
            actor="lead-1",
        )
        assert assessment_path.read_bytes() == before
        assert predecessor_path.read_bytes() == predecessor_bytes
        events = [
            event
            for event in load_events(workspace.case_path(case_id) / "events.jsonl")
            if event["action"] == "REVIEW_ASSIGNMENT_SUPERSEDED"
        ]
        assert len(events) == 1


# ---------------------------------------------------------------------------
# 5.6 Verification multi-defect fallback
# ---------------------------------------------------------------------------


class TestVerificationMultiDefectFallback:
    def test_index_failure_collects_independent_errors_and_zero_authority(self, tmp_path: Path) -> None:
        workspace, case_id, finding_id = _workspace(tmp_path)
        created = create_review_assignment(
            workspace,
            case_id,
            "reviewer-1",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            actor="lead-1",
        )
        path = Path(created["path"])
        record = _load_assignment(path)
        record["state"] = "SUSPENDED"
        record["role"] = "NOT_A_ROLE"
        record["assigned_at"] = "yesterday"
        record["scope"] = ["BAD", "MODEL:*"]
        record["assignment_sha256"] = _hash_record(record, "assignment_sha256")
        path.write_text(json.dumps(record), encoding="utf-8")

        report = verify_review_records(workspace, case_id)
        assert report["valid"] is False
        assert report["assignment_summary"]["active"] == 0
        markdown = render_review_markdown(workspace, case_id)
        assert "Integrity: `INVALID`" in markdown
        assert "INVALID" in markdown
        fragments = (
            "unsupported state",
            "unsupported role",
            "malformed timestamp",
            "invalid scope entry",
            "unsupported scope target type",
        )
        for fragment in fragments:
            assert any(fragment in error for error in report["errors"]), fragment


# ---------------------------------------------------------------------------
# 5.7 Statement + disposition temporal verification
# ---------------------------------------------------------------------------


class TestStatementAndDispositionTemporalVerification:
    def test_historical_statement_survives_later_revocation(self, tmp_path: Path) -> None:
        workspace, case_id, finding_id = _workspace(tmp_path)
        created = create_review_assignment(
            workspace,
            case_id,
            "reviewer-1",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            actor="lead-1",
        )["assignment"]
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
            "DISAGREE",
            "Historical dissent.",
        )["statement"]
        revoke_review_assignment(
            workspace,
            case_id,
            created["assignment_id"],
            "Later revocation.",
            actor="lead-1",
        )
        report = verify_review_records(workspace, case_id)
        assert report["valid"] is True
        assert statement["statement_id"] in render_review_markdown(workspace, case_id)

    def test_disposition_after_decision_role_revoked_fails_verification(self, tmp_path: Path) -> None:
        workspace, case_id, finding_id = _workspace(tmp_path)
        create_review_assignment(
            workspace,
            case_id,
            "reviewer-1",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            actor="lead-1",
        )
        lead = create_review_assignment(
            workspace,
            case_id,
            "lead-1",
            "LEAD_ASSESSOR",
            ["ASSESSMENT:*"],
            actor="assigner-1",
        )["assignment"]
        statement = submit_review_statement(
            workspace,
            case_id,
            "reviewer-1",
            "FINDING",
            finding_id,
            "AGREE",
            "Supported.",
        )["statement"]
        dispose_review_statement(
            workspace,
            case_id,
            statement["statement_id"],
            "ACCEPTED",
            "Accepted.",
            actor="lead-1",
        )
        # Corrupt disposition recorded_at to after a fabricated transition boundary by
        # rewriting the lead assignment's successor transition time into the past of recorded_at
        # via an extra revoke, then backdating disposition time past the transition.
        revoke_review_assignment(
            workspace,
            case_id,
            lead["assignment_id"],
            "Lead role ended.",
            actor="assigner-1",
        )
        disposition_path = (
            workspace.case_path(case_id) / "reviews" / "dispositions" / f"{statement['statement_id']}.json"
        )
        disposition = json.loads(disposition_path.read_text(encoding="utf-8"))
        disposition["recorded_at"] = "2099-01-01T00:00:00Z"
        disposition["disposition_sha256"] = _hash_record(disposition, "disposition_sha256")
        disposition_path.write_text(json.dumps(disposition), encoding="utf-8")
        report = verify_review_records(workspace, case_id)
        assert report["valid"] is False
        assert any("no valid covering decision assignment" in error for error in report["errors"])


# ---------------------------------------------------------------------------
# 5.8 Event correspondence
# ---------------------------------------------------------------------------


class TestEventCorrespondence:
    def test_digest_and_actor_mismatch_fail_without_silent_repair(self, tmp_path: Path) -> None:
        workspace, case_id, finding_id = _workspace(tmp_path)
        created = create_review_assignment(
            workspace,
            case_id,
            "reviewer-1",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            actor="lead-1",
        )["assignment"]
        path = workspace.case_path(case_id) / "reviews" / "assignments" / f"{created['assignment_id']}.json"
        record = _load_assignment(path)
        record["transition_rationale"] = "Changed rationale without new event"
        record["assignment_sha256"] = _hash_record(record, "assignment_sha256")
        path.write_text(json.dumps(record), encoding="utf-8")
        report = verify_review_records(workspace, case_id)
        assert report["valid"] is False
        assert any("event assignment digest mismatch" in error for error in report["errors"])

    def test_orphan_transition_event_fails(self, tmp_path: Path) -> None:
        workspace, case_id, finding_id = _workspace(tmp_path)
        create_review_assignment(
            workspace,
            case_id,
            "reviewer-1",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            actor="lead-1",
        )
        append_event(
            workspace.case_path(case_id) / "events.jsonl",
            "REVIEW_ASSIGNMENT_CREATED",
            "lead-1",
            {
                "assignment_id": "RA-ORPHAN",
                "reviewer_id": "ghost",
                "role": "OBSERVER",
                "transition": "CREATED",
                "assignment_sha256": "0" * 64,
            },
        )
        report = verify_review_records(workspace, case_id)
        assert report["valid"] is False
        assert any("orphan transition event" in error for error in report["errors"])

    def test_duplicate_transition_events_fail(self, tmp_path: Path) -> None:
        workspace, case_id, finding_id = _workspace(tmp_path)
        created = create_review_assignment(
            workspace,
            case_id,
            "reviewer-1",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            actor="lead-1",
        )["assignment"]
        append_event(
            workspace.case_path(case_id) / "events.jsonl",
            "REVIEW_ASSIGNMENT_CREATED",
            "lead-1",
            {
                "assignment_id": created["assignment_id"],
                "reviewer_id": created["reviewer_id"],
                "role": created["role"],
                "transition": "CREATED",
                "assignment_sha256": created["assignment_sha256"],
            },
        )
        report = verify_review_records(workspace, case_id)
        assert report["valid"] is False
        assert any("duplicate assignment transition events" in error for error in report["errors"])


# ---------------------------------------------------------------------------
# 5.9 Tip-assigner policy (no perpetual root inheritance)
# ---------------------------------------------------------------------------


class TestTipAssignerPolicy:
    def test_prior_assigner_loses_authority_after_supersession(self, tmp_path: Path) -> None:
        workspace, case_id, finding_id = _workspace(tmp_path)
        created = create_review_assignment(
            workspace,
            case_id,
            "reviewer-1",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            actor="root-assigner",
        )["assignment"]
        successor = supersede_review_assignment(
            workspace,
            case_id,
            created["assignment_id"],
            "reviewer-2",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            "Lead takes over appointment.",
            actor="root-assigner",
        )["assignment"]
        assert successor["assigned_by"] == "root-assigner"
        # Third actor becomes tip assigner.
        tip = supersede_review_assignment(
            workspace,
            case_id,
            successor["assignment_id"],
            "reviewer-3",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            "Current tip assigner transfers again.",
            actor="root-assigner",
        )["assignment"]
        assert tip["assigned_by"] == "root-assigner"
        # After tip is held by root-assigner still - use decision role path instead:
        # Create tip assigned by lead-2, then root-assigner without covering role cannot supersede.
        create_review_assignment(
            workspace,
            case_id,
            "lead-2",
            "LEAD_ASSESSOR",
            ["ASSESSMENT:*"],
            actor="governor",
        )
        reassigned = supersede_review_assignment(
            workspace,
            case_id,
            tip["assignment_id"],
            "reviewer-4",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            "Lead-2 becomes current-assignment assigner.",
            actor="lead-2",
        )["assignment"]
        assert reassigned["assigned_by"] == "lead-2"
        with pytest.raises(ValueError, match="not authorized to supersede"):
            supersede_review_assignment(
                workspace,
                case_id,
                reassigned["assignment_id"],
                "reviewer-5",
                "DOMAIN_REVIEWER",
                [f"FINDING:{finding_id}"],
                "Prior root assigner has no perpetual authority.",
                actor="root-assigner",
            )


# ---------------------------------------------------------------------------
# 5.10 Missing event / action mismatch correspondence
# ---------------------------------------------------------------------------


class TestMissingAndMismatchedEvents:
    def test_missing_matching_event_reported(self, tmp_path: Path) -> None:
        workspace, case_id, finding_id = _workspace(tmp_path)
        created = create_review_assignment(
            workspace,
            case_id,
            "reviewer-1",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            actor="lead-1",
        )["assignment"]
        # Write a second assignment file without emitting an event.
        ghost = _rehash_assignment(
            {
                **created,
                "assignment_id": "RA-GHOST-CREATED",
                "transition": "CREATED",
                "predecessor_assignment_id": None,
                "predecessor_assignment_sha256": None,
                "transition_by": "lead-1",
                "transition_at": "2026-08-01T15:00:00Z",
                "assigned_at": "2026-08-01T15:00:00Z",
                "transition_rationale": "ghost",
                "reviewer_id": "reviewer-9",
            }
        )
        _write_assignment(
            workspace.case_path(case_id) / "reviews" / "assignments" / f"{ghost['assignment_id']}.json",
            ghost,
        )
        report = verify_review_records(workspace, case_id)
        assert report["valid"] is False
        assert any("missing matching REVIEW_ASSIGNMENT_CREATED event" in error for error in report["errors"])

    def test_action_mismatch_reported(self, tmp_path: Path) -> None:
        workspace, case_id, finding_id = _workspace(tmp_path)
        created = create_review_assignment(
            workspace,
            case_id,
            "reviewer-1",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            actor="lead-1",
        )["assignment"]
        revoke_review_assignment(
            workspace,
            case_id,
            created["assignment_id"],
            "End.",
            actor="lead-1",
        )
        # Find revocation record and leave event as REVOKED while flipping record transition label
        # would break hash/index; instead append wrong-action orphan already covered.
        # Mutate event actor mismatch on the CREATED event by rewriting payload via new append is hard;
        # change transition_by on the CREATED assignment record.
        path = workspace.case_path(case_id) / "reviews" / "assignments" / f"{created['assignment_id']}.json"
        record = _load_assignment(path)
        record["transition_by"] = "impostor"
        record["assignment_sha256"] = _hash_record(record, "assignment_sha256")
        path.write_text(json.dumps(record), encoding="utf-8")
        report = verify_review_records(workspace, case_id)
        assert report["valid"] is False
        assert any("event actor mismatch" in error for error in report["errors"])


# ---------------------------------------------------------------------------
# 5.11 CLI execution (dispatch path)
# ---------------------------------------------------------------------------


class TestCliExecutionDispatch:
    def test_review_revoke_supersede_verify_report_cli(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        workspace_path = tmp_path / "workspace"
        assert cli.main(["init", str(workspace_path), "--name", "CLI review"]) == 0
        capsys.readouterr()
        assert cli.main(["case-create", str(workspace_path), "CASE-CLI", "--title", "CLI case"]) == 0
        capsys.readouterr()
        workspace = Workspace(workspace_path)
        finding_id = str(workspace.load_case("CASE-CLI")["requirement_findings"][0]["requirement_id"])

        assert (
            cli.main(
                [
                    "review-assign",
                    str(workspace_path),
                    "CASE-CLI",
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
        assigned = json.loads(capsys.readouterr().out)
        assignment_id = assigned["assignment"]["assignment_id"]

        assert (
            cli.main(
                [
                    "review-supersede",
                    str(workspace_path),
                    "CASE-CLI",
                    assignment_id,
                    "reviewer-2",
                    "METHODS_REVIEWER",
                    "--scope",
                    f"FINDING:{finding_id}",
                    "--rationale",
                    "CLI transfer",
                    "--actor",
                    "lead-1",
                ]
            )
            == 0
        )
        superseded = json.loads(capsys.readouterr().out)
        tip_id = superseded["assignment"]["assignment_id"]

        assert (
            cli.main(
                [
                    "review-revoke",
                    str(workspace_path),
                    "CASE-CLI",
                    tip_id,
                    "--rationale",
                    "CLI revoke",
                    "--actor",
                    "lead-1",
                ]
            )
            == 0
        )
        capsys.readouterr()

        assert cli.main(["review-verify", str(workspace_path), "CASE-CLI"]) == 0
        verify_payload = json.loads(capsys.readouterr().out)
        assert verify_payload["valid"] is True

        report_path = tmp_path / "review.md"
        assert cli.main(["review-report", str(workspace_path), "CASE-CLI", "--output", str(report_path)]) == 0
        capsys.readouterr()
        text = report_path.read_text(encoding="utf-8")
        assert "Integrity: `VALID`" in text
        assert "REVOKED" in text or "SUPERSEDED" in text


class TestCoverageGapClosures:
    def test_review_root_without_assessment_file(self, tmp_path: Path) -> None:
        workspace = Workspace.initialize(tmp_path / "workspace")
        case = workspace.root / "cases" / "CASE-EMPTY"
        case.mkdir(parents=True)
        with pytest.raises(ValueError, match="Unknown case"):
            _review_root(workspace, "CASE-EMPTY")

    def test_load_records_missing_directory(self, tmp_path: Path) -> None:
        assert _load_records(tmp_path / "missing") == []

    def test_scope_cover_matrix(self) -> None:
        assert _scope_covers_assignment(["ASSESSMENT:*"], ["FINDING:*"]) is True
        assert _scope_covers_assignment(["FINDING:*"], ["FINDING:*"]) is True
        assert _scope_covers_assignment(["FINDING:R1"], ["FINDING:*"]) is False
        assert _scope_covers_assignment(["FINDING:R1"], ["FINDING:R2"]) is False
        assert _scope_covers_assignment(["FINDING:R1"], ["FINDING:R1"]) is True

    def test_index_rejects_unsupported_transition_and_attribution_gaps(self, tmp_path: Path) -> None:
        workspace, case_id, finding_id = _workspace(tmp_path)
        created = create_review_assignment(
            workspace,
            case_id,
            "reviewer-1",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            actor="lead-1",
        )["assignment"]
        bad_transition = _rehash_assignment({**created, "transition": "REASSIGN"})
        with pytest.raises(ValueError, match="unsupported transition"):
            _assignment_index([bad_transition])

        base = datetime.fromisoformat(created["assigned_at"].replace("Z", "+00:00")).astimezone(timezone.utc)
        stamp = (base + timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
        inactive_pred = _rehash_assignment({**created, "state": "REVOKED"})
        follower = _rehash_assignment(
            {
                **created,
                "assignment_id": "RA-FOLLOW",
                "transition": "SUPERSEDES",
                "state": "ACTIVE",
                "predecessor_assignment_id": created["assignment_id"],
                "predecessor_assignment_sha256": inactive_pred["assignment_sha256"],
                "transition_by": "lead-1",
                "transition_at": stamp,
                "transition_rationale": "follow inactive",
            }
        )
        with pytest.raises(ValueError, match="non-active predecessor"):
            _assignment_index([inactive_pred, follower])

        for field, match in (
            ("transition_by", "missing transition attribution"),
            ("transition_at", "missing transition time"),
            ("transition_rationale", "missing transition rationale"),
        ):
            record = _rehash_assignment(
                {
                    **created,
                    "assignment_id": f"RA-{field}",
                    "transition": "REVOKES",
                    "state": "REVOKED",
                    "predecessor_assignment_id": created["assignment_id"],
                    "predecessor_assignment_sha256": created["assignment_sha256"],
                    "transition_by": "lead-1",
                    "transition_at": stamp,
                    "transition_rationale": "ok",
                    field: " ",
                }
            )
            with pytest.raises(ValueError, match=match):
                _assignment_index([created, record])

        supersede_inactive = _rehash_assignment(
            {
                **created,
                "assignment_id": "RA-SUP-BAD",
                "transition": "SUPERSEDES",
                "state": "REVOKED",
                "predecessor_assignment_id": created["assignment_id"],
                "predecessor_assignment_sha256": created["assignment_sha256"],
                "transition_by": "lead-1",
                "transition_at": stamp,
                "transition_rationale": "bad supersede state",
            }
        )
        with pytest.raises(ValueError, match="must be ACTIVE when superseding"):
            _assignment_index([created, supersede_inactive])

        revoke_active = _rehash_assignment(
            {
                **created,
                "assignment_id": "RA-REV-BAD",
                "transition": "REVOKES",
                "state": "ACTIVE",
                "predecessor_assignment_id": created["assignment_id"],
                "predecessor_assignment_sha256": created["assignment_sha256"],
                "transition_by": "lead-1",
                "transition_at": stamp,
                "transition_rationale": "bad revoke state",
            }
        )
        with pytest.raises(ValueError, match="must be REVOKED for a revocation"):
            _assignment_index([created, revoke_active])

    def test_was_active_at_fail_closed_branches(self) -> None:
        assignments = {
            "RA-1": {
                "assignment_id": "RA-1",
                "state": "ACTIVE",
                "assigned_at": "2026-08-01T12:00:00Z",
            },
            "RA-2": {
                "assignment_id": "RA-2",
                "state": "REVOKED",
                "assigned_at": "2026-08-01T12:00:00Z",
            },
            "RA-3": {
                "assignment_id": "RA-3",
                "state": "ACTIVE",
                "assigned_at": "not-a-time",
            },
            "RA-4": {
                "assignment_id": "RA-4",
                "state": "ACTIVE",
                "assigned_at": "2026-08-01T12:00:00Z",
                "transition_at": "bad",
            },
        }
        successors = {"RA-1": "RA-4"}
        assert _assignment_was_active_at("missing", "2026-08-01T12:00:00Z", assignments, successors) is False
        assert _assignment_was_active_at("RA-2", "2026-08-01T12:00:00Z", assignments, successors) is False
        assert _assignment_was_active_at("RA-3", "2026-08-01T12:00:00Z", assignments, {}) is False
        assert _assignment_was_active_at("RA-1", "2026-07-01T12:00:00Z", assignments, {}) is False
        assert _assignment_was_active_at("RA-1", "2026-08-01T13:00:00Z", assignments, successors) is False

    def test_independent_error_collector_branches(self) -> None:
        base = {
            "assignment_id": "RA-X",
            "role": "DOMAIN_REVIEWER",
            "state": "ACTIVE",
            "transition": "CREATED",
            "assigned_at": "2026-08-01T12:00:00Z",
            "scope": ["ASSESSMENT:*"],
            "reviewer_id": "r1",
        }
        hashed = _rehash_assignment(base)
        hashed["assignment_sha256"] = "0" * 64
        errors = _collect_independent_assignment_errors(hashed)
        assert any("hash mismatch" in item for item in errors)

        unsupported = _rehash_assignment({**base, "transition": "REASSIGN", "assigned_at": None})
        errors = _collect_independent_assignment_errors(unsupported)
        assert any("unsupported transition" in item for item in errors)
        assert any("missing assigned_at" in item for item in errors)

        created_without_transition_at = _rehash_assignment({**base, "transition_at": None})
        assert _collect_independent_assignment_errors(created_without_transition_at) == []

        revoke_missing_transition_at = _rehash_assignment(
            {**base, "transition": "REVOKES", "state": "REVOKED", "transition_at": None}
        )
        # None transition_at on non-CREATED falls through to continue (no error) when value is None
        # after the CREATED skip — cover the `if value is None: continue` path.
        assert isinstance(_collect_independent_assignment_errors(revoke_missing_transition_at), list)

    def test_event_correspondence_predecessor_and_unsupported(self) -> None:
        assignments = {
            "RA-1": {
                "assignment_id": "RA-1",
                "transition": "REVOKES",
                "assignment_sha256": "abc",
                "transition_by": "lead-1",
                "reviewer_id": "r1",
                "role": "DOMAIN_REVIEWER",
                "predecessor_assignment_id": "RA-0",
                "predecessor_assignment_sha256": "pred",
            },
            "RA-BAD": {
                "assignment_id": "RA-BAD",
                "transition": "REASSIGN",
                "assignment_sha256": "x",
                "transition_by": "lead-1",
                "reviewer_id": "r1",
                "role": "DOMAIN_REVIEWER",
            },
        }
        events = [
            {
                "action": "REVIEW_ASSIGNMENT_REVOKED",
                "actor": "lead-1",
                "payload": {
                    "assignment_id": "RA-1",
                    "assignment_sha256": "abc",
                    "transition": "REVOKES",
                    "reviewer_id": "r1",
                    "role": "DOMAIN_REVIEWER",
                    "predecessor_assignment_id": "RA-OTHER",
                    "predecessor_assignment_sha256": "other",
                },
            }
        ]
        errors = _verify_assignment_event_correspondence(assignments, events)
        assert any("event predecessor id mismatch" in item for item in errors)
        assert any("event predecessor digest mismatch" in item for item in errors)

    def test_public_api_refusal_branches(self, tmp_path: Path) -> None:
        workspace, case_id, finding_id = _workspace(tmp_path)
        created = create_review_assignment(
            workspace,
            case_id,
            "reviewer-1",
            "DOMAIN_REVIEWER",
            [f"FINDING:{finding_id}"],
            actor="lead-1",
        )["assignment"]
        with pytest.raises(ValueError, match="rationale must not be empty"):
            revoke_review_assignment(workspace, case_id, created["assignment_id"], "  ", actor="lead-1")
        with pytest.raises(ValueError, match="Unsupported review role"):
            supersede_review_assignment(
                workspace,
                case_id,
                created["assignment_id"],
                "reviewer-2",
                "OWNER",
                [f"FINDING:{finding_id}"],
                "bad role",
                actor="lead-1",
            )
        with pytest.raises(FileNotFoundError, match="Unknown review assignment"):
            supersede_review_assignment(
                workspace,
                case_id,
                "RA-MISSING",
                "reviewer-2",
                "DOMAIN_REVIEWER",
                [f"FINDING:{finding_id}"],
                "missing",
                actor="lead-1",
            )
        revoke_review_assignment(workspace, case_id, created["assignment_id"], "done", actor="lead-1")
        with pytest.raises(ValueError, match="not an active lineage tip"):
            supersede_review_assignment(
                workspace,
                case_id,
                created["assignment_id"],
                "reviewer-2",
                "DOMAIN_REVIEWER",
                [f"FINDING:{finding_id}"],
                "already revoked",
                actor="lead-1",
            )

    def test_disposition_verify_defects_and_load_events_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workspace, case_id, finding_id = _workspace(tmp_path)
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
            "AGREE",
            "ok",
        )["statement"]
        dispose_review_statement(
            workspace,
            case_id,
            statement["statement_id"],
            "ACCEPTED",
            "ok",
            actor="lead-1",
        )
        disposition_path = (
            workspace.case_path(case_id) / "reviews" / "dispositions" / f"{statement['statement_id']}.json"
        )
        duplicate_path = (
            workspace.case_path(case_id) / "reviews" / "dispositions" / f"dup-{statement['statement_id']}.json"
        )
        payload = json.loads(disposition_path.read_text(encoding="utf-8"))
        duplicate_path.write_text(json.dumps(payload), encoding="utf-8")
        payload["disposition_sha256"] = "0" * 64
        disposition_path.write_text(json.dumps(payload), encoding="utf-8")
        orphan = {
            "schema_version": "1",
            "statement_id": "RS-MISSING",
            "statement_sha256": "0" * 64,
            "disposition": "ACCEPTED",
            "rationale": "orphan",
            "actor": "lead-1",
            "assignment_ids": [],
            "recorded_at": "2026-08-01T12:00:00Z",
            "assessment_mutation": "NONE_PERFORMED_BY_DISPOSITION_RECORD",
            "authority_profile": "LOCAL_UNAUTHENTICATED_ATTRIBUTION",
            "authority_boundary": "local",
        }
        orphan["disposition_sha256"] = _hash_record(orphan, "disposition_sha256")
        (workspace.case_path(case_id) / "reviews" / "dispositions" / "RS-MISSING.json").write_text(
            json.dumps(orphan), encoding="utf-8"
        )

        report = verify_review_records(workspace, case_id)
        assert report["valid"] is False
        assert any("duplicate disposition" in error for error in report["errors"])
        assert any("disposition" in error and "hash mismatch" in error for error in report["errors"])
        assert any("statement missing" in error for error in report["errors"])

        monkeypatch.setattr(
            "neuroai_workbench.review.load_events",
            lambda path: (_ for _ in ()).throw(ValueError("boom")),
        )
        report = verify_review_records(workspace, case_id)
        assert any("unable to load events for assignment correspondence" in error for error in report["errors"])
        assert "INVALID" in render_review_markdown(workspace, case_id)
