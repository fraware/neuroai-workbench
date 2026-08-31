from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

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
