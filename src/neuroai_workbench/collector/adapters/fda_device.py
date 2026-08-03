"""FDA device record adapter for explicit PMA/HDE/De Novo/510(k) identifiers.

Selects FDA regulatory landing retrieval when an explicit device identifier is
present on the source or URL. Does not imply completeness of the adverse-event
universe. Capture proves retrieval only.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..service import CollectionOutcome, HttpCollector, PriorCapture
from .base import HttpCollectorAdapter

FDA_DEVICE_ADAPTER_ID = "fda_device"
_DENOVO_RE = re.compile(r"\bDEN\d{6}\b", re.I)
_PMA_RE = re.compile(r"\bP\d{6}\b", re.I)
_HDE_RE = re.compile(r"\bH\d{6}\b", re.I)
_K_RE = re.compile(r"\bK\d{6}\b", re.I)


class FdaDeviceAdapter(HttpCollectorAdapter):
    adapter_id = FDA_DEVICE_ADAPTER_ID

    _SOURCE_CLASSES = frozenset(
        {
            "REGULATORY_RECORD",
            "OFFICIAL_COMPANY_REGULATORY_ANNOUNCEMENT",
            "OFFICIAL_COMPANY_US_REGULATORY_ANNOUNCEMENT",
            "COMPANY_REGULATORY_ANNOUNCEMENT",
        }
    )

    def __init__(self, collector: HttpCollector) -> None:
        super().__init__(collector)

    def supports_source_class(self, source_class: str) -> bool:
        return source_class in self._SOURCE_CLASSES

    def extract_device_id(self, source_record: dict[str, Any] | None, request: dict[str, Any]) -> str | None:
        candidates: list[str] = []
        if source_record:
            for key in ("fda_device_id", "device_id", "pma_number", "denovo_number", "k_number", "hde_number"):
                value = source_record.get(key)
                if isinstance(value, str):
                    candidates.append(value)
            metadata = source_record.get("metadata")
            if isinstance(metadata, dict):
                for key in ("fda_device_id", "knumber", "pmanumber"):
                    value = metadata.get(key)
                    if isinstance(value, str):
                        candidates.append(value)
        url = str(request.get("requested_url") or "")
        candidates.append(url)
        query = parse_qs(urlparse(url).query)
        for key in ("knumber", "pmanumber", "id"):
            for value in query.get(key, []):
                candidates.append(value)
        for candidate in candidates:
            for pattern in (_DENOVO_RE, _PMA_RE, _HDE_RE, _K_RE):
                match = pattern.search(candidate)
                if match:
                    return match.group(0).upper()
        return None

    def supports_source(self, source_record: dict[str, Any], request: dict[str, Any] | None = None) -> bool:
        if not self.supports_source_class(str(source_record.get("source_class", ""))):
            return False
        synthetic_request = request or {"requested_url": source_record.get("url", "")}
        return self.extract_device_id(source_record, synthetic_request) is not None

    def collect(
        self,
        request: dict[str, Any],
        *,
        prior_capture: PriorCapture | None = None,
        attempt_count: int = 1,
        source_record: dict[str, Any] | None = None,
    ) -> CollectionOutcome:
        # Landing URL retrieval only; identifier presence selects this adapter.
        _ = self.extract_device_id(source_record, request)
        return super().collect(request, prior_capture=prior_capture, attempt_count=attempt_count)
