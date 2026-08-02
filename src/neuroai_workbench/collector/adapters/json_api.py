from __future__ import annotations

import json
from typing import Any

from ..errors import CollectionFailureError
from ..service import CollectionOutcome, HttpCollector, PriorCapture
from .base import HttpCollectorAdapter


class JsonApiAdapter(HttpCollectorAdapter):
    adapter_id = "json_api"

    _SOURCE_CLASSES = frozenset(
        {
            "PUBLIC_JSON_API",
            "OFFICIAL_BIBLIOGRAPHIC_METADATA",
        }
    )

    def __init__(self, collector: HttpCollector) -> None:
        super().__init__(collector)

    def supports_source_class(self, source_class: str) -> bool:
        if source_class in self._SOURCE_CLASSES:
            return True
        return "API" in source_class or source_class.endswith("_JSON")

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
            json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return CollectionOutcome(
                kind="failure",
                record=self.collector._build_failure(  # noqa: SLF001
                    request,
                    CollectionFailureError("CONTENT_TYPE_REJECTED", f"Response body is not valid JSON: {exc}"),
                    attempt_count=attempt_count,
                ),
            )
        return outcome

    def _read_quarantine_body(self, result: dict[str, Any]) -> bytes:
        path = self.collector.quarantine_root / str(result["quarantine_path"])
        return path.read_bytes()
