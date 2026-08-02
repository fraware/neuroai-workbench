from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from ..errors import CollectionFailureError
from ..service import CollectionOutcome, HttpCollector, PriorCapture
from .base import HttpCollectorAdapter

_FEED_ROOTS = frozenset(
    {
        "rss",
        "{http://www.w3.org/2005/Atom}feed",
        "feed",
    }
)


class XmlFeedAdapter(HttpCollectorAdapter):
    adapter_id = "xml_feed"

    _SOURCE_CLASSES = frozenset(
        {
            "RSS_FEED",
            "ATOM_FEED",
            "XML_FEED",
            "OFFICIAL_REGULATOR_PROCEDURAL_GUIDANCE",
        }
    )

    def __init__(self, collector: HttpCollector) -> None:
        super().__init__(collector)

    def supports_source_class(self, source_class: str) -> bool:
        if source_class in self._SOURCE_CLASSES:
            return True
        return any(token in source_class for token in ("RSS", "ATOM", "XML"))

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
        body = self._read_quarantine_body(outcome.record)
        try:
            root = ET.fromstring(body)
        except ET.ParseError as exc:
            return CollectionOutcome(
                kind="failure",
                record=self.collector._build_failure(  # noqa: SLF001
                    request,
                    CollectionFailureError("CONTENT_TYPE_REJECTED", f"Response body is not valid XML: {exc}"),
                    attempt_count=attempt_count,
                ),
            )
        tag = root.tag
        if tag not in _FEED_ROOTS and not tag.endswith("}feed") and tag != "rss":
            return CollectionOutcome(
                kind="failure",
                record=self.collector._build_failure(  # noqa: SLF001
                    request,
                    CollectionFailureError(
                        "CONTENT_TYPE_REJECTED",
                        f"XML root element {tag!r} is not RSS, Atom, or generic XML feed",
                    ),
                    attempt_count=attempt_count,
                ),
            )
        return outcome

    def _read_quarantine_body(self, result: dict[str, Any]) -> bytes:
        path = self.collector.quarantine_root / str(result["quarantine_path"])
        return path.read_bytes()
