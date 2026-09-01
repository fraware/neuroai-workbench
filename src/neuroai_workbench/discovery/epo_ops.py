"""Bounded EPO OPS search-page projection for patent-publication discovery.

Callers supply already-retrieved OPS XML search responses. This module performs no network I/O,
uses exact DOCDB publication references as discovery identity, and never infers patent-family,
applicant, inventor, product, system, capability, validity, enforceability, deployment, or
assessment relationships from a search hit.
"""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import quote

OPS_MAX_RANGE = 100
OPS_MAX_RETRIEVABLE_RESULTS = 2000
ESPACENET_SEARCH_PREFIX = "https://worldwide.espacenet.com/patent/search?q=pn%3D"
_DOC_NUMBER_RE = re.compile(r"^[A-Z0-9./-]+$", re.I)
_KIND_RE = re.compile(r"^[A-Z][A-Z0-9]*$", re.I)

DISCOVERY_BOUNDARY = (
    "EPO OPS search projection produces patent-publication discovery candidates for one exact "
    "configured search traversal only. A patent publication does not establish implementation, "
    "product integration, deployment, safety, effectiveness, validity, enforceability, freedom "
    "to operate, present ownership, patent-family identity, system capability, assessment effect, "
    "canonical publication, or global NeuroAI patent recall."
)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag.split(":")[-1]


def _child_text(element: ET.Element, name: str) -> str | None:
    for child in element.iter():
        if _local(child.tag) == name and child.text and child.text.strip():
            return child.text.strip()
    return None


def _direct_child_text(element: ET.Element, name: str) -> str | None:
    for child in element:
        if _local(child.tag) == name and child.text and child.text.strip():
            return child.text.strip()
    return None


def _normalize_country(value: Any) -> str:
    country = _text(value, "DOCDB country").upper()
    if not re.fullmatch(r"[A-Z]{2}", country):
        raise ValueError(f"Invalid DOCDB country {country!r}")
    return country


def _normalize_doc_number(value: Any) -> str:
    number = re.sub(r"\s+", "", _text(value, "DOCDB document number")).upper()
    if not _DOC_NUMBER_RE.fullmatch(number):
        raise ValueError(f"Invalid DOCDB document number {number!r}")
    return number


def _normalize_kind(value: Any) -> str:
    kind = re.sub(r"\s+", "", _text(value, "DOCDB kind code")).upper()
    if not _KIND_RE.fullmatch(kind):
        raise ValueError(f"Invalid DOCDB kind code {kind!r}")
    return kind


def _docdb_identity(country: str, document_number: str, kind_code: str) -> str:
    return f"DOCDB:{country}:{document_number}:{kind_code}"


def _docdb_from_document_id(element: ET.Element) -> tuple[str, str, str] | None:
    if _local(element.tag) != "document-id":
        return None
    doc_type = str(element.attrib.get("document-id-type") or "").lower()
    if doc_type and doc_type != "docdb":
        return None
    country = _direct_child_text(element, "country")
    number = _direct_child_text(element, "doc-number")
    kind = _direct_child_text(element, "kind")
    if country is None or number is None or kind is None:
        return None
    return _normalize_country(country), _normalize_doc_number(number), _normalize_kind(kind)


def _docdb_from_element(element: ET.Element) -> tuple[str, str, str] | None:
    if _local(element.tag) == "exchange-document":
        country = element.attrib.get("country")
        number = element.attrib.get("doc-number")
        kind = element.attrib.get("kind")
        if country and number and kind:
            return _normalize_country(country), _normalize_doc_number(number), _normalize_kind(kind)
    for descendant in element.iter():
        parsed = _docdb_from_document_id(descendant)
        if parsed is not None:
            return parsed
    return None


def _canonical_json_sha256(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _suggested_source_id(identity: str) -> str:
    token = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20].upper()
    return f"SRC-OPS-{token}"


def _first_english_or_first(elements: Sequence[ET.Element]) -> str | None:
    values: list[tuple[str | None, str]] = []
    for element in elements:
        text = " ".join(part.strip() for part in element.itertext() if part.strip())
        if text:
            lang = element.attrib.get("lang") or element.attrib.get("language")
            values.append((str(lang).lower() if lang else None, text))
    if not values:
        return None
    for lang, text in values:
        if lang in {"en", "eng"}:
            return text
    return values[0][1]


