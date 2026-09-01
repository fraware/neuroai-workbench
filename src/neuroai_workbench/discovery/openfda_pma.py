"""Bounded openFDA PMA projection for human-gated discovery."""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

MAX_LIMIT = 1000
MAX_SKIP = 25000
MAX_DIRECT = 26000
ORIGINAL_SENTINEL = "ORIGINAL"
PMA_RE = re.compile(r"^(?:BP|P|D)[A-Z0-9._-]+$", re.I)
HDE_RE = re.compile(r"^H[A-Z0-9._-]+$", re.I)
LEGACY_NDA_RE = re.compile(r"^N[A-Z0-9._-]+$", re.I)
DECISION_MAP = {
    "APPR": "APPROVAL_RECORDED",
    "WTDR": "WITHDRAWAL_RECORDED",
    "DENY": "DENIAL_RECORDED",
    "LE30": "THIRTY_DAY_NOTICE_ACCEPTANCE_RECORDED",
    "APRL": "RECLASSIFICATION_AFTER_APPROVAL_RECORDED",
    "APWD": "WITHDRAWAL_AFTER_APPROVAL_RECORDED",
    "GT30": "NO_DECISION_WITHIN_30_DAYS_RECORDED",
    "APCV": "CONVERSION_AFTER_APPROVAL_RECORDED",
}
BOUNDARY = (
    "A projected PMA record preserves exact FDA application/supplement decision metadata. "
    "Only APPR creates APPROVAL_RECORDED for that exact record; supplements do not rewrite the original "
    "application. Projection does not establish global authorization, exact current commercial configuration, "
    "all-configuration conformance, automatic assessment reopening, or canonical authority."
)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, Mapping):
        return {str(k): _safe(v) for k, v in sorted(value.items(), key=lambda pair: str(pair[0]))}
    return str(value)


