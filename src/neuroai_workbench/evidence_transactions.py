from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from .events import LOCK_PROFILE_LOCAL, _exclusive_lock, append_event, load_events
from .util import atomic_write_bytes, atomic_write_json, load_json, sha256_bytes, sha256_file, utc_now

JOURNAL_VERSION = 1
TERMINAL_STATES = frozenset({"COMMITTED", "ROLLED_BACK"})


class EvidenceTransactionRecoveryError(RuntimeError):
    """Raised when recovery would overwrite state outside the recorded transaction."""


def _registration_fault(point: str) -> None:
    """Fault-injection hook used by adversarial tests."""


def _transactions_root(case_path: Path) -> Path:
    return case_path / "evidence" / "transactions"


def _registration_lock_path(case_path: Path) -> Path:
    return case_path / "evidence" / "registration.lock"


def _journal_path(transaction_path: Path) -> Path:
    return transaction_path / "journal.json"


def _path_hash(path: Path) -> str | None:
    return sha256_file(path) if path.is_file() else None


def _event_exists(events_path: Path, action: str, transaction_id: str) -> bool:
    for event in load_events(events_path):
        if event.get("action") == action and event.get("payload", {}).get("transaction_id") == transaction_id:
            return True
    return False


def _write_journal(transaction_path: Path, journal: dict[str, Any], state: str, **updates: Any) -> dict[str, Any]:
    value = dict(journal)
    value.update(updates)
    value["state"] = state
    value["updated_at"] = utc_now()
    atomic_write_json(_journal_path(transaction_path), value)
    return value