def _elements_named(root: ET.Element, name: str) -> list[ET.Element]:
    return [element for element in root.iter() if _local(element.tag) == name]


def _names_from_container(root: ET.Element, container_name: str, item_name: str) -> list[str]:
    values: list[str] = []
    for container in _elements_named(root, container_name):
        for item in container.iter():
            if _local(item.tag) != item_name:
                continue
            text = " ".join(part.strip() for part in item.itertext() if part.strip())
            if text and text not in values:
                values.append(text)
    return values


def _classification_values(root: ET.Element, family: str) -> list[str]:
    values: list[str] = []
    if family == "IPC":
        accepted = {"classification-ipc", "classification-ipcr", "main-classification", "further-classification"}
        for element in root.iter():
            if _local(element.tag) not in accepted:
                continue
            text = " ".join(part.strip() for part in element.itertext() if part.strip())
            if text and text not in values:
                values.append(text)
    else:
        for element in root.iter():
            if _local(element.tag) != "patent-classification":
                continue
            scheme = str(element.attrib.get("classification-scheme") or element.attrib.get("scheme") or "").upper()
            symbol = _child_text(element, "classification-symbol")
            if symbol and ("CPC" in scheme or not scheme):
                symbol = " ".join(symbol.split())
                if symbol not in values:
                    values.append(symbol)
    return values


def _reference_values(root: ET.Element, container_names: set[str]) -> list[str]:
    values: list[str] = []
    for container in root.iter():
        if _local(container.tag) not in container_names:
            continue
        for doc_id in container.iter():
            if _local(doc_id.tag) != "document-id":
                continue
            parsed = _docdb_from_document_id(doc_id)
            if parsed is not None:
                value = _docdb_identity(*parsed)
            else:
                number = _direct_child_text(doc_id, "doc-number")
                country = _direct_child_text(doc_id, "country")
                kind = _direct_child_text(doc_id, "kind")
                date = _direct_child_text(doc_id, "date")
                parts = [part for part in (country, number, kind, date) if part]
                if not parts:
                    continue
                value = ":".join(parts)
            if value not in values:
                values.append(value)
    return values


def _publication_date(root: ET.Element) -> str | None:
    for reference in _elements_named(root, "publication-reference"):
        date = _child_text(reference, "date")
        if date:
            return date
    return None


def _normalize_record(element: ET.Element, *, query_id: str) -> dict[str, Any]:
    parsed = _docdb_from_element(element)
    if parsed is None:
        raise ValueError("OPS publication record has no exact DOCDB publication reference")
    country, document_number, kind_code = parsed
    identity = _docdb_identity(country, document_number, kind_code)
    titles = _elements_named(element, "invention-title")
    abstracts = _elements_named(element, "abstract")
    normalized: dict[str, Any] = {
        "record_kind": "NORMALIZED_EPO_OPS_PATENT_PUBLICATION",
        "docdb_publication_reference": identity,
        "country": country,
        "document_number": document_number,
        "kind_code": kind_code,
        "title": _first_english_or_first(titles),
        "publication_date": _publication_date(element),
        "applicants": _names_from_container(element, "applicants", "name"),
        "inventors": _names_from_container(element, "inventors", "name"),
        "ipc_symbols": _classification_values(element, "IPC"),
        "cpc_symbols": _classification_values(element, "CPC"),
        "application_references": _reference_values(element, {"application-reference"}),
        "priority_references": _reference_values(element, {"priority-claim", "priority-claims"}),
        "abstract": _first_english_or_first(abstracts),
        "query_memberships": [query_id],
        "boundary": (
            "Normalized OPS bibliographic/search metadata for exact publication identity and discovery review only; "
            "not evidence of implementation, patent-family identity, present ownership, validity, enforceability, "
            "freedom to operate, deployment, system capability, safety, effectiveness, or conformance."
        ),
    }
    digest_input = dict(normalized)
    digest_input.pop("query_memberships", None)
    normalized["normalized_record_sha256"] = _canonical_json_sha256(digest_input)
    return normalized


def _page_xml(raw: Mapping[str, Any] | str, index: int) -> str:
    if isinstance(raw, str):
        return _text(raw, f"page {index} XML")
    if not isinstance(raw, Mapping):
        raise ValueError(f"page {index}: expected XML string or object")
    xml = raw.get("xml")
    return _text(xml, f"page {index} xml")


