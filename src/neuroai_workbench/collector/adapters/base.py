from __future__ import annotations

from typing import Any, Protocol

from ..credentials import refuse_embedded_secrets_in_request, refuse_secrets_in_value
from ..service import CollectionOutcome, HttpCollector, PriorCapture


class CollectorAdapter(Protocol):
    adapter_id: str

    def supports_source_class(self, source_class: str) -> bool: ...

    def resolve_request(
        self,
        request: dict[str, Any],
        *,
        source_record: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    def collect(
        self,
        request: dict[str, Any],
        *,
        prior_capture: PriorCapture | None = None,
        attempt_count: int = 1,
    ) -> CollectionOutcome: ...


class HttpCollectorAdapter:
    adapter_id: str = "http"

    def __init__(self, collector: HttpCollector) -> None:
        self.collector = collector

    def supports_source_class(self, source_class: str) -> bool:
        return True

    def resolve_request(
        self,
        request: dict[str, Any],
        *,
        source_record: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del source_record
        return dict(request)

    def collect(
        self,
        request: dict[str, Any],
        *,
        prior_capture: PriorCapture | None = None,
        attempt_count: int = 1,
    ) -> CollectionOutcome:
        refuse_embedded_secrets_in_request(request)
        outcome = self.collector.collect(
            request,
            prior_capture=prior_capture,
            attempt_count=attempt_count,
        )
        if outcome.kind == "result":
            refuse_secrets_in_value(outcome.record, label="collection result")
        elif outcome.kind == "failure":
            refuse_secrets_in_value(outcome.record, label="collection failure")
        return outcome
