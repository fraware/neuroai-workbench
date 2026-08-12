from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import neuroai_workbench.governance_transactions as tx
from neuroai_workbench.events import append_event
from neuroai_workbench.util import atomic_write_json, canonical_json_bytes, sha256_bytes
from neuroai_workbench.workspace import Workspace


def _workspace(tmp_path: Path) -> Workspace:
    return Workspace.initialize(tmp_path / "workspace")


def _prepared(
    workspace: Workspace,
    *,
    transaction_id: str = "GOVTXN-coverage",
) -> tuple[Path, dict[str, Any], Path, dict[str, Any], dict[str, Any]]:
    record = {
        "schema_version": "1",
        "record_id": "GOVREC-COVERAGE",
        "value": "immutable",
        "release_authorization_performed": False,
    }
    record_sha256 = sha256_bytes(canonical_json_bytes(record))
    secondary = {"register_sha256": "b" * 64}
    payload = {
        "purpose": "coverage",
        "transaction_id": transaction_id,
        "transaction_record_id": record["record_id"],
        "transaction_record_sha256": record_sha256,
        "transaction_secondary_digests": secondary,
    }
    journal: dict[str, Any] = {
        "schema_version": tx.TRANSACTION_SCHEMA_VERSION,
        "transaction_id": transaction_id,
        "state": tx.TRANSACTION_STATE_PREPARED,
        "prepared_at": "2026-08-12T00:00:00Z",
        "record_relative_path": "records/GOVREC-COVERAGE.json",
        "record_id": record["record_id"],
        "record_sha256": record_sha256,
        "record_bytes_sha256": sha256_bytes(tx._record_bytes(record)),
        "secondary_digests": secondary,
        "event_action": "GOVERNANCE_TEST_RECORDED",
        "event_payload_sha256": tx._event_payload_hash(payload),
        "authority_profile": tx.TRANSACTION_AUTHORITY_PROFILE,
        "boundary": tx.TRANSACTION_BOUNDARY,
    }
    journal["journal_sha256"] = tx._journal_hash(journal)
    journal_path = tx._journal_path(workspace, transaction_id)
    record_path = workspace.root / "governance" / "records" / "GOVREC-COVERAGE.json"
    atomic_write_json(journal_path, journal)
    return journal_path, journal, record_path, record, payload


def _rewrite_journal(path: Path, journal: dict[str, Any]) -> None:
    journal["journal_sha256"] = tx._journal_hash(journal)
    atomic_write_json(path, journal)


@pytest.mark.parametrize("value", [None, "x" * 63, "G" * 64])
def test_digest_validation_rejects_malformed_values(value: object) -> None:
    with pytest.raises(tx.GovernanceRecoveryBlocked, match="64-character lowercase hexadecimal digest"):
        tx._assert_digest(value, "digest")


