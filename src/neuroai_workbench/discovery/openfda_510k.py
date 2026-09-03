"""Bounded openFDA 510(k) projection for human-gated discovery."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

MAX_LIMIT = 1000
MAX_SKIP = 25000
MAX_DIRECT = 26000
SE_CODES = {"SEKD", "SESD", "SESE", "SESK", "SESP", "SESU", "SESR"}
K_RE = re.compile(r"^(?:K|BK)[A-Z0-9._-]+$", re.I)
DEN_RE = re.compile(r"^DEN[A-Z0-9._-]+$", re.I)
BOUNDARY = (
    "A projected 510(k) record preserves exact FDA submission/decision metadata. "
    "Substantially-equivalent semantics are emitted only for documented FDA SE decision codes; "
    "the projection does not establish PMA approval, global authorization, full clinical effectiveness, "
    "all-configuration conformance, automatic assessment reopening, or canonical authority."
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


def _identity(v: Any) -> tuple[str, str]:
    s = (_text(v) or "").upper()
    if DEN_RE.fullmatch(s):
        return s, "DE_NOVO_OUT_OF_SCOPE"
    if K_RE.fullmatch(s):
        return s, "510K"
    if not s:
        return "", "UNRESOLVED"
    return s, "UNRESOLVED"


def _decision_semantics(code: Any, description: Any) -> dict[str, Any]:
    c = (_text(code) or "").upper()
    _ = description
    if c in SE_CODES:
        return {
            "decision_semantics": "SUBSTANTIALLY_EQUIVALENT_RECORDED",
            "decision_supports_substantial_equivalence": True,
            "decision_code_recognized": True,
        }
    return {
        "decision_semantics": "UNRESOLVED_DECISION_CODE",
        "decision_supports_substantial_equivalence": False,
        "decision_code_recognized": False,
    }


def _normalize(raw: Mapping[str, Any], query_id: str) -> tuple[dict[str, Any] | None, str]:
    k, scope = _identity(raw.get("k_number"))
    if scope != "510K":
        return None, scope
    dec = _decision_semantics(raw.get("decision_code"), raw.get("decision_description"))
    out = {
        "record_kind": "NORMALIZED_OPENFDA_510K_SUBMISSION_DECISION",
        "k_number": k,
        "device_name": _text(raw.get("device_name")),
        "applicant": _text(raw.get("applicant")),
        "date_received": _safe(raw.get("date_received")),
        "decision_date": _safe(raw.get("decision_date")),
        "decision_code": (_text(raw.get("decision_code")) or "").upper() or None,
        "decision_description": _text(raw.get("decision_description")),
        "clearance_type": _text(raw.get("clearance_type")),
        "product_code": _text(raw.get("product_code")),
        "statement_or_summary": _text(raw.get("statement_or_summary")),
        "expedited_review_flag": _safe(raw.get("expedited_review_flag")),
        "third_party_flag": _safe(raw.get("third_party_flag")),
        **dec,
        "query_memberships": [query_id],
        "boundary": "K/BK identity and FDA decision metadata are preserved; device/applicant/product-code identity and broader authorization/conformance are not inferred.",
    }
    core = dict(out)
    core.pop("query_memberships", None)
    out["normalized_record_sha256"] = _sha(core)
    return out, scope


def project_search_pages(
    *, query_id: str, search: str, pages: Sequence[Mapping[str, Any]], known_k_sources: Mapping[str, str] | None = None
) -> dict[str, Any]:
    if (
        not isinstance(query_id, str)
        or not query_id.strip()
        or not isinstance(search, str)
        or not search.strip()
        or not pages
    ):
        raise ValueError("query_id, search and pages are required")
    known = {str(k).upper(): str(v) for k, v in (known_k_sources or {}).items()}
    totals = []
    by_id = {}
    page_reports = []
    raw_count = 0
    dup = 0
    seq = True
    prev_skip = prev_limit = None
    den_count = 0
    unresolved = 0
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
            n, scope = _normalize(raw, query_id)
            if scope == "DE_NOVO_OUT_OF_SCOPE":
                den_count += 1
                continue
            if scope != "510K" or n is None:
                unresolved += 1
                continue
            k = n["k_number"]
            prior = by_id.get(k)
            if prior is None:
                by_id[k] = n
            else:
                a = dict(prior)
                b = dict(n)
                a.pop("query_memberships", None)
                b.pop("query_memberships", None)
                if a != b:
                    raise ValueError(f"Conflicting normalized 510(k) representations for k_number {k}")
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
    elif len(by_id) + den_count + unresolved == reported:
        cov = "MATCH"
    else:
        cov = "PARTIAL_OR_MISMATCH"
    records = []
    norms = []
    known_dups = []
    if not over:
        for k in sorted(by_id):
            n = by_id[k]
            d = known.get(k)
            rec = {
                "record_key": f"OPENFDA_510K:{k}",
                "title": n.get("device_name") or f"FDA 510(k) {k}",
                "url": f"https://api.fda.gov/device/510k.json?search=k_number:%22{k}%22",
                "publisher": "U.S. FDA",
                "source_class": "OFFICIAL_REGULATORY_RECORD",
                "suggested_source_id": f"SRC-OPENFDA-510K-{k}",
                "classification_hint": "DUPLICATE" if d else "NEW",
                "decision_semantics": n["decision_semantics"],
            }
            if d:
                rec["duplicate_of_source_id"] = d
                known_dups.append({"k_number": k, "source_id": d})
            records.append(rec)
            norms.append(n)
    coverage = {
        "source_system": "OPENFDA_DEVICE_510K",
        "query_id": query_id,
        "search_sha256": hashlib.sha256(search.encode()).hexdigest(),
        "supplied_page_count": len(pages),
        "returned_record_count": raw_count,
        "unique_k_number_count": len(by_id),
        "reported_total_count": reported,
        "reported_total_count_state": total_state,
        "skip_sequence_valid": seq,
        "skip_coverage_state": cov,
        "over_26000_limit": over,
        "search_after_or_partition_required": over,
        "out_of_scope_den_count": den_count,
        "known_controlled_duplicate_count": len(known_dups),
        "known_controlled_duplicates": known_dups,
        "new_candidate_count": len(records) - len(known_dups),
        "duplicate_representation_count": dup,
        "unresolved_k_number_count": unresolved,
        "page_reports": page_reports,
        "record_presence_is_clearance_claim": False,
        "decision_semantics_derived_only_from_exact_decision_code": True,
        "automatic_system_or_device_entity_creation_performed": False,
        "automatic_applicant_entity_creation_performed": False,
        "automatic_predicate_relationship_creation_performed": False,
        "automatic_global_authorization_claim_creation_performed": False,
        "automatic_safety_effectiveness_claim_creation_performed": False,
        "automatic_system_conformance_claim_creation_performed": False,
        "automatic_reopening_decision_performed": False,
        "automatic_assessment_mutation_performed": False,
        "boundary": BOUNDARY,
    }
    return {"result_records": records, "normalized_records": norms, "coverage": coverage}
