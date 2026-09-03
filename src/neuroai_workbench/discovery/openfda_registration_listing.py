"""Bounded openFDA device registration/listing projection for human-gated discovery."""

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
    "A projected FDA registration/listing representation preserves establishment-registration "
    "and product-category metadata only. FDA registration or listing does not denote approval, "
    "clearance, or authorization. The representation identity is not exact device identity; "
    "K/PMA references, product codes, proprietary names, and establishment identifiers remain "
    "bounded linkage/status evidence requiring explicit human resolution."
)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    rows = {_text(item) for item in value}
    return sorted((item for item in rows if item is not None), key=lambda item: (item.casefold(), item))


def _name_identity_set(names: Sequence[str]) -> list[str]:
    return sorted({name.casefold() for name in names})


def _sha(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _representation_identity(
    registration_number: str,
    owner_operator_number: str,
    product_code: str,
    proprietary_names: Sequence[str],
) -> str:
    name_set_sha256 = _sha(_name_identity_set(proprietary_names)).upper()
    return (
        f"REGLIST:{registration_number.upper()}:{owner_operator_number.upper()}:"
        f"{product_code.upper()}:{name_set_sha256}"
    )


def _candidate_locator(
    registration_number: str,
    owner_operator_number: str,
    product_code: str,
) -> str:
    search = (
        f'registration.registration_number:"{registration_number}"+AND+'
        f'products.owner_operator_number:"{owner_operator_number}"+AND+'
        f'products.product_code:"{product_code}"'
    )
    return "https://api.fda.gov/device/registrationlisting.json?search=" + quote(
        search,
        safe='.:+"',
    )


def _normalize_product(
    raw: Mapping[str, Any],
    product: Mapping[str, Any],
    *,
    query_id: str,
) -> tuple[dict[str, Any] | None, str]:
    registration = raw.get("registration")
    if not isinstance(registration, Mapping):
        registration = {}

    registration_number = _text(registration.get("registration_number"))
    owner_operator_number = _text(product.get("owner_operator_number"))
    product_code = _text(product.get("product_code"))

    if registration_number is None:
        return None, "UNRESOLVED_REGISTRATION_NUMBER"
    if owner_operator_number is None:
        return None, "UNRESOLVED_OWNER_OPERATOR_NUMBER"
    if product_code is None:
        return None, "UNRESOLVED_PRODUCT_CODE"

    openfda = product.get("openfda")
    if not isinstance(openfda, Mapping):
        openfda = {}

    proprietary_names = _string_list(raw.get("proprietary_name"))
    identity = _representation_identity(
        registration_number,
        owner_operator_number,
        product_code,
        proprietary_names,
    )

    normalized: dict[str, Any] = {
        "record_kind": "NORMALIZED_OPENFDA_DEVICE_REGISTRATION_LISTING_REPRESENTATION",
        "representation_identity": identity,
        "registration_number": registration_number,
        "fei_number": _text(registration.get("fei_number")),
        "registration_name": _text(registration.get("name")),
        "registration_status_code": _text(registration.get("status_code")),
        "registration_expiry_year": _text(registration.get("reg_expiry_date_year")),
        "owner_operator_number": owner_operator_number,
        "establishment_type": _string_list(raw.get("establishment_type")),
        "product_code": product_code,
        "product_created_date": _text(product.get("created_date")),
        "product_exempt": _text(product.get("exempt")),
        "device_class": _text(openfda.get("device_class")),
        "device_name": _text(openfda.get("device_name")),
        "regulation_number": _text(openfda.get("regulation_number")),
        "proprietary_names": proprietary_names,
        "k_number": _text(raw.get("k_number")),
        "pma_number": _text(raw.get("pma_number")),
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
    known_representation_sources: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if not isinstance(query_id, str) or not query_id.strip():
        raise ValueError("query_id must be non-empty")
    if not isinstance(search, str) or not search.strip():
        raise ValueError("search must be non-empty")
    if not pages:
        raise ValueError("At least one registration/listing page is required")

    known = {
        str(identity).upper(): str(source_id) for identity, source_id in (known_representation_sources or {}).items()
    }
    totals: list[int] = []
    by_identity: dict[str, dict[str, Any]] = {}
    returned_provider_record_count = 0
    expanded_representation_count = 0
    duplicate_representation_count = 0
    unresolved_registration_number_count = 0
    unresolved_owner_operator_number_count = 0
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
        if (
            not isinstance(meta_results, Mapping)
            or not isinstance(rows, list)
            or not all(isinstance(row, Mapping) for row in rows)
        ):
            raise ValueError(f"page {page_index}: invalid openFDA registration/listing shape")

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
        returned_provider_record_count += len(rows)

        for raw in rows:
            registration = raw.get("registration")
            if not isinstance(registration, Mapping) or _text(registration.get("registration_number")) is None:
                unresolved_registration_number_count += 1

            products = raw.get("products")
            if not isinstance(products, list):
                products = []
            for product in products:
                if not isinstance(product, Mapping):
                    continue
                expanded_representation_count += 1
                normalized, state = _normalize_product(raw, product, query_id=query_id)
                if state == "UNRESOLVED_REGISTRATION_NUMBER":
                    continue
                if state == "UNRESOLVED_OWNER_OPERATOR_NUMBER":
                    unresolved_owner_operator_number_count += 1
                    continue
                if state == "UNRESOLVED_PRODUCT_CODE":
                    unresolved_product_code_count += 1
                    continue
                assert normalized is not None
                identity = normalized["representation_identity"]
                prior = by_identity.get(identity)
                if prior is None:
                    by_identity[identity] = normalized
                else:
                    prior_core = dict(prior)
                    current_core = dict(normalized)
                    prior_core.pop("query_memberships", None)
                    current_core.pop("query_memberships", None)
                    if prior_core != current_core:
                        raise ValueError(f"Conflicting normalized registration/listing representations for {identity}")
                    duplicate_representation_count += 1

        page_reports.append(
            {
                "page_index": page_index,
                "reported_total_count": total,
                "skip": skip,
                "limit": limit,
                "returned_provider_record_count": len(rows),
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
    elif returned_provider_record_count == reported_total:
        skip_coverage_state = "MATCH"
    else:
        skip_coverage_state = "PARTIAL_OR_MISMATCH"

    result_records: list[dict[str, Any]] = []
    normalized_records: list[dict[str, Any]] = []
    known_duplicates: list[dict[str, str]] = []
    if not over_limit:
        for identity in sorted(by_identity):
            normalized = by_identity[identity]
            duplicate_of = known.get(identity.upper())
            title = (
                (normalized.get("proprietary_names") or [None])[0]
                or normalized.get("device_name")
                or normalized.get("registration_name")
                or identity
            )
            record: dict[str, Any] = {
                "record_key": identity,
                "title": title,
                "url": _candidate_locator(
                    normalized["registration_number"],
                    normalized["owner_operator_number"],
                    normalized["product_code"],
                ),
                "publisher": "U.S. FDA",
                "source_class": "OFFICIAL_DEVICE_REGISTRATION_LISTING_RECORD",
                "suggested_source_id": (
                    "SRC-OPENFDA-REGLIST-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16].upper()
                ),
                "classification_hint": "DUPLICATE" if duplicate_of else "NEW",
            }
            if duplicate_of:
                record["duplicate_of_source_id"] = duplicate_of
                known_duplicates.append({"representation_identity": identity, "source_id": duplicate_of})
            result_records.append(record)
            normalized_records.append(normalized)

    coverage = {
        "source_system": "OPENFDA_DEVICE_REGISTRATION_LISTING",
        "query_id": query_id,
        "search_sha256": hashlib.sha256(search.encode("utf-8")).hexdigest(),
        "supplied_page_count": len(pages),
        "returned_provider_record_count": returned_provider_record_count,
        "expanded_representation_count": expanded_representation_count,
        "unique_representation_count": len(by_identity),
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
        "unresolved_registration_number_count": unresolved_registration_number_count,
        "unresolved_owner_operator_number_count": unresolved_owner_operator_number_count,
        "unresolved_product_code_count": unresolved_product_code_count,
        "page_reports": page_reports,
        "representation_identity_is_exact_device_identity": False,
        "registration_or_listing_is_marketing_authorization_claim": False,
        "registration_or_listing_is_clearance_or_approval_claim": False,
        "k_or_pma_reference_is_exact_configuration_authorization_claim": False,
        "product_code_is_exact_device_identity_claim": False,
        "automatic_establishment_entity_creation_performed": False,
        "automatic_owner_operator_entity_creation_performed": False,
        "automatic_device_or_system_entity_creation_performed": False,
        "automatic_registration_relationship_creation_performed": False,
        "automatic_premarket_authorization_relationship_creation_performed": False,
        "automatic_marketing_authorization_claim_creation_performed": False,
        "automatic_clearance_or_approval_claim_creation_performed": False,
        "automatic_current_commercial_availability_claim_creation_performed": False,
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