def _parse_page(raw: Mapping[str, Any] | str, index: int) -> tuple[ET.Element, int | None, tuple[int, int] | None]:
    xml = _page_xml(raw, index)
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ValueError(f"page {index}: invalid OPS XML") from exc

    searches = _elements_named(root, "biblio-search")
    if len(searches) != 1:
        raise ValueError(f"page {index}: expected exactly one biblio-search element")
    raw_total = searches[0].attrib.get("total-result-count")
    total: int | None = None
    if raw_total is not None:
        try:
            total = int(raw_total)
        except ValueError as exc:
            raise ValueError(f"page {index}: invalid total-result-count {raw_total!r}") from exc
        if total < 0:
            raise ValueError(f"page {index}: total-result-count must be non-negative")

    ranges = _elements_named(searches[0], "range")
    page_range: tuple[int, int] | None = None
    if ranges:
        if len(ranges) != 1:
            raise ValueError(f"page {index}: expected at most one range element")
        try:
            begin = int(ranges[0].attrib["begin"])
            end = int(ranges[0].attrib["end"])
        except (KeyError, ValueError) as exc:
            raise ValueError(f"page {index}: invalid OPS range") from exc
        if begin < 1 or end < begin or (end - begin + 1) > OPS_MAX_RANGE:
            raise ValueError(f"page {index}: OPS range must be positive and no wider than {OPS_MAX_RANGE}")
        page_range = (begin, end)
    return root, total, page_range


def _publication_elements(root: ET.Element) -> list[ET.Element]:
    exchange = _elements_named(root, "exchange-document")
    if exchange:
        return exchange
    return _elements_named(root, "publication-reference")


