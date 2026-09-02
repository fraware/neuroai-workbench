from __future__ import annotations

from pathlib import Path
from typing import Any

from .authorization import (
    require_network_authorization,
    validate_authorization_packet,
)
from .scan import ContentSafetyScanner, default_scanner, ensure_content_safety_scan
from .service import CollectionOutcome, HttpCollector, PriorCapture


class EvidenceCollectionService:
    """Gated facade over HttpCollector.collect.

    Network capture requires an authorization packet AND NEUROAI_LIVE_COLLECTION=1.
    Default CLI and data builds must not call this service. HttpCollector remains
    available for tests and offline fake transports.
    """

    def __init__(
        self,
        collector: HttpCollector,
        *,
        scanner: ContentSafetyScanner | None = None,
    ) -> None:
        self.collector = collector
        self.scanner = scanner or default_scanner()

    def collect(
        self,
        authorization: dict[str, Any],
        collection_request: dict[str, Any],
        *,
        prior_capture: PriorCapture | None = None,
        attempt_count: int = 1,
    ) -> CollectionOutcome:
        packet = validate_authorization_packet(authorization)
        if packet["network_mode"] == "AUTHORIZED_NETWORK":
            require_network_authorization(packet)
        outcome = self.collector.collect(
            collection_request,
            prior_capture=prior_capture,
            attempt_count=attempt_count,
        )
        if outcome.kind == "result":
            ensure_content_safety_scan(
                self.collector.quarantine_root,
                outcome.record,
                scanner=self.scanner,
                quarantine_record=outcome.quarantine_record,
            )
        return outcome


class QuarantineService:
    """Append-only quarantine disposition facade."""

    def __init__(self, quarantine_root: Path) -> None:
        self.quarantine_root = quarantine_root

    def dispose(
        self,
        quarantine_id: str,
        *,
        decision: str,
        actor: str,
        rationale: str,
        rights_redistribution: dict[str, Any] | None = None,
        retention_policy: dict[str, Any] | None = None,
        scan_hook: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from .handoff import approve_quarantine_record, reject_quarantine_record

        if decision == "APPROVE":
            return approve_quarantine_record(
                self.quarantine_root,
                quarantine_id,
                approved_by=actor,
                rationale=rationale,
                rights_redistribution=rights_redistribution,
                retention_policy=retention_policy,
                scan_hook=scan_hook,
            )
        if decision == "REJECT":
            return reject_quarantine_record(
                self.quarantine_root,
                quarantine_id,
                rejected_by=actor,
                rejection_reason=rationale,
                rights_redistribution=rights_redistribution,
                retention_policy=retention_policy,
                scan_hook=scan_hook,
            )
        raise ValueError(f"Unsupported quarantine decision {decision!r}")
