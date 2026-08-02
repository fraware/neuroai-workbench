from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from ..util import atomic_write_json, load_json, safe_join, sha256_file, utc_now
from .boundary import COLLECTOR_BOUNDARY
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


def load_quarantine_record(quarantine_root: Path, quarantine_id: str) -> dict[str, Any]:
    path = safe_join(quarantine_root, "records", f"{quarantine_id}.json")
    record = cast(dict[str, Any], load_json(path))
    validate_or_raise(record, QUARANTINE_SCHEMA)
    return record


def load_collection_result(quarantine_root: Path, result_id: str) -> dict[str, Any]:
    path = safe_join(quarantine_root, "results", f"{result_id}.json")
    return cast(dict[str, Any], load_json(path))


def approve_quarantine_record(
    quarantine_root: Path,
    quarantine_id: str,
    *,
    approved_by: str,
    approved_at: str | None = None,
) -> dict[str, Any]:
    record = load_quarantine_record(quarantine_root, quarantine_id)
    if record["approval_state"] == "REJECTED":
        raise HandoffBlockedError("Rejected quarantine records cannot be approved")
    record = {
        **record,
        "approval_state": "APPROVED_FOR_HANDOFF",
        "approved_at": approved_at or utc_now(),
        "approved_by": approved_by,
        "rejection_reason": None,
    }
    validate_or_raise(record, QUARANTINE_SCHEMA)
    atomic_write_json(safe_join(quarantine_root, "records", f"{quarantine_id}.json"), record)
    return record


def reject_quarantine_record(
    quarantine_root: Path,
    quarantine_id: str,
    *,
    rejected_by: str,
    rejection_reason: str,
) -> dict[str, Any]:
    record = load_quarantine_record(quarantine_root, quarantine_id)
    record = {
        **record,
        "approval_state": "REJECTED",
        "approved_at": None,
        "approved_by": rejected_by,
        "rejection_reason": rejection_reason,
    }
    validate_or_raise(record, QUARANTINE_SCHEMA)
    atomic_write_json(safe_join(quarantine_root, "records", f"{quarantine_id}.json"), record)
    return record


def prepare_monitoring_handoff(quarantine_root: Path, quarantine_id: str) -> MonitoringHandoffPayload:
    record = load_quarantine_record(quarantine_root, quarantine_id)
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
