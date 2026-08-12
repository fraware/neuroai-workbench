from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from neuroai_workbench.events import load_events, verify_chain
from neuroai_workbench.governance_transactions import (
    GovernanceRecoveryBlocked,
    append_governance_record_locked,
    diagnose_governance_transactions,
    governance_write_lock,
    recover_governance_transactions,
)
from neuroai_workbench.util import canonical_json_bytes, load_json, sha256_bytes
from neuroai_workbench.workspace import Workspace


def _workspace(tmp_path: Path) -> Workspace:
    return Workspace.initialize(tmp_path / "workspace")


def _record() -> tuple[dict[str, object], str]:
    value: dict[str, object] = {
        "schema_version": "1",
        "record_id": "GOVREC-TEST",
        "value": "immutable",
        "release_authorization_performed": False,
    }
    return value, sha256_bytes(canonical_json_bytes(value))


def _commit(
    workspace: Workspace,
    *,
    phase_hook=None,
    record_id: str = "GOVREC-TEST",
    name: str = "GOVREC-TEST.json",
):
    record, digest = _record()
    record["record_id"] = record_id
    digest = sha256_bytes(canonical_json_bytes(record))
    with governance_write_lock(workspace):
        return append_governance_record_locked(
            workspace,
            record_path=workspace.root / "governance" / "records" / name,
            record=record,
            record_id=record_id,
            record_sha256=digest,
            event_action="GOVERNANCE_TEST_RECORDED",
            actor="local-test",
            event_payload={"record_id": record_id, "record_sha256": digest},
            secondary_digests={"register_sha256": "b" * 64},
            phase_hook=phase_hook,
        )


def _journals(workspace: Workspace) -> list[Path]:
    return sorted((workspace.root / "governance" / "transactions").glob("*.json"))


