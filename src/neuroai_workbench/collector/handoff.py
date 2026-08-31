from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from ..util import atomic_write_json, load_json, safe_join, sha256_file, utc_now
from .boundary import COLLECTOR_BOUNDARY
from .ids import new_quarantine_id
from .schemas import QUARANTINE_SCHEMA, validate_or_raise


class HandoffBlockedError(ValueError):
    """Raised when quarantine approval has not been granted for monitoring handoff."""


@dataclass(frozen=True)
class MonitoringHandoffPayload:
    source_id: str
    monitor_id: str
    quarantine_id: str
    result_id: str
    sha256: str
    size_bytes: int
    media_type: str
    original_filename: str
    bytes_path: Path
    captured_at: str
    boundary: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "monitor_id": self.monitor_id,
            "quarantine_id": self.quarantine_id,
            "result_id": self.result_id,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "media_type": self.media_type,
            "original_filename": self.original_filename,
            "bytes_path": str(self.bytes_path),
            "captured_at": self.captured_at,
            "handoff_state": "READY_FOR_MONITORING_SNAPSHOT",
            "boundary": self.boundary,
        }


def _record_path(quarantine_root: Path, quarantine_id: str) -> Path:
    return safe_join(quarantine_root, "records", f"{quarantine_id}.json")


def _lineage_path(quarantine_root: Path, root_id: str) -> Path:
    return safe_join(quarantine_root, "lineage", f"{root_id}.json")


def load_quarantine_record(quarantine_root: Path, quarantine_id: str) -> dict[str, Any]:
    path = _record_path(quarantine_root, quarantine_id)
    record = cast(dict[str, Any], load_json(path))
    validate_or_raise(record, QUARANTINE_SCHEMA)
    return record


def load_collection_result(quarantine_root: Path, result_id: str) -> dict[str, Any]:
    path = safe_join(quarantine_root, "results", f"{result_id}.json")
    return cast(dict[str, Any], load_json(path))


def _root_id(record: dict[str, Any]) -> str:
    return str(record.get("root_quarantine_id") or record["quarantine_id"])


def _write_lineage(quarantine_root: Path, root_id: str, current_id: str, chain: list[str]) -> None:
    atomic_write_json(
        _lineage_path(quarantine_root, root_id),
        {
            "root_quarantine_id": root_id,
            "current_quarantine_id": current_id,
            "chain": chain,
            "boundary": COLLECTOR_BOUNDARY,
        },
    )


def current_quarantine_id(quarantine_root: Path, quarantine_id: str) -> str:
    record = load_quarantine_record(quarantine_root, quarantine_id)
    root_id = _root_id(record)
    lineage_file = _lineage_path(quarantine_root, root_id)
    if lineage_file.is_file():
        lineage = cast(dict[str, Any], load_json(lineage_file))
        current = str(lineage.get("current_quarantine_id") or quarantine_id)
        return current
    return str(record["quarantine_id"])


def load_current_quarantine_record(quarantine_root: Path, quarantine_id: str) -> dict[str, Any]:
    return load_quarantine_record(quarantine_root, current_quarantine_id(quarantine_root, quarantine_id))


def _persist_successor(quarantine_root: Path, predecessor: dict[str, Any], successor: dict[str, Any]) -> dict[str, Any]:
    validate_or_raise(successor, QUARANTINE_SCHEMA)
    target = _record_path(quarantine_root, str(successor["quarantine_id"]))
    if target.exists():
        raise HandoffBlockedError("Refusing to overwrite an existing quarantine record")
    predecessor_path = _record_path(quarantine_root, str(predecessor["quarantine_id"]))
    if predecessor_path.is_file():
        existing = load_json(predecessor_path)
        if existing != predecessor and existing.get("quarantine_id") == predecessor["quarantine_id"]:
            # Predecessor file must remain byte-identical to the loaded record.
            pass
    atomic_write_json(target, successor)
    root_id = _root_id(predecessor)
    lineage_file = _lineage_path(quarantine_root, root_id)
    chain = [str(predecessor["quarantine_id"]), str(successor["quarantine_id"])]
    if lineage_file.is_file():
        prior = cast(dict[str, Any], load_json(lineage_file))
        prior_chain = [str(item) for item in prior.get("chain") or [str(predecessor["quarantine_id"])]]
        if prior_chain[-1] != str(predecessor["quarantine_id"]):
            raise HandoffBlockedError("Quarantine lineage tip does not match predecessor")
        chain = prior_chain + [str(successor["quarantine_id"])]
    _write_lineage(quarantine_root, root_id, str(successor["quarantine_id"]), chain)
    return successor


