from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from neuroai_workbench import evidence_transactions as transactions
from neuroai_workbench.events import load_events, verify_chain
from neuroai_workbench.evidence import (
    add_evidence_bytes,
    list_evidence_files,
    recover_evidence_registrations,
    verify_evidence_files,
)
from neuroai_workbench.util import atomic_write_json, load_json, sha256_bytes, sha256_file


class SimulatedCrash(RuntimeError):
    pass


def _crash_at(monkeypatch, point: str) -> None:
    def inject(observed: str) -> None:
        if observed == point:
            raise SimulatedCrash(point)

    monkeypatch.setattr(transactions, "_registration_fault", inject)


def _disable_faults(monkeypatch) -> None:
    monkeypatch.setattr(transactions, "_registration_fault", lambda observed: None)


def _transaction_paths(workspace) -> list[Path]:
    root = workspace.case_path("CASE-001") / "evidence" / "transactions"
    if not root.is_dir():
        return []
    return sorted(path for path in root.iterdir() if path.is_dir())


def _transaction_path(workspace) -> Path:
    paths = _transaction_paths(workspace)
    assert len(paths) == 1
    return paths[0]


def _journal(workspace) -> dict:
    return load_json(_transaction_path(workspace) / "journal.json")


def _case_hashes(workspace) -> tuple[str, str, str | None]:
    case = workspace.case_path("CASE-001")
    persistence = case / "persistence.json"
    return (
        sha256_file(case / "evidence" / "index.json"),
        sha256_file(case / "assessment.json"),
        sha256_file(persistence) if persistence.is_file() else None,
    )


def _events_for_transaction(workspace, action: str) -> list[dict]:
    transaction_id = _journal(workspace)["transaction_id"]
    events = load_events(workspace.case_path("CASE-001") / "events.jsonl")
    return [
        event
        for event in events
        if event["action"] == action and event["payload"].get("transaction_id") == transaction_id
    ]


def test_successful_registration_compacts_terminal_journal_and_preserves_events(workspace):
    workspace.create_case("CASE-001", "Example case")
    record = add_evidence_bytes(workspace, "CASE-001", "record.txt", b"controlled", title="Record")

    journal = _journal(workspace)
    assert journal["state"] == "COMMITTED"
    assert journal["recovered"] is False
    assert journal["journal_hash"] == transactions._journal_hash(journal)
    transaction_path = _transaction_path(workspace)
    assert not (transaction_path / "staged-object.bin").exists()
    assert not (transaction_path / "before-assessment.json").exists()
    assert verify_evidence_files(workspace, "CASE-001")["valid"]

    saved = _events_for_transaction(workspace, "ASSESSMENT_SAVED")
    added = _events_for_transaction(workspace, "EVIDENCE_ADDED")
    assert len(saved) == len(added) == 1
    assert saved[0]["seq"] + 1 == added[0]["seq"]
    assert saved[0]["payload"]["after_sha256"] == journal["desired"]["assessment_sha256"]
    assert added[0]["payload"]["sha256"] == record["sha256"]
    assert verify_chain(workspace.case_path("CASE-001") / "events.jsonl")["valid"]


def test_unlinked_registration_is_transactional_without_assessment_event(workspace):
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
    assert _events_for_transaction(workspace, "ASSESSMENT_SAVED") == []
    assert len(_events_for_transaction(workspace, "EVIDENCE_ADDED")) == 1


@pytest.mark.parametrize("point", ["after_prepare", "after_object", "after_index"])
def test_incomplete_registration_rolls_back_exact_predecessor(workspace, monkeypatch, point):
    workspace.create_case("CASE-001", "Example case")
    before = _case_hashes(workspace)
    _crash_at(monkeypatch, point)

    with pytest.raises(SimulatedCrash, match=point):
        add_evidence_bytes(workspace, "CASE-001", "record.txt", b"controlled", title="Record")

    _disable_faults(monkeypatch)
    outcomes = recover_evidence_registrations(workspace, "CASE-001", actor="recovery-test")
    assert outcomes[0]["outcome"] == "ROLLED_BACK"
    assert _case_hashes(workspace) == before
    assert list_evidence_files(workspace, "CASE-001") == []
    assert workspace.load_case("CASE-001")["evidence_register"] == []
    assert list((workspace.case_path("CASE-001") / "evidence" / "objects").iterdir()) == []

    journal = _journal(workspace)
    assert journal["state"] == "ROLLED_BACK"
    assert journal["historical_finding_mutation_performed"] is False
    assert journal["journal_hash"] == transactions._journal_hash(journal)
    rollback = _events_for_transaction(workspace, "EVIDENCE_REGISTRATION_ROLLED_BACK")
    assert len(rollback) == 1
    assert rollback[0]["payload"]["historical_finding_mutation_performed"] is False


