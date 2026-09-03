"""Bounded Europe PMC search-page projection for publication discovery.

Callers supply already-retrieved Europe PMC search response payloads. This module performs
no network I/O and does not admit Sources, create model/system/dataset relationships, create
monitors, mutate assessments, or establish literature/global NeuroAI completeness.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import quote

EUROPE_PMC_ARTICLE_PREFIX = "https://europepmc.org/article/"
_DOI_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi:",
)
_PMID_RE = re.compile(r"^[0-9]+$")
_PMCID_RE = re.compile(r"^PMC[0-9]+$", re.I)

DISCOVERY_BOUNDARY = (
    "Europe PMC search projection produces publication-discovery candidates for one exact "
    "query traversal only. It does not establish Europe PMC completeness, NeuroAI publication "
    "recall, publication relevance, peer-review state beyond retrieved metadata, scientific "
    "truth, source admission, system/model/dataset relationships, assessment effect, or "
    "canonical publication."
)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _page_payload(raw: Mapping[str, Any], index: int) -> dict[str, Any]:
    payload = raw.get("payload")
    if payload is None:
        payload = raw
    if not isinstance(payload, dict):
        raise ValueError(f"page {index}: payload must be an object")
    return dict(payload)


def _normalize_doi(value: Any) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    lowered = text.lower()
    for prefix in _DOI_PREFIXES:
        if lowered.startswith(prefix):
            lowered = lowered[len(prefix) :]
            break
    lowered = lowered.strip()
    if not lowered.startswith("10.") or "/" not in lowered:
        return None
    return lowered


def _normalize_pmid(value: Any) -> str | None:
    text = _optional_text(value)
    if text is None or not _PMID_RE.fullmatch(text):
        return None
    return text


def _normalize_pmcid(value: Any) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    normalized = text.upper()
    return normalized if _PMCID_RE.fullmatch(normalized) else None


def _normalize_source(value: Any) -> str:
    return _text(value, "Europe PMC source").upper()


def _normalize_ext_id(value: Any) -> str:
    return _text(value, "Europe PMC id")


def _resolved_identity(record: Mapping[str, Any]) -> tuple[str, str]:
    doi = _normalize_doi(record.get("doi"))
    if doi is not None:
        return "DOI", f"DOI:{doi}"
    pmid = _normalize_pmid(record.get("pmid"))
    if pmid is not None:
        return "PMID", f"PMID:{pmid}"
    pmcid = _normalize_pmcid(record.get("pmcid"))
    if pmcid is not None:
        return "PMCID", f"PMCID:{pmcid}"
    source = _normalize_source(record.get("source"))
    ext_id = _normalize_ext_id(record.get("id"))
    return "SOURCE_PLUS_EXT_ID", f"EPMC:{source}:{ext_id}"


def _publication_type(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, list):
        values = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        if values:
            return " | ".join(values)
    return None


def _is_preprint(source: str, publication_type: str | None) -> bool:
    if source == "PPR":
        return True
    return publication_type is not None and "preprint" in publication_type.lower()


def _canonical_json_sha256(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _suggested_source_id(resolved_identity: str) -> str:
    token = hashlib.sha256(resolved_identity.encode("utf-8")).hexdigest()[:20].upper()
    return f"SRC-EPMC-{token}"


def _known_identity_index(values: Mapping[str, str] | None) -> dict[str, str]:
    index: dict[str, str] = {}
    for raw_identity, raw_source_id in (values or {}).items():
        identity = _text(raw_identity, "known_publication_sources key")
        source_id = _text(raw_source_id, f"known_publication_sources[{identity}]")
        prior = index.get(identity)
        if prior is not None and prior != source_id:
            raise ValueError(f"Conflicting controlled source identities for known publication {identity}")
        index[identity] = source_id
    return index


def _known_source_match(normalized: Mapping[str, Any], known: Mapping[str, str]) -> str | None:
    candidates: set[str] = {str(normalized["resolved_identity"])}
    doi = normalized.get("doi")
    if isinstance(doi, str):
        candidates.add(f"DOI:{doi}")
    pmid = normalized.get("pmid")
    if isinstance(pmid, str):
        candidates.add(f"PMID:{pmid}")
    pmcid = normalized.get("pmcid")
    if isinstance(pmcid, str):
        candidates.add(f"PMCID:{pmcid}")
    source_plus_ext_id = normalized.get("source_plus_ext_id")
    if isinstance(source_plus_ext_id, str):
        candidates.add(f"EPMC:{source_plus_ext_id}")

    matched = {known[key] for key in candidates if key in known}
    if len(matched) > 1:
        raise ValueError(
            "Exact publication identifiers resolve to conflicting controlled Sources: "
            f"identities={sorted(candidates)} source_ids={sorted(matched)}"
        )
    return next(iter(matched)) if matched else None


def _anchor_identity_set(values: Sequence[str] | None) -> set[str]:
    anchors: set[str] = set()
    for raw_identity in values or []:
        identity = _text(raw_identity, "known_anchor_identities item")
        if identity in anchors:
            raise ValueError(f"Duplicate known anchor identity {identity}")
        anchors.add(identity)
    return anchors


def _result_rows(payload: Mapping[str, Any], page_index: int) -> list[dict[str, Any]]:
    result_list = payload.get("resultList")
    if not isinstance(result_list, Mapping):
        raise ValueError(f"page {page_index}: resultList must be an object")
    rows = result_list.get("result")
    if rows is None:
        return []
    if not isinstance(rows, list):
        raise ValueError(f"page {page_index}: resultList.result must be an array")
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"page {page_index}: every result must be an object")
    return [dict(row) for row in rows]


def _normalized_record(raw: Mapping[str, Any], *, query_id: str) -> dict[str, Any]:
    source = _normalize_source(raw.get("source"))
    ext_id = _normalize_ext_id(raw.get("id"))
    identity_type, resolved_identity = _resolved_identity(raw)
    publication_type = _publication_type(raw.get("pubType"))
    content = {
        "record_kind": "NORMALIZED_EUROPEPMC_PUBLICATION",
        "resolved_identity": resolved_identity,
        "identity_type": identity_type,
        "source": source,
        "ext_id": ext_id,
        "source_plus_ext_id": f"{source}:{ext_id}",
        "pmid": _normalize_pmid(raw.get("pmid")),
        "pmcid": _normalize_pmcid(raw.get("pmcid")),
        "doi": _normalize_doi(raw.get("doi")),
        "title": _optional_text(raw.get("title")),
        "author_string": _optional_text(raw.get("authorString")),
        "journal_or_source": _optional_text(raw.get("journalTitle")) or source,
        "publication_year": _optional_text(raw.get("pubYear")),
        "publication_type": publication_type,
        "is_preprint": _is_preprint(source, publication_type),
        "boundary": (
            "Normalized Europe PMC lite metadata for discovery identity and mechanical "
            "reconciliation only; not a relevance, quality, peer-review, or truth determination."
        ),
    }
    return {
        **content,
        "query_memberships": [query_id],
        "normalized_record_sha256": _canonical_json_sha256(content),
    }


def project_search_pages(
    *,
    query_id: str,
    query_text: str,
    pages: Sequence[Mapping[str, Any]],
    known_publication_sources: Mapping[str, str] | None = None,
    known_anchor_identities: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Project supplied Europe PMC search pages into generic discovery result records.

    Exact publication identities are resolved in DOI -> PMID -> PMCID -> source+id order. Fuzzy
    title matching is never performed. Identical same-identity representations collapse while
    conflicting normalized state fails closed. Cursor termination and reported-hit reconciliation
    are separate exact-traversal facts and never imply literature or NeuroAI recall completeness.
    """

    qid = _text(query_id, "query_id")
    qtext = _text(query_text, "query_text")
    if not pages:
        raise ValueError("At least one Europe PMC search page is required")
    known = _known_identity_index(known_publication_sources)
    anchors = _anchor_identity_set(known_anchor_identities)

    by_identity: dict[str, dict[str, Any]] = {}
    page_reports: list[dict[str, Any]] = []
    raw_record_count = 0
    duplicate_representation_count = 0
    reported_hit_counts: list[int] = []

    for index, raw_page in enumerate(pages, start=1):
        if not isinstance(raw_page, Mapping):
            raise ValueError(f"page {index}: page must be an object")
        payload = _page_payload(raw_page, index)
        rows = _result_rows(payload, index)
        raw_record_count += len(rows)

        hit_count = payload.get("hitCount")
        if hit_count is not None:
            if not isinstance(hit_count, int) or isinstance(hit_count, bool) or hit_count < 0:
                raise ValueError(f"page {index}: hitCount must be non-negative integer/null")
            reported_hit_counts.append(hit_count)

        next_cursor = payload.get("nextCursorMark")
        if next_cursor is not None and (not isinstance(next_cursor, str) or not next_cursor.strip()):
            raise ValueError(f"page {index}: nextCursorMark must be non-empty string/null")

        page_identities: list[str] = []
        for raw_record in rows:
            normalized = _normalized_record(raw_record, query_id=qid)
            identity = normalized["resolved_identity"]
            page_identities.append(identity)
            prior = by_identity.get(identity)
            if prior is None:
                by_identity[identity] = normalized
            elif prior == normalized:
                duplicate_representation_count += 1
            else:
                raise ValueError(f"Conflicting normalized Europe PMC representations for {identity}")

        page_reports.append(
            {
                "page_index": index,
                "returned_record_count": len(rows),
                "unique_resolved_identities_on_page": len(set(page_identities)),
                "reported_hit_count": hit_count,
                "next_cursor_mark_present": next_cursor is not None,
            }
        )

    for report in page_reports[:-1]:
        if not report["next_cursor_mark_present"]:
            raise ValueError(
                f"Invalid Europe PMC pagination sequence: non-final page {report['page_index']} has no nextCursorMark"
            )

    distinct_hits = sorted(set(reported_hit_counts))
    if not reported_hit_counts:
        hit_count_state = "NOT_REPORTED"
        reported_hit_count: int | None = None
    elif len(distinct_hits) == 1:
        hit_count_state = "CONSISTENT"
        reported_hit_count = distinct_hits[0]
    else:
        hit_count_state = "INCONSISTENT_ACROSS_PAGES"
        reported_hit_count = None

    final_has_more = bool(page_reports[-1]["next_cursor_mark_present"])
    terminal_cursor_state = "NONTERMINAL" if final_has_more else "TERMINAL"
    if reported_hit_count is None:
        reconciliation_state = "DENOMINATOR_UNAVAILABLE"
    elif final_has_more:
        reconciliation_state = "PARTIAL_TRAVERSAL_NOT_RECONCILED"
    elif len(by_identity) == reported_hit_count:
        reconciliation_state = "MATCH"
    else:
        reconciliation_state = "MISMATCH"

    result_records: list[dict[str, Any]] = []
    normalized_records: list[dict[str, Any]] = []
    known_duplicates: list[dict[str, str]] = []
    preprint_count = 0
    non_preprint_count = 0
    missing_publication_type_count = 0
    source_distribution: Counter[str] = Counter()
    anchor_hits: list[str] = []

    for identity in sorted(by_identity):
        normalized = by_identity[identity]
        source = normalized["source"]
        ext_id = normalized["ext_id"]
        title = normalized.get("title") or identity
        duplicate_of = _known_source_match(normalized, known)
        source_distribution[source] += 1
        if normalized["is_preprint"]:
            preprint_count += 1
        else:
            non_preprint_count += 1
        if normalized["publication_type"] is None:
            missing_publication_type_count += 1
        if identity in anchors:
            anchor_hits.append(identity)
        record: dict[str, Any] = {
            "record_key": identity,
            "title": title,
            "url": (f"{EUROPE_PMC_ARTICLE_PREFIX}{quote(source, safe='')}/{quote(ext_id, safe='')}"),
            "publisher": "Europe PMC",
            "source_class": "OFFICIAL_BIBLIOGRAPHIC_METADATA",
            "suggested_source_id": _suggested_source_id(identity),
            "classification_hint": "DUPLICATE" if duplicate_of is not None else "NEW",
        }
        if duplicate_of is not None:
            record["duplicate_of_source_id"] = duplicate_of
            known_duplicates.append({"resolved_identity": identity, "source_id": duplicate_of})
        result_records.append(record)
        normalized_records.append(normalized)

    missing_anchor_identities = sorted(anchors.difference(by_identity))
    coverage = {
        "source_system": "EUROPE_PMC",
        "query_id": qid,
        "query_text": qtext,
        "supplied_page_count": len(pages),
        "raw_returned_record_count": raw_record_count,
        "unique_resolved_identity_count": len(by_identity),
        "known_anchor_count": len(anchor_hits),
        "known_anchor_identities_found": sorted(anchor_hits),
        "known_anchor_identities_missing": missing_anchor_identities,
        "known_controlled_source_duplicate_count": len(known_duplicates),
        "known_controlled_source_duplicates": known_duplicates,
        "new_candidate_count": len(result_records) - len(known_duplicates),
        "cross_query_duplicate_representation_count": duplicate_representation_count,
        "unresolved_identity_count": 0,
        "preprint_count": preprint_count,
        "non_preprint_record_count": non_preprint_count,
        "publication_type_missing_count": missing_publication_type_count,
        "source_distribution": dict(sorted(source_distribution.items())),
        "reported_hit_count_state": hit_count_state,
        "reported_hit_count": reported_hit_count,
        "reported_hit_count_values": distinct_hits,
        "cursor_sequence_valid": True,
        "terminal_cursor_state": terminal_cursor_state,
        "reported_total_reconciliation_state": reconciliation_state,
        "page_reports": page_reports,
        "publication_database_completeness_claim": False,
        "query_recall_claim": False,
        "global_neuroai_publication_recall_claim": False,
        "automatic_source_admission_performed": False,
        "automatic_relationship_creation_performed": False,
        "automatic_assessment_mutation_performed": False,
        "boundary": DISCOVERY_BOUNDARY,
    }
    return {
        "result_records": result_records,
        "normalized_records": normalized_records,
        "coverage": coverage,
    }
