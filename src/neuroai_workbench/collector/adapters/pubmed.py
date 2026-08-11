"""PubMed / PMC (+ Crossref DOI) publication metadata adapter.

Rewrites sources with explicit PMID, PMCID, or DOI to reviewed NCBI E-utilities
or Crossref API URLs. Capture proves retrieval of selected metadata payloads
only — not literature-corpus completeness or publication authenticity beyond
retrieved bytes.
"""

from __future__ import annotations

import re
from typing import Any, Literal
from urllib.parse import quote

from ..schemas import validate_or_raise
from ..service import CollectionOutcome, HttpCollector, PriorCapture
from .base import HttpCollectorAdapter
from .structured import (
    NORMALIZED_PUBLICATION_SCHEMA,
    aggregate_digest,
    field_digest,
    field_digests_for,
    load_adapter_contract,
)

PUBMED_ADAPTER_ID = "pubmed_crossref"
EUTILS_SUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
CROSSREF_WORKS = "https://api.crossref.org/works"

_PMID_RE = re.compile(r"\bPMID[:\s-]*([0-9]{5,9})\b", re.I)
_PMID_BARE_RE = re.compile(r"\b([0-9]{7,8})\b")
_PMCID_RE = re.compile(r"\bPMC\d+\b", re.I)
_DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.I)

IdType = Literal["PMID", "PMCID", "DOI"]

PUBLICATION_BOUNDARY = (
    "Normalized publication metadata for mechanical field-change detection only. "
    "Does not establish authenticity beyond retrieved metadata bytes or literature completeness."
)


