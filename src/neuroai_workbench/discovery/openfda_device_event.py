"""Bounded openFDA/MAUDE device-event projection for post-market discovery.

Callers supply already-retrieved openFDA JSON response pages. This module performs no network I/O.
It deliberately projects only selected report/device metadata: patient-level fields, MDR narrative text,
and unrelated raw provider fields are excluded from normalized output and from its digest.

An MDR report establishes only that a report exists in the provider data. It does not establish
causality, incidence, comparative safety, an FDA conclusion, recall/enforcement, system
nonconformance, assessment failure, or canonical authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import quote

OPENFDA_EVENT_ENDPOINT = "https://api.fda.gov/device/event.json"
OPENFDA_MAX_LIMIT = 1000
OPENFDA_MAX_SKIP = 25000
OPENFDA_MAX_DIRECT_RESULTS = 26000

_DEVICE_FIELDS = (
    "brand_name",
    "generic_name",
    "udi_di",
    "device_report_product_code",
    "model_number",
    "manufacturer_d_name",
    "implant_flag",
)

DISCOVERY_BOUNDARY = (
    "openFDA/MAUDE projection establishes only selected metadata for an exact public MDR report "
    "returned by one configured traversal. Report existence or count does not establish device "
    "causation, incidence/prevalence, event-rate change, comparative safety, an FDA conclusion, "
    "recall/enforcement, safety/effectiveness, system nonconformance, assessment effect, global "
    "post-market completeness, or canonical authority."
)


def _canonical_sha(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _safe(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _safe(item) for key, item in value.items()}
    raise ValueError(f"Unsupported openFDA metadata type {type(value).__name__}")


def _mdr_report_key(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        raise ValueError("openFDA mdr_report_key must be a non-empty string/integer identity")
    if isinstance(value, int):
        if value <= 0:
            raise ValueError("openFDA mdr_report_key integer must be positive")
        return str(value)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ValueError("openFDA mdr_report_key must be a non-empty string/integer identity")


def _normalize_devices(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("openFDA device must be an array when present")
    normalized: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, Mapping):
            raise ValueError("openFDA device entries must be objects")
        normalized.append({field: _safe(raw.get(field)) for field in _DEVICE_FIELDS})
    return normalized


def _normalize_record(raw: Mapping[str, Any], *, query_id: str) -> dict[str, Any]:
    key = _mdr_report_key(raw.get("mdr_report_key"))
    normalized: dict[str, Any] = {
        "record_kind": "NORMALIZED_OPENFDA_MAUDE_DEVICE_EVENT_REPORT",
        "mdr_report_key": key,
        "report_number": _text(raw.get("report_number")),
        "date_received": _safe(raw.get("date_received")),
        "report_date": _safe(raw.get("report_date")),
        "event_type": _safe(raw.get("event_type")),
        "product_problems": _safe(raw.get("product_problems")),
        "source_type": _safe(raw.get("source_type")),
        "remedial_action": _safe(raw.get("remedial_action")),
        "removal_correction_number": _safe(raw.get("removal_correction_number")),
        "devices": _normalize_devices(raw.get("device")),
        "query_memberships": [query_id],
        "patient_level_fields_included": False,
        "mdr_text_narrative_included": False,
        "boundary": (
            "Selected report/device metadata only. Patient data and MDR narrative text are excluded. "
            "Device/manufacturer names and identifiers remain unresolved metadata until separate review."
        ),
    }
    digest_input = dict(normalized)
    digest_input.pop("query_memberships", None)
    normalized["normalized_record_sha256"] = _canonical_sha(digest_input)
    return normalized


def _known_index(values: Mapping[str | int, str] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_key, raw_source in (values or {}).items():
        key = _mdr_report_key(raw_key)
        source_id = _text(raw_source)
        if source_id is None:
            raise ValueError(f"Controlled Source for MDR report {key} must be non-empty")
        prior = result.get(key)
        if prior is not None and prior != source_id:
            raise ValueError(f"Conflicting controlled Sources for MDR report {key}")
        result[key] = source_id
    return result


def _page_payload(raw: Mapping[str, Any], index: int) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    payload = raw.get("payload") if isinstance(raw, Mapping) and "payload" in raw else raw
    if not isinstance(payload, Mapping):
        raise ValueError(f"page {index}: payload must be object")
    meta = payload.get("meta")
    results = payload.get("results")
    if not isinstance(meta, Mapping):
        raise ValueError(f"page {index}: meta must be object")
    meta_results = meta.get("results")
    if not isinstance(meta_results, Mapping):
        raise ValueError(f"page {index}: meta.results must be object")
    if not isinstance(results, list) or not all(isinstance(row, dict) for row in results):
        raise ValueError(f"page {index}: results must be an object array")
    return dict(payload), dict(meta_results), [dict(row) for row in results]


def _suggested_source_id(key: str) -> str:
    token = re.sub(r"[^A-Za-z0-9]+", "-", key).strip("-")
    if not token:
        token = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    if len(token) > 48:
        token = f"{token[:31]}-{hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]}"
    return f"SRC-MAUDE-MDR-{token}"


def _exact_report_url(key: str) -> str:
    return f'{OPENFDA_EVENT_ENDPOINT}?search=mdr_report_key:"{quote(key, safe="")}"&limit=1'


def project_search_pages(
    *,
    query_id: str,
    search: str,
    pages: Sequence[Mapping[str, Any]],
    known_mdr_sources: Mapping[str | int, str] | None = None,
) -> dict[str, Any]:
    """Project supplied openFDA device-event pages into human-review candidate records."""
    if not isinstance(query_id, str) or not query_id.strip():
        raise ValueError("query_id must be non-empty")
    if not isinstance(search, str) or not search.strip():
        raise ValueError("search must be non-empty")
    if not pages:
        raise ValueError("At least one openFDA page is required")
    known = _known_index(known_mdr_sources)

    totals: list[int] = []
    page_reports: list[dict[str, Any]] = []
    by_key: dict[str, dict[str, Any]] = {}
    raw_count = 0
    duplicate_count = 0
    previous_skip: int | None = None
    previous_limit: int | None = None
    sequence_valid = True

    for index, raw_page in enumerate(pages, start=1):
        _, meta, rows = _page_payload(raw_page, index)
        total = meta.get("total")
        skip = meta.get("skip")
        limit = meta.get("limit")
        if not isinstance(total, int) or isinstance(total, bool) or total < 0:
            raise ValueError(f"page {index}: meta.results.total must be non-negative integer")
        if not isinstance(skip, int) or isinstance(skip, bool) or skip < 0 or skip > OPENFDA_MAX_SKIP:
            raise ValueError(f"page {index}: meta.results.skip outside 0..{OPENFDA_MAX_SKIP}")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1 or limit > OPENFDA_MAX_LIMIT:
            raise ValueError(f"page {index}: meta.results.limit outside 1..{OPENFDA_MAX_LIMIT}")
        totals.append(total)
        if index == 1 and skip != 0:
            sequence_valid = False
        if previous_skip is not None and previous_limit is not None and skip != previous_skip + previous_limit:
            sequence_valid = False
        previous_skip, previous_limit = skip, limit
        raw_count += len(rows)

        keys_on_page: list[str] = []
        for raw_record in rows:
            normalized = _normalize_record(raw_record, query_id=query_id)
            key = normalized["mdr_report_key"]
            keys_on_page.append(key)
            prior = by_key.get(key)
            if prior is None:
                by_key[key] = normalized
            else:
                prior_content = dict(prior)
                current_content = dict(normalized)
                prior_content.pop("query_memberships", None)
                current_content.pop("query_memberships", None)
                if prior_content != current_content:
                    raise ValueError(f"Conflicting normalized openFDA representations for mdr_report_key {key}")
                duplicate_count += 1

        page_reports.append(
            {
                "page_index": index,
                "reported_total_count": total,
                "skip": skip,
                "limit": limit,
                "returned_record_count": len(rows),
                "unique_mdr_report_keys_on_page": len(set(keys_on_page)),
            }
        )

    distinct_totals = sorted(set(totals))
    if len(distinct_totals) == 1:
        total_state = "CONSISTENT"
        reported_total: int | None = distinct_totals[0]
    else:
        total_state = "INCONSISTENT_ACROSS_PAGES"
        reported_total = None

    over_limit = reported_total is not None and reported_total > OPENFDA_MAX_DIRECT_RESULTS
    required = over_limit
    if reported_total is None:
        coverage_state = "DENOMINATOR_UNAVAILABLE"
    elif over_limit:
        coverage_state = "OVER_LIMIT_SEARCH_AFTER_OR_PARTITION_REQUIRED"
    elif not sequence_valid:
        coverage_state = "INVALID_SEQUENCE"
    elif len(by_key) == reported_total:
        coverage_state = "MATCH"
    else:
        coverage_state = "PARTIAL_OR_MISMATCH"

    result_records: list[dict[str, Any]] = []
    normalized_records: list[dict[str, Any]] = []
    known_duplicates: list[dict[str, Any]] = []
    if not over_limit:
        for key in sorted(by_key):
            normalized = by_key[key]
            duplicate_of = known.get(key)
            record: dict[str, Any] = {
                "record_key": f"MAUDE:MDR:{key}",
                "title": f"MAUDE device adverse-event report {key}",
                "url": _exact_report_url(key),
                "publisher": "U.S. FDA / openFDA",
                "source_class": "OFFICIAL_REGULATORY_POSTMARKET_REPORT",
                "suggested_source_id": _suggested_source_id(key),
                "classification_hint": "DUPLICATE" if duplicate_of is not None else "NEW",
            }
            if duplicate_of is not None:
                record["duplicate_of_source_id"] = duplicate_of
                known_duplicates.append({"mdr_report_key": key, "source_id": duplicate_of})
            result_records.append(record)
            normalized_records.append(normalized)

    coverage = {
        "source_system": "OPENFDA_DEVICE_EVENT",
        "query_id": query_id,
        "search_sha256": hashlib.sha256(search.encode("utf-8")).hexdigest(),
        "supplied_page_count": len(pages),
        "returned_record_count": raw_count,
        "unique_mdr_report_key_count": len(by_key),
        "reported_total_count": reported_total,
        "reported_total_count_state": total_state,
        "reported_total_count_values": distinct_totals,
        "skip_sequence_valid": sequence_valid,
        "skip_coverage_state": coverage_state,
        "over_26000_limit": over_limit,
        "search_after_or_partition_required": required,
        "candidate_emission_refused_due_to_over_limit": over_limit,
        "known_controlled_duplicate_count": len(known_duplicates),
        "known_controlled_duplicates": known_duplicates,
        "new_candidate_count": len(result_records) - len(known_duplicates),
        "duplicate_representation_count": duplicate_count,
        "unresolved_mdr_report_key_count": 0,
        "page_reports": page_reports,
        "patient_level_fields_projected": False,
        "mdr_text_narrative_projected": False,
        "maude_database_completeness_claim": False,
        "global_neuroai_postmarket_recall_claim": False,
        "query_recall_claim": False,
        "causality_claim": False,
        "incidence_or_rate_claim": False,
        "comparative_safety_claim": False,
        "automatic_source_admission_performed": False,
        "automatic_system_or_device_entity_creation_performed": False,
        "automatic_manufacturer_entity_creation_performed": False,
        "automatic_safety_signal_creation_performed": False,
        "automatic_regulatory_action_creation_performed": False,
        "automatic_assessment_mutation_performed": False,
        "boundary": DISCOVERY_BOUNDARY,
    }
    return {"result_records": result_records, "normalized_records": normalized_records, "coverage": coverage}
