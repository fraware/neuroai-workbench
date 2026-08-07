from __future__ import annotations

import json
from pathlib import Path

import pytest

import neuroai_workbench.workspace as workspace_module
from neuroai_workbench.errors import WorkspaceError
from neuroai_workbench.events import load_events
from neuroai_workbench.util import sha256_file


def _changed(workspace, case_id: str = "CASE-001", text: str = "changed"):
    assessment = workspace.load_case(case_id)
    assessment["assessment_metadata"]["assessment_purpose"] = text
    return assessment


def test_save_rolls_back_all_files_before_event_commit(workspace, monkeypatch) -> None:
    workspace.create_case("CASE-001", "Case")
    case = workspace.case_path("CASE-001")
    assessment_path = case / "assessment.json"
    before_bytes = assessment_path.read_bytes()
    before_sha = sha256_file(assessment_path)
    application = case / "applications" / "one.json"

    def fail(*_args, **_kwargs):
        raise RuntimeError("injected event failure")

    monkeypatch.setattr(workspace_module, "append_event", fail)
    with pytest.raises(RuntimeError, match="injected"):
        workspace.save_case(
            "CASE-001",
            _changed(workspace),
            expected_sha256=before_sha,
            exclusive_records=[(application, {"ok": True})],
        )
    assert assessment_path.read_bytes() == before_bytes
    assert not application.exists()
    assert not (case / "persistence.json").exists()
    assert not workspace.assessment_history_path("CASE-001", before_sha).exists()
    transactions = list((case / "transactions" / "assessment-saves").glob("*/transaction.json"))
    assert len(transactions) == 1
    assert json.loads(transactions[0].read_text(encoding="utf-8"))["state"] == "ROLLED_BACK"


def test_save_accepts_durable_event_if_append_raises_after_commit(workspace, monkeypatch) -> None:
    workspace.create_case("CASE-001", "Case")
    case = workspace.case_path("CASE-001")
    before_sha = sha256_file(case / "assessment.json")
    real_append = workspace_module.append_event

    def commit_then_raise(*args, **kwargs):
        real_append(*args, **kwargs)
        raise RuntimeError("post-commit interruption")

    monkeypatch.setattr(workspace_module, "append_event", commit_then_raise)
    result = workspace.save_case("CASE-001", _changed(workspace), expected_sha256=before_sha)
    assert result["transaction_id"]
    saved = [event for event in load_events(case / "events.jsonl") if event.get("action") == "ASSESSMENT_SAVED"]
    assert len(saved) == 1
    transaction = next((case / "transactions" / "assessment-saves").glob("*/transaction.json"))
    assert json.loads(transaction.read_text(encoding="utf-8"))["state"] == "COMMITTED"


def test_next_save_recovers_prepared_crash_transaction(workspace, monkeypatch) -> None:
    workspace.create_case("CASE-001", "Case")
    case = workspace.case_path("CASE-001")
    original = workspace.load_case("CASE-001")
    original_sha = sha256_file(case / "assessment.json")
    real_append = workspace_module.append_event

    def crash(*_args, **_kwargs):
        raise SystemExit("simulated process interruption")

    monkeypatch.setattr(workspace_module, "append_event", crash)
    with pytest.raises(SystemExit):
        workspace.save_case("CASE-001", _changed(workspace, text="interrupted"), expected_sha256=original_sha)
    monkeypatch.setattr(workspace_module, "append_event", real_append)
    successor = json.loads(json.dumps(original))
    successor["assessment_metadata"]["assessment_purpose"] = "recovered successor"
    result = workspace.save_case("CASE-001", successor, expected_sha256=original_sha)
    assert result["after_sha256"] == sha256_file(case / "assessment.json")
    states = [
        json.loads(path.read_text(encoding="utf-8"))["state"]
        for path in (case / "transactions" / "assessment-saves").glob("*/transaction.json")
    ]
    assert sorted(states) == ["COMMITTED", "ROLLED_BACK"]


def test_history_digest_and_exclusive_path_are_fail_closed(workspace, tmp_path: Path) -> None:
    workspace.create_case("CASE-001", "Case")
    case = workspace.case_path("CASE-001")
    before_sha = sha256_file(case / "assessment.json")
    workspace.save_case("CASE-001", _changed(workspace), expected_sha256=before_sha)
    original = workspace.load_assessment_history("CASE-001", before_sha)
    changed_sha = sha256_file(case / "assessment.json")
    workspace.save_case("CASE-001", original, expected_sha256=changed_sha)
    history = workspace.assessment_history_path("CASE-001", before_sha)
    history.write_text("{}\n", encoding="utf-8")
    with pytest.raises(WorkspaceError, match="history digest mismatch"):
        workspace.load_assessment_history("CASE-001", before_sha)
    current_sha = sha256_file(case / "assessment.json")
    with pytest.raises(WorkspaceError, match="history digest mismatch"):
        workspace.save_case("CASE-001", _changed(workspace, text="again"), expected_sha256=current_sha)

    workspace.create_case("CASE-002", "Second case")
    second_sha = sha256_file(workspace.case_path("CASE-002") / "assessment.json")
    with pytest.raises(WorkspaceError, match="escapes"):
        workspace.save_case(
            "CASE-002",
            workspace.load_case("CASE-002"),
            expected_sha256=second_sha,
            exclusive_records=[(tmp_path / "outside.json", {"x": 1})],
        )
