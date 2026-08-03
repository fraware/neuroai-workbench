"""ClinicalTrials.gov structured study adapter.

Rewrites allowlisted NCT-bearing sources to the CT.gov studies API URL. Capture
proves retrieval of the selected study payload only — not registry completeness
or clinical truth. CI uses recorded fixtures through the injectable transport.
"""

from __future__ import annotations

import re
from typing import Any

from ..service import CollectionOutcome, HttpCollector, PriorCapture
from .base import HttpCollectorAdapter

CTGOV_ADAPTER_ID = "clinicaltrials_gov"
CTGOV_API_PREFIX = "https://clinicaltrials.gov/api/v2/studies/"
_NCT_RE = re.compile(r"\bNCT\d{8}\b", re.I)


class ClinicalTrialsGovAdapter(HttpCollectorAdapter):
    adapter_id = CTGOV_ADAPTER_ID

    _SOURCE_CLASSES = frozenset(
        {
            "CLINICAL_TRIAL_REGISTRY",
            "OFFICIAL_TRIAL_REGISTRY",
            "OFFICIAL_TRIAL_PAGE",
        }
    )

    def __init__(self, collector: HttpCollector) -> None:
        super().__init__(collector)

    def supports_source_class(self, source_class: str) -> bool:
        return source_class in self._SOURCE_CLASSES

    def extract_nct_id(self, source_record: dict[str, Any] | None, request: dict[str, Any]) -> str | None:
        candidates: list[str] = []
        if source_record:
            for key in ("nct_id", "trial_id", "registry_id"):
                value = source_record.get(key)
                if isinstance(value, str):
                    candidates.append(value)
            metadata = source_record.get("metadata")
            if isinstance(metadata, dict):
                value = metadata.get("nct_id")
                if isinstance(value, str):
                    candidates.append(value)
        candidates.append(str(request.get("requested_url") or ""))
        for candidate in candidates:
            match = _NCT_RE.search(candidate)
            if match:
                return match.group(0).upper()
        return None

    def collect(
        self,
        request: dict[str, Any],
        *,
        prior_capture: PriorCapture | None = None,
        attempt_count: int = 1,
        source_record: dict[str, Any] | None = None,
    ) -> CollectionOutcome:
        nct_id = self.extract_nct_id(source_record, request)
        if nct_id is None:
            return super().collect(request, prior_capture=prior_capture, attempt_count=attempt_count)
        rewritten = {**request, "requested_url": f"{CTGOV_API_PREFIX}{nct_id}"}
        return super().collect(rewritten, prior_capture=prior_capture, attempt_count=attempt_count)
