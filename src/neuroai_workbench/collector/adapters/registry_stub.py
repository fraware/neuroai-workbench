"""HTTP page-capture adapter for clinical/regulatory landing pages.

Renamed for routing honesty: this is page capture, not structured registry
integration. Prefer ClinicalTrialsGovAdapter / FdaDeviceAdapter when explicit
identifiers are present.
"""

from __future__ import annotations

from typing import Any

from ..service import CollectionOutcome, HttpCollector, PriorCapture
from .base import HttpCollectorAdapter

REGISTRY_STUB_BODY = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<registry-stub xmlns="https://neuroai-workbench.example/collector/registry-stub">'
    b"<status>HTTP_PAGE_CAPTURE_ONLY</status>"
    b"<boundary>Page capture records retrieval only; it does not establish regulatory truth or registry completeness.</boundary>"
    b"</registry-stub>"
)


class ClinicalRegulatoryHttpCaptureAdapter(HttpCollectorAdapter):
    """HTTP capture for selected clinical/regulatory landing pages — not structured integration."""

    adapter_id = "clinical_regulatory_http_capture"

    _SOURCE_CLASSES = frozenset(
        {
            "REGULATORY_RECORD",
            "OFFICIAL_LEGAL_TEXT",
            "PEER_REVIEWED_PRIMARY_CLINICAL_STUDY",
            "OFFICIAL_COMPANY_REGULATORY_PROCESS_ANNOUNCEMENT",
        }
    )

    def __init__(self, collector: HttpCollector) -> None:
        super().__init__(collector)

    def supports_source_class(self, source_class: str) -> bool:
        # Explicit allowlist only — no over-broad REGULATORY/TRIAL substring matching.
        return source_class in self._SOURCE_CLASSES

    def collect(
        self,
        request: dict[str, Any],
        *,
        prior_capture: PriorCapture | None = None,
        attempt_count: int = 1,
    ) -> CollectionOutcome:
        return super().collect(
            request,
            prior_capture=prior_capture,
            attempt_count=attempt_count,
        )


# Backward-compatible alias.
ClinicalRegulatoryRegistryStub = ClinicalRegulatoryHttpCaptureAdapter