def test_success_commits_record_event_and_cleans_journal(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    result = _commit(workspace)

    record_path = workspace.root / "governance" / "records" / "GOVREC-TEST.json"
    assert record_path.is_file()
    assert _journals(workspace) == []
    events = load_events(workspace.root / "events.jsonl")
    assert len(events) == 1
    payload = events[0]["payload"]
    assert payload["transaction_id"] == result["transaction_id"]
    assert payload["transaction_record_id"] == "GOVREC-TEST"
    assert payload["transaction_record_sha256"] == result["record_sha256"]
    assert payload["transaction_secondary_digests"] == {"register_sha256": "b" * 64}
    report = verify_chain(workspace.root / "events.jsonl")
    assert report["valid"] is True
    assert report["trailer_valid"] is True


@pytest.mark.parametrize(
    "phase",
    [
        "BEFORE_JOURNAL_WRITE",
        "AFTER_JOURNAL_WRITE",
        "AFTER_RECORD_WRITE",
        "BEFORE_EVENT_APPEND",
    ],
)
def test_pre_event_crashes_leave_no_committed_record(tmp_path: Path, phase: str) -> None:
    workspace = _workspace(tmp_path)

    def crash(observed: str) -> None:
        if observed == phase:
            raise RuntimeError(f"crash:{phase}")

    with pytest.raises(RuntimeError, match=f"crash:{phase}"):
        _commit(workspace, phase_hook=crash)

    record_path = workspace.root / "governance" / "records" / "GOVREC-TEST.json"
    assert not record_path.exists()
    assert _journals(workspace) == []
    events_path = workspace.root / "events.jsonl"
    if events_path.exists():
        assert load_events(events_path) == []


def test_error_after_durable_event_is_recovered_as_committed(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)

    def crash(phase: str) -> None:
        if phase == "AFTER_EVENT_APPEND":
            raise RuntimeError("caller lost response after durable commit")

    with pytest.raises(RuntimeError, match="caller lost response"):
        _commit(workspace, phase_hook=crash)

    record_path = workspace.root / "governance" / "records" / "GOVREC-TEST.json"
    assert record_path.is_file()
    assert _journals(workspace) == []
    events = load_events(workspace.root / "events.jsonl")
    assert len(events) == 1
    assert events[0]["action"] == "GOVERNANCE_TEST_RECORDED"
    recovery = recover_governance_transactions(workspace)
    assert recovery["recovery_blocked"] is False
    assert recovery["prepared"] == 0


def test_diagnostic_is_non_authorizing(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _commit(workspace)
    report = diagnose_governance_transactions(workspace)
    assert report["valid"] is True
    assert report["prepared"] == 0
    assert report["release_authorization_performed"] is False
    assert "do not authenticate governance actors" in report["boundary"]
    assert "authorize a successor release" in report["boundary"]


def test_record_path_escape_is_rejected(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    record, digest = _record()
    with governance_write_lock(workspace):
        with pytest.raises(ValueError, match="escapes"):
            append_governance_record_locked(
                workspace,
                record_path=workspace.root / "outside.json",
                record=record,
                record_id="GOVREC-TEST",
                record_sha256=digest,
                event_action="GOVERNANCE_TEST_RECORDED",
                actor="local-test",
                event_payload={},
            )


def test_reserved_transaction_payload_keys_are_rejected(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    record, digest = _record()
    with governance_write_lock(workspace):
        with pytest.raises(ValueError, match="reserved transaction keys"):
            append_governance_record_locked(
                workspace,
                record_path=workspace.root / "governance" / "records" / "record.json",
                record=record,
                record_id="GOVREC-TEST",
                record_sha256=digest,
                event_action="GOVERNANCE_TEST_RECORDED",
                actor="local-test",
                event_payload={"transaction_id": "forged"},
            )


def test_corrupt_prepared_journal_fails_closed(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    transaction_root = workspace.root / "governance" / "transactions"
    transaction_root.mkdir(parents=True)
    (transaction_root / "GOVTXN-corrupt.json").write_text("{not-json", encoding="utf-8")

    with pytest.raises(GovernanceRecoveryBlocked, match="Corrupt governance transaction journal"):
        recover_governance_transactions(workspace)

    assert (transaction_root / "GOVTXN-corrupt.json").exists()


def test_tampered_pre_event_record_blocks_recovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _workspace(tmp_path)
    record_path = workspace.root / "governance" / "records" / "GOVREC-TEST.json"

    class StopRecovery(BaseException):
        pass

    # Simulate process death after the record is durable. BaseException is intercepted by
    # the implementation, so make recovery itself fail before it can clean the prepared state.
    import neuroai_workbench.governance_transactions as transactions

    original_recovery = transactions._recover_prepared_transactions_unlocked

    def crash(phase: str) -> None:
        if phase == "AFTER_RECORD_WRITE":
            monkeypatch.setattr(
                transactions,
                "_recover_prepared_transactions_unlocked",
                lambda _workspace: (_ for _ in ()).throw(StopRecovery()),
            )
            raise RuntimeError("simulated process loss")

    with pytest.raises(StopRecovery):
        _commit(workspace, phase_hook=crash)

    monkeypatch.setattr(transactions, "_recover_prepared_transactions_unlocked", original_recovery)
    assert record_path.is_file()
    assert len(_journals(workspace)) == 1
    record_path.write_text("tampered\n", encoding="utf-8")

    with pytest.raises(GovernanceRecoveryBlocked, match="record bytes diverge"):
        recover_governance_transactions(workspace)

    assert record_path.is_file()
    assert len(_journals(workspace)) == 1


def test_event_witness_without_record_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _workspace(tmp_path)

    class StopRecovery(BaseException):
        pass

    import neuroai_workbench.governance_transactions as transactions

    original_recovery = transactions._recover_prepared_transactions_unlocked

    def crash(phase: str) -> None:
        if phase == "AFTER_EVENT_APPEND":
            monkeypatch.setattr(
                transactions,
                "_recover_prepared_transactions_unlocked",
                lambda _workspace: (_ for _ in ()).throw(StopRecovery()),
            )
            raise RuntimeError("simulated process loss")

    with pytest.raises(StopRecovery):
        _commit(workspace, phase_hook=crash)

    monkeypatch.setattr(transactions, "_recover_prepared_transactions_unlocked", original_recovery)
    record_path = workspace.root / "governance" / "records" / "GOVREC-TEST.json"
    record_path.unlink()
    with pytest.raises(GovernanceRecoveryBlocked, match="record is missing"):
        recover_governance_transactions(workspace)


def test_governance_lock_serializes_semantic_check_and_commit(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    outcomes: list[str] = []
    outcomes_lock = threading.Lock()
    barrier = threading.Barrier(2)

    def writer(label: str) -> None:
        barrier.wait()
        with governance_write_lock(workspace):
            existing = list((workspace.root / "governance" / "records").glob("*.json"))
            if existing:
                with outcomes_lock:
                    outcomes.append(f"{label}:rejected")
                return
            # Increase the chance that a missing outer lock would expose the check/write race.
            time.sleep(0.03)
            _record_value, digest = _record()
            record_value = {
                "schema_version": "1",
                "record_id": f"GOVREC-{label}",
                "release_authorization_performed": False,
            }
            digest = sha256_bytes(canonical_json_bytes(record_value))
            append_governance_record_locked(
                workspace,
                record_path=workspace.root / "governance" / "records" / f"{label}.json",
                record=record_value,
                record_id=f"GOVREC-{label}",
                record_sha256=digest,
                event_action="GOVERNANCE_TEST_RECORDED",
                actor="local-test",
                event_payload={"label": label},
            )
            with outcomes_lock:
                outcomes.append(f"{label}:committed")

    threads = [threading.Thread(target=writer, args=(label,)) for label in ("A", "B")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    assert sum(item.endswith(":committed") for item in outcomes) == 1
    assert sum(item.endswith(":rejected") for item in outcomes) == 1
    assert len(list((workspace.root / "governance" / "records").glob("*.json"))) == 1
    assert len(load_events(workspace.root / "events.jsonl")) == 1


def test_prepared_journal_contains_no_record_body_or_protected_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)

    class StopRecovery(BaseException):
        pass

    import neuroai_workbench.governance_transactions as transactions

    secret = "PROTECTED-CAPTURE-BYTES-MUST-NOT-ENTER-JOURNAL"
    original_recovery = transactions._recover_prepared_transactions_unlocked
    record = {
        "schema_version": "1",
        "record_id": "GOVREC-PROTECTED",
        "opaque_reference": "protected-ref:CAPTURE-001",
        "test_secret": secret,
        "release_authorization_performed": False,
    }
    digest = sha256_bytes(canonical_json_bytes(record))

    def crash(phase: str) -> None:
        if phase == "AFTER_JOURNAL_WRITE":
            monkeypatch.setattr(
                transactions,
                "_recover_prepared_transactions_unlocked",
                lambda _workspace: (_ for _ in ()).throw(StopRecovery()),
            )
            raise RuntimeError("simulated process loss")

    with pytest.raises(StopRecovery):
        with governance_write_lock(workspace):
            append_governance_record_locked(
                workspace,
                record_path=workspace.root / "governance" / "records" / "protected.json",
                record=record,
                record_id="GOVREC-PROTECTED",
                record_sha256=digest,
                event_action="GOVERNANCE_TEST_RECORDED",
                actor="local-test",
                event_payload={"opaque_reference": "protected-ref:CAPTURE-001"},
                phase_hook=crash,
            )

    monkeypatch.setattr(transactions, "_recover_prepared_transactions_unlocked", original_recovery)
    journal = _journals(workspace)[0]
    raw = journal.read_text(encoding="utf-8")
    assert secret not in raw
    assert "test_secret" not in raw
    assert load_json(journal)["record_id"] == "GOVREC-PROTECTED"