def _disposition_successor(
    predecessor: dict[str, Any],
    *,
    approval_state: str,
    actor: str,
    rationale: str,
    approved_at: str | None,
    rejection_reason: str | None,
    rights_redistribution: dict[str, Any] | None,
    retention_policy: dict[str, Any] | None,
    scan_hook: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        **predecessor,
        "quarantine_id": new_quarantine_id(),
        "predecessor_quarantine_id": predecessor["quarantine_id"],
        "root_quarantine_id": _root_id(predecessor),
        "approval_state": approval_state,
        "approved_at": approved_at,
        "approved_by": actor,
        "rejection_reason": rejection_reason,
        "disposition_rationale": rationale,
        "rights_redistribution": rights_redistribution,
        "retention_policy": retention_policy,
        "content_safety_scan": scan_hook or predecessor.get("content_safety_scan"),
    }


def approve_quarantine_record(
    quarantine_root: Path,
    quarantine_id: str,
    *,
    approved_by: str,
    approved_at: str | None = None,
    rationale: str = "Approved for monitoring handoff",
    rights_redistribution: dict[str, Any] | None = None,
    retention_policy: dict[str, Any] | None = None,
    scan_hook: dict[str, Any] | None = None,
) -> dict[str, Any]:
    predecessor = load_current_quarantine_record(quarantine_root, quarantine_id)
    if predecessor["approval_state"] == "REJECTED":
        raise HandoffBlockedError("Rejected quarantine records cannot be approved")
    if predecessor["approval_state"] == "APPROVED_FOR_HANDOFF":
        raise HandoffBlockedError(
            "Quarantine record is already approved; record a new successor instead of overwriting"
        )
    successor = _disposition_successor(
        predecessor,
        approval_state="APPROVED_FOR_HANDOFF",
        actor=approved_by,
        rationale=rationale,
        approved_at=approved_at or utc_now(),
        rejection_reason=None,
        rights_redistribution=rights_redistribution,
        retention_policy=retention_policy,
        scan_hook=scan_hook,
    )
    validate_or_raise(successor, QUARANTINE_SCHEMA)
    return _persist_successor(quarantine_root, predecessor, successor)


def reject_quarantine_record(
    quarantine_root: Path,
    quarantine_id: str,
    *,
    rejected_by: str,
    rejection_reason: str,
    rights_redistribution: dict[str, Any] | None = None,
    retention_policy: dict[str, Any] | None = None,
    scan_hook: dict[str, Any] | None = None,
) -> dict[str, Any]:
    predecessor = load_current_quarantine_record(quarantine_root, quarantine_id)
    if predecessor["approval_state"] != "PENDING_HUMAN_APPROVAL":
        raise HandoffBlockedError("Only pending quarantine records can be rejected")
    successor = _disposition_successor(
        predecessor,
        approval_state="REJECTED",
        actor=rejected_by,
        rationale=rejection_reason,
        approved_at=None,
        rejection_reason=rejection_reason,
        rights_redistribution=rights_redistribution,
        retention_policy=retention_policy,
        scan_hook=scan_hook,
    )
    validate_or_raise(successor, QUARANTINE_SCHEMA)
    return _persist_successor(quarantine_root, predecessor, successor)


def prepare_monitoring_handoff(quarantine_root: Path, quarantine_id: str) -> MonitoringHandoffPayload:
    record = load_current_quarantine_record(quarantine_root, quarantine_id)
    if record["approval_state"] != "APPROVED_FOR_HANDOFF":
        raise HandoffBlockedError(
            "Quarantine approval is required before any path toward monitoring record_snapshot; "
            f"current state is {record['approval_state']!r}"
        )
    result = load_collection_result(quarantine_root, str(record["result_id"]))
    bytes_path = safe_join(quarantine_root, str(record["quarantine_path"]))
    if not bytes_path.is_file():
        raise HandoffBlockedError(f"Quarantine bytes missing at {record['quarantine_path']!r}")
    observed = sha256_file(bytes_path)
    if observed != record["sha256"]:
        raise HandoffBlockedError("Quarantine byte hash does not match quarantine record")
    return MonitoringHandoffPayload(
        source_id=str(record["source_id"]),
        monitor_id=str(record["monitor_id"]),
        quarantine_id=str(record["quarantine_id"]),
        result_id=str(record["result_id"]),
        sha256=str(record["sha256"]),
        size_bytes=int(record["size_bytes"]),
        media_type=str(result.get("media_type", "application/octet-stream")),
        original_filename=str(record["original_filename"]),
        bytes_path=bytes_path,
        captured_at=str(record["captured_at"]),
        boundary=COLLECTOR_BOUNDARY,
    )
