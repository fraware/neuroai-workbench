from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from . import __version__
from .case_lock import case_mutation_lock
from .errors import WorkspaceError
from .events import append_event, load_events, verify_chain
from .resource_loader import read_resource_bytes
from .util import (
    atomic_write_bytes,
    atomic_write_json,
    canonical_json_bytes,
    ensure_identifier,
    load_json,
    safe_join,
    sha256_bytes,
    sha256_file,
    utc_now,
)
from .validation import validate_assessment

WORKSPACE_FILE = "workspace.json"
CASE_FILE = "assessment.json"
ASSESSMENT_HISTORY_DIR = "history/assessments"
ASSESSMENT_SAVE_TRANSACTION_DIR = "transactions/assessment-saves"


class Workspace:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.meta_path = self.root / WORKSPACE_FILE
        self.cases_dir = self.root / "cases"

    @classmethod
    def initialize(cls, root: Path, name: str = "NeuroAI assessment workspace") -> Workspace:
        root = root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        workspace = cls(root)
        if workspace.meta_path.exists():
            raise WorkspaceError(f"Workspace already exists at {root}")
        (root / "cases").mkdir()
        (root / "exports").mkdir()
        (root / "tmp").mkdir()
        atomic_write_json(
            workspace.meta_path,
            {
                "workspace_version": "1",
                "workbench_version": __version__,
                "name": name,
                "created_at": utc_now(),
                "instrument_version": "v4.2",
                "boundary": "This workspace stores evidence and assessment records. Software state does not establish substantive conformance.",
            },
        )
        return workspace

    @classmethod
    def open(cls, root: Path) -> Workspace:
        workspace = cls(root)
        if not workspace.meta_path.is_file():
            raise WorkspaceError(f"No {WORKSPACE_FILE} found at {root}")
        meta = load_json(workspace.meta_path)
        if meta.get("workspace_version") != "1":
            raise WorkspaceError(f"Unsupported workspace version: {meta.get('workspace_version')}")
        return workspace

    @property
    def metadata(self) -> dict[str, Any]:
        return cast(dict[str, Any], load_json(self.meta_path))

    def case_path(self, case_id: str) -> Path:
        ensure_identifier(case_id, "case ID")
        return safe_join(self.cases_dir, case_id)

    def list_cases(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not self.cases_dir.exists():
            return rows
        for path in sorted(self.cases_dir.iterdir()):
            assessment_path = path / CASE_FILE
            if not path.is_dir() or not assessment_path.is_file():
                continue
            try:
                assessment = load_json(assessment_path)
                meta = assessment.get("assessment_metadata", {})
                system = assessment.get("system_profile", {})
                report = validate_assessment(assessment)
                rows.append(
                    {
                        "case_id": path.name,
                        "assessment_id": meta.get("assessment_id"),
                        "title": meta.get("title"),
                        "status": meta.get("assessment_status"),
                        "system_name": system.get("system_name"),
                        "configuration_id": system.get("configuration_id"),
                        "valid": report.valid,
                        "schema_errors": len(report.schema_issues),
                        "semantic_errors": len(report.semantic_issues),
                        "p0_blockers": report.counts.get("p0_blockers", 0),
                        "assessment_sha256": sha256_file(assessment_path),
                    }
                )
            except Exception as exc:  # preserve discoverability of a damaged case
                rows.append({"case_id": path.name, "valid": False, "error": str(exc)})
        return rows

    def create_case(self, case_id: str, title: str, actor: str = "local-user") -> dict[str, Any]:
        path = self.case_path(case_id)
        if path.exists():
            raise WorkspaceError(f"Case {case_id!r} already exists")
        (path / "evidence/objects").mkdir(parents=True)
        (path / "snapshots").mkdir()
        (path / "exports").mkdir()
        assessment = json.loads(read_resource_bytes("BLANK_UNIVERSAL_ASSESSMENT_INSTANCE_v4.2.json"))
        assessment["assessment_metadata"]["assessment_id"] = case_id
        assessment["assessment_metadata"]["title"] = title
        assessment["system_profile"]["system_id"] = f"SYSTEM-{case_id}"
        atomic_write_json(path / CASE_FILE, assessment)
        atomic_write_json(path / "evidence/index.json", {"version": "1", "objects": []})
        append_event(
            path / "events.jsonl",
            "CASE_CREATED",
            actor,
            {
                "case_id": case_id,
                "assessment_sha256": sha256_file(path / CASE_FILE),
            },
        )
        return cast(dict[str, Any], assessment)

    def import_case(self, source: Path, case_id: str | None = None, actor: str = "local-user") -> dict[str, Any]:
        assessment = cast(dict[str, Any], load_json(source))
        report = validate_assessment(assessment)
        if not report.valid:
            raise WorkspaceError(f"Assessment is invalid: {json.dumps(report.to_dict(), ensure_ascii=False)}")
        resolved_id = case_id or str(assessment["assessment_metadata"]["assessment_id"])
        path = self.case_path(resolved_id)
        if path.exists():
            raise WorkspaceError(f"Case {resolved_id!r} already exists")
        (path / "evidence/objects").mkdir(parents=True)
        (path / "snapshots").mkdir()
        (path / "exports").mkdir()
        atomic_write_json(path / CASE_FILE, assessment)
        atomic_write_json(path / "evidence/index.json", {"version": "1", "objects": []})
        append_event(
            path / "events.jsonl",
            "CASE_IMPORTED",
            actor,
            {
                "case_id": resolved_id,
                "source_name": source.name,
                "assessment_sha256": sha256_file(path / CASE_FILE),
            },
        )
        return assessment

    def load_case(self, case_id: str) -> dict[str, Any]:
        path = self.case_path(case_id) / CASE_FILE
        if not path.is_file():
            raise WorkspaceError(f"Unknown case {case_id!r}")
        return cast(dict[str, Any], load_json(path))

    def assessment_history_path(self, case_id: str, assessment_sha256: str) -> Path:
        ensure_identifier(case_id, "case ID")
        digest = assessment_sha256.strip().lower()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError(f"Invalid assessment history digest {assessment_sha256!r}")
        return self.case_path(case_id) / ASSESSMENT_HISTORY_DIR / f"{digest}.json"

    def load_assessment_history(self, case_id: str, assessment_sha256: str) -> dict[str, Any]:
        path = self.assessment_history_path(case_id, assessment_sha256)
        if not path.is_file():
            raise WorkspaceError(f"No recoverable assessment history for digest {assessment_sha256}")
        if sha256_file(path) != assessment_sha256.lower():
            raise WorkspaceError(f"Assessment history digest mismatch for {assessment_sha256}")
        return cast(dict[str, Any], load_json(path))

    @staticmethod
    def _json_bytes(value: Any) -> bytes:
        return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"

    @staticmethod
    def _transaction_hash(record: dict[str, Any]) -> str:
        return sha256_bytes(
            canonical_json_bytes({key: value for key, value in record.items() if key != "transaction_sha256"})
        )

    @classmethod
    def _write_transaction_record(cls, path: Path, record: dict[str, Any]) -> None:
        controlled = dict(record)
        controlled["transaction_sha256"] = cls._transaction_hash(controlled)
        atomic_write_json(path, controlled)

    @classmethod
    def _load_transaction_record(cls, path: Path) -> dict[str, Any]:
        value = load_json(path)
        if not isinstance(value, dict):
            raise WorkspaceError(f"Assessment-save transaction must be an object: {path}")
        record = cast(dict[str, Any], value)
        if record.get("transaction_sha256") != cls._transaction_hash(record):
            raise WorkspaceError(f"Assessment-save transaction hash mismatch: {path}")
        return record

    @staticmethod
    def _case_relative_path(case_path: Path, candidate: Path, label: str) -> str:
        resolved_case = case_path.resolve()
        resolved = candidate.resolve()
        if resolved == resolved_case or resolved_case not in resolved.parents:
            raise WorkspaceError(f"{label} escapes the controlled case directory: {candidate}")
        return resolved.relative_to(resolved_case).as_posix()

    @staticmethod
    def _transaction_event_committed(case_path: Path, transaction_id: str, after_sha256: str) -> bool:
        event_path = case_path / "events.jsonl"
        report = verify_chain(event_path)
        if not report.get("valid") or not report.get("trailer_valid"):
            raise WorkspaceError("Event chain is invalid during assessment-save transaction recovery")
        matches = [
            event
            for event in load_events(event_path)
            if event.get("action") == "ASSESSMENT_SAVED"
            and isinstance(event.get("payload"), dict)
            and event["payload"].get("transaction_id") == transaction_id
        ]
        if len(matches) > 1:
            raise WorkspaceError(f"Duplicate ASSESSMENT_SAVED transaction event {transaction_id}")
        if not matches:
            return False
        return matches[0]["payload"].get("after_sha256") == after_sha256

    def _rollback_save_transaction(self, case_path: Path, transaction_path: Path, record: dict[str, Any]) -> None:
        transaction_dir = transaction_path.parent
        before_assessment = transaction_dir / "before-assessment.json"
        expected_before = str(record["before_assessment_sha256"])
        if not before_assessment.is_file() or sha256_file(before_assessment) != expected_before:
            raise WorkspaceError(f"Assessment-save rollback snapshot is missing or corrupt: {transaction_dir}")

        exclusive_records = record.get("exclusive_records")
        if not isinstance(exclusive_records, list):
            raise WorkspaceError(f"Assessment-save transaction has invalid exclusive records: {transaction_dir}")
        for item in exclusive_records:
            if not isinstance(item, dict):
                raise WorkspaceError(f"Assessment-save transaction has invalid exclusive record: {transaction_dir}")
            path = safe_join(case_path, str(item["path"]))
            if path.exists():
                if sha256_file(path) != item.get("sha256"):
                    raise WorkspaceError(f"Exclusive record diverged during rollback: {path}")
                path.unlink()

        atomic_write_bytes(case_path / CASE_FILE, before_assessment.read_bytes())
        persistence_path = case_path / "persistence.json"
        before_persistence = transaction_dir / "before-persistence.json"
        if record.get("persistence_existed"):
            expected_persistence = record.get("before_persistence_sha256")
            if not before_persistence.is_file() or sha256_file(before_persistence) != expected_persistence:
                raise WorkspaceError(f"Persistence rollback snapshot is missing or corrupt: {transaction_dir}")
            atomic_write_bytes(persistence_path, before_persistence.read_bytes())
        else:
            persistence_path.unlink(missing_ok=True)

        if record.get("history_created"):
            history_path = safe_join(case_path, str(record["history_path"]))
            if history_path.exists():
                if sha256_file(history_path) != expected_before:
                    raise WorkspaceError(f"Assessment history diverged during rollback: {history_path}")
                history_path.unlink()

        rolled_back = dict(record)
        rolled_back["state"] = "ROLLED_BACK"
        rolled_back["completed_at"] = utc_now()
        self._write_transaction_record(transaction_path, rolled_back)
        before_assessment.unlink(missing_ok=True)
        before_persistence.unlink(missing_ok=True)

    def _recover_save_transactions(self, case_path: Path) -> None:
        root = case_path / ASSESSMENT_SAVE_TRANSACTION_DIR
        if not root.exists():
            return
        for transaction_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            transaction_path = transaction_dir / "transaction.json"
            if not transaction_path.is_file():
                raise WorkspaceError(f"Assessment-save transaction lacks transaction.json: {transaction_dir}")
            record = self._load_transaction_record(transaction_path)
            if record.get("state") != "PREPARED":
                continue
            transaction_id = str(record["transaction_id"])
            after_sha256 = str(record["after_assessment_sha256"])
            if self._transaction_event_committed(case_path, transaction_id, after_sha256):
                target = case_path / CASE_FILE
                if not target.is_file() or sha256_file(target) != after_sha256:
                    raise WorkspaceError(
                        "Committed assessment-save transaction has divergent assessment: "
                        f"{transaction_id}"
                    )
                for item in record.get("exclusive_records", []):
                    path = safe_join(case_path, str(item["path"]))
                    if not path.is_file() or sha256_file(path) != item.get("sha256"):
                        raise WorkspaceError(f"Committed assessment-save transaction has divergent record: {path}")
                committed = dict(record)
                committed["state"] = "COMMITTED"
                committed["completed_at"] = utc_now()
                self._write_transaction_record(transaction_path, committed)
                (transaction_dir / "before-assessment.json").unlink(missing_ok=True)
                (transaction_dir / "before-persistence.json").unlink(missing_ok=True)
                continue
            self._rollback_save_transaction(case_path, transaction_path, record)

    def save_case(
        self,
        case_id: str,
        assessment: dict[str, Any],
        actor: str = "local-user",
        require_valid: bool = False,
        *,
        expected_sha256: str | None = None,
        event_metadata: Mapping[str, Any] | None = None,
        additional_events: Sequence[tuple[str, Mapping[str, Any]]] | None = None,
        exclusive_records: Sequence[tuple[Path, Mapping[str, Any]]] | None = None,
        precondition: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        path = self.case_path(case_id)
        if not path.is_dir():
            raise WorkspaceError(f"Unknown case {case_id!r}")
        with case_mutation_lock(path):
            self._recover_save_transactions(path)
            if precondition is not None:
                precondition()

            target = path / CASE_FILE
            before = sha256_file(target) if target.exists() else None
            if before is None:
                raise WorkspaceError(f"Case {case_id!r} has no assessment.json")
            if expected_sha256 is not None and before != expected_sha256:
                raise WorkspaceError(
                    "Optimistic concurrency refusal: assessment digest no longer matches "
                    f"expected_assessment_sha256 ({expected_sha256})"
                )

            report = validate_assessment(assessment)
            if require_valid and not report.valid:
                raise WorkspaceError("Assessment failed the required validation gate")
            validation_state = "VALID" if report.valid else "DRAFT_INVALID"
            persisted_as = "valid" if report.valid else "draft_invalid"
            desired_assessment = self._json_bytes(assessment)
            after = sha256_bytes(desired_assessment)
            history_path = path / ASSESSMENT_HISTORY_DIR / f"{before}.json"
            history_created = not history_path.exists()
            if history_path.exists() and sha256_file(history_path) != before:
                raise WorkspaceError(f"Assessment history digest mismatch: {history_path}")

            persistence_path = path / "persistence.json"
            persistence_before = persistence_path.read_bytes() if persistence_path.exists() else None
            history_relative = history_path.relative_to(path).as_posix()
            persistence = {
                "validation_state": validation_state,
                "persisted_as": persisted_as,
                "require_valid": require_valid,
                "assessment_sha256": after,
                "previous_assessment_sha256": before,
                "history_path": history_relative,
                "updated_at": utc_now(),
                "actor": actor,
                "boundary": (
                    "validation_state records schema/semantic gate outcome only; "
                    "it does not establish substantive truth or conformance."
                ),
            }
            desired_persistence = self._json_bytes(persistence)

            normalized_records: list[tuple[Path, bytes, str]] = []
            seen_record_paths: set[str] = set()
            for record_path, payload in exclusive_records or ():
                relative = self._case_relative_path(path, record_path, "exclusive record")
                if relative in seen_record_paths:
                    raise WorkspaceError(f"Duplicate exclusive record path: {relative}")
                seen_record_paths.add(relative)
                if record_path.exists():
                    raise WorkspaceError(f"Exclusive record already exists: {record_path.name}")
                data = self._json_bytes(dict(payload))
                normalized_records.append((record_path.resolve(), data, relative))

            transaction_id = f"AST-{uuid4().hex}"
            transaction_dir = path / ASSESSMENT_SAVE_TRANSACTION_DIR / transaction_id
            transaction_dir.mkdir(parents=True)
            before_assessment_bytes = target.read_bytes()
            atomic_write_bytes(transaction_dir / "before-assessment.json", before_assessment_bytes)
            if persistence_before is not None:
                atomic_write_bytes(transaction_dir / "before-persistence.json", persistence_before)
            transaction_path = transaction_dir / "transaction.json"
            transaction: dict[str, Any] = {
                "schema_version": "1",
                "transaction_id": transaction_id,
                "state": "PREPARED",
                "prepared_at": utc_now(),
                "actor": actor,
                "before_assessment_sha256": before,
                "after_assessment_sha256": after,
                "persistence_existed": persistence_before is not None,
                "before_persistence_sha256": (
                    sha256_bytes(persistence_before) if persistence_before is not None else None
                ),
                "after_persistence_sha256": sha256_bytes(desired_persistence),
                "history_path": history_relative,
                "history_created": history_created,
                "exclusive_records": [
                    {"path": relative, "sha256": sha256_bytes(data)}
                    for _record_path, data, relative in normalized_records
                ],
                "authority_profile": "LOCAL_FILESYSTEM_TRANSACTION",
                "boundary": (
                    "This journal coordinates recoverable local file mutation only; "
                    "it establishes no source, identity, custody, or substantive authority."
                ),
            }
            self._write_transaction_record(transaction_path, transaction)

            saved_payload: dict[str, Any] = {
                "transaction_id": transaction_id,
                "before_sha256": before,
                "after_sha256": after,
                "valid": report.valid,
                "validation_state": validation_state,
                "persisted_as": persisted_as,
                "schema_errors": len(report.schema_issues),
                "semantic_errors": len(report.semantic_issues),
                "prior_history": {
                    "prior_assessment_sha256": before,
                    "history_path": history_relative,
                },
            }
            if event_metadata:
                saved_payload["apply_provenance"] = dict(event_metadata)
            if additional_events:
                saved_payload["related_events"] = [
                    {"action": action, "payload": dict(payload)} for action, payload in additional_events
                ]

            try:
                if history_created:
                    atomic_write_bytes(history_path, before_assessment_bytes)
                if sha256_file(history_path) != before:
                    raise WorkspaceError("Failed to preserve recoverable prior assessment state")
                atomic_write_bytes(target, desired_assessment)
                atomic_write_bytes(persistence_path, desired_persistence)
                for record_path, data, _relative in normalized_records:
                    atomic_write_bytes(record_path, data)
                append_event(path / "events.jsonl", "ASSESSMENT_SAVED", actor, saved_payload)
            except Exception:
                if self._transaction_event_committed(path, transaction_id, after):
                    pass
                else:
                    self._rollback_save_transaction(path, transaction_path, transaction)
                    raise

            committed = dict(transaction)
            committed["state"] = "COMMITTED"
            committed["completed_at"] = utc_now()
            self._write_transaction_record(transaction_path, committed)
            (transaction_dir / "before-assessment.json").unlink(missing_ok=True)
            (transaction_dir / "before-persistence.json").unlink(missing_ok=True)

            result = report.to_dict()
            result["validation_state"] = validation_state
            result["persisted_as"] = persisted_as
            result["before_sha256"] = before
            result["after_sha256"] = after
            result["prior_history"] = saved_payload["prior_history"]
            result["transaction_id"] = transaction_id
            return result

    def snapshot(self, case_id: str, actor: str = "local-user", label: str = "snapshot") -> dict[str, Any]:
        case = self.case_path(case_id)
        assessment_path = case / CASE_FILE
        if not assessment_path.is_file():
            raise WorkspaceError(f"Unknown case {case_id!r}")
        with case_mutation_lock(case):
            timestamp = utc_now().replace(":", "").replace("-", "")
            safe_label = ensure_identifier(label, "snapshot label")
            destination = case / "snapshots" / f"{timestamp}-{safe_label}"
            destination.mkdir(parents=True)
            shutil.copy2(assessment_path, destination / CASE_FILE)
            evidence_index = case / "evidence/index.json"
            if evidence_index.exists():
                shutil.copy2(evidence_index, destination / "evidence-index.json")
            record = {
                "snapshot_id": destination.name,
                "created_at": utc_now(),
                "assessment_sha256": sha256_file(destination / CASE_FILE),
                "event_chain": verify_chain(case / "events.jsonl"),
            }
            atomic_write_json(destination / "snapshot.json", record)
            append_event(case / "events.jsonl", "SNAPSHOT_CREATED", actor, record)
            return record

    def delete_case(self, case_id: str, confirmation: str) -> None:
        if confirmation != case_id:
            raise WorkspaceError("Deletion confirmation must exactly match the case ID")
        path = self.case_path(case_id)
        if not path.is_dir():
            raise WorkspaceError(f"Unknown case {case_id!r}")
        with case_mutation_lock(path):
            shutil.rmtree(path)
