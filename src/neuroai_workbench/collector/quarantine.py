from __future__ import annotations

from pathlib import Path
from typing import Any

from ..util import atomic_write_bytes, atomic_write_json, safe_join, sha256_bytes, sha256_file
from .boundary import COLLECTOR_BOUNDARY
from .errors import CollectionFailureError
from .ids import new_quarantine_id
from .schemas import QUARANTINE_SCHEMA, validate_or_raise


def _safe_filename(name: str) -> str:
    candidate = Path(name).name
    if candidate != name or not candidate or candidate in {".", ".."}:
        raise CollectionFailureError("UNSAFE_FILENAME", "original_filename must be a safe basename")
    if any(char in candidate for char in "/\\") or ".." in candidate:
        raise CollectionFailureError("UNSAFE_FILENAME", "original_filename must not contain path separators")
    if any(ord(char) < 32 for char in candidate):
        raise CollectionFailureError("UNSAFE_FILENAME", "original_filename must not contain control characters")
    return candidate


def _safe_quarantine_path(path: str) -> str:
    normalized = path.replace("\\", "/").lstrip("/")
    if not normalized or ".." in normalized.split("/"):
        raise CollectionFailureError("QUARANTINE_REJECTED", "quarantine_path must be a safe relative path")
    return normalized


def write_quarantine_bytes(root: Path, relative_path: str, data: bytes) -> Path:
    safe_path = _safe_quarantine_path(relative_path)
    target = safe_join(root, safe_path)
    if target.exists():
        if sha256_file(target) != sha256_bytes(data):
            raise CollectionFailureError(
                "QUARANTINE_REJECTED",
                f"Refusing to overwrite quarantine object at {safe_path!r} with different bytes",
            )
        return target
    atomic_write_bytes(target, data)
    return target


def build_quarantine_record(
    *,
    result_id: str,
    source_id: str,
    monitor_id: str,
    captured_at: str,
    content_sha256: str,
    size_bytes: int,
    original_filename: str,
    quarantine_path: str,
    collector_version: str,
    configuration_hash: str,
) -> dict[str, Any]:
    record = {
        "quarantine_id": new_quarantine_id(),
        "result_id": result_id,
        "source_id": source_id,
        "monitor_id": monitor_id,
        "captured_at": captured_at,
        "sha256": content_sha256,
        "size_bytes": size_bytes,
        "original_filename": _safe_filename(original_filename),
        "quarantine_path": _safe_quarantine_path(quarantine_path),
        "approval_state": "PENDING_HUMAN_APPROVAL",
        "approved_at": None,
        "approved_by": None,
        "rejection_reason": None,
        "collector_version": collector_version,
        "configuration_hash": configuration_hash,
        "boundary": COLLECTOR_BOUNDARY,
    }
    validate_or_raise(record, QUARANTINE_SCHEMA)
    return record


def persist_quarantine_record(root: Path, record: dict[str, Any]) -> Path:
    validate_or_raise(record, QUARANTINE_SCHEMA)
    target = safe_join(root, "records", f"{record['quarantine_id']}.json")
    atomic_write_json(target, record)
    return target
