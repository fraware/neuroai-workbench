"""Bounded openFDA device-recall projection for human-gated discovery."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

MAX_LIMIT = 1000
MAX_SKIP = 25000
MAX_DIRECT = 26000
BOUNDARY = (
    "An openFDA device-recall projection establishes selected provider metadata for an exact recall record. "
    "It does not establish global product unsafety, all-configuration nonconformance, exact system identity, "
    "complete lifecycle state, automatic assessment reopening, or canonical authority."
)


def _text(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _safe(v: Any) -> Any:
    if v is None or isinstance(v, str | int | float | bool):
        return v
    if isinstance(v, list):
        return [_safe(x) for x in v]
    if isinstance(v, Mapping):
        return {str(k): _safe(x) for k, x in sorted(v.items(), key=lambda p: str(p[0]))}
    return str(v)


def _sha(v: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _cfres(v: Any) -> str:
    s = _text(v)
    if not s:
        raise ValueError("openFDA cfres_id must be non-empty")
    return s


def _normalize(raw: Mapping[str, Any], query_id: str) -> dict[str, Any]:
    out = {
        "record_kind": "NORMALIZED_OPENFDA_DEVICE_RECALL",
        "cfres_id": _cfres(raw.get("cfres_id")),
        "res_event_number": _text(raw.get("res_event_number")),
        "product_res_number": _text(raw.get("product_res_number")),
        "event_date_initiated": _safe(raw.get("event_date_initiated")),
        "event_date_created": _safe(raw.get("event_date_created")),
        "event_date_posted": _safe(raw.get("event_date_posted")),
        "event_date_terminated": _safe(raw.get("event_date_terminated")),
        "recall_status": _text(raw.get("recall_status")),
        "recalling_firm": _text(raw.get("recalling_firm")),
        "firm_fei_number": _safe(raw.get("firm_fei_number")),
        "reason_for_recall": _text(raw.get("reason_for_recall")),
        "root_cause_description": _text(raw.get("root_cause_description")),
        "action": _text(raw.get("action")),
        "product_description": _text(raw.get("product_description")),
        "product_code": _text(raw.get("product_code")),
        "k_numbers": _safe(raw.get("k_numbers")),
        "pma_numbers": _safe(raw.get("pma_numbers")),
        "query_memberships": [query_id],
        "boundary": "Recall metadata is scoped to this provider record; K/PMA/product/firm metadata do not resolve exact systems automatically.",
    }
    core = dict(out)
    core.pop("query_memberships", None)
    out["normalized_record_sha256"] = _sha(core)
    return out


def project_search_pages(
    *,
    query_id: str,
    search: str,
    pages: Sequence[Mapping[str, Any]],
    known_cfres_sources: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if not query_id.strip() or not search.strip() or not pages:
        raise ValueError("query_id, search and pages are required")
    known = {str(k): str(v) for k, v in (known_cfres_sources or {}).items()}
    totals = []
    by_id = {}
    page_reports = []
    raw_count = 0
    dup = 0
    seq = True
    prev_skip = prev_limit = None
    for i, page in enumerate(pages, 1):
        payload = page.get("payload") if isinstance(page, Mapping) and "payload" in page else page
        if not isinstance(payload, Mapping):
            raise ValueError(f"page {i}: payload must be object")
        meta = payload.get("meta", {})
        mr = meta.get("results", {}) if isinstance(meta, Mapping) else {}
        rows = payload.get("results")
        if not isinstance(mr, Mapping) or not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            raise ValueError(f"page {i}: invalid openFDA shape")
        total, skip, limit = mr.get("total"), mr.get("skip"), mr.get("limit")
        if not isinstance(total, int) or isinstance(total, bool) or total < 0:
            raise ValueError(f"page {i}: total invalid")
        if not isinstance(skip, int) or isinstance(skip, bool) or not 0 <= skip <= MAX_SKIP:
            raise ValueError(f"page {i}: skip invalid")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_LIMIT:
            raise ValueError(f"page {i}: limit invalid")
        if i == 1 and skip != 0:
            seq = False
        if prev_skip is not None and skip != prev_skip + prev_limit:
            seq = False
        prev_skip, prev_limit = skip, limit
        totals.append(total)
        raw_count += len(rows)
        for raw in rows:
            n = _normalize(raw, query_id)
            rid = n["cfres_id"]
            prior = by_id.get(rid)
            if prior is None:
                by_id[rid] = n
            else:
                a = dict(prior)
                b = dict(n)
                a.pop("query_memberships", None)
                b.pop("query_memberships", None)
                if a != b:
                    raise ValueError(f"Conflicting normalized recall representations for cfres_id {rid}")
                dup += 1
        page_reports.append(
            {
                "page_index": i,
                "reported_total_count": total,
                "skip": skip,
                "limit": limit,
                "returned_record_count": len(rows),
            }
        )
    distinct = sorted(set(totals))
    reported = distinct[0] if len(distinct) == 1 else None
    total_state = "CONSISTENT" if reported is not None else "INCONSISTENT_ACROSS_PAGES"
    over = reported is not None and reported > MAX_DIRECT
    if reported is None:
        cov = "DENOMINATOR_UNAVAILABLE"
    elif over:
        cov = "OVER_LIMIT_SEARCH_AFTER_OR_PARTITION_REQUIRED"
    elif not seq:
        cov = "INVALID_SEQUENCE"
    elif len(by_id) == reported:
        cov = "MATCH"
    else:
        cov = "PARTIAL_OR_MISMATCH"
    records = []
    norms = []
    known_dups = []
    if not over:
        for rid in sorted(by_id):
            n = by_id[rid]
            d = known.get(rid)
            rec = {
                "record_key": f"OPENFDA_RECALL:{rid}",
                "title": n.get("product_description") or f"FDA device recall {rid}",
                "url": f"https://api.fda.gov/device/recall.json?search=cfres_id:%22{rid}%22",
                "publisher": "U.S. FDA",
                "source_class": "OFFICIAL_RECALL_OR_POSTMARKET_RECORD",
                "suggested_source_id": f"SRC-OPENFDA-RECALL-{rid}",
                "classification_hint": "DUPLICATE" if d else "NEW",
            }
            if d:
                rec["duplicate_of_source_id"] = d
                known_dups.append({"cfres_id": rid, "source_id": d})
            records.append(rec)
            norms.append(n)
    coverage = {
        "source_system": "OPENFDA_DEVICE_RECALL",
        "query_id": query_id,
        "search_sha256": hashlib.sha256(search.encode()).hexdigest(),
        "supplied_page_count": len(pages),
        "returned_record_count": raw_count,
        "unique_cfres_id_count": len(by_id),
        "reported_total_count": reported,
        "reported_total_count_state": total_state,
        "skip_sequence_valid": seq,
        "skip_coverage_state": cov,
        "over_26000_limit": over,
        "search_after_or_partition_required": over,
        "known_controlled_duplicate_count": len(known_dups),
        "known_controlled_duplicates": known_dups,
        "new_candidate_count": len(records) - len(known_dups),
        "duplicate_representation_count": dup,
        "unresolved_cfres_id_count": 0,
        "page_reports": page_reports,
        "address_or_contact_fields_projected": False,
        "code_info_lot_serial_text_projected": False,
        "distribution_pattern_projected": False,
        "recall_status_is_complete_lifecycle_tracker": False,
        "automatic_system_nonconformance_claim_creation_performed": False,
        "automatic_reopening_decision_performed": False,
        "automatic_assessment_mutation_performed": False,
        "boundary": BOUNDARY,
    }
    return {"result_records": records, "normalized_records": norms, "coverage": coverage}
