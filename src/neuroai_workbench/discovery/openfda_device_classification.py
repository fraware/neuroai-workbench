"""Bounded openFDA device-classification projection for human-gated discovery."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import quote

MAX_LIMIT = 1000
MAX_SKIP = 25000
MAX_DIRECT = 26000
BOUNDARY = (
    "A projected FDA Product Classification record preserves generic device-category metadata "
    "keyed by exact FDA product code. Product code and device name identify a generic category, "
    "not an exact commercial device or system. If no regulation number is referenced, the listed "
    "device class is proposed rather than final. Classification context does not itself establish "
    "marketing authorization, clearance or approval, exact device identity, system conformance, "
    "assessment effect, or canonical authority."
)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _sha(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _candidate_locator(product_code: str) -> str:
    search = f'product_code:"{product_code}"'
    return "https://api.fda.gov/device/classification.json?search=" + quote(
        search,
        safe=".:+\"",
    )


def _normalize_record(
    raw: Mapping[str, Any],
    *,
    query_id: str,
) -> tuple[dict[str, Any] | None, str]:
    product_code = _text(raw.get("product_code"))
    if product_code is None:
        return None, "UNRESOLVED_PRODUCT_CODE"

    product_code = product_code.upper()
    regulation_number = _text(raw.get("regulation_number"))
    classification_finality = (
        "REGULATION_REFERENCED_CLASSIFICATION"
        if regulation_number is not None
        else "PROPOSED_CLASS_NOT_FINAL"
    )

    normalized: dict[str, Any] = {
        "record_kind": "NORMALIZED_OPENFDA_DEVICE_CLASSIFICATION_RECORD",
        "record_identity": product_code,
        "product_code": product_code,
        "device_name": _text(raw.get("device_name")),
        "definition": _text(raw.get("definition")),
        "device_class": _text(raw.get("device_class")),
        "classification_finality": classification_finality,
        "regulation_number": regulation_number,
        "medical_specialty": _text(raw.get("medical_specialty")),
        "medical_specialty_description": _text(raw.get("medical_specialty_description")),
        "review_code": _text(raw.get("review_code")),
        "implant_flag": _text(raw.get("implant_flag")),
        "life_sustain_support_flag": _text(raw.get("life_sustain_support_flag")),
        "gmp_exempt_flag": _text(raw.get("gmp_exempt_flag")),
        "query_memberships": [query_id],
        "boundary": BOUNDARY,
    }
    core = dict(normalized)
    core.pop("query_memberships")
    normalized["normalized_record_sha256"] = _sha(core)
    return normalized, "VALID"


def project_search_pages(
    *,
    query_id: str,
    search: str,
    pages: Sequence[Mapping[str, Any]],
    known_product_code_sources: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if not isinstance(query_id, str) or not query_id.strip():
        raise ValueError("query_id must be non-empty")
    if not isinstance(search, str) or not search.strip():
        raise ValueError("search must be non-empty")
    if not pages:
        raise ValueError("At least one device-classification page is required")

    known = {
        str(product_code).upper(): str(source_id)
        for product_code, source_id in (known_product_code_sources or {}).items()
    }
    totals: list[int] = []
    by_product_code: dict[str, dict[str, Any]] = {}
    returned_record_count = 0
    duplicate_representation_count = 0
    unresolved_product_code_count = 0
    sequence_valid = True
    previous_skip: int | None = None
    previous_limit: int | None = None
    page_reports: list[dict[str, Any]] = []

    for page_index, raw_page in enumerate(pages, start=1):
        payload = raw_page.get("payload") if isinstance(raw_page, Mapping) and "payload" in raw_page else raw_page
        if not isinstance(payload, Mapping):
            raise ValueError(f"page {page_index}: payload must be object")
        meta = payload.get("meta")
        meta_results = meta.get("results") if isinstance(meta, Mapping) else None
        rows = payload.get("results")
        if not isinstance(meta_results, Mapping) or not isinstance(rows, list) or not all(isinstance(row, Mapping) for row in rows):
            raise ValueError(f"page {page_index}: invalid openFDA device-classification shape")

        total = meta_results.get("total")
        skip = meta_results.get("skip")
        limit = meta_results.get("limit")
        if not isinstance(total, int) or isinstance(total, bool) or total < 0:
            raise ValueError(f"page {page_index}: total invalid")
        if not isinstance(skip, int) or isinstance(skip, bool) or not 0 <= skip <= MAX_SKIP:
            raise ValueError(f"page {page_index}: skip invalid")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_LIMIT:
            raise ValueError(f"page {page_index}: limit invalid")
        if page_index == 1 and skip != 0:
            sequence_valid = False
        if previous_skip is not None and previous_limit is not None and skip != previous_skip + previous_limit:
            sequence_valid = False
        previous_skip, previous_limit = skip, limit
        totals.append(total)
        returned_record_count += len(rows)

        for raw in rows:
            normalized, state = _normalize_record(raw, query_id=query_id)
            if state == "UNRESOLVED_PRODUCT_CODE":
                unresolved_product_code_count += 1
                continue
            assert normalized is not None
            identity = normalized["record_identity"]
            prior = by_product_code.get(identity)
            if prior is None:
                by_product_code[identity] = normalized
            else:
                prior_core = dict(prior)
                current_core = dict(normalized)
                prior_core.pop("query_memberships", None)
                current_core.pop("query_memberships", None)
                if prior_core != current_core:
                    raise ValueError(
                        "Conflicting normalized device-classification records "
                        f"for product code {identity}"
                    )
                duplicate_representation_count += 1

        page_reports.append(
            {
                "page_index": page_index,
                "reported_total_count": total,
                "skip": skip,
                "limit": limit,
                "returned_record_count": len(rows),
            }
        )

    distinct_totals = sorted(set(totals))
    reported_total = distinct_totals[0] if len(distinct_totals) == 1 else None
    reported_total_state = "CONSISTENT" if reported_total is not None else "INCONSISTENT_ACROSS_PAGES"
    over_limit = reported_total is not None and reported_total > MAX_DIRECT

    if reported_total is None:
        skip_coverage_state = "DENOMINATOR_UNAVAILABLE"
    elif over_limit:
        skip_coverage_state = "OVER_LIMIT_BULK_OR_PARTITION_REQUIRED"
    elif not sequence_valid:
        skip_coverage_state = "INVALID_SEQUENCE"
    elif returned_record_count == reported_total:
        skip_coverage_state = "MATCH"
    else:
        skip_coverage_state = "PARTIAL_OR_MISMATCH"

    result_records: list[dict[str, Any]] = []
    normalized_records: list[dict[str, Any]] = []
    known_duplicates: list[dict[str, str]] = []
    if not over_limit:
        for identity in sorted(by_product_code):
            normalized = by_product_code[identity]
            duplicate_of = known.get(identity.upper())
            title = normalized.get("device_name") or f"FDA product code {identity}"
            record: dict[str, Any] = {
                "record_key": identity,
                "title": title,
                "url": _candidate_locator(identity),
                "publisher": "U.S. FDA",
                "source_class": "OFFICIAL_DEVICE_CLASSIFICATION_RECORD",
                "suggested_source_id": (
                    "SRC-OPENFDA-CLASS-"
                    + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16].upper()
                ),
                "classification_hint": "DUPLICATE" if duplicate_of else "NEW",
            }
            if duplicate_of:
                record["duplicate_of_source_id"] = duplicate_of
                known_duplicates.append({"product_code": identity, "source_id": duplicate_of})
            result_records.append(record)
            normalized_records.append(normalized)

    regulation_referenced_classification_count = sum(
        row["classification_finality"] == "REGULATION_REFERENCED_CLASSIFICATION"
        for row in by_product_code.values()
    )
    proposed_not_final_classification_count = sum(
        row["classification_finality"] == "PROPOSED_CLASS_NOT_FINAL"
        for row in by_product_code.values()
    )

    coverage = {
        "source_system": "OPENFDA_DEVICE_CLASSIFICATION",
        "query_id": query_id,
        "search_sha256": hashlib.sha256(search.encode("utf-8")).hexdigest(),
        "supplied_page_count": len(pages),
        "returned_record_count": returned_record_count,
        "unique_product_code_count": len(by_product_code),
        "reported_total_count": reported_total,
        "reported_total_count_state": reported_total_state,
        "skip_sequence_valid": sequence_valid,
        "skip_coverage_state": skip_coverage_state,
        "over_26000_limit": over_limit,
        "bulk_download_or_partition_required": over_limit,
        "known_controlled_duplicate_count": len(known_duplicates),
        "known_controlled_duplicates": known_duplicates,
        "new_candidate_count": len(result_records) - len(known_duplicates),
        "duplicate_representation_count": duplicate_representation_count,
        "unresolved_product_code_count": unresolved_product_code_count,
        "regulation_referenced_classification_count": regulation_referenced_classification_count,
        "proposed_not_final_classification_count": proposed_not_final_classification_count,
        "page_reports": page_reports,
        "product_code_is_exact_device_identity_claim": False,
        "classification_record_is_marketing_authorization_claim": False,
        "classification_record_is_clearance_or_approval_claim": False,
        "device_class_is_system_conformance_claim": False,
        "automatic_source_admission_performed": False,
        "automatic_device_or_system_entity_creation_performed": False,
        "automatic_product_code_relationship_creation_performed": False,
        "automatic_regulation_relationship_creation_performed": False,
        "automatic_marketing_authorization_claim_creation_performed": False,
        "automatic_clearance_or_approval_claim_creation_performed": False,
        "automatic_exact_device_identity_claim_creation_performed": False,
        "automatic_system_conformance_claim_creation_performed": False,
        "automatic_reopening_decision_performed": False,
        "automatic_assessment_mutation_performed": False,
        "boundary": BOUNDARY,
    }
    return {
        "result_records": result_records,
        "normalized_records": normalized_records,
        "coverage": coverage,
    }
