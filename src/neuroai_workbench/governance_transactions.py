from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from functools import wraps
from pathlib import Path, PurePosixPath
from typing import Any, ParamSpec, TypeVar, cast
from uuid import uuid4

from .events import _exclusive_lock, append_event, load_events, verify_chain
from .util import (
    atomic_write_json,
    canonical_json_bytes,
    fsync_directory,
    load_json,
    safe_join,
    sha256_bytes,
    sha256_file,
    utc_now,
)
from .workspace import Workspace

P = ParamSpec("P")
R = TypeVar("R")

TRANSACTION_SCHEMA_VERSION = "1"
TRANSACTION_PREFIX = "GOVTXN-"
TRANSACTION_STATE_PREPARED = "PREPARED"
TRANSACTION_AUTHORITY_PROFILE = "PERSISTENCE_INTEGRITY_ONLY"
TRANSACTION_BOUNDARY = (
    "Governance append transactions establish crash-consistent local persistence only. "
    "They do not authenticate governance actors, establish substantive review sufficiency, "
    "authorize a successor release, or confer publication authority."
)


class GovernanceRecoveryBlocked(RuntimeError):
    """Raised when recovery cannot determine a safe commit or rollback outcome."""


def _governance_root(workspace: Workspace) -> Path:
    root = workspace.root / "governance"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _transaction_root(workspace: Workspace) -> Path:
    root = _governance_root(workspace) / "transactions"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _transaction_lock_path(workspace: Workspace) -> Path:
    return _governance_root(workspace) / ".append.lock"


def _events_path(workspace: Workspace) -> Path:
    return workspace.root / "events.jsonl"


def _events_lock_path(workspace: Workspace) -> Path:
    path = _events_path(workspace)
    return path.with_suffix(path.suffix + ".lock")


def _journal_hash(journal: dict[str, Any]) -> str:
    controlled = {key: value for key, value in journal.items() if key != "journal_sha256"}
    return sha256_bytes(canonical_json_bytes(controlled))


def _record_bytes(record: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(record), ensure_ascii=False, indent=2).encode("utf-8") + b"\n"