def test_relative_record_path_rejects_governance_root_and_transaction_storage(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    governance_root = workspace.root / "governance"
    governance_root.mkdir(parents=True)
    with pytest.raises(ValueError, match="escapes"):
        tx._relative_record_path(workspace, governance_root)
    with pytest.raises(ValueError, match="transaction-control storage"):
        tx._relative_record_path(workspace, governance_root / "transactions" / "record.json")
    with pytest.raises(ValueError, match="transaction-control storage"):
        tx._relative_record_path(workspace, governance_root / ".append.lock")


@pytest.mark.parametrize(
    "relative, message",
    [
        ("../record.json", "invalid record path"),
        ("/tmp/record.json", "invalid record path"),
        ("transactions/record.json", "transaction-control storage"),
        (".append.lock", "transaction-control storage"),
    ],
)
def test_resolve_record_path_rejects_unsafe_targets(tmp_path: Path, relative: str, message: str) -> None:
    workspace = _workspace(tmp_path)
    with pytest.raises(tx.GovernanceRecoveryBlocked, match=message):
        tx._resolve_record_path(workspace, relative)


def test_journal_must_be_object(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    path = tx._transaction_root(workspace) / "GOVTXN-list.json"
    path.write_text("[]\n", encoding="utf-8")
    with pytest.raises(tx.GovernanceRecoveryBlocked, match="must be an object"):
        tx._load_and_validate_journal(path)


@pytest.mark.parametrize(
    "field, value, message",
    [
        ("schema_version", "999", "unsupported schema version"),
        ("transaction_id", "GOVTXN-other", "conflicting identity"),
        ("state", "COMMITTED", "unsupported state"),
        ("authority_profile", "AUTHORIZING", "invalid authority boundary"),
        ("boundary", "forged", "invalid authority boundary"),
    ],
)
def test_journal_control_fields_fail_closed(tmp_path: Path, field: str, value: str, message: str) -> None:
    workspace = _workspace(tmp_path)
    path, journal, _record_path, _record, _payload = _prepared(workspace)
    journal[field] = value
    _rewrite_journal(path, journal)
    with pytest.raises(tx.GovernanceRecoveryBlocked, match=message):
        tx._load_and_validate_journal(path)


def test_journal_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    path, journal, _record_path, _record, _payload = _prepared(workspace)
    journal["record_id"] = "GOVREC-TAMPERED"
    atomic_write_json(path, journal)
    with pytest.raises(tx.GovernanceRecoveryBlocked, match="hash mismatch"):
        tx._load_and_validate_journal(path)


@pytest.mark.parametrize("field", ["record_sha256", "record_bytes_sha256", "event_payload_sha256"])
def test_journal_digest_fields_are_validated(tmp_path: Path, field: str) -> None:
    workspace = _workspace(tmp_path)
    path, journal, _record_path, _record, _payload = _prepared(workspace)
    journal[field] = "bad"
    _rewrite_journal(path, journal)
    with pytest.raises(tx.GovernanceRecoveryBlocked, match=field):
        tx._load_and_validate_journal(path)


def test_journal_secondary_digest_map_is_validated(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    path, journal, _record_path, _record, _payload = _prepared(workspace)
    journal["secondary_digests"] = []
    _rewrite_journal(path, journal)
    with pytest.raises(tx.GovernanceRecoveryBlocked, match="secondary_digests must be an object"):
        tx._load_and_validate_journal(path)

    path, journal, _record_path, _record, _payload = _prepared(workspace, transaction_id="GOVTXN-empty-key")
    journal["secondary_digests"] = {"": "b" * 64}
    _rewrite_journal(path, journal)
    with pytest.raises(tx.GovernanceRecoveryBlocked, match="invalid secondary digest key"):
        tx._load_and_validate_journal(path)

    path, journal, _record_path, _record, _payload = _prepared(workspace, transaction_id="GOVTXN-bad-secondary")
    journal["secondary_digests"] = {"register_sha256": "bad"}
    _rewrite_journal(path, journal)
    with pytest.raises(tx.GovernanceRecoveryBlocked, match="secondary_digests.register_sha256"):
        tx._load_and_validate_journal(path)


def test_invalid_event_chain_blocks_snapshot_and_recovery(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _prepared(workspace)
    append_event(workspace.root / "events.jsonl", "UNRELATED", "local-test", {})
    with (workspace.root / "events.jsonl").open("ab") as handle:
        handle.write(b"corrupt\n")

    with pytest.raises(tx.GovernanceRecoveryBlocked, match="Event chain is not fully valid"):
        tx.recover_governance_transactions(workspace)

    report = tx.diagnose_governance_transactions(workspace)
    assert report["valid"] is False
    assert report["recovery_blocked"] is True
    assert report["release_authorization_performed"] is False


def test_commit_event_requires_object_payload(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _path, journal, _record_path, _record, _payload = _prepared(workspace)
    with pytest.raises(tx.GovernanceRecoveryBlocked, match="no object payload"):
        tx._verify_commit_event(journal, {"action": journal["event_action"], "payload": []})


@pytest.mark.parametrize(
    "case, message",
    [
        ("action", "action mismatch"),
        ("transaction_id", "transaction event identity mismatch"),
        ("record_id", "record identity mismatch"),
        ("record_sha256", "record digest mismatch"),
        ("secondary", "secondary digest mismatch"),
        ("payload_hash", "event payload digest mismatch"),
    ],
)
def test_commit_event_binding_fails_closed(tmp_path: Path, case: str, message: str) -> None:
    workspace = _workspace(tmp_path)
    _path, journal, _record_path, _record, payload = _prepared(workspace)
    event: dict[str, Any] = {"action": journal["event_action"], "payload": dict(payload)}
    event_payload = event["payload"]
    assert isinstance(event_payload, dict)
    if case == "action":
        event["action"] = "WRONG"
    elif case == "transaction_id":
        event_payload["transaction_id"] = "GOVTXN-wrong"
    elif case == "record_id":
        event_payload["transaction_record_id"] = "GOVREC-WRONG"
    elif case == "record_sha256":
        event_payload["transaction_record_sha256"] = "c" * 64
    elif case == "secondary":
        event_payload["transaction_secondary_digests"] = {"register_sha256": "c" * 64}
    else:
        event_payload["purpose"] = "tampered"

    with pytest.raises(tx.GovernanceRecoveryBlocked, match=message):
        tx._verify_commit_event(journal, event)


def test_duplicate_commit_witnesses_fail_closed(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _path, journal, record_path, record, payload = _prepared(workspace)
    atomic_write_json(record_path, record)
    append_event(workspace.root / "events.jsonl", str(journal["event_action"]), "local-test", payload)
    append_event(workspace.root / "events.jsonl", str(journal["event_action"]), "local-test", payload)

    with pytest.raises(tx.GovernanceRecoveryBlocked, match="multiple commit-witness events"):
        tx.recover_governance_transactions(workspace)


def test_diagnostic_reports_prepared_and_committed_pending_cleanup(tmp_path: Path) -> None:
    prepared_workspace = _workspace(tmp_path / "prepared")
    _prepared(prepared_workspace)
    prepared = tx.diagnose_governance_transactions(prepared_workspace)
    assert prepared["valid"] is True
    assert prepared["records"][0]["state"] == "PREPARED"
    assert prepared["records"][0]["commit_witness_count"] == 0

    committed_workspace = _workspace(tmp_path / "committed")
    _path, journal, record_path, record, payload = _prepared(committed_workspace)
    atomic_write_json(record_path, record)
    append_event(
        committed_workspace.root / "events.jsonl",
        str(journal["event_action"]),
        "local-test",
        payload,
    )
    committed = tx.diagnose_governance_transactions(committed_workspace)
    assert committed["valid"] is True
    assert committed["records"][0]["state"] == "COMMITTED_PENDING_CLEANUP"
    assert committed["records"][0]["record_present"] is True


def test_diagnostic_preserves_corrupt_journal_as_error(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    root = tx._transaction_root(workspace)
    (root / "GOVTXN-corrupt.json").write_text("{bad-json", encoding="utf-8")
    report = tx.diagnose_governance_transactions(workspace)
    assert report["valid"] is False
    assert report["recovery_blocked"] is True
    assert "Corrupt governance transaction journal" in report["errors"][0]


def test_append_rejects_existing_record_and_invalid_writer_digest(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    record = {"record_id": "GOVREC-EXISTING"}
    record_path = workspace.root / "governance" / "records" / "existing.json"
    atomic_write_json(record_path, record)
    digest = sha256_bytes(canonical_json_bytes(record))

    with tx.governance_write_lock(workspace):
        with pytest.raises(ValueError, match="already exists"):
            tx.append_governance_record_locked(
                workspace,
                record_path=record_path,
                record=record,
                record_id="GOVREC-EXISTING",
                record_sha256=digest,
                event_action="GOVERNANCE_TEST_RECORDED",
                actor="local-test",
                event_payload={},
            )

    new_path = workspace.root / "governance" / "records" / "new.json"
    with tx.governance_write_lock(workspace):
        with pytest.raises(tx.GovernanceRecoveryBlocked, match="record_sha256"):
            tx.append_governance_record_locked(
                workspace,
                record_path=new_path,
                record=record,
                record_id="GOVREC-NEW",
                record_sha256="bad",
                event_action="GOVERNANCE_TEST_RECORDED",
                actor="local-test",
                event_payload={},
            )


def test_recovery_rolls_back_journal_without_record(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    journal_path, _journal, record_path, _record, _payload = _prepared(workspace)
    result = tx.recover_governance_transactions(workspace)
    assert result["rolled_back"] == 1
    assert result["committed_recovered"] == 0
    assert not journal_path.exists()
    assert not record_path.exists()


def test_recovery_keeps_exact_committed_record_and_removes_journal(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    journal_path, journal, record_path, record, payload = _prepared(workspace)
    atomic_write_json(record_path, record)
    append_event(workspace.root / "events.jsonl", str(journal["event_action"]), "local-test", payload)
    original = record_path.read_bytes()

    result = tx.recover_governance_transactions(workspace)

    assert result["committed_recovered"] == 1
    assert result["rolled_back"] == 0
    assert not journal_path.exists()
    assert record_path.read_bytes() == original
