from __future__ import annotations

from typing import Any

from ..service import CollectionOutcome, HttpCollector, PriorCapture
from .base import HttpCollectorAdapter

REGISTRY_STUB_BODY = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<registry-stub xmlns="https://neuroai-workbench.example/collector/registry-stub">'
    b"<status>STUB_RETRIEVAL_ONLY</status>"
    b"<boundary>Stub registry lookup records retrieval intent only; it does not establish regulatory truth.</boundary>"
    b"</registry-stub>"
)


class ClinicalRegulatoryRegistryStub(HttpCollectorAdapter):
    adapter_id = "registry_stub"

    _SOURCE_CLASSES = frozenset(
        {
            "REGULATORY_RECORD",
            "OFFICIAL_TRIAL_REGISTRY",
            "OFFICIAL_COMPANY_REGULATORY_ANNOUNCEMENT",
            "OFFICIAL_COMPANY_US_REGULATORY_ANNOUNCEMENT",
            "OFFICIAL_COMPANY_REGULATORY_PROCESS_ANNOUNCEMENT",
            "OFFICIAL_LEGAL_TEXT",
            "PEER_REVIEWED_PRIMARY_CLINICAL_STUDY",
        }
    )

    def __init__(self, collector: HttpCollector) -> None:
        super().__init__(collector)

    def supports_source_class(self, source_class: str) -> bool:
        return source_class in self._SOURCE_CLASSES or "REGULATORY" in source_class or "TRIAL" in source_class

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
