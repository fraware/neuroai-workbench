from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from neuroai_workbench import evidence_transactions as transactions
from neuroai_workbench.evidence import (
    add_evidence_bytes,
    list_evidence_files,
    recover_evidence_registrations,
    verify_evidence_files,
)
from neuroai_workbench.events import load_events
from neuroai_workbench.util import load_json, sha256_file


class SimulatedCrash(RuntimeError):
    pass


def _crash_at(monkeypatch, point: str) -> None:
    def inject(observed: str) -> None:
        if observed == point:
            raise SimulatedCrash(point)

    monkeypatch.setattr(transactions, "_registration_fault", inject)


def _transaction_paths(workspace) -> list[Path]:
    root = workspace.case_path("CASE-001") / "evidence" / "transactions"
    return sorted(path for path in root.iterdir() if path.is_dir())


def _journal(workspace) -> dict:
    paths = _transaction_paths(workspace)
    assert len(paths) == 1
    return load_json(paths[0] / "journal.json")


def _case_hashes(workspace) -> tuple[str, str, str | None]:
    case = workspace.case_path("CASE-001")
    persistence = case / "persistence.json"
    return (
        sha256_file(case / "evidence" / "index.json"),
        sha256_file(case / "assessment.json"),
        sha256_file(persistence) if persistence.is_file() else None,
    )


def test_successful_registration_compacts_terminal_journal(workspace):
    workspace.create_case("CASE-001", "Example case")
    record = add_evidence_bytes(workspace, "CASE-001", "record.txt", b"controlled", title="Record")

    journal = _journal(workspace)
    assert journal["state"] == "COMMITTED"
    assert journal["recovered"] is False
    transaction_path = _transaction_paths(workspace)[0]
    assert not (transaction_path / "staged-object.bin").exists()
    assert not (transaction_path / "before-assessment.json").exists()
    assert verify_evidence_files(workspace, "CASE-001")["valid"]

    events = load_events(workspace.case_path("CASE-001") / "events.jsonl")
    added = [event for event in events if event["action"] == "EVIDENCE_ADDED"]
    assert len(added) == 1
    assert added[0]["payload"]["transaction_id"] == journal["transaction_id"]
    assert added[0]["payload"]["sha256"] == record["sha256"]


def test_unlinked_registration_is_transactional(workspace):
    workspace.create_case("CASE-001", "Example case")
    before = sha256_file(workspace.case_path("CASE-001") / "assessment.json")
    record = add_evidence_bytes(
        workspace,
        "CASE-001",
        "unlinked.bin",
        b"unlinked",
        title="Unlinked",
        link_to_assessment=False,
    )
    assert record["evidence_id"] == "EV-001"
    assert sha256_file(workspace.case_path("CASE-001") / "assessment.json") == before
    assert workspace.load_case("CASE-001")["evidence_register"] == []
    assert _journal(workspace)["state"] == "COMMITTED"


@pytest.mark.parametrize("point", ["after_prepare", "after_object", "after_index"])
def test_incomplete_registration_rolls_back_exact_predecessor(workspace, monkeypatch, point):
    workspace.create_case("CASE-001", "Example case")
    before = _case_hashes(workspace)
    _crash_at(monkeypatch, point)

    with pytest.raises(SimulatedCrash, match=point):
        add_evidence_bytes(workspace, "CASE-001", "record.txt", b"controlled", title="Record")

    monkeypatch.setattr(transactions, "_registration_fault", lambda observed: None)
    outcomes = recover_evidence_registrations(workspace, "CASE-001", actor="recovery-test")
    assert outcomes[0]["outcome"] == "ROLLED_BACK"
    assert _case_hashes(workspace) == before
    assert list_evidence_files(workspace, "CASE-001") == []
    assert workspace.load_case("CASE-001")["evidence_register"] == []
    assert list((workspace.case_path("CASE-001") / "evidence" / "objects").iterdir()) == []

    journal = _journal(workspace)
    assert journal["state"] == "ROLLED_BACK"
    assert journal["historical_finding_mutation_performed"] is False
    events = load_events(workspace.case_path("CASE-001") / "events.jsonl")
    rollback = [event for event in events if event["action"] == "EVIDENCE_REGISTRATION_ROLLED_BACK"]
    assert len(rollback) == 1
    assert rollback[0]["payload"]["historical_finding_mutation_performed"] is False


def test_fully_written_state_is_forward_completed_after_case_crash(workspace, monkeypatch):
    workspace.create_case("CASE-001", "Example case")
    _crash_at(monkeypatch, "after_case")
    with pytest.raises(SimulatedCrash, match="after_case"):
        add_evidence_bytes(workspace, "CASE-001", "record.txt", b"controlled", title="Record")

    monkeypatch.setattr(transactions, "_registration_fault", lambda observed: None)
    outcomes = recover_evidence_registrations(workspace, "CASE-001", actor="recovery-test")
    assert outcomes == [{"transaction_id": _journal(workspace)["transaction_id"], "outcome": "FORWARD_COMPLETED"}]
    assert _journal(workspace)["state"] == "COMMITTED"
    assert _journal(workspace)["recovered"] is True
    assert len(list_evidence_files(workspace, "CASE-001")) == 1
    assert len(workspace.load_case("CASE-001")["evidence_register"]) == 1
    assert verify_evidence_files(workspace, "CASE-001")["valid"]


