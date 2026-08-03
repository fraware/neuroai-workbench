"""FDA device record adapter for explicit PMA/HDE/De Novo/510(k) identifiers.

Rewrites identifier-bearing sources to reviewed openFDA device endpoints and
emits normalized pathway-linked records. Does not imply completeness of the
adverse-event or recall universe. Capture proves retrieval only.
"""

from __future__ import annotations

import re
from typing import Any, Literal
from urllib.parse import parse_qs, quote, urlparse

from ..schemas import validate_or_raise
from ..service import CollectionOutcome, HttpCollector, PriorCapture
from .base import HttpCollectorAdapter
from .structured import (
    NORMALIZED_DEVICE_SCHEMA,
    aggregate_digest,
    changed_fields,
    field_digests_for,
    load_adapter_contract,
)

FDA_DEVICE_ADAPTER_ID = "fda_device"
OPENFDA_BASE = "https://api.fda.gov"
_DENOVO_RE = re.compile(r"\bDEN\d{6}\b", re.I)
_PMA_RE = re.compile(r"\bP\d{6}\b", re.I)
_HDE_RE = re.compile(r"\bH\d{6}\b", re.I)
_K_RE = re.compile(r"\bK\d{6}\b", re.I)

Pathway = Literal["510K", "DENOVO", "PMA", "HDE"]

DEVICE_BOUNDARY = (
    "Normalized FDA device projection for pathway linkage and mechanical field-change "
    "detection only. Does not establish regulatory authorization or completeness of "
    "MAUDE/recall corpora."
)

_CHANGE_FIELD_KEYS = (
    "device_id",
    "pathway",
    "applicant",
    "decision_date",
    "product_code",
    "device_name",
)


def classify_device_id(device_id: str) -> Pathway:
    upper = device_id.upper()
    if upper.startswith("DEN"):
        return "DENOVO"
    if upper.startswith("K"):
        return "510K"
    if upper.startswith("H"):
        return "HDE"
    if upper.startswith("P"):
        return "PMA"
    raise ValueError(f"Unrecognized FDA device identifier: {device_id!r}")


def openfda_endpoint_for(pathway: Pathway) -> str:
    if pathway in {"510K", "DENOVO"}:
        return "device/510k"
    return "device/pma"


def openfda_search_field(pathway: Pathway) -> str:
    if pathway in {"510K", "DENOVO"}:
        return "k_number"
    if pathway == "HDE":
        return "pma_number"
    return "pma_number"


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
        self.contract = load_adapter_contract(FDA_DEVICE_ADAPTER_ID)

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
                for key in ("fda_device_id", "knumber", "pmanumber", "k_number", "pma_number"):
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

    def build_openfda_url(self, device_id: str) -> str:
        pathway = classify_device_id(device_id)
        endpoint = openfda_endpoint_for(pathway)
        field = openfda_search_field(pathway)
        # Quote identifier; openFDA accepts exact match search expressions.
        expression = quote(f'{field}:"{device_id.upper()}"', safe="")
        return f"{OPENFDA_BASE}/{endpoint}.json?search={expression}&limit=1"

    def pathway_linkage(self, device_id: str) -> dict[str, Any]:
        pathway = classify_device_id(device_id)
        return {
            "device_id": device_id.upper(),
            "pathway": pathway,
            "openfda_endpoint": openfda_endpoint_for(pathway),
            "search_field": openfda_search_field(pathway),
            "related_pathways": ["510K", "DENOVO", "PMA", "HDE"],
            "boundary": (
                "Pathway classification is identifier-prefix based. It does not prove "
                "regulatory status or cross-pathway completeness."
            ),
        }

    def supports_source(self, source_record: dict[str, Any], request: dict[str, Any] | None = None) -> bool:
        if not self.supports_source_class(str(source_record.get("source_class", ""))):
            return False
        synthetic_request = request or {"requested_url": source_record.get("url", "")}
        return self.extract_device_id(source_record, synthetic_request) is not None

    def normalize_device(self, openfda_payload: dict[str, Any], *, device_id: str) -> dict[str, Any]:
        pathway = classify_device_id(device_id)
        results = openfda_payload.get("results")
        row: dict[str, Any] = {}
        if isinstance(results, list) and results and isinstance(results[0], dict):
            row = results[0]

        applicant = row.get("applicant") if isinstance(row.get("applicant"), str) else None
        decision_date = None
        for key in ("decision_date", "date_received", "decision_date_formatted"):
            value = row.get(key)
            if isinstance(value, str):
                decision_date = value
                break
        product_code = row.get("product_code") if isinstance(row.get("product_code"), str) else None
        device_name = None
        for key in ("device_name", "generic_name", "trade_name"):
            value = row.get(key)
            if isinstance(value, str):
                device_name = value
                break

        linked: list[dict[str, str]] = [{"identifier": device_id.upper(), "relationship": "SAME_RECORD"}]
        for key, relationship in (
            ("k_number", "DECLARED_LINK"),
            ("pma_number", "DECLARED_LINK"),
            ("supplement_number", "SUPPLEMENT"),
        ):
            value = row.get(key)
            if isinstance(value, str) and value.upper() != device_id.upper():
                linked.append({"identifier": value.upper(), "relationship": relationship})

        fields = {
            "device_id": device_id.upper(),
            "pathway": pathway,
            "applicant": applicant,
            "decision_date": decision_date,
            "product_code": product_code,
            "device_name": device_name,
        }
        digests = field_digests_for({key: fields[key] for key in _CHANGE_FIELD_KEYS})
        record = {
            "record_kind": "NORMALIZED_FDA_DEVICE",
            **fields,
            "openfda_endpoint": openfda_endpoint_for(pathway),
            "linked_identifiers": linked,
            "field_digests": digests,
            "aggregate_digest": aggregate_digest(digests),
            "boundary": DEVICE_BOUNDARY,
        }
        validate_or_raise(record, NORMALIZED_DEVICE_SCHEMA)
        return record

    def compare_normalized_devices(
        self,
        prior: dict[str, Any],
        current: dict[str, Any],
    ) -> dict[str, Any]:
        prior_digests = prior.get("field_digests")
        current_digests = current.get("field_digests")
        if not isinstance(prior_digests, dict) or not isinstance(current_digests, dict):
            raise ValueError("Normalized device records require field_digests")
        changed = changed_fields(
            {str(k): str(v) for k, v in prior_digests.items()},
            {str(k): str(v) for k, v in current_digests.items()},
        )
        return {
            "device_id": current.get("device_id"),
            "changed_fields": changed,
            "unchanged": len(changed) == 0,
            "prior_aggregate_digest": prior.get("aggregate_digest"),
            "current_aggregate_digest": current.get("aggregate_digest"),
            "boundary": (
                "Field-level comparison of normalized digests only; unchanged digests do not "
                "prove substantive regulatory stability."
            ),
        }

    def collect(
        self,
        request: dict[str, Any],
        *,
        prior_capture: PriorCapture | None = None,
        attempt_count: int = 1,
        source_record: dict[str, Any] | None = None,
    ) -> CollectionOutcome:
        device_id = self.extract_device_id(source_record, request)
        if device_id is None:
            return super().collect(request, prior_capture=prior_capture, attempt_count=attempt_count)
        rewritten = {**request, "requested_url": self.build_openfda_url(device_id)}
        return super().collect(rewritten, prior_capture=prior_capture, attempt_count=attempt_count)