def _load_journal(transaction_path: Path) -> dict[str, Any]:
    path = _journal_path(transaction_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    value = load_json(path)
    if not isinstance(value, dict) or value.get("version") != JOURNAL_VERSION:
        raise ValueError(f"Invalid evidence transaction journal: {path}")
    if value.get("transaction_id") != transaction_path.name:
        raise ValueError(f"Evidence transaction directory identity mismatch: {path}")
    return value


def _snapshot_path(transaction_path: Path, name: str) -> Path:
    return transaction_path / name


def _restore_snapshot(snapshot: Path, target: Path, *, existed: bool) -> None:
    if existed:
        if not snapshot.is_file():
            raise EvidenceTransactionRecoveryError(f"Missing rollback snapshot: {snapshot}")
        atomic_write_bytes(target, snapshot.read_bytes())
    else:
        target.unlink(missing_ok=True)


def _compact_transaction(transaction_path: Path) -> None:
    for name in (
        "staged-object.bin",
        "before-index.json",
        "before-assessment.json",
        "before-persistence.json",
        "desired-index.json",
        "desired-assessment.json",
        "desired-persistence.json",
    ):
        _snapshot_path(transaction_path, name).unlink(missing_ok=True)


@contextmanager
def evidence_registration_lock(case_path: Path) -> Iterator[dict[str, Any]]:
    with _exclusive_lock(_registration_lock_path(case_path), profile=LOCK_PROFILE_LOCAL) as owner:
        yield owner


def prepare_evidence_transaction(
    case_path: Path,
    *,
    data: bytes,
    record: dict[str, Any],
    desired_index: dict[str, Any],
    desired_assessment: dict[str, Any] | None,
    desired_persistence: dict[str, Any] | None,
) -> Path:
    transaction_id = f"EVTX-{uuid4().hex}"
    transaction_path = _transactions_root(case_path) / transaction_id
    transaction_path.mkdir(parents=True, exist_ok=False)

    index_path = case_path / "evidence" / "index.json"
    assessment_path = case_path / "assessment.json"
    persistence_path = case_path / "persistence.json"
    object_path = case_path / "evidence" / "objects" / str(record["stored_filename"])

    before_index = index_path.read_bytes()
    before_assessment = assessment_path.read_bytes()
    before_persistence = persistence_path.read_bytes() if persistence_path.is_file() else None

    atomic_write_bytes(_snapshot_path(transaction_path, "staged-object.bin"), data)
    atomic_write_bytes(_snapshot_path(transaction_path, "before-index.json"), before_index)
    atomic_write_bytes(_snapshot_path(transaction_path, "before-assessment.json"), before_assessment)
    if before_persistence is not None:
        atomic_write_bytes(_snapshot_path(transaction_path, "before-persistence.json"), before_persistence)
    atomic_write_json(_snapshot_path(transaction_path, "desired-index.json"), desired_index)
    if desired_assessment is not None:
        atomic_write_json(_snapshot_path(transaction_path, "desired-assessment.json"), desired_assessment)
    if desired_persistence is not None:
        atomic_write_json(_snapshot_path(transaction_path, "desired-persistence.json"), desired_persistence)

    journal = {
        "version": JOURNAL_VERSION,
        "transaction_id": transaction_id,
        "state": "PREPARED",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "record": record,
        "link_to_assessment": desired_assessment is not None,
        "object_preexisting": object_path.is_file(),
        "before": {
            "index_sha256": sha256_bytes(before_index),
            "assessment_sha256": sha256_bytes(before_assessment),
            "persistence_existed": before_persistence is not None,
            "persistence_sha256": sha256_bytes(before_persistence) if before_persistence is not None else None,
        },
        "desired": {
            "object_sha256": str(record["sha256"]),
            "index_sha256": sha256_file(_snapshot_path(transaction_path, "desired-index.json")),
            "assessment_sha256": (
                sha256_file(_snapshot_path(transaction_path, "desired-assessment.json"))
                if desired_assessment is not None
                else None
            ),
            "persistence_sha256": (
                sha256_file(_snapshot_path(transaction_path, "desired-persistence.json"))
                if desired_persistence is not None
                else None
            ),
        },
        "boundary": (
            "The journal coordinates local filesystem state only. Digest equality establishes byte identity, "
            "not evidence authenticity, quality, relevance, completeness, custody, or disclosure authority."
        ),
    }
    atomic_write_json(_journal_path(transaction_path), journal)
    _registration_fault("after_prepare")
    return transaction_path


def _assert_predecessor(path: Path, expected: str | None, label: str) -> None:
    if _path_hash(path) != expected:
        raise EvidenceTransactionRecoveryError(f"{label} changed after transaction preparation")


def _append_commit_event(case_path: Path, journal: dict[str, Any], actor: str) -> None:
    transaction_id = str(journal["transaction_id"])
    events_path = case_path / "events.jsonl"
    if _event_exists(events_path, "EVIDENCE_ADDED", transaction_id):
        return
    payload = dict(journal["record"])
    payload.update(
        {
            "transaction_id": transaction_id,
            "registration_state": "COMMITTED",
            "journal_version": JOURNAL_VERSION,
        }
    )
    append_event(events_path, "EVIDENCE_ADDED", actor, payload)


def apply_evidence_transaction(case_path: Path, transaction_path: Path, *, actor: str) -> dict[str, Any]:
    journal = _load_journal(transaction_path)
    if journal["state"] in TERMINAL_STATES:
        return journal

    record = journal["record"]
    object_path = case_path / "evidence" / "objects" / str(record["stored_filename"])
    staged = _snapshot_path(transaction_path, "staged-object.bin")
    if object_path.is_file():
        if sha256_file(object_path) != journal["desired"]["object_sha256"]:
            raise EvidenceTransactionRecoveryError("Existing content-addressed evidence object has a digest mismatch")
    else:
        atomic_write_bytes(object_path, staged.read_bytes())
    journal = _write_journal(transaction_path, journal, "OBJECT_WRITTEN")
    _registration_fault("after_object")

    index_path = case_path / "evidence" / "index.json"
    _assert_predecessor(index_path, journal["before"]["index_sha256"], "Evidence index")
    atomic_write_bytes(index_path, _snapshot_path(transaction_path, "desired-index.json").read_bytes())
    journal = _write_journal(transaction_path, journal, "INDEX_WRITTEN")
    _registration_fault("after_index")

    if journal["link_to_assessment"]:
        assessment_path = case_path / "assessment.json"
        persistence_path = case_path / "persistence.json"
        _assert_predecessor(assessment_path, journal["before"]["assessment_sha256"], "Assessment")
        _assert_predecessor(persistence_path, journal["before"]["persistence_sha256"], "Persistence record")
        atomic_write_bytes(
            assessment_path,
            _snapshot_path(transaction_path, "desired-assessment.json").read_bytes(),
        )
        atomic_write_bytes(
            persistence_path,
            _snapshot_path(transaction_path, "desired-persistence.json").read_bytes(),
        )
    journal = _write_journal(transaction_path, journal, "CASE_WRITTEN")
    _registration_fault("after_case")

    _append_commit_event(case_path, journal, actor)
    journal = _write_journal(transaction_path, journal, "EVENT_WRITTEN")
    _registration_fault("after_event")
    journal = _write_journal(transaction_path, journal, "COMMITTED", recovered=False)
    _compact_transaction(transaction_path)
    return journal


def _current_matches_expected(path: Path, before: str | None, desired: str | None) -> bool:
    return _path_hash(path) in {before, desired}


def _transaction_is_fully_applied(case_path: Path, journal: dict[str, Any]) -> bool:
    record = journal["record"]
    object_path = case_path / "evidence" / "objects" / str(record["stored_filename"])
    index_path = case_path / "evidence" / "index.json"
    if _path_hash(object_path) != journal["desired"]["object_sha256"]:
        return False
    if _path_hash(index_path) != journal["desired"]["index_sha256"]:
        return False
    if not journal["link_to_assessment"]:
        return True
    return (
        _path_hash(case_path / "assessment.json") == journal["desired"]["assessment_sha256"]
        and _path_hash(case_path / "persistence.json") == journal["desired"]["persistence_sha256"]
    )


def _assert_recovery_safe(case_path: Path, journal: dict[str, Any]) -> None:
    before = journal["before"]
    desired = journal["desired"]
    checks = [
        (
            case_path / "evidence" / "index.json",
            before["index_sha256"],
            desired["index_sha256"],
            "Evidence index",
        ),
        (
            case_path / "assessment.json",
            before["assessment_sha256"],
            desired["assessment_sha256"] if journal["link_to_assessment"] else before["assessment_sha256"],
            "Assessment",
        ),
        (
            case_path / "persistence.json",
            before["persistence_sha256"],
            desired["persistence_sha256"] if journal["link_to_assessment"] else before["persistence_sha256"],
            "Persistence record",
        ),
    ]
    for path, predecessor, successor, label in checks:
        if not _current_matches_expected(path, predecessor, successor):
            raise EvidenceTransactionRecoveryError(f"{label} diverged outside the recorded transaction")
    object_path = case_path / "evidence" / "objects" / str(journal["record"]["stored_filename"])
    object_hash = _path_hash(object_path)
    if object_hash not in {None, journal["desired"]["object_sha256"]}:
        raise EvidenceTransactionRecoveryError("Evidence object diverged outside the recorded transaction")


def _append_rollback_event(case_path: Path, journal: dict[str, Any], actor: str, reason: str) -> None:
    transaction_id = str(journal["transaction_id"])
    events_path = case_path / "events.jsonl"
    if _event_exists(events_path, "EVIDENCE_REGISTRATION_ROLLED_BACK", transaction_id):
        return
    append_event(
        events_path,
        "EVIDENCE_REGISTRATION_ROLLED_BACK",
        actor,
        {
            "transaction_id": transaction_id,
            "evidence_id": journal["record"]["evidence_id"],
            "stored_filename": journal["record"]["stored_filename"],
            "reason": reason,
            "before": journal["before"],
            "desired": journal["desired"],
            "historical_finding_mutation_performed": False,
        },
    )


def rollback_evidence_transaction(
    case_path: Path,
    transaction_path: Path,
    *,
    actor: str,
    reason: str,
) -> dict[str, Any]:
    journal = _load_journal(transaction_path)
    _assert_recovery_safe(case_path, journal)

    _restore_snapshot(
        _snapshot_path(transaction_path, "before-index.json"),
        case_path / "evidence" / "index.json",
        existed=True,
    )
    _restore_snapshot(
        _snapshot_path(transaction_path, "before-assessment.json"),
        case_path / "assessment.json",
        existed=True,
    )
    _restore_snapshot(
        _snapshot_path(transaction_path, "before-persistence.json"),
        case_path / "persistence.json",
        existed=bool(journal["before"]["persistence_existed"]),
    )

    object_path = case_path / "evidence" / "objects" / str(journal["record"]["stored_filename"])
    restored_index = load_json(case_path / "evidence" / "index.json")
    references = {
        str(item.get("stored_filename"))
        for item in restored_index.get("objects", [])
        if isinstance(item, dict)
    }
    if not journal["object_preexisting"] and object_path.name not in references:
        object_path.unlink(missing_ok=True)

    _append_rollback_event(case_path, journal, actor, reason)
    journal = _write_journal(
        transaction_path,
        journal,
        "ROLLED_BACK",
        recovered=True,
        recovery_reason=reason,
        historical_finding_mutation_performed=False,
    )
    _compact_transaction(transaction_path)
    return journal


def _clean_orphan_transaction(case_path: Path, transaction_path: Path, actor: str) -> dict[str, Any]:
    transaction_id = transaction_path.name
    shutil.rmtree(transaction_path)
    append_event(
        case_path / "events.jsonl",
        "EVIDENCE_REGISTRATION_ORPHAN_CLEANED",
        actor,
        {
            "transaction_id": transaction_id,
            "reason": "PREPARE_DID_NOT_REACH_DURABLE_JOURNAL",
            "external_state_mutation_performed": False,
        },
    )
    return {"transaction_id": transaction_id, "outcome": "ORPHAN_CLEANED"}


def recover_evidence_transactions_unlocked(case_path: Path, *, actor: str) -> list[dict[str, Any]]:
    root = _transactions_root(case_path)
    if not root.is_dir():
        return []
    outcomes: list[dict[str, Any]] = []
    for transaction_path in sorted(path for path in root.iterdir() if path.is_dir()):
        try:
            journal = _load_journal(transaction_path)
        except FileNotFoundError:
            outcomes.append(_clean_orphan_transaction(case_path, transaction_path, actor))
            continue
        if journal["state"] in TERMINAL_STATES:
            _compact_transaction(transaction_path)
            continue
        try:
            _assert_recovery_safe(case_path, journal)
            if _transaction_is_fully_applied(case_path, journal):
                _append_commit_event(case_path, journal, actor)
                journal = _write_journal(
                    transaction_path,
                    journal,
                    "COMMITTED",
                    recovered=True,
                    recovery_reason="FORWARD_COMPLETED_DURABLE_STATE",
                )
                _compact_transaction(transaction_path)
                outcomes.append(
                    {"transaction_id": journal["transaction_id"], "outcome": "FORWARD_COMPLETED"}
                )
            else:
                rolled_back = rollback_evidence_transaction(
                    case_path,
                    transaction_path,
                    actor=actor,
                    reason="INCOMPLETE_REGISTRATION_STATE",
                )
                outcomes.append(
                    {"transaction_id": rolled_back["transaction_id"], "outcome": "ROLLED_BACK"}
                )
        except EvidenceTransactionRecoveryError as exc:
            _write_journal(
                transaction_path,
                journal,
                "RECOVERY_BLOCKED",
                recovered=False,
                recovery_reason=str(exc),
            )
            raise
    return outcomes


def recover_evidence_transactions(case_path: Path, *, actor: str = "evidence-recovery") -> list[dict[str, Any]]:
    with evidence_registration_lock(case_path):
        return recover_evidence_transactions_unlocked(case_path, actor=actor)