class PubmedCrossrefAdapter(HttpCollectorAdapter):
    adapter_id = PUBMED_ADAPTER_ID

    _SOURCE_CLASSES = frozenset(
        {
            "PEER_REVIEWED_PRIMARY_CLINICAL_STUDY",
            "OFFICIAL_BIBLIOGRAPHIC_METADATA",
            "PUBLICATION_RECORD",
        }
    )

    def __init__(self, collector: HttpCollector) -> None:
        super().__init__(collector)
        self.contract = load_adapter_contract(PUBMED_ADAPTER_ID)

    def supports_source_class(self, source_class: str) -> bool:
        return source_class in self._SOURCE_CLASSES

    def extract_publication_id(
        self,
        source_record: dict[str, Any] | None,
        request: dict[str, Any],
    ) -> tuple[IdType, str] | None:
        candidates: list[str] = []
        if source_record:
            for key in ("pmid", "pmcid", "doi", "publication_id"):
                value = source_record.get(key)
                if isinstance(value, str):
                    candidates.append(value)
            metadata = source_record.get("metadata")
            if isinstance(metadata, dict):
                for key in ("pmid", "pmcid", "doi"):
                    value = metadata.get(key)
                    if isinstance(value, str):
                        candidates.append(value)
        candidates.append(str(request.get("requested_url") or ""))

        for candidate in candidates:
            pmc = _PMCID_RE.search(candidate)
            if pmc:
                return "PMCID", pmc.group(0).upper()
            doi = _DOI_RE.search(candidate)
            if doi:
                return "DOI", doi.group(0)
            pmid = _PMID_RE.search(candidate)
            if pmid:
                return "PMID", pmid.group(1)

        # Prefer explicit metadata keys over bare numeric URL segments.
        if source_record:
            for key in ("pmid",):
                value = source_record.get(key)
                if isinstance(value, str) and value.isdigit():
                    return "PMID", value
            metadata = source_record.get("metadata")
            if isinstance(metadata, dict):
                value = metadata.get("pmid")
                if isinstance(value, str) and value.isdigit():
                    return "PMID", value

        for candidate in candidates:
            if "pubmed.ncbi.nlm.nih.gov" in candidate.lower():
                bare = _PMID_BARE_RE.search(candidate)
                if bare:
                    return "PMID", bare.group(1)
        return None

    def supports_source(self, source_record: dict[str, Any], request: dict[str, Any] | None = None) -> bool:
        if not self.supports_source_class(str(source_record.get("source_class", ""))):
            return False
        synthetic = request or {"requested_url": source_record.get("url", "")}
        return self.extract_publication_id(source_record, synthetic) is not None

    def build_retrieval_url(self, id_type: IdType, identifier: str) -> str:
        if id_type == "DOI":
            # Query form keeps quarantine filenames free of percent-encoded path separators.
            return f"{CROSSREF_WORKS}?filter=doi:{quote(identifier, safe='')}"
        if id_type == "PMCID":
            return f"{EUTILS_SUMMARY}?db=pmc&id={quote(identifier.replace('PMC', ''), safe='')}&retmode=json"
        return f"{EUTILS_SUMMARY}?db=pubmed&id={quote(identifier, safe='')}&retmode=json"

    def normalize_publication(
        self,
        payload: dict[str, Any],
        *,
        id_type: IdType,
        identifier: str,
    ) -> dict[str, Any]:
        title: str | None = None
        journal: str | None = None
        publication_date: str | None = None
        doi: str | None = None
        authors: Any = None

        if id_type == "DOI":
            message = payload.get("message")
            if isinstance(message, dict):
                titles = message.get("title")
                if isinstance(titles, list) and titles and isinstance(titles[0], str):
                    title = titles[0]
                container = message.get("container-title")
                if isinstance(container, list) and container and isinstance(container[0], str):
                    journal = container[0]
                issued = message.get("issued")
                if isinstance(issued, dict) and isinstance(issued.get("date-parts"), list):
                    parts = issued["date-parts"]
                    if parts and isinstance(parts[0], list):
                        publication_date = "-".join(str(p) for p in parts[0])
                if isinstance(message.get("DOI"), str):
                    doi = message["DOI"]
                authors = message.get("author")
        else:
            result = payload.get("result")
            if isinstance(result, dict):
                uids = result.get("uids")
                docs = None
                if isinstance(uids, list) and uids:
                    docs = result.get(str(uids[0]))
                if isinstance(docs, dict):
                    title = docs.get("title") if isinstance(docs.get("title"), str) else None
                    journal = docs.get("fulljournalname") if isinstance(docs.get("fulljournalname"), str) else None
                    publication_date = docs.get("pubdate") if isinstance(docs.get("pubdate"), str) else None
                    articleids = docs.get("articleids")
                    if isinstance(articleids, list):
                        for item in articleids:
                            if (
                                isinstance(item, dict)
                                and item.get("idtype") == "doi"
                                and isinstance(item.get("value"), str)
                            ):
                                doi = item["value"]
                                break
                    authors = docs.get("authors")

        fields = {
            "primary_id": identifier.upper() if id_type != "DOI" else identifier,
            "title": title,
            "journal": journal,
            "publication_date": publication_date,
            "doi": doi,
        }
        digests = field_digests_for(fields)
        record = {
            "record_kind": "NORMALIZED_PUBLICATION",
            "primary_id": fields["primary_id"],
            "id_type": id_type,
            "title": title,
            "journal": journal,
            "publication_date": publication_date,
            "doi": doi,
            "authors_digest": field_digest(authors) if authors is not None else None,
            "field_digests": digests,
            "aggregate_digest": aggregate_digest(digests),
            "boundary": PUBLICATION_BOUNDARY,
        }
        validate_or_raise(record, NORMALIZED_PUBLICATION_SCHEMA)
        return record

    def resolve_request(
        self,
        request: dict[str, Any],
        *,
        source_record: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        extracted = self.extract_publication_id(source_record, request)
        if extracted is None:
            return dict(request)
        id_type, identifier = extracted
        return {**request, "requested_url": self.build_retrieval_url(id_type, identifier)}

    def collect(
        self,
        request: dict[str, Any],
        *,
        prior_capture: PriorCapture | None = None,
        attempt_count: int = 1,
        source_record: dict[str, Any] | None = None,
    ) -> CollectionOutcome:
        resolved = self.resolve_request(request, source_record=source_record)
        return super().collect(resolved, prior_capture=prior_capture, attempt_count=attempt_count)