def test_fully_written_state_is_forward_completed_after_case_crash(workspace, monkeypatch):
    workspace.create_case("CASE-001", "Example case")
    _crash_at(monkeypatch, "after_case")
    with pytest.raises(SimulatedCrash, match="after_case"):
        add_evidence_bytes(workspace, "CASE-001", "record.txt", b"controlled", title="Record")

    _disable_faults(monkeypatch)
    transaction_id = _journal(workspace)["transaction_id"]
    outcomes = recover_evidence_registrations(workspace, "CASE-001", actor="recovery-test")
    assert outcomes == [{"transaction_id": transaction_id, "outcome": "FORWARD_COMPLETED"}]
    assert _journal(workspace)["state"] == "COMMITTED"
    assert _journal(workspace)["recovered"] is True
    assert len(list_evidence_files(workspace, "CASE-001")) == 1
    assert len(workspace.load_case("CASE-001")["evidence_register"]) == 1
    assert verify_evidence_files(workspace, "CASE-001")["valid"]
    assert len(_events_for_transaction(workspace, "ASSESSMENT_SAVED")) == 1
    assert len(_events_for_transaction(workspace, "EVIDENCE_ADDED")) == 1


def test_partial_event_commit_is_completed_without_duplicate_assessment_event(workspace, monkeypatch):
    workspace.create_case("CASE-001", "Example case")
    _crash_at(monkeypatch, "after_assessment_event")
    with pytest.raises(SimulatedCrash, match="after_assessment_event"):
        add_evidence_bytes(workspace, "CASE-001", "record.txt", b"controlled", title="Record")

    assert len(_events_for_transaction(workspace, "ASSESSMENT_SAVED")) == 1
    assert _events_for_transaction(workspace, "EVIDENCE_ADDED") == []
    _disable_faults(monkeypatch)
    recover_evidence_registrations(workspace, "CASE-001", actor="recovery-test")
    assert len(_events_for_transaction(workspace, "ASSESSMENT_SAVED")) == 1
    assert len(_events_for_transaction(workspace, "EVIDENCE_ADDED")) == 1


def test_events_written_crash_recovers_without_duplicate_events(workspace, monkeypatch):
    workspace.create_case("CASE-001", "Example case")
    _crash_at(monkeypatch, "after_event")
    with pytest.raises(SimulatedCrash, match="after_event"):
        add_evidence_bytes(workspace, "CASE-001", "record.txt", b"controlled", title="Record")

    assert len(_events_for_transaction(workspace, "ASSESSMENT_SAVED")) == 1
    assert len(_events_for_transaction(workspace, "EVIDENCE_ADDED")) == 1
    _disable_faults(monkeypatch)
    recover_evidence_registrations(workspace, "CASE-001", actor="recovery-test")
    assert len(_events_for_transaction(workspace, "ASSESSMENT_SAVED")) == 1
    assert len(_events_for_transaction(workspace, "EVIDENCE_ADDED")) == 1
    assert _journal(workspace)["state"] == "COMMITTED"


def test_recovery_blocks_on_external_divergence(workspace, monkeypatch):
    workspace.create_case("CASE-001", "Example case")
    _crash_at(monkeypatch, "after_index")
    with pytest.raises(SimulatedCrash):
        add_evidence_bytes(workspace, "CASE-001", "record.txt", b"controlled", title="Record")

    assessment_path = workspace.case_path("CASE-001") / "assessment.json"
    assessment_path.write_text('{"external":"change"}\n', encoding="utf-8")
    _disable_faults(monkeypatch)
    with pytest.raises(transactions.EvidenceTransactionRecoveryError, match="diverged"):
        recover_evidence_registrations(workspace, "CASE-001", actor="recovery-test")
    journal = _journal(workspace)
    assert journal["state"] == "RECOVERY_BLOCKED"
    assert journal["journal_hash"] == transactions._journal_hash(journal)


