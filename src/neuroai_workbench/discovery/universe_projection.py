"""Offline fixture/replay projections for first-wave source universes.

Caller-supplied pages only. No embedded HTTP client. Conflicting same-identity
representations fail closed. Cursor completion is not universe completeness.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from .errors import DiscoveryError

PROJECTION_BOUNDARY = (
    "Universe projections produce discovery candidates and coverage reports from "
    "caller-supplied pages only. They do not establish corpus completeness, "
    "regulatory authorization, funding control, model capability, or assessment effect."
)

FAILURE_TAXONOMY = frozenset(
    {
        "INVALID_IDENTITY",
        "CONFLICTING_SAME_IDENTITY",
        "DUPLICATE_IDENTICAL",
        "KNOWN_IDENTITY_DUPLICATE",
        "EXCLUDED_BY_FILTER",
        "MISSING_REQUIRED_FIELD",
        "PAGINATION_SEQUENCE_INVALID",
    }
)

# Per-universe projection metadata. Adapters supply capture; programmes project.
UNIVERSE_PROJECTION_META: dict[str, dict[str, Any]] = {
    "SU-PUBS": {
        "source_system": "PUBMED_CROSSREF",
        "adapter_id": "pubmed_crossref",
        "publisher": "PubMed/Crossref",
        "source_class": "OFFICIAL_BIBLIOGRAPHIC_METADATA",
        "identity_field": "identity",
        "suggested_prefix": "SRC-PUBS-",
        "required_optional_states": (),
    },
    "SU-REG": {
        "source_system": "FDA_DEVICE_PUBLIC",
        "adapter_id": "fda_device",
        "publisher": "openFDA",
        "source_class": "REGULATORY_RECORD",
        "identity_field": "identity",
        "suggested_prefix": "SRC-REG-",
        "required_optional_states": (),
    },
    "SU-GRANTS": {
        "source_system": "PUBLIC_FUNDER_RECORDS",
        "adapter_id": "patents_grants",
        "publisher": "Public funder registry",
        "source_class": "PATENT_OR_GRANT_RECORD",
        "identity_field": "identity",
        "suggested_prefix": "SRC-GRANT-",
        "required_optional_states": (),
        "prohibited_inference": "investor_or_funder_to_control",
    },
    "SU-MODEL": {
        "source_system": "PUBLIC_MODEL_DATASET_REGISTRIES",
        "adapter_id": "neuroscience_archive",
        "publisher": "Public model/dataset registry",
        "source_class": "MODEL_OR_DATASET_RECORD",
        "identity_field": "identity",
        "suggested_prefix": "SRC-MODEL-",
        "required_optional_states": ("checkpoint", "license", "lineage"),
    },
}


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DiscoveryError(f"{field} must be a non-empty string")
    return value.strip()


def _page_records(raw: Mapping[str, Any], index: int) -> tuple[list[Mapping[str, Any]], str | None, int | None]:
    payload = raw.get("payload") if "payload" in raw else raw
    if not isinstance(payload, Mapping):
        raise DiscoveryError(f"page {index}: payload must be an object")
    records = payload.get("records")
    if records is None:
        records = payload.get("items")
    if not isinstance(records, list):
        raise DiscoveryError(f"page {index}: records/items must be an array")
    next_token = payload.get("next_page_token")
    if next_token is not None and (not isinstance(next_token, str) or not next_token.strip()):
        raise DiscoveryError(f"page {index}: next_page_token must be non-empty string/null")
    total = payload.get("total_count")
    if total is not None and (not isinstance(total, int) or isinstance(total, bool) or total < 0):
        raise DiscoveryError(f"page {index}: total_count must be non-negative integer/null")
    return [item for item in records if isinstance(item, Mapping)], next_token, total


def _normalize_identity(raw: Mapping[str, Any], identity_re: re.Pattern[str], index: int, row: int) -> str:
    identity = raw.get("identity") or raw.get("record_key") or raw.get("id")
    key = _text(identity, f"page {index} record {row} identity").strip()
    # DOI identities are case-folded in the namespace only via lowercasing the whole key when DOI-like.
    if key.lower().startswith("10."):
        key = key.lower()
    if key.upper().startswith("PMID:"):
        key = "PMID:" + key.split(":", 1)[1].strip()
    if not identity_re.fullmatch(key):
        raise DiscoveryError(f"page {index} record {row}: identity {key!r} fails programme pattern")
    return key


def project_universe_pages(
    *,
    universe_id: str,
    query_id: str,
    query_text: str,
    pages: Sequence[Mapping[str, Any]],
    identity_pattern: str,
    known_identities: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Project caller-supplied universe pages into discovery result records + coverage."""
    meta = UNIVERSE_PROJECTION_META.get(universe_id)
    if meta is None:
        raise DiscoveryError(f"No offline projection registered for universe_id {universe_id!r}")
    if not pages:
        raise DiscoveryError(f"{universe_id} execution requires at least one caller-supplied page")

    identity_re = re.compile(identity_pattern)
    known = {
        _text(k, "known_identities key"): _text(v, f"known_identities[{k}]")
        for k, v in (known_identities or {}).items()
    }

    by_id: dict[str, dict[str, Any]] = {}
    page_reports: list[dict[str, Any]] = []
    raw_record_count = 0
    duplicate_identical = 0
    failures: list[dict[str, Any]] = []
    reported_totals: list[int] = []

    for index, raw_page in enumerate(pages, start=1):
        if not isinstance(raw_page, Mapping):
            raise DiscoveryError(f"page {index}: page must be an object")
        records, next_token, total = _page_records(raw_page, index)
        raw_record_count += len(records)
        if total is not None:
            reported_totals.append(total)
        page_ids: list[str] = []
        for row, item in enumerate(records, start=1):
            try:
                identity = _normalize_identity(item, identity_re, index, row)
            except DiscoveryError as exc:
                failures.append(
                    {
                        "failure_class": "INVALID_IDENTITY",
                        "page_index": index,
                        "row": row,
                        "detail": str(exc),
                    }
                )
                continue
            page_ids.append(identity)
            normalized = {
                "identity": identity,
                "title": _text(item.get("title") or identity, f"page {index} record {row} title"),
                "url": str(item.get("url") or ""),
                "states": {key: item.get(key) for key in meta["required_optional_states"] if key in item},
                "raw": dict(item),
            }
            prior = by_id.get(identity)
            if prior is None:
                by_id[identity] = normalized
            elif prior["raw"] == normalized["raw"]:
                duplicate_identical += 1
                failures.append(
                    {
                        "failure_class": "DUPLICATE_IDENTICAL",
                        "identity": identity,
                        "page_index": index,
                        "row": row,
                    }
                )
            else:
                raise DiscoveryError(
                    f"Conflicting same-identity representations for {identity!r} "
                    f"(failure_class=CONFLICTING_SAME_IDENTITY)"
                )
        page_reports.append(
            {
                "page_index": index,
                "returned_record_count": len(records),
                "unique_identities_on_page": len(set(page_ids)),
                "reported_total_count": total,
                "next_page_token_present": next_token is not None,
            }
        )

    for report in page_reports[:-1]:
        if not report["next_page_token_present"]:
            raise DiscoveryError(
                f"Invalid pagination sequence: non-final page {report['page_index']} has no next_page_token "
                "(failure_class=PAGINATION_SEQUENCE_INVALID)"
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
    if reported_total_count is None:
        reconciliation = "DENOMINATOR_UNAVAILABLE"
    elif not fully_paginated:
        reconciliation = "PARTIAL_TRAVERSAL_NOT_RECONCILED"
    elif len(by_id) == reported_total_count:
        reconciliation = "MATCH"
    else:
        reconciliation = "MISMATCH"

    result_records: list[dict[str, Any]] = []
    known_duplicates: list[dict[str, str]] = []
    missing_state_counts: dict[str, int] = {key: 0 for key in meta["required_optional_states"]}
    for identity in sorted(by_id):
        normalized = by_id[identity]
        states = dict(normalized.get("states") or {})
        for state_key in meta["required_optional_states"]:
            if states.get(state_key) in (None, ""):
                missing_state_counts[state_key] += 1
                failures.append(
                    {
                        "failure_class": "MISSING_REQUIRED_FIELD",
                        "identity": identity,
                        "field": state_key,
                    }
                )
        duplicate_of = known.get(identity)
        record: dict[str, Any] = {
            "record_key": identity,
            "title": normalized["title"],
            "url": normalized["url"] or f"synthetic://{universe_id}/{identity}",
            "publisher": meta["publisher"],
            "source_class": meta["source_class"],
            "suggested_source_id": f"{meta['suggested_prefix']}{identity.replace('/', '_').replace(':', '_')}",
            "classification_hint": "DUPLICATE" if duplicate_of is not None else "NEW",
        }
        if duplicate_of is not None:
            record["duplicate_of_source_id"] = duplicate_of
            known_duplicates.append({"identity": identity, "source_id": duplicate_of})
            failures.append(
                {
                    "failure_class": "KNOWN_IDENTITY_DUPLICATE",
                    "identity": identity,
                    "source_id": duplicate_of,
                }
            )
        result_records.append(record)

    coverage = {
        "source_system": meta["source_system"],
        "adapter_id": meta["adapter_id"],
        "universe_id": universe_id,
        "query_id": query_id,
        "query_text": query_text,
        "supplied_page_count": len(pages),
        "raw_returned_record_count": raw_record_count,
        "unique_identity_count": len(by_id),
        "included_candidate_count": len(result_records),
        "known_identity_duplicate_count": len(known_duplicates),
        "known_identity_duplicates": known_duplicates,
        "new_candidate_count": len(result_records) - len(known_duplicates),
        "duplicate_identical_representation_count": duplicate_identical,
        "reported_total_count_state": total_count_state,
        "reported_total_count": reported_total_count,
        "reported_total_count_values": distinct_totals,
        "pagination_sequence_valid": True,
        "fully_paginated": fully_paginated,
        "final_next_page_token_present": final_has_more,
        "reported_total_reconciliation_state": reconciliation,
        "page_reports": page_reports,
        "failure_taxonomy_classes": sorted(FAILURE_TAXONOMY),
        "failures": failures,
        "missing_optional_state_counts": missing_state_counts,
        "corpus_completeness_claim": False,
        "automatic_registry_mutation_performed": False,
        "evaluation_hooks": {
            "precision_method": "Sampled human review of NEW candidates (not executed by this software).",
            "offline_fixture_replay_supported": True,
            "network_execution_in_this_module": False,
        },
        "boundary": PROJECTION_BOUNDARY,
    }
    if meta.get("prohibited_inference"):
        coverage["prohibited_inference"] = meta["prohibited_inference"]
    return {"result_records": result_records, "normalized_records": list(by_id.values()), "coverage": coverage}