def _sha(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _pma_scope(value: Any) -> tuple[str, str]:
    pma = (_text(value) or "").upper()
    if not pma:
        return "", "UNRESOLVED"
    if HDE_RE.fullmatch(pma):
        return pma, "HDE_OUT_OF_SCOPE"
    if LEGACY_NDA_RE.fullmatch(pma):
        return pma, "LEGACY_NDA_OUT_OF_SCOPE"
    if PMA_RE.fullmatch(pma):
        return pma, "PMA"
    return pma, "UNRESOLVED"


def _supplement(value: Any) -> str:
    return (_text(value) or ORIGINAL_SENTINEL).upper()


def _record_identity(pma_number: str, supplement_number: str) -> str:
    return f"PMA:{pma_number}:{supplement_number}"


def _decision(code: Any) -> dict[str, Any]:
    normalized = (_text(code) or "").upper()
    semantics = DECISION_MAP.get(normalized, "UNRESOLVED_DECISION_CODE")
    return {
        "decision_code": normalized or None,
        "decision_semantics": semantics,
        "decision_code_recognized": normalized in DECISION_MAP,
        "decision_supports_approval": normalized == "APPR",
    }


def _normalize(raw: Mapping[str, Any], query_id: str) -> tuple[dict[str, Any] | None, str]:
    pma_number, scope = _pma_scope(raw.get("pma_number"))
    if scope != "PMA":
        return None, scope
    supplement_number = _supplement(raw.get("supplement_number"))
    decision = _decision(raw.get("decision_code"))
    record_role = "ORIGINAL_APPLICATION" if supplement_number == ORIGINAL_SENTINEL else "SUPPLEMENT"
    normalized: dict[str, Any] = {
        "record_kind": "NORMALIZED_OPENFDA_PMA_DECISION",
        "pma_number": pma_number,
        "supplement_number": supplement_number,
        "record_identity": _record_identity(pma_number, supplement_number),
        "record_role": record_role,
        "trade_name": _text(raw.get("trade_name")),
        "generic_name": _text(raw.get("generic_name")),
        "applicant": _text(raw.get("applicant")),
        "date_received": _safe(raw.get("date_received")),
        "decision_date": _safe(raw.get("decision_date")),
        "decision_code": decision["decision_code"],
        "decision_semantics": decision["decision_semantics"],
        "decision_code_recognized": decision["decision_code_recognized"],
        "decision_supports_approval": decision["decision_supports_approval"],
        "product_code": _text(raw.get("product_code")),
        "supplement_type": _text(raw.get("supplement_type")),
        "supplement_reason": _text(raw.get("supplement_reason")),
        "ao_statement": _text(raw.get("ao_statement")),
        "expedited_review_flag": _safe(raw.get("expedited_review_flag")),
        "query_memberships": [query_id],
        "boundary": (
            "PMA original/supplement identity and exact FDA decision state are preserved. "
            "Trade name, applicant, product code, supplement metadata and approval state do not resolve the exact "
            "current commercial configuration or broader system conformance automatically."
        ),
    }
    core = dict(normalized)
    core.pop("query_memberships", None)
    normalized["normalized_record_sha256"] = _sha(core)
    return normalized, scope


def project_search_pages(
    *,
    query_id: str,
    search: str,
    pages: Sequence[Mapping[str, Any]],
    known_record_sources: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if not isinstance(query_id, str) or not query_id.strip():
        raise ValueError("query_id must be non-empty")
    if not isinstance(search, str) or not search.strip():
        raise ValueError("search must be non-empty")
    if not pages:
        raise ValueError("At least one PMA page is required")

    known = {str(key).upper(): str(value) for key, value in (known_record_sources or {}).items()}
    totals: list[int] = []
    by_identity: dict[str, dict[str, Any]] = {}
    page_reports: list[dict[str, Any]] = []
    raw_count = 0
    duplicate_count = 0
    hde_count = 0
    legacy_nda_count = 0
    unresolved_count = 0
    sequence_valid = True
    previous_skip: int | None = None
    previous_limit: int | None = None

    for index, raw_page in enumerate(pages, start=1):
        payload = raw_page.get("payload") if isinstance(raw_page, Mapping) and "payload" in raw_page else raw_page
        if not isinstance(payload, Mapping):
            raise ValueError(f"page {index}: payload must be object")
        meta = payload.get("meta")
        meta_results = meta.get("results") if isinstance(meta, Mapping) else None
        rows = payload.get("results")
        if not isinstance(meta_results, Mapping) or not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise ValueError(f"page {index}: invalid openFDA PMA shape")
        total, skip, limit = meta_results.get("total"), meta_results.get("skip"), meta_results.get("limit")
        if not isinstance(total, int) or isinstance(total, bool) or total < 0:
            raise ValueError(f"page {index}: total invalid")
        if not isinstance(skip, int) or isinstance(skip, bool) or not 0 <= skip <= MAX_SKIP:
            raise ValueError(f"page {index}: skip invalid")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_LIMIT:
            raise ValueError(f"page {index}: limit invalid")
        if index == 1 and skip != 0:
            sequence_valid = False
        if previous_skip is not None and previous_limit is not None and skip != previous_skip + previous_limit:
            sequence_valid = False
        previous_skip, previous_limit = skip, limit
        totals.append(total)
        raw_count += len(rows)

        for raw in rows:
            normalized, scope = _normalize(raw, query_id)
            if scope == "HDE_OUT_OF_SCOPE":
                hde_count += 1
                continue
            if scope == "LEGACY_NDA_OUT_OF_SCOPE":
                legacy_nda_count += 1
                continue
            if scope != "PMA" or normalized is None:
                unresolved_count += 1
                continue
            identity = normalized["record_identity"]
            prior = by_identity.get(identity)
            if prior is None:
                by_identity[identity] = normalized
            else:
                a, b = dict(prior), dict(normalized)
                a.pop("query_memberships", None)
                b.pop("query_memberships", None)
                if a != b:
                    raise ValueError(f"Conflicting normalized PMA representations for {identity}")
                duplicate_count += 1

        page_reports.append({
            "page_index": index,
            "reported_total_count": total,
            "skip": skip,
            "limit": limit,
            "returned_record_count": len(rows),
        })

    distinct_totals = sorted(set(totals))
    reported_total = distinct_totals[0] if len(distinct_totals) == 1 else None
    total_state = "CONSISTENT" if reported_total is not None else "INCONSISTENT_ACROSS_PAGES"
    over_limit = reported_total is not None and reported_total > MAX_DIRECT
    if reported_total is None:
        coverage_state = "DENOMINATOR_UNAVAILABLE"
    elif over_limit:
        coverage_state = "OVER_LIMIT_SEARCH_AFTER_OR_PARTITION_REQUIRED"
    elif not sequence_valid:
        coverage_state = "INVALID_SEQUENCE"
    elif len(by_identity) + hde_count + legacy_nda_count + unresolved_count == reported_total:
        coverage_state = "MATCH"
    else:
        coverage_state = "PARTIAL_OR_MISMATCH"

    records: list[dict[str, Any]] = []
    normalized_records: list[dict[str, Any]] = []
    known_duplicates: list[dict[str, Any]] = []
    if not over_limit:
        for identity in sorted(by_identity):
            normalized = by_identity[identity]
            duplicate_of = known.get(identity.upper())
            title = normalized.get("trade_name") or normalized.get("generic_name") or identity
            record: dict[str, Any] = {
                "record_key": identity,
                "title": title,
                "url": (
                    "https://api.fda.gov/device/pma.json?search="
                    f"pma_number:%22{normalized['pma_number']}%22"
                ),
                "publisher": "U.S. FDA",
                "source_class": "OFFICIAL_REGULATORY_RECORD",
                "suggested_source_id": (
                    f"SRC-OPENFDA-PMA-{normalized['pma_number']}-{normalized['supplement_number']}"
                ),
                "classification_hint": "DUPLICATE" if duplicate_of else "NEW",
                "decision_semantics": normalized["decision_semantics"],
            }
            if duplicate_of:
                record["duplicate_of_source_id"] = duplicate_of
                known_duplicates.append({"record_identity": identity, "source_id": duplicate_of})
            records.append(record)
            normalized_records.append(normalized)

    coverage = {
        "source_system": "OPENFDA_DEVICE_PMA",
        "query_id": query_id,
        "search_sha256": hashlib.sha256(search.encode("utf-8")).hexdigest(),
        "supplied_page_count": len(pages),
        "returned_record_count": raw_count,
        "unique_composite_record_count": len(by_identity),
        "reported_total_count": reported_total,
        "reported_total_count_state": total_state,
        "skip_sequence_valid": sequence_valid,
        "skip_coverage_state": coverage_state,
        "over_26000_limit": over_limit,
        "search_after_or_partition_required": over_limit,
        "out_of_scope_hde_count": hde_count,
        "out_of_scope_legacy_nda_count": legacy_nda_count,
        "known_controlled_duplicate_count": len(known_duplicates),
        "known_controlled_duplicates": known_duplicates,
        "new_candidate_count": len(records) - len(known_duplicates),
        "duplicate_representation_count": duplicate_count,
        "unresolved_pma_number_count": unresolved_count,
        "page_reports": page_reports,
        "decision_semantics_derived_only_from_exact_decision_code": True,
        "record_presence_is_approval_claim": False,
        "automatic_device_or_system_entity_creation_performed": False,
        "automatic_applicant_entity_creation_performed": False,
        "automatic_original_supplement_lineage_relationship_creation_performed": False,
        "automatic_current_commercial_configuration_claim_creation_performed": False,
        "automatic_global_authorization_claim_creation_performed": False,
        "automatic_system_conformance_claim_creation_performed": False,
        "automatic_reopening_decision_performed": False,
        "automatic_assessment_mutation_performed": False,
        "boundary": BOUNDARY,
    }
    return {"result_records": records, "normalized_records": normalized_records, "coverage": coverage}
