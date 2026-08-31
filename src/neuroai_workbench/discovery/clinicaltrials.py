"""Bounded ClinicalTrials.gov search-page projection for discovery.

This module bridges structured CT.gov search responses to the generic discovery workflow.
It does not perform network I/O, mutate source/monitor registries, create trial/site graph
entities, or establish registry/global completeness. Callers supply already-retrieved page
payloads and later pass ``result_records`` to ``execute_discovery_query``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from ..collector.adapters.clinicaltrials import CTGOV_ADAPTER_ID

CTGOV_STUDY_PAGE_PREFIX = "https://clinicaltrials.gov/study/"
DISCOVERY_BOUNDARY = (
    "ClinicalTrials.gov search projection produces source-discovery candidates for one exact "
    "query traversal only. It does not establish ClinicalTrials.gov completeness, NeuroAI trial "
    "recall, clinical truth, trial-site identity, canonical source admission, or assessment effect."
)


class _ClinicalTrialsProjectionAdapter(Protocol):
    def parse_search_page(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def normalize_study(self, study_payload: dict[str, Any]) -> dict[str, Any]: ...


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _page_payload(raw: Mapping[str, Any], index: int) -> dict[str, Any]:
    payload = raw.get("payload")
    if payload is None:
        payload = raw
    if not isinstance(payload, dict):
        raise ValueError(f"page {index}: payload must be an object")
    return dict(payload)


def project_search_pages(
    adapter: _ClinicalTrialsProjectionAdapter,
    *,
    query_id: str,
    query_text: str,
    pages: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Project supplied CT.gov search pages into generic discovery result records.

    Pages are interpreted in caller-supplied order. Duplicate NCT IDs are collapsed only when
    their normalized projections are byte-for-byte-equivalent as Python values; conflicting
    duplicates fail closed. ``fully_paginated`` describes only whether the supplied sequence
    terminates with no next-page token. It is not a recall/completeness claim.
    """
    qid = _text(query_id, "query_id")
    qtext = _text(query_text, "query_text")
    if not pages:
        raise ValueError("At least one ClinicalTrials.gov search page is required")

    by_nct: dict[str, dict[str, Any]] = {}
    page_reports: list[dict[str, Any]] = []
    raw_record_count = 0
    duplicate_record_count = 0
    reported_totals: list[int] = []

    for index, raw_page in enumerate(pages, start=1):
        if not isinstance(raw_page, Mapping):
            raise ValueError(f"page {index}: page must be an object")
        parsed = adapter.parse_search_page(_page_payload(raw_page, index))
        studies = parsed.get("studies")
        if not isinstance(studies, list):
            raise ValueError(f"page {index}: parsed studies must be an array")
        raw_record_count += len(studies)

        total = parsed.get("total_count")
        if total is not None:
            if not isinstance(total, int) or total < 0:
                raise ValueError(f"page {index}: total_count must be non-negative integer/null")
            reported_totals.append(total)

        page_nct_ids: list[str] = []
        for study in studies:
            if not isinstance(study, dict):
                raise ValueError(f"page {index}: every study must be an object")
            normalized = adapter.normalize_study(study)
            nct_id = _text(normalized.get("nct_id"), f"page {index} normalized nct_id").upper()
            page_nct_ids.append(nct_id)
            prior = by_nct.get(nct_id)
            if prior is None:
                by_nct[nct_id] = normalized
            elif prior == normalized:
                duplicate_record_count += 1
            else:
                raise ValueError(
                    f"Conflicting normalized ClinicalTrials.gov representations for {nct_id}"
                )

        page_reports.append(
            {
                "page_index": index,
                "returned_record_count": len(studies),
                "unique_nct_ids_on_page": len(set(page_nct_ids)),
                "reported_total_count": total,
                "next_page_token_present": parsed.get("next_page_token") is not None,
            }
        )

    distinct_totals = sorted(set(reported_totals))
    if not reported_totals:
        total_count_state = "NOT_REPORTED"
        reported_total_count: int | None = None
    elif len(distinct_totals) == 1:
        total_count_state = "CONSISTENT"
        reported_total_count = distinct_totals[0]
    else:
        total_count_state = "INCONSISTENT_ACROSS_PAGES"
        reported_total_count = None

    final_has_more = bool(page_reports[-1]["next_page_token_present"])
    fully_paginated = not final_has_more

    result_records: list[dict[str, Any]] = []
    normalized_records: list[dict[str, Any]] = []
    for nct_id in sorted(by_nct):
        normalized = by_nct[nct_id]
        title = normalized.get("brief_title")
        display_title = title.strip() if isinstance(title, str) and title.strip() else nct_id
        result_records.append(
            {
                "record_key": nct_id,
                "title": display_title,
                "url": f"{CTGOV_STUDY_PAGE_PREFIX}{nct_id}",
                "publisher": "ClinicalTrials.gov",
                "source_class": "OFFICIAL_TRIAL_REGISTRY",
                "suggested_source_id": f"SRC-CTGOV-{nct_id}",
                "classification_hint": "NEW",
            }
        )
        normalized_records.append(normalized)

    coverage = {
        "source_system": "CLINICALTRIALS_GOV",
        "adapter_id": CTGOV_ADAPTER_ID,
        "query_id": qid,
        "query_text": qtext,
        "supplied_page_count": len(pages),
        "raw_returned_record_count": raw_record_count,
        "unique_nct_record_count": len(by_nct),
        "duplicate_nct_representation_count": duplicate_record_count,
        "reported_total_count_state": total_count_state,
        "reported_total_count": reported_total_count,
        "reported_total_count_values": distinct_totals,
        "fully_paginated": fully_paginated,
        "final_next_page_token_present": final_has_more,
        "page_reports": page_reports,
        "registry_completeness_claim": False,
        "neuroai_discovery_recall_claim": False,
        "automatic_registry_mutation_performed": False,
        "boundary": DISCOVERY_BOUNDARY,
    }
    return {
        "result_records": result_records,
        "normalized_records": normalized_records,
        "coverage": coverage,
    }
