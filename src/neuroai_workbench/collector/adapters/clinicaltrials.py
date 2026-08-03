"""ClinicalTrials.gov structured study adapter.

Supports:
- NCT identifier rewrite to the CT.gov studies API
- Search query URL construction with pagination tokens
- Normalized study projection and field-level digest comparison

Capture proves retrieval of the selected study or search payload only — not
registry completeness or clinical truth. CI uses recorded fixtures through the
injectable transport.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlencode

from ..schemas import validate_or_raise
from ..service import CollectionOutcome, HttpCollector, PriorCapture
from .base import HttpCollectorAdapter
from .structured import (
    NORMALIZED_STUDY_SCHEMA,
    aggregate_digest,
    changed_fields,
    field_digests_for,
    load_adapter_contract,
)

CTGOV_ADAPTER_ID = "clinicaltrials_gov"
CTGOV_API_PREFIX = "https://clinicaltrials.gov/api/v2/studies/"
CTGOV_SEARCH_URL = "https://clinicaltrials.gov/api/v2/studies"
_NCT_RE = re.compile(r"\bNCT\d{8}\b", re.I)

STUDY_BOUNDARY = (
    "Normalized CT.gov study projection for mechanical field-change detection only. "
    "Does not establish clinical truth or registry completeness."
)

_CHANGE_FIELD_KEYS = (
    "nct_id",
    "brief_title",
    "overall_status",
    "last_update_post_date",
    "primary_completion_date",
    "enrollment_count",
    "phase",
)


class ClinicalTrialsGovAdapter(HttpCollectorAdapter):
    adapter_id = CTGOV_ADAPTER_ID

    _SOURCE_CLASSES = frozenset(
        {
            "CLINICAL_TRIAL_REGISTRY",
            "OFFICIAL_TRIAL_REGISTRY",
            "OFFICIAL_TRIAL_PAGE",
        }
    )

    def __init__(self, collector: HttpCollector) -> None:
        super().__init__(collector)
        self.contract = load_adapter_contract(CTGOV_ADAPTER_ID)

    def supports_source_class(self, source_class: str) -> bool:
        return source_class in self._SOURCE_CLASSES

    def extract_nct_id(self, source_record: dict[str, Any] | None, request: dict[str, Any]) -> str | None:
        candidates: list[str] = []
        if source_record:
            for key in ("nct_id", "trial_id", "registry_id"):
                value = source_record.get(key)
                if isinstance(value, str):
                    candidates.append(value)
            metadata = source_record.get("metadata")
            if isinstance(metadata, dict):
                value = metadata.get("nct_id")
                if isinstance(value, str):
                    candidates.append(value)
        candidates.append(str(request.get("requested_url") or ""))
        for candidate in candidates:
            match = _NCT_RE.search(candidate)
            if match:
                return match.group(0).upper()
        return None

    def extract_search_query(self, source_record: dict[str, Any] | None) -> str | None:
        if not source_record:
            return None
        for key in ("search_query", "ctgov_query"):
            value = source_record.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        metadata = source_record.get("metadata")
        if isinstance(metadata, dict):
            for key in ("search_query", "ctgov_query", "query.term"):
                value = metadata.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    def extract_page_token(self, source_record: dict[str, Any] | None) -> str | None:
        if not source_record:
            return None
        token = source_record.get("page_token")
        if isinstance(token, str) and token.strip():
            return token.strip()
        metadata = source_record.get("metadata")
        if isinstance(metadata, dict):
            token = metadata.get("page_token")
            if isinstance(token, str) and token.strip():
                return token.strip()
        return None

    def extract_page_size(self, source_record: dict[str, Any] | None) -> int:
        default = 10
        if not source_record:
            return default
        raw: Any = source_record.get("page_size")
        metadata = source_record.get("metadata")
        if raw is None and isinstance(metadata, dict):
            raw = metadata.get("page_size")
        if isinstance(raw, bool):
            return default
        if isinstance(raw, int) and 1 <= raw <= 100:
            return raw
        if isinstance(raw, str) and raw.isdigit():
            value = int(raw)
            if 1 <= value <= 100:
                return value
        return default

    def build_study_url(self, nct_id: str) -> str:
        return f"{CTGOV_API_PREFIX}{nct_id.upper()}"

    def build_search_url(
        self,
        query: str,
        *,
        page_size: int = 10,
        page_token: str | None = None,
    ) -> str:
        params: dict[str, str] = {
            "query.term": query,
            "pageSize": str(page_size),
            "format": "json",
        }
        if page_token:
            params["pageToken"] = page_token
        return f"{CTGOV_SEARCH_URL}?{urlencode(params)}"

    def parse_search_page(self, payload: dict[str, Any]) -> dict[str, Any]:
        studies = payload.get("studies")
        if not isinstance(studies, list):
            studies = []
        next_token = payload.get("nextPageToken")
        if not isinstance(next_token, str) or not next_token.strip():
            next_token = None
        else:
            next_token = next_token.strip()
        total = payload.get("totalCount")
        if not isinstance(total, int):
            total = None
        return {
            "studies": studies,
            "next_page_token": next_token,
            "total_count": total,
            "has_more": next_token is not None,
        }

    def normalize_study(self, study_payload: dict[str, Any]) -> dict[str, Any]:
        protocol = study_payload.get("protocolSection")
        if not isinstance(protocol, dict):
            protocol = {}
        identification = protocol.get("identificationModule")
        status = protocol.get("statusModule")
        design = protocol.get("designModule")
        if not isinstance(identification, dict):
            identification = {}
        if not isinstance(status, dict):
            status = {}
        if not isinstance(design, dict):
            design = {}

        nct_raw = identification.get("nctId")
        nct_id = str(nct_raw).upper() if isinstance(nct_raw, str) and _NCT_RE.fullmatch(str(nct_raw).upper()) else None
        if nct_id is None:
            raise ValueError("Study payload missing usable NCT identifier")

        completion = status.get("primaryCompletionDateStruct")
        completion_date = None
        if isinstance(completion, dict) and isinstance(completion.get("date"), str):
            completion_date = completion["date"]

        enrollment = status.get("enrollmentInfo")
        enrollment_count = None
        if isinstance(enrollment, dict) and isinstance(enrollment.get("count"), int):
            enrollment_count = enrollment["count"]

        phases = design.get("phases")
        phase = None
        if isinstance(phases, list) and phases and isinstance(phases[0], str):
            phase = phases[0]

        fields = {
            "nct_id": nct_id,
            "brief_title": identification.get("briefTitle")
            if isinstance(identification.get("briefTitle"), str)
            else None,
            "overall_status": status.get("overallStatus") if isinstance(status.get("overallStatus"), str) else None,
            "last_update_post_date": (
                status.get("lastUpdatePostDateStruct", {}).get("date")
                if isinstance(status.get("lastUpdatePostDateStruct"), dict)
                and isinstance(status.get("lastUpdatePostDateStruct", {}).get("date"), str)
                else None
            ),
            "primary_completion_date": completion_date,
            "enrollment_count": enrollment_count,
            "phase": phase,
        }
        digests = field_digests_for({key: fields[key] for key in _CHANGE_FIELD_KEYS})
        record = {
            "record_kind": "NORMALIZED_CTGOV_STUDY",
            **fields,
            "field_digests": digests,
            "aggregate_digest": aggregate_digest(digests),
            "boundary": STUDY_BOUNDARY,
        }
        validate_or_raise(record, NORMALIZED_STUDY_SCHEMA)
        return record

    def compare_normalized_studies(
        self,
        prior: dict[str, Any],
        current: dict[str, Any],
    ) -> dict[str, Any]:
        prior_digests = prior.get("field_digests")
        current_digests = current.get("field_digests")
        if not isinstance(prior_digests, dict) or not isinstance(current_digests, dict):
            raise ValueError("Normalized study records require field_digests")
        changed = changed_fields(
            {str(k): str(v) for k, v in prior_digests.items()},
            {str(k): str(v) for k, v in current_digests.items()},
        )
        return {
            "nct_id": current.get("nct_id"),
            "changed_fields": changed,
            "unchanged": len(changed) == 0,
            "prior_aggregate_digest": prior.get("aggregate_digest"),
            "current_aggregate_digest": current.get("aggregate_digest"),
            "boundary": (
                "Field-level comparison of normalized digests only; unchanged digests do not "
                "prove substantive equivalence or clinical stability."
            ),
        }

    def collect(
        self,
        request: dict[str, Any],
        *,
        prior_capture: PriorCapture | None = None,
        attempt_count: int = 1,
        source_record: dict[str, Any] | None = None,
    ) -> CollectionOutcome:
        nct_id = self.extract_nct_id(source_record, request)
        if nct_id is not None:
            rewritten = {**request, "requested_url": self.build_study_url(nct_id)}
            return super().collect(rewritten, prior_capture=prior_capture, attempt_count=attempt_count)

        query = self.extract_search_query(source_record)
        if query is not None:
            search_url = self.build_search_url(
                query,
                page_size=self.extract_page_size(source_record),
                page_token=self.extract_page_token(source_record),
            )
            rewritten = {**request, "requested_url": search_url}
            return super().collect(rewritten, prior_capture=prior_capture, attempt_count=attempt_count)

        return super().collect(request, prior_capture=prior_capture, attempt_count=attempt_count)
