"""Local content-addressed ingest for CONTROLLED_LOCAL_INPUT sources.

Never constructs an HTTP collection request. Reads bytes from an explicit
allowlisted root and writes quarantine objects. Monitoring snapshot recording
remains a separate workbench step after quarantine approval or explicit local
ingest composition outside this package. Capture proves byte identity only —
not substantive truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..util import sha256_bytes, utc_now
from .boundary import COLLECTOR_BOUNDARY
from .ids import new_result_id
from .quarantine import build_quarantine_record, persist_quarantine_record, write_quarantine_bytes

LOCAL_ADAPTER_ID = "local-content-addressed"
MAX_LOCAL_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class LocalContentAddressedAdapter:
    """Optional ingest path for allowlisted local files — never via HTTP request schema."""

    quarantine_root: Path
    allowlisted_roots: tuple[Path, ...]
    collector_version: str
    configuration_hash: str

    adapter_id: str = LOCAL_ADAPTER_ID

    def resolve_allowlisted_path(self, path: Path) -> Path:
        resolved = path.resolve()
        if not resolved.is_file():
            raise ValueError(f"Local input path is not a file: {path}")
        for root in self.allowlisted_roots:
            root_resolved = root.resolve()
            try:
                resolved.relative_to(root_resolved)
                return resolved
            except ValueError:
                continue
        raise ValueError("Local input path is outside allowlisted roots; refusing broad filesystem crawl")

    def ingest_file(
        self,
        *,
        source_id: str,
        monitor_id: str,
        source_path: Path,
        media_type: str = "application/octet-stream",
        original_filename: str | None = None,
    ) -> dict[str, Any]:
        resolved = self.resolve_allowlisted_path(source_path)
        data = resolved.read_bytes()
        if not data:
            raise ValueError("Local ingest refuses zero-byte inputs")
        if len(data) > MAX_LOCAL_BYTES:
            raise ValueError(f"Local ingest exceeds the {MAX_LOCAL_BYTES}-byte limit")
        digest = sha256_bytes(data)
        result_id = new_result_id()
        filename = original_filename or resolved.name
        relative = f"objects/{digest[:2]}/{digest}.bin"
        write_quarantine_bytes(self.quarantine_root, relative, data)
        captured_at = utc_now()
        record = build_quarantine_record(
            result_id=result_id,
            source_id=source_id,
            monitor_id=monitor_id,
            captured_at=captured_at,
            content_sha256=digest,
            size_bytes=len(data),
            original_filename=filename,
            quarantine_path=relative,
            collector_version=self.collector_version,
            configuration_hash=self.configuration_hash,
        )
        persist_quarantine_record(self.quarantine_root, record)
        return {
            "adapter_id": self.adapter_id,
            "result_id": result_id,
            "quarantine_id": record["quarantine_id"],
            "source_id": source_id,
            "monitor_id": monitor_id,
            "sha256": digest,
            "size_bytes": len(data),
            "media_type": media_type,
            "original_filename": filename,
            "quarantine_path": relative,
            "bytes_path": str(self.quarantine_root / relative),
            "captured_at": captured_at,
            "evidence_state": "RETRIEVED_BYTES_NOT_SUBSTANTIVELY_ADJUDICATED",
            "boundary": COLLECTOR_BOUNDARY,
        }
