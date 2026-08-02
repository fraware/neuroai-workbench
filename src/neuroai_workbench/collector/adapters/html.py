from __future__ import annotations

import re
from typing import Any

from ..errors import CollectionFailureError
from ..service import CollectionOutcome, HttpCollector, PriorCapture
from .base import HttpCollectorAdapter

_HTML_HINT = re.compile(r"(?is)<(?:!doctype\s+html|html|head|body)\b")


class HtmlPageAdapter(HttpCollectorAdapter):
    adapter_id = "html"

    _SOURCE_CLASSES = frozenset(
        {
            "OFFICIAL_COMPANY_PAGE",
            "OFFICIAL_PRODUCT_PAGE",
            "OFFICIAL_COMPANY_TECHNOLOGY_PAGE",
            "PUBLIC_HISTORICAL_PATIENT_MANUAL",
            "PRESS_RELEASE_SYNDICATION",
            "REPUTABLE_MEDIA_CORROBORATION",
        }
    )

    def __init__(self, collector: HttpCollector) -> None:
        super().__init__(collector)

    def supports_source_class(self, source_class: str) -> bool:
        return source_class in self._SOURCE_CLASSES or source_class.endswith("_PAGE")

    def collect(
        self,
        request: dict[str, Any],
        *,
        prior_capture: PriorCapture | None = None,
        attempt_count: int = 1,
    ) -> CollectionOutcome:
        outcome = super().collect(
            request,
            prior_capture=prior_capture,
            attempt_count=attempt_count,
        )
        if outcome.kind != "result" or outcome.record.get("http_status") == 304:
            return outcome
        media_type = str(outcome.record.get("media_type", ""))
        if not media_type.startswith("text/html"):
            return outcome
        body = self._read_quarantine_body(outcome.record)
        if not _HTML_HINT.search(body.decode("utf-8", errors="replace")):
            return CollectionOutcome(
                kind="failure",
                record=self.collector._build_failure(  # noqa: SLF001
                    request,
                    CollectionFailureError("CONTENT_TYPE_REJECTED", "Response body is not HTML"),
                    attempt_count=attempt_count,
                ),
            )
        return outcome

    def _read_quarantine_body(self, result: dict[str, Any]) -> bytes:
        path = self.collector.quarantine_root / str(result["quarantine_path"])
        return path.read_bytes()