def _known_index(values: Mapping[str, str] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_identity, raw_source_id in (values or {}).items():
        identity = _text(raw_identity, "known_docdb_sources key")
        source_id = _text(raw_source_id, f"known_docdb_sources[{identity}]")
        if not identity.startswith("DOCDB:"):
            raise ValueError(f"Known EPO OPS identity must be DOCDB, got {identity!r}")
        prior = result.get(identity)
        if prior is not None and prior != source_id:
            raise ValueError(f"Conflicting controlled Sources for {identity}: {prior} vs {source_id}")
        result[identity] = source_id
    return result


def project_search_pages(
    *,
    query_id: str,
    query_text: str,
    pages: Sequence[Mapping[str, Any] | str],
    known_docdb_sources: Mapping[str, str] | None = None,
    max_retrievable_results: int = OPS_MAX_RETRIEVABLE_RESULTS,
) -> dict[str, Any]:
    """Project recorded OPS search pages into patent-publication discovery candidates.

    Candidate emission is refused when the exact OPS search denominator exceeds the configured
    retrievable-result ceiling. Such searches require explicit partitioning before materialization.
    """
    qid = _text(query_id, "query_id")
    qtext = _text(query_text, "query_text")
    if not pages:
        raise ValueError("At least one EPO OPS search page is required")
    if max_retrievable_results != OPS_MAX_RETRIEVABLE_RESULTS:
        raise ValueError(f"OPS max retrievable results must remain {OPS_MAX_RETRIEVABLE_RESULTS}")
    known = _known_index(known_docdb_sources)

    totals: list[int] = []
    ranges: list[tuple[int, int] | None] = []
    by_identity: dict[str, dict[str, Any]] = {}
    raw_reference_count = 0
    duplicate_representation_count = 0
    page_reports: list[dict[str, Any]] = []

    for index, raw_page in enumerate(pages, start=1):
        root, total, page_range = _parse_page(raw_page, index)
        if total is not None:
            totals.append(total)
        ranges.append(page_range)
        elements = _publication_elements(root)
        raw_reference_count += len(elements)
        page_identities: list[str] = []
        for element in elements:
            normalized = _normalize_record(element, query_id=qid)
            identity = normalized["docdb_publication_reference"]
            page_identities.append(identity)
            prior = by_identity.get(identity)
            if prior is None:
                by_identity[identity] = normalized
                continue
            prior_content = dict(prior)
            current_content = dict(normalized)
            prior_content.pop("query_memberships", None)
            current_content.pop("query_memberships", None)
            if prior_content != current_content:
                raise ValueError(f"Conflicting normalized OPS representations for {identity}")
            duplicate_representation_count += 1

        page_reports.append(
            {
                "page_index": index,
                "reported_total_result_count": total,
                "range_begin": page_range[0] if page_range else None,
                "range_end": page_range[1] if page_range else None,
                "returned_publication_reference_count": len(elements),
                "unique_docdb_identities_on_page": len(set(page_identities)),
            }
        )

    distinct_totals = sorted(set(totals))
    if not totals:
        total_state = "NOT_REPORTED"
        reported_total: int | None = None
    elif len(distinct_totals) == 1:
        total_state = "CONSISTENT"
        reported_total = distinct_totals[0]
    else:
        total_state = "INCONSISTENT_ACROSS_PAGES"
        reported_total = None

    ranges_present = all(item is not None for item in ranges)
    sequence_valid = ranges_present
    if ranges_present:
        concrete = [item for item in ranges if item is not None]
        if concrete[0][0] != 1:
            sequence_valid = False
        for previous, current in zip(concrete, concrete[1:]):
            if current[0] != previous[1] + 1:
                sequence_valid = False
                break

    over_limit = reported_total is not None and reported_total > max_retrievable_results
    partition_required = over_limit
    if reported_total is None:
        range_coverage_state = "DENOMINATOR_UNAVAILABLE"
    elif over_limit:
        range_coverage_state = "OVER_LIMIT_PARTITION_REQUIRED"
    elif not sequence_valid:
        range_coverage_state = "INVALID_SEQUENCE"
    elif len(by_identity) == reported_total:
        range_coverage_state = "MATCH"
    else:
        range_coverage_state = "PARTIAL_OR_MISMATCH"

    known_duplicates: list[dict[str, str]] = []
    result_records: list[dict[str, Any]] = []
    normalized_records: list[dict[str, Any]] = []

    if not over_limit:
        for identity in sorted(by_identity):
            normalized = by_identity[identity]
            duplicate_of = known.get(identity)
            title = normalized.get("title") or identity
            pn = f"{normalized['country']}{normalized['document_number']}{normalized['kind_code']}"
            record: dict[str, Any] = {
                "record_key": identity,
                "title": title,
                "url": f"{ESPACENET_SEARCH_PREFIX}{quote(pn, safe='')}",
                "publisher": "European Patent Office Open Patent Services",
                "source_class": "OFFICIAL_PATENT_BIBLIOGRAPHIC_METADATA",
                "suggested_source_id": _suggested_source_id(identity),
                "classification_hint": "DUPLICATE" if duplicate_of is not None else "NEW",
            }
            if duplicate_of is not None:
                record["duplicate_of_source_id"] = duplicate_of
                known_duplicates.append({"docdb_publication_reference": identity, "source_id": duplicate_of})
            result_records.append(record)
            normalized_records.append(normalized)

    coverage = {
        "source_system": "EPO_OPS",
        "query_id": qid,
        "query_text": qtext,
        "requested_range_count": len(pages),
        "returned_publication_reference_count": raw_reference_count,
        "unique_docdb_publication_count": len(by_identity),
        "reported_total_result_count": reported_total,
        "reported_total_result_count_state": total_state,
        "reported_total_result_count_values": distinct_totals,
        "range_sequence_valid": sequence_valid,
        "range_coverage_state": range_coverage_state,
        "over_2000_limit": over_limit,
        "partition_required": partition_required,
        "candidate_emission_refused_due_to_over_limit": over_limit,
        "known_controlled_duplicate_count": len(known_duplicates),
        "known_controlled_duplicates": known_duplicates,
        "new_candidate_count": len(result_records) - len(known_duplicates),
        "cross_query_duplicate_representation_count": duplicate_representation_count,
        "unresolved_docdb_identity_count": 0,
        "page_reports": page_reports,
        "epo_database_completeness_claim": False,
        "global_neuroai_patent_recall_claim": False,
        "query_recall_claim": False,
        "patent_family_completeness_claim": False,
        "automatic_source_admission_performed": False,
        "automatic_family_creation_performed": False,
        "automatic_entity_creation_performed": False,
        "automatic_product_or_system_relationship_creation_performed": False,
        "automatic_capability_claim_creation_performed": False,
        "automatic_assessment_mutation_performed": False,
        "boundary": DISCOVERY_BOUNDARY,
    }
    return {
        "result_records": result_records,
        "normalized_records": normalized_records,
        "coverage": coverage,
    }
