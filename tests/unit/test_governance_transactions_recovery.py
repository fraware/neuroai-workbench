from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import neuroai_workbench.governance_transactions as tx
from neuroai_workbench.util import canonical_json_bytes, sha256_bytes
from neuroai_workbench.workspace import Workspace


def _workspace(tmp_path: Path) -> Workspace:
    return Workspace.initialize(tmp_path / "workspace")


def _record() -> tuple[dict[str, Any], str]:
    record: dict[str, Any] = {
        "schema_version": "1",
        "record_id": "GOVREC-RECOVERY",
        "release_authorization_performed": False,
    }
    return record, sha256_bytes(canonical_json_bytes(record))


def _leave_prepared_record(workspace: Workspace, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    class StopRecovery(BaseException):
        pass

    original_recovery = tx._recover_prepared_transactions_unlocked
    record, digest = _record()
    record_path = workspace.root / "governance" / "records" / "GOVREC-RECOVERY.json"

    def phase_hook(phase: str) -> None:
        if phase == "AFTER_RECORD_WRITE":
            monkeypatch.setattr(
                tx,
                "_recover_prepared_transactions_unlocked",
                lambda _workspace: (_ for _ in ()).throw(StopRecovery()),
            )
            raise RuntimeError("simulate process loss")

    with pytest.raises(StopRecovery):
        with tx.governance_write_lock(workspace):
            tx.append_governance_record_locked(
                workspace,
                record_path=record_path,
                record=record,
                record_id="GOVREC-RECOVERY",
                record_sha256=digest,
                event_action="GOVERNANCE_TEST_RECORDED",
                actor="local-test",
                event_payload={},
                phase_hook=phase_hook,
            )

    monkeypatch.setattr(tx, "_recover_prepared_transactions_unlocked", original_recovery)
    journals = list((workspace.root / "governance" / "transactions").glob("*.json"))
    assert len(journals) == 1
    assert record_path.is_file()
    return journals[0], record_path


def test_exception_during_event_append_rolls_back_only_uncommitted_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)
    record, digest = _record()
    record_path = workspace.root / "governance" / "records" / "GOVREC-RECOVERY.json"

    def fail_event_append(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("event append interrupted")

    monkeypatch.setattr(tx, "append_event", fail_event_append)
    with pytest.raises(RuntimeError, match="event append interrupted"):
        with tx.governance_write_lock(workspace):
            tx.append_governance_record_locked(
                workspace,
                record_path=record_path,
                record=record,
                record_id="GOVREC-RECOVERY",
                record_sha256=digest,
                event_action="GOVERNANCE_TEST_RECORDED",
                actor="local-test",
                event_payload={},
            )

    assert not record_path.exists()
    assert list((workspace.root / "governance" / "transactions").glob("*.json")) == []


def test_recovery_is_idempotent_after_interruption_during_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)
    journal_path, record_path = _leave_prepared_record(workspace, monkeypatch)
    original_remove_journal = tx._remove_journal
    calls = 0

    def fail_first_cleanup(path: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("recovery cleanup interrupted")
        original_remove_journal(path)

    monkeypatch.setattr(tx, "_remove_journal", fail_first_cleanup)
    with pytest.raises(RuntimeError, match="recovery cleanup interrupted"):
        tx.recover_governance_transactions(workspace)

    assert not record_path.exists()
    assert journal_path.exists()

    monkeypatch.setattr(tx, "_remove_journal", original_remove_journal)
    recovered = tx.recover_governance_transactions(workspace)
    assert recovered["rolled_back"] == 1
    assert not journal_path.exists()
    assert not record_path.exists()


def test_failed_record_byte_postcheck_enters_recovery_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _workspace(tmp_path)
    record, digest = _record()
    record_path = workspace.root / "governance" / "records" / "GOVREC-RECOVERY.json"
    real_sha256_file = tx.sha256_file
    first_record_check = True

    def mismatching_first_record_check(path: Path) -> str:
        nonlocal first_record_check
        if path == record_path and first_record_check:
            first_record_check = False
            return "f" * 64
        return real_sha256_file(path)

    monkeypatch.setattr(tx, "sha256_file", mismatching_first_record_check)
    with pytest.raises(RuntimeError, match="record bytes do not match prepared transaction"):
        with tx.governance_write_lock(workspace):
            tx.append_governance_record_locked(
                workspace,
                record_path=record_path,
                record=record,
                record_id="GOVREC-RECOVERY",
                record_sha256=digest,
                event_action="GOVERNANCE_TEST_RECORDED",
                actor="local-test",
                event_payload={},
            )

    assert not record_path.exists()
    assert list((workspace.root / "governance" / "transactions").glob("*.json")) == []


def test_secondary_digest_writer_validation_fails_before_journal(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    record, digest = _record()
    with tx.governance_write_lock(workspace):
        with pytest.raises(tx.GovernanceRecoveryBlocked, match="secondary_digests.register_sha256"):
            tx.append_governance_record_locked(
                workspace,
                record_path=workspace.root / "governance" / "records" / "record.json",
                record=record,
                record_id="GOVREC-RECOVERY",
                record_sha256=digest,
                event_action="GOVERNANCE_TEST_RECORDED",
                actor="local-test",
                event_payload={},
                secondary_digests={"register_sha256": "invalid"},
            )

    assert list((workspace.root / "governance" / "transactions").glob("*.json")) == []
