"""Shared helpers for structured source adapters.

Normalized records and field digests support mechanical change detection only.
They do not establish authenticity, completeness, or substantive truth.
"""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

from ...util import canonical_json_bytes, sha256_bytes
from ..errors import CollectionFailureError
from ..schemas import validate_or_raise
from ..service import CollectionOutcome, HttpCollector, PriorCapture
from .base import HttpCollectorAdapter

COLLECTOR_RESOURCE_PACKAGE = "neuroai_workbench.resources.collector"
STRUCTURED_ADAPTER_CONTRACT_SCHEMA = "structured-adapter-contract.schema.json"
NORMALIZED_STUDY_SCHEMA = "normalized-study-record.schema.json"
NORMALIZED_DEVICE_SCHEMA = "normalized-device-record.schema.json"
NORMALIZED_PUBLICATION_SCHEMA = "normalized-publication-record.schema.json"

SCAFFOLD_REFUSAL_MESSAGE = (
    "Adapter completeness is SCAFFOLD_NOT_COMPLETE; live retrieval through this "
    "scaffold is refused. Page capture remains available via the HTML fallback when "
    "applicable. This refusal is not a substantive FAIL finding."
)


def load_adapter_contract(adapter_id: str) -> dict[str, Any]:
    name = f"adapter-contract-{adapter_id}.json"
    payload = json.loads(files(COLLECTOR_RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8"))
    validate_or_raise(payload, STRUCTURED_ADAPTER_CONTRACT_SCHEMA)
    if payload.get("adapter_id") != adapter_id:
        raise ValueError(f"Contract adapter_id mismatch for {adapter_id!r}")
    return payload


def field_digest(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def field_digests_for(mapping: dict[str, Any]) -> dict[str, str]:
    return {key: field_digest(value) for key, value in mapping.items()}


def changed_fields(prior_digests: dict[str, str], current_digests: dict[str, str]) -> list[str]:
    keys = sorted(set(prior_digests) | set(current_digests))
    return [key for key in keys if prior_digests.get(key) != current_digests.get(key)]


def aggregate_digest(field_digest_map: dict[str, str]) -> str:
    return sha256_bytes(canonical_json_bytes(field_digest_map))


class ScaffoldAdapter(HttpCollectorAdapter):
    """Refuse live collection for adapters marked SCAFFOLD_NOT_COMPLETE."""

    adapter_id: str = "scaffold"
    _SOURCE_CLASSES: frozenset[str] = frozenset()

    def __init__(self, collector: HttpCollector) -> None:
        super().__init__(collector)
        self.contract = load_adapter_contract(self.adapter_id)
        if self.contract["completeness"] != "SCAFFOLD_NOT_COMPLETE":
            raise ValueError(f"{self.adapter_id} must declare SCAFFOLD_NOT_COMPLETE")

    def supports_source_class(self, source_class: str) -> bool:
        return source_class in self._SOURCE_CLASSES

    def collect(
        self,
        request: dict[str, Any],
        *,
        prior_capture: PriorCapture | None = None,
        attempt_count: int = 1,
        source_record: dict[str, Any] | None = None,
    ) -> CollectionOutcome:
        _ = prior_capture, source_record
        return CollectionOutcome(
            kind="failure",
            record=self.collector._build_failure(  # noqa: SLF001
                request,
                CollectionFailureError("TERMS_OF_USE_BLOCKED", SCAFFOLD_REFUSAL_MESSAGE),
                attempt_count=attempt_count,
            ),
        )