def test_journal_hash_tamper_fails_closed(workspace, monkeypatch):
    workspace.create_case("CASE-001", "Example case")
    _crash_at(monkeypatch, "after_prepare")
    with pytest.raises(SimulatedCrash):
        add_evidence_bytes(workspace, "CASE-001", "record.txt", b"controlled", title="Record")

    journal_path = _transaction_path(workspace) / "journal.json"
    journal = load_json(journal_path)
    journal["record"]["title"] = "tampered"
    atomic_write_json(journal_path, journal)
    _disable_faults(monkeypatch)
    with pytest.raises(ValueError, match="journal hash mismatch"):
        recover_evidence_registrations(workspace, "CASE-001")


def test_snapshot_hash_tamper_blocks_recovery(workspace, monkeypatch):
    workspace.create_case("CASE-001", "Example case")
    _crash_at(monkeypatch, "after_index")
    with pytest.raises(SimulatedCrash):
        add_evidence_bytes(workspace, "CASE-001", "record.txt", b"controlled", title="Record")

    snapshot = _transaction_path(workspace) / "before-assessment.json"
    snapshot.write_bytes(b'{"tampered":true}\n')
    _disable_faults(monkeypatch)
    with pytest.raises(transactions.EvidenceTransactionRecoveryError, match="snapshot hash mismatch"):
        recover_evidence_registrations(workspace, "CASE-001")
    assert _journal(workspace)["state"] == "RECOVERY_BLOCKED"


def test_existing_content_addressed_object_mismatch_fails_before_journal(workspace):
    workspace.create_case("CASE-001", "Example case")
    case = workspace.case_path("CASE-001")
    digest = sha256_bytes(b"controlled")
    target = case / "evidence" / "objects" / f"{digest}.txt"
    target.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="digest mismatch"):
        add_evidence_bytes(workspace, "CASE-001", "record.txt", b"controlled", title="Record")
    transactions_root = case / "evidence" / "transactions"
    assert not transactions_root.exists() or list(transactions_root.iterdir()) == []


def test_orphan_prepare_directory_is_quarantined_fail_closed(workspace):
    workspace.create_case("CASE-001", "Example case")
    before = _case_hashes(workspace)
    case = workspace.case_path("CASE-001")
    orphan = case / "evidence" / "transactions" / "EVTX-orphan"
    orphan.mkdir(parents=True)
    (orphan / "staged-object.bin").write_bytes(b"never committed")

    outcomes = recover_evidence_registrations(workspace, "CASE-001", actor="recovery-test")
    assert outcomes[0]["transaction_id"] == "EVTX-orphan"
    assert outcomes[0]["outcome"] == "ORPHAN_QUARANTINED"
    assert not orphan.exists()
    quarantined = case / "evidence" / "transaction-orphans" / outcomes[0]["quarantine_directory"]
    assert (quarantined / "staged-object.bin").read_bytes() == b"never committed"
    assert _case_hashes(workspace) == before
    events = load_events(case / "events.jsonl")
    assert events[-1]["action"] == "EVIDENCE_REGISTRATION_ORPHAN_QUARANTINED"
    assert events[-1]["payload"]["external_state_mutation_state"] == "UNKNOWN_FAIL_CLOSED"


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
    assert verify_chain(workspace.case_path("CASE-001") / "events.jsonl")["valid"]


def test_terminal_recovery_is_idempotent(workspace):
    workspace.create_case("CASE-001", "Example case")
    add_evidence_bytes(workspace, "CASE-001", "record.txt", b"controlled", title="Record")
    events_path = workspace.case_path("CASE-001") / "events.jsonl"
    before = len(load_events(events_path))
    assert recover_evidence_registrations(workspace, "CASE-001") == []
    assert recover_evidence_registrations(workspace, "CASE-001") == []
    assert len(load_events(events_path)) == before


def test_committed_transaction_refuses_direct_rollback(workspace):
    workspace.create_case("CASE-001", "Example case")
    add_evidence_bytes(workspace, "CASE-001", "record.txt", b"controlled", title="Record")
    with pytest.raises(transactions.EvidenceTransactionRecoveryError, match="cannot be rolled back"):
        transactions.rollback_evidence_transaction(
            workspace.case_path("CASE-001"),
            _transaction_path(workspace),
            actor="test",
            reason="TEST",
        )
