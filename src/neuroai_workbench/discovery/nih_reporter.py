"""Bounded NIH RePORTER project-search projection for grant discovery.

Callers supply already-retrieved RePORTER JSON response pages. This module performs no network I/O
and never turns award existence or amount into research-success, system-effectiveness, commercial,
entity-resolution, relationship, assessment, or canonical claims.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

REPORTER_PROJECT_PREFIX = "https://reporter.nih.gov/project-details/"
REPORTER_MAX_LIMIT = 500
REPORTER_MAX_OFFSET = 14999
REPORTER_MAX_DIRECT_RESULTS = 15000

DISCOVERY_BOUNDARY = (
    "NIH RePORTER projection establishes only exact project/application metadata returned for one "
    "configured traversal. Award existence or amount does not establish research success, scientific "
    "validity, system effectiveness, commercialization, entity identity, implementation, regulatory "
    "authorization, assessment effect, global NeuroAI grant recall, or canonical authority."
)


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _canonical_sha(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _appl_id(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("RePORTER appl_id must be a positive integer")
    return value


def _safe_json_value(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list):
        return [_safe_json_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _safe_json_value(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    raise ValueError(f"Unsupported RePORTER metadata type {type(value).__name__}")


def _normalize_record(raw: Mapping[str, Any], *, query_id: str) -> dict[str, Any]:
    appl_id = _appl_id(raw.get("appl_id"))
    normalized: dict[str, Any] = {
        "record_kind": "NORMALIZED_NIH_REPORTER_GRANT_APPLICATION",
        "appl_id": appl_id,
        "project_num": _text(raw.get("project_num")),
        "core_project_num": _text(raw.get("core_project_num")),
        "subproject_id": _safe_json_value(raw.get("subproject_id")),
        "fiscal_year": _safe_json_value(raw.get("fiscal_year")),
        "project_title": _text(raw.get("project_title")),
        "abstract_text": _text(raw.get("abstract_text")),
        "project_start_date": _safe_json_value(raw.get("project_start_date")),
        "project_end_date": _safe_json_value(raw.get("project_end_date")),
        "award_notice_date": _safe_json_value(raw.get("award_notice_date")),
        "award_amount": _safe_json_value(raw.get("award_amount")),
        "funding_mechanism": _safe_json_value(raw.get("funding_mechanism")),
        "agency_ic_admin": _safe_json_value(raw.get("agency_ic_admin")),
        "organization": _safe_json_value(raw.get("organization")),
        "principal_investigators": _safe_json_value(raw.get("principal_investigators")),
        "query_memberships": [query_id],
        "boundary": (
            "Normalized RePORTER metadata preserves provider application/project/funding fields for discovery review only. "
            "PI and organization names remain unresolved metadata; award amount is not a success/quality signal."
        ),
    }
    digest_input = dict(normalized)
    digest_input.pop("query_memberships", None)
    normalized["normalized_record_sha256"] = _canonical_sha(digest_input)
    return normalized


def _known_index(values: Mapping[int | str, str] | None) -> dict[int, str]:
    result: dict[int, str] = {}
    for raw_id, raw_source in (values or {}).items():
        try:
            appl_id = int(raw_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid controlled RePORTER appl_id {raw_id!r}") from exc
        if appl_id <= 0:
            raise ValueError("Controlled RePORTER appl_id must be positive")
        source_id = _text(raw_source)
        if source_id is None:
            raise ValueError(f"Controlled Source for appl_id {appl_id} must be non-empty")
        prior = result.get(appl_id)
        if prior is not None and prior != source_id:
            raise ValueError(f"Conflicting controlled Sources for RePORTER appl_id {appl_id}")
        result[appl_id] = source_id
    return result


def _page_payload(raw: Mapping[str, Any], index: int) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    payload = raw.get("payload") if isinstance(raw, Mapping) and "payload" in raw else raw
    if not isinstance(payload, Mapping):
        raise ValueError(f"page {index}: payload must be object")
    meta = payload.get("meta")
    results = payload.get("results")
    if not isinstance(meta, Mapping):
        raise ValueError(f"page {index}: meta must be object")
    if not isinstance(results, list) or not all(isinstance(row, dict) for row in results):
        raise ValueError(f"page {index}: results must be an object array")
    return dict(payload), dict(meta), [dict(row) for row in results]


def _suggested_source_id(appl_id: int) -> str:
    return f"SRC-REPORTER-APPL-{appl_id}"


def project_search_pages(
    *,
    query_id: str,
    query_payload: Mapping[str, Any],
    pages: Sequence[Mapping[str, Any]],
    known_appl_sources: Mapping[int | str, str] | None = None,
) -> dict[str, Any]:
    """Project supplied NIH RePORTER project-search pages into discovery candidate records."""
    if not isinstance(query_id, str) or not query_id.strip():
        raise ValueError("query_id must be non-empty")
    if not isinstance(query_payload, Mapping) or not query_payload:
        raise ValueError("query_payload must be non-empty object")
    if not pages:
        raise ValueError("At least one RePORTER page is required")
    known = _known_index(known_appl_sources)

    totals: list[int] = []
    page_reports: list[dict[str, Any]] = []
    by_appl: dict[int, dict[str, Any]] = {}
    raw_count = 0
    duplicate_count = 0
    previous_offset: int | None = None
    previous_limit: int | None = None
    sequence_valid = True

    for index, raw_page in enumerate(pages, start=1):
        _, meta, rows = _page_payload(raw_page, index)
        total = meta.get("total")
        offset = meta.get("offset")
        limit = meta.get("limit")
        if not isinstance(total, int) or isinstance(total, bool) or total < 0:
            raise ValueError(f"page {index}: meta.total must be non-negative integer")
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0 or offset > REPORTER_MAX_OFFSET:
            raise ValueError(f"page {index}: meta.offset outside 0..{REPORTER_MAX_OFFSET}")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1 or limit > REPORTER_MAX_LIMIT:
            raise ValueError(f"page {index}: meta.limit outside 1..{REPORTER_MAX_LIMIT}")
        totals.append(total)
        if index == 1 and offset != 0:
            sequence_valid = False
        if previous_offset is not None and previous_limit is not None and offset != previous_offset + previous_limit:
            sequence_valid = False
        previous_offset, previous_limit = offset, limit
        raw_count += len(rows)

        ids_on_page: list[int] = []
        for raw_record in rows:
            normalized = _normalize_record(raw_record, query_id=query_id)
            appl_id = normalized["appl_id"]
            ids_on_page.append(appl_id)
            prior = by_appl.get(appl_id)
            if prior is None:
                by_appl[appl_id] = normalized
            else:
                prior_content = dict(prior)
                current_content = dict(normalized)
                prior_content.pop("query_memberships", None)
                current_content.pop("query_memberships", None)
                if prior_content != current_content:
                    raise ValueError(f"Conflicting normalized RePORTER representations for appl_id {appl_id}")
                duplicate_count += 1

        page_reports.append(
            {
                "page_index": index,
                "reported_total_count": total,
                "offset": offset,
                "limit": limit,
                "returned_record_count": len(rows),
                "unique_appl_ids_on_page": len(set(ids_on_page)),
            }
        )

    distinct_totals = sorted(set(totals))
    if len(distinct_totals) == 1:
        total_state = "CONSISTENT"
        reported_total: int | None = distinct_totals[0]
    else:
        total_state = "INCONSISTENT_ACROSS_PAGES"
        reported_total = None

    over_limit = reported_total is not None and reported_total > REPORTER_MAX_DIRECT_RESULTS
    partition_required = over_limit
    if reported_total is None:
        coverage_state = "DENOMINATOR_UNAVAILABLE"
    elif over_limit:
        coverage_state = "OVER_LIMIT_PARTITION_REQUIRED"
    elif not sequence_valid:
        coverage_state = "INVALID_SEQUENCE"
    elif len(by_appl) == reported_total:
        coverage_state = "MATCH"
    else:
        coverage_state = "PARTIAL_OR_MISMATCH"

    result_records: list[dict[str, Any]] = []
    normalized_records: list[dict[str, Any]] = []
    known_duplicates: list[dict[str, Any]] = []
    if not over_limit:
        for appl_id in sorted(by_appl):
            normalized = by_appl[appl_id]
            duplicate_of = known.get(appl_id)
            record: dict[str, Any] = {
                "record_key": f"REPORTER:APPL:{appl_id}",
                "title": normalized.get("project_title")
                or normalized.get("project_num")
                or f"RePORTER application {appl_id}",
                "url": f"{REPORTER_PROJECT_PREFIX}{appl_id}",
                "publisher": "NIH RePORTER",
                "source_class": "OFFICIAL_GRANT_DATABASE",
                "suggested_source_id": _suggested_source_id(appl_id),
                "classification_hint": "DUPLICATE" if duplicate_of is not None else "NEW",
            }
            if duplicate_of is not None:
                record["duplicate_of_source_id"] = duplicate_of
                known_duplicates.append({"appl_id": appl_id, "source_id": duplicate_of})
            result_records.append(record)
            normalized_records.append(normalized)

    coverage = {
        "source_system": "NIH_REPORTER_V2",
        "query_id": query_id,
        "query_payload_sha256": _canonical_sha(query_payload),
        "supplied_page_count": len(pages),
        "returned_record_count": raw_count,
        "unique_appl_id_count": len(by_appl),
        "reported_total_count": reported_total,
        "reported_total_count_state": total_state,
        "reported_total_count_values": distinct_totals,
        "offset_sequence_valid": sequence_valid,
        "offset_coverage_state": coverage_state,
        "over_15000_limit": over_limit,
        "partition_required": partition_required,
        "candidate_emission_refused_due_to_over_limit": over_limit,
        "known_controlled_duplicate_count": len(known_duplicates),
        "known_controlled_duplicates": known_duplicates,
        "new_candidate_count": len(result_records) - len(known_duplicates),
        "duplicate_representation_count": duplicate_count,
        "unresolved_appl_id_count": 0,
        "page_reports": page_reports,
        "reporter_database_completeness_claim": False,
        "global_neuroai_grant_recall_claim": False,
        "query_recall_claim": False,
        "funding_success_claim": False,
        "automatic_source_admission_performed": False,
        "automatic_project_entity_creation_performed": False,
        "automatic_pi_or_org_entity_creation_performed": False,
        "automatic_system_or_model_relationship_creation_performed": False,
        "automatic_funding_success_claim_creation_performed": False,
        "automatic_assessment_mutation_performed": False,
        "boundary": DISCOVERY_BOUNDARY,
    }
    return {"result_records": result_records, "normalized_records": normalized_records, "coverage": coverage}
