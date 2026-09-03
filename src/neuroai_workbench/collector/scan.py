from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from ..util import atomic_write_json, load_json, safe_join
from .schemas import QUARANTINE_SCHEMA, RESULT_SCHEMA, validate_or_raise

SCAN_BOUNDARY = (
    "Content-safety scanning records whether a scanner ran and whether it returned a fail-closed "
    "or unclean result. Scanning is not substantive adjudication, authenticity, or legal clearance."
)
SCAN_STATES = frozenset(
    {
        "NOT_EXECUTED_FAIL_CLOSED",
        "SCANNER_UNAVAILABLE_FAIL_CLOSED",
        "UNCLEAN",
        "CLEAN_NOT_ADJUDICATION",
    }
)


@dataclass(frozen=True)
class ScanResult:
    state: str
    scanner_id: str
    detail: str
    boundary: str = SCAN_BOUNDARY

    def as_dict(self) -> dict[str, str]:
        if self.state not in SCAN_STATES:
            raise ValueError(f"Unknown scan state {self.state!r}")
        return {
            "state": self.state,
            "scanner_id": self.scanner_id,
            "detail": self.detail,
            "boundary": self.boundary,
        }


class ContentSafetyScanner(Protocol):
    def scan(self, *, sha256: str, media_type: str, size_bytes: int) -> ScanResult:
        """Return a scan result. Must not imply substantive adjudication."""


class FailClosedContentSafetyScanner:
    """Default scanner. Never reports CLEAN; absence of an AV binary is fail-closed."""

    scanner_id = "workbench.fail_closed_default"

    def scan(self, *, sha256: str, media_type: str, size_bytes: int) -> ScanResult:
        if not sha256 or size_bytes < 0:
            return ScanResult(
                state="SCANNER_UNAVAILABLE_FAIL_CLOSED",
                scanner_id=self.scanner_id,
                detail="Scan refused because capture identity is incomplete",
            )
        return ScanResult(
            state="NOT_EXECUTED_FAIL_CLOSED",
            scanner_id=self.scanner_id,
            detail="No content-safety engine is configured; default is fail-closed and is not CLEAN",
        )


def default_scanner() -> FailClosedContentSafetyScanner:
    return FailClosedContentSafetyScanner()


def _validate_persisted_scan(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError("Persisted content-safety scan must be an object")
    state = value.get("state")
    scanner_id = value.get("scanner_id")
    detail = value.get("detail")
    boundary = value.get("boundary")
    if state not in SCAN_STATES:
        raise ValueError(f"Persisted content-safety scan has unknown state {state!r}")
    if not isinstance(scanner_id, str) or not scanner_id.strip():
        raise ValueError("Persisted content-safety scan scanner_id must be non-empty")
    if not isinstance(detail, str):
        raise ValueError("Persisted content-safety scan detail must be a string")
    if boundary != SCAN_BOUNDARY:
        raise ValueError("Persisted content-safety scan boundary is invalid")
    return {
        "state": str(state),
        "scanner_id": scanner_id,
        "detail": detail,
        "boundary": str(boundary),
    }


def _root_quarantine_record_for_result(quarantine_root: Path, result_id: str) -> dict[str, Any]:
    records_dir = quarantine_root / "records"
    if not records_dir.is_dir():
        raise ValueError(f"No quarantine records directory exists for result {result_id!r}")
    matches: list[dict[str, Any]] = []
    for path in sorted(records_dir.glob("*.json")):
        value = load_json(path)
        if not isinstance(value, dict):
            raise ValueError(f"Quarantine record {path.name!r} is not an object")
        record = cast(dict[str, Any], value)
        validate_or_raise(record, QUARANTINE_SCHEMA)
        if str(record.get("result_id") or "") != result_id:
            continue
        if record.get("predecessor_quarantine_id"):
            continue
        matches.append(record)
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one root quarantine record for result {result_id!r}; found {len(matches)}")
    return matches[0]


def _verify_result_quarantine_binding(result: dict[str, Any], quarantine: dict[str, Any]) -> None:
    pairs = (
        ("result_id", result.get("result_id"), quarantine.get("result_id")),
        ("source_id", result.get("source_id"), quarantine.get("source_id")),
        ("monitor_id", result.get("monitor_id"), quarantine.get("monitor_id")),
        ("sha256", result.get("sha256"), quarantine.get("sha256")),
        ("size_bytes", result.get("size_bytes"), quarantine.get("size_bytes")),
        ("quarantine_path", result.get("quarantine_path"), quarantine.get("quarantine_path")),
    )
    mismatches = [name for name, left, right in pairs if left != right]
    if mismatches:
        raise ValueError("Collection result and root quarantine record disagree on: " + ", ".join(sorted(mismatches)))


def ensure_content_safety_scan(
    quarantine_root: Path,
    result_record: dict[str, Any],
    *,
    scanner: ContentSafetyScanner | None = None,
    quarantine_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ensure one durable fail-closed scan record exists for a collected result.

    Existing scan metadata is verified and reused. Scanner state remains custody metadata;
    it does not adjudicate source truth, legal status, or canonical publication.
    """
    validate_or_raise(result_record, RESULT_SCHEMA)
    result_id = str(result_record["result_id"])
    quarantine = quarantine_record or _root_quarantine_record_for_result(quarantine_root, result_id)
    validate_or_raise(quarantine, QUARANTINE_SCHEMA)
    if quarantine.get("predecessor_quarantine_id"):
        raise ValueError("Content-safety scan must bind to the root quarantine capture record")
    _verify_result_quarantine_binding(result_record, quarantine)

    quarantine_id = str(quarantine["quarantine_id"])
    scan_path = safe_join(quarantine_root, "scans", f"{quarantine_id}.json")
    if scan_path.is_file():
        persisted = _validate_persisted_scan(load_json(scan_path))
        return {
            "result_id": result_id,
            "quarantine_id": quarantine_id,
            "state": persisted["state"],
            "scanner_id": persisted["scanner_id"],
            "existing_scan_verified": True,
            "boundary": SCAN_BOUNDARY,
        }

    active_scanner = scanner or default_scanner()
    scan = active_scanner.scan(
        sha256=str(result_record["sha256"]),
        media_type=str(result_record.get("media_type") or "application/octet-stream"),
        size_bytes=int(result_record["size_bytes"]),
    )
    payload = _validate_persisted_scan(scan.as_dict())
    atomic_write_json(scan_path, payload)
    return {
        "result_id": result_id,
        "quarantine_id": quarantine_id,
        "state": payload["state"],
        "scanner_id": payload["scanner_id"],
        "existing_scan_verified": False,
        "boundary": SCAN_BOUNDARY,
    }


def ensure_quarantine_result_scans(
    quarantine_root: Path,
    *,
    scanner: ContentSafetyScanner | None = None,
) -> list[dict[str, Any]]:
    """Verify or create scan metadata for every durable result in a quarantine root.

    Auditing durable results instead of only in-memory outcomes closes the crash window where
    result/quarantine records are persisted before a scheduler checkpoint is committed.
    """
    results_dir = quarantine_root / "results"
    if not results_dir.is_dir():
        return []
    active_scanner = scanner or default_scanner()
    records: list[dict[str, Any]] = []
    for path in sorted(results_dir.glob("*.json")):
        value = load_json(path)
        if not isinstance(value, dict):
            raise ValueError(f"Collection result {path.name!r} is not an object")
        result = cast(dict[str, Any], value)
        validate_or_raise(result, RESULT_SCHEMA)
        records.append(
            ensure_content_safety_scan(
                quarantine_root,
                result,
                scanner=active_scanner,
            )
        )
    return records