def _assert_digest(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise GovernanceRecoveryBlocked(f"{field} must be a 64-character lowercase hexadecimal digest")
    return value


def _relative_record_path(workspace: Workspace, record_path: Path) -> str:
    governance_root = _governance_root(workspace).resolve()
    resolved = record_path.resolve()
    if resolved == governance_root or governance_root not in resolved.parents:
        raise ValueError("Governance record path escapes the workspace governance root")
    relative = resolved.relative_to(governance_root).as_posix()
    pure = PurePosixPath(relative)
    if pure.is_absolute() or pure.as_posix() != relative or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError("Governance record path must be a normalized relative path below the governance root")
    if pure.parts[0] == "transactions" or pure.name == ".append.lock":
        raise ValueError("Governance records cannot be written into transaction-control storage")
    return relative


def _resolve_record_path(workspace: Workspace, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or pure.as_posix() != relative or any(part in {"", ".", ".."} for part in pure.parts):
        raise GovernanceRecoveryBlocked("Prepared transaction contains an invalid record path")
    if not pure.parts or pure.parts[0] == "transactions" or pure.name == ".append.lock":
        raise GovernanceRecoveryBlocked("Prepared transaction targets transaction-control storage")
    return safe_join(_governance_root(workspace), *pure.parts)


def _journal_path(workspace: Workspace, transaction_id: str) -> Path:
    return _transaction_root(workspace) / f"{transaction_id}.json"


def _event_payload_hash(payload: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(dict(payload)))


def _load_and_validate_journal(path: Path) -> dict[str, Any]:
    try:
        value = load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        raise GovernanceRecoveryBlocked(f"Corrupt governance transaction journal {path.name}") from exc
    if not isinstance(value, dict):
        raise GovernanceRecoveryBlocked(f"Governance transaction journal {path.name} must be an object")
    journal = cast(dict[str, Any], value)
    if journal.get("schema_version") != TRANSACTION_SCHEMA_VERSION:
        raise GovernanceRecoveryBlocked(f"Governance transaction journal {path.name} has unsupported schema version")
    transaction_id = str(journal.get("transaction_id", ""))
    if not transaction_id.startswith(TRANSACTION_PREFIX) or path.name != f"{transaction_id}.json":
        raise GovernanceRecoveryBlocked(f"Governance transaction journal {path.name} has conflicting identity")
    if journal.get("state") != TRANSACTION_STATE_PREPARED:
        raise GovernanceRecoveryBlocked(f"Governance transaction journal {path.name} has unsupported state")
    if journal.get("authority_profile") != TRANSACTION_AUTHORITY_PROFILE or journal.get("boundary") != TRANSACTION_BOUNDARY:
        raise GovernanceRecoveryBlocked(f"Governance transaction journal {path.name} has invalid authority boundary")
    if journal.get("journal_sha256") != _journal_hash(journal):
        raise GovernanceRecoveryBlocked(f"Governance transaction journal {path.name} hash mismatch")
    _assert_digest(journal.get("record_sha256"), "record_sha256")
    _assert_digest(journal.get("record_bytes_sha256"), "record_bytes_sha256")
    _assert_digest(journal.get("event_payload_sha256"), "event_payload_sha256")
    secondary = journal.get("secondary_digests")
    if not isinstance(secondary, dict):
        raise GovernanceRecoveryBlocked(f"Governance transaction journal {path.name} secondary_digests must be an object")
    for key, digest in secondary.items():
        if not isinstance(key, str) or not key:
            raise GovernanceRecoveryBlocked(f"Governance transaction journal {path.name} has invalid secondary digest key")
        _assert_digest(digest, f"secondary_digests.{key}")
    return journal


def _event_snapshot(workspace: Workspace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    events_path = _events_path(workspace)
    with _exclusive_lock(_events_lock_path(workspace)):
        report = verify_chain(events_path)
        if not report.get("valid") or report.get("trailer_valid") is not True:
            raise GovernanceRecoveryBlocked(
                "Event chain is not fully valid; governance transaction recovery is blocked"
            )
        return load_events(events_path), report


def _matching_transaction_events(events: list[dict[str, Any]], transaction_id: str) -> list[dict[str, Any]]:
    return [
        event
        for event in events
        if isinstance(event.get("payload"), dict) and event["payload"].get("transaction_id") == transaction_id
    ]


def _verify_commit_event(journal: dict[str, Any], event: dict[str, Any]) -> None:
    payload = event.get("payload")
    if not isinstance(payload, dict):
        raise GovernanceRecoveryBlocked("Committed governance transaction event has no object payload")
    if event.get("action") != journal.get("event_action"):
        raise GovernanceRecoveryBlocked("Committed governance transaction event action mismatch")
    if payload.get("transaction_id") != journal.get("transaction_id"):
        raise GovernanceRecoveryBlocked("Committed governance transaction event identity mismatch")
    if payload.get("transaction_record_id") != journal.get("record_id"):
        raise GovernanceRecoveryBlocked("Committed governance transaction record identity mismatch")
    if payload.get("transaction_record_sha256") != journal.get("record_sha256"):
        raise GovernanceRecoveryBlocked("Committed governance transaction record digest mismatch")
    if payload.get("transaction_secondary_digests") != journal.get("secondary_digests"):
        raise GovernanceRecoveryBlocked("Committed governance transaction secondary digest mismatch")
    if _event_payload_hash(payload) != journal.get("event_payload_sha256"):
        raise GovernanceRecoveryBlocked("Committed governance transaction event payload digest mismatch")


def _verify_record_bytes(journal: dict[str, Any], record_path: Path) -> None:
    if not record_path.is_file():
        raise GovernanceRecoveryBlocked("Committed governance transaction record is missing")
    if sha256_file(record_path) != journal.get("record_bytes_sha256"):
        raise GovernanceRecoveryBlocked("Governance transaction record bytes diverge from the prepared journal")


def _remove_file(path: Path) -> None:
    path.unlink(missing_ok=False)
    fsync_directory(path.parent)


def _remove_journal(path: Path) -> None:
    _remove_file(path)


def _recover_prepared_transactions_unlocked(workspace: Workspace) -> dict[str, Any]:
    journals = sorted(_transaction_root(workspace).glob("*.json"))
    if not journals:
        return {
            "valid": True,
            "prepared": 0,
            "committed_recovered": 0,
            "rolled_back": 0,
            "recovery_blocked": False,
            "release_authorization_performed": False,
            "boundary": TRANSACTION_BOUNDARY,
        }

    events, _ = _event_snapshot(workspace)
    committed = 0
    rolled_back = 0
    for journal_path in journals:
        journal = _load_and_validate_journal(journal_path)
        record_path = _resolve_record_path(workspace, str(journal.get("record_relative_path", "")))
        matches = _matching_transaction_events(events, str(journal["transaction_id"]))
        if len(matches) > 1:
            raise GovernanceRecoveryBlocked(
                f"Transaction {journal['transaction_id']} has multiple commit-witness events"
            )
        if matches:
            _verify_commit_event(journal, matches[0])
            _verify_record_bytes(journal, record_path)
            _remove_journal(journal_path)
            committed += 1
            continue

        if record_path.exists():
            _verify_record_bytes(journal, record_path)
            _remove_file(record_path)
        _remove_journal(journal_path)
        rolled_back += 1

    return {
        "valid": True,
        "prepared": len(journals),
        "committed_recovered": committed,
        "rolled_back": rolled_back,
        "recovery_blocked": False,
        "release_authorization_performed": False,
        "boundary": TRANSACTION_BOUNDARY,
    }


@contextmanager
def governance_write_lock(workspace: Workspace) -> Iterator[dict[str, Any]]:
    """Serialize governance validation/write operations and recover interrupted transactions first."""
    with _exclusive_lock(_transaction_lock_path(workspace)) as owner:
        recovery = _recover_prepared_transactions_unlocked(workspace)
        yield {"lock_id": owner["lock_id"], "recovery": recovery}


def governance_serialized(function: Callable[P, R]) -> Callable[P, R]:
    """Serialize a governance recorder whose first positional argument is a Workspace."""

    @wraps(function)
    def wrapped(workspace: Workspace, *args: P.args, **kwargs: P.kwargs) -> R:
        with governance_write_lock(workspace):
            return function(workspace, *args, **kwargs)

    return cast(Callable[P, R], wrapped)


def append_governance_record_locked(
    workspace: Workspace,
    *,
    record_path: Path,
    record: Mapping[str, Any],
    record_id: str,
    record_sha256: str,
    event_action: str,
    actor: str,
    event_payload: Mapping[str, Any],
    secondary_digests: Mapping[str, str] | None = None,
    phase_hook: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Commit one immutable governance record while the governance write lock is held."""
    if record_path.exists():
        raise ValueError(f"Governance record already exists: {record_path.name}")
    relative = _relative_record_path(workspace, record_path)
    record_sha256 = _assert_digest(record_sha256, "record_sha256")
    normalized_secondary = {
        str(key): _assert_digest(value, f"secondary_digests.{key}")
        for key, value in sorted((secondary_digests or {}).items())
    }
    transaction_id = f"{TRANSACTION_PREFIX}{uuid4().hex}"
    payload = dict(event_payload)
    reserved = {
        "transaction_id",
        "transaction_record_id",
        "transaction_record_sha256",
        "transaction_secondary_digests",
    }
    overlap = sorted(reserved & payload.keys())
    if overlap:
        raise ValueError(f"Governance event payload uses reserved transaction keys: {', '.join(overlap)}")
    payload.update(
        {
            "transaction_id": transaction_id,
            "transaction_record_id": record_id,
            "transaction_record_sha256": record_sha256,
            "transaction_secondary_digests": normalized_secondary,
        }
    )
    bytes_sha256 = sha256_bytes(_record_bytes(record))
    journal: dict[str, Any] = {
        "schema_version": TRANSACTION_SCHEMA_VERSION,
        "transaction_id": transaction_id,
        "state": TRANSACTION_STATE_PREPARED,
        "prepared_at": utc_now(),
        "record_relative_path": relative,
        "record_id": record_id,
        "record_sha256": record_sha256,
        "record_bytes_sha256": bytes_sha256,
        "secondary_digests": normalized_secondary,
        "event_action": event_action,
        "event_payload_sha256": _event_payload_hash(payload),
        "authority_profile": TRANSACTION_AUTHORITY_PROFILE,
        "boundary": TRANSACTION_BOUNDARY,
    }
    journal["journal_sha256"] = _journal_hash(journal)
    journal_path = _journal_path(workspace, transaction_id)

    def checkpoint(phase: str) -> None:
        if phase_hook is not None:
            phase_hook(phase)

    checkpoint("BEFORE_JOURNAL_WRITE")
    atomic_write_json(journal_path, journal)
    checkpoint("AFTER_JOURNAL_WRITE")
    try:
        atomic_write_json(record_path, dict(record))
        checkpoint("AFTER_RECORD_WRITE")
        if sha256_file(record_path) != bytes_sha256:
            raise RuntimeError("Governance record bytes do not match prepared transaction")
        checkpoint("BEFORE_EVENT_APPEND")
        event = append_event(_events_path(workspace), event_action, actor, payload)
        checkpoint("AFTER_EVENT_APPEND")
        _verify_commit_event(journal, event)
        _remove_journal(journal_path)
        checkpoint("AFTER_JOURNAL_CLEANUP")
        return {
            "transaction_id": transaction_id,
            "event": event,
            "record_path": str(record_path),
            "record_sha256": record_sha256,
            "secondary_digests": normalized_secondary,
        }
    except BaseException:
        if journal_path.exists():
            _recover_prepared_transactions_unlocked(workspace)
        raise


def recover_governance_transactions(workspace: Workspace) -> dict[str, Any]:
    """Recover interrupted governance appends under the governance lock."""
    with _exclusive_lock(_transaction_lock_path(workspace)):
        return _recover_prepared_transactions_unlocked(workspace)


def diagnose_governance_transactions(workspace: Workspace) -> dict[str, Any]:
    """Inspect prepared transaction residue without modifying governance state."""
    journals = sorted(_transaction_root(workspace).glob("*.json"))
    errors: list[str] = []
    records: list[dict[str, Any]] = []
    try:
        events, report = _event_snapshot(workspace)
    except GovernanceRecoveryBlocked as exc:
        return {
            "valid": False,
            "prepared": len(journals),
            "records": [],
            "errors": [str(exc)],
            "recovery_blocked": True,
            "release_authorization_performed": False,
            "boundary": TRANSACTION_BOUNDARY,
        }
    for path in journals:
        try:
            journal = _load_and_validate_journal(path)
            record_path = _resolve_record_path(workspace, str(journal.get("record_relative_path", "")))
            matches = _matching_transaction_events(events, str(journal["transaction_id"]))
            records.append(
                {
                    "transaction_id": journal["transaction_id"],
                    "record_id": journal["record_id"],
                    "record_present": record_path.is_file(),
                    "commit_witness_count": len(matches),
                    "state": "COMMITTED_PENDING_CLEANUP" if len(matches) == 1 else "PREPARED",
                }
            )
        except GovernanceRecoveryBlocked as exc:
            errors.append(str(exc))
    return {
        "valid": not errors and report.get("valid") is True and report.get("trailer_valid") is True,
        "prepared": len(journals),
        "records": records,
        "errors": errors,
        "recovery_blocked": bool(errors),
        "release_authorization_performed": False,
        "boundary": TRANSACTION_BOUNDARY,
    }