def test_event_written_crash_recovers_without_duplicate_event(workspace, monkeypatch):
    workspace.create_case("CASE-001", "Example case")
    _crash_at(monkeypatch, "after_event")
    with pytest.raises(SimulatedCrash, match="after_event"):
        add_evidence_bytes(workspace, "CASE-001", "record.txt", b"controlled", title="Record")

    events_path = workspace.case_path("CASE-001") / "events.jsonl"
    before = [event for event in load_events(events_path) if event["action"] == "EVIDENCE_ADDED"]
    assert len(before) == 1

    monkeypatch.setattr(transactions, "_registration_fault", lambda observed: None)
    recover_evidence_registrations(workspace, "CASE-001", actor="recovery-test")
    after = [event for event in load_events(events_path) if event["action"] == "EVIDENCE_ADDED"]
    assert len(after) == 1
    assert _journal(workspace)["state"] == "COMMITTED"


def test_recovery_blocks_on_external_divergence(workspace, monkeypatch):
    workspace.create_case("CASE-001", "Example case")
    _crash_at(monkeypatch, "after_index")
    with pytest.raises(SimulatedCrash):
        add_evidence_bytes(workspace, "CASE-001", "record.txt", b"controlled", title="Record")

    assessment_path = workspace.case_path("CASE-001") / "assessment.json"
    assessment_path.write_text('{"external":"change"}\n', encoding="utf-8")
    monkeypatch.setattr(transactions, "_registration_fault", lambda observed: None)
    with pytest.raises(transactions.EvidenceTransactionRecoveryError, match="diverged"):
        recover_evidence_registrations(workspace, "CASE-001", actor="recovery-test")
    assert _journal(workspace)["state"] == "RECOVERY_BLOCKED"


def test_existing_content_addressed_object_mismatch_fails_before_journal(workspace):
    workspace.create_case("CASE-001", "Example case")
    case = workspace.case_path("CASE-001")
    digest = transactions.sha256_bytes(b"controlled")
    target = case / "evidence" / "objects" / f"{digest}.txt"
    target.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="digest mismatch"):
        add_evidence_bytes(workspace, "CASE-001", "record.txt", b"controlled", title="Record")
    transactions_root = case / "evidence" / "transactions"
    assert not transactions_root.exists() or list(transactions_root.iterdir()) == []


def test_orphan_prepare_directory_is_cleaned_without_state_mutation(workspace):
    workspace.create_case("CASE-001", "Example case")
    before = _case_hashes(workspace)
    case = workspace.case_path("CASE-001")
    orphan = case / "evidence" / "transactions" / "EVTX-orphan"
    orphan.mkdir(parents=True)
    (orphan / "staged-object.bin").write_bytes(b"never committed")

    outcomes = recover_evidence_registrations(workspace, "CASE-001", actor="recovery-test")
    assert outcomes == [{"transaction_id": "EVTX-orphan", "outcome": "ORPHAN_CLEANED"}]
    assert not orphan.exists()
    assert _case_hashes(workspace) == before
    events = load_events(case / "events.jsonl")
    assert events[-1]["action"] == "EVIDENCE_REGISTRATION_ORPHAN_CLEANED"
    assert events[-1]["payload"]["external_state_mutation_performed"] is False


def test_concurrent_registrations_allocate_unique_ids_and_valid_chain(workspace):
    workspace.create_case("CASE-001", "Example case")

    def register(number: int) -> str:
        record = add_evidence_bytes(
            workspace,
            "CASE-001",
            f"record-{number}.txt",
            f"controlled-{number}".encode(),
            title=f"Record {number}",
            actor=f"actor-{number}",
        )
        return str(record["evidence_id"])

    with ThreadPoolExecutor(max_workers=6) as pool:
        ids = list(pool.map(register, range(12)))
    assert sorted(ids) == [f"EV-{number:03d}" for number in range(1, 13)]
    assert len(list_evidence_files(workspace, "CASE-001")) == 12
    assert len(workspace.load_case("CASE-001")["evidence_register"]) == 12
    assert verify_evidence_files(workspace, "CASE-001")["valid"]


def test_terminal_recovery_is_idempotent(workspace):
    workspace.create_case("CASE-001", "Example case")
    add_evidence_bytes(workspace, "CASE-001", "record.txt", b"controlled", title="Record")
    events_path = workspace.case_path("CASE-001") / "events.jsonl"
    before = len(load_events(events_path))
    assert recover_evidence_registrations(workspace, "CASE-001") == []
    assert recover_evidence_registrations(workspace, "CASE-001") == []
    assert len(load_events(events_path)) == before
