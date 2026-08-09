"""Deterministic cross-record search for NeuroAI research data."""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from .assessment_evidence import build_assessment_evidence_analysis
from .data_health import registry_records
from .util import atomic_write_json

TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:[-_.:/][A-Za-z0-9]+)*")
ID_FIELDS = (
    "organization_id",
    "source_id",
    "monitor_id",
    "model_id",
    "event_id",
    "dependency_id",
    "governance_id",
    "decision_id",
    "assessment_id",
    "evidence_id",
    "requirement_id",
    "priority_id",
    "candidate_id",
    "adjudication_id",
    "id",
)
TITLE_FIELDS = (
    "canonical_name",
    "title",
    "name",
    "system_name",
    "system",
    "subject",
    "organization",
    "developer",
    "publisher_or_source",
    "publisher",
    "event",
    "recommended_focus",
)
FIELD_WEIGHTS = {
    "canonical_name": 6,
    "title": 6,
    "name": 6,
    "system_name": 6,
    "system": 6,
    "subject": 5,
    "organization": 5,
    "developer": 5,
    "publisher_or_source": 5,
    "publisher": 5,
    "source_class": 4,
    "evidence_class": 4,
    "event_type": 4,
    "relationship_type": 4,
    "module": 4,
    "priority": 4,
    "finding_status": 4,
    "recommended_focus": 4,
    "roles": 3,
    "url": 3,
    "url_or_path": 3,
}
SUBSTANTIVE_DATE_FIELDS = (
    "publication_date",
    "published_at",
    "published",
    "event_date",
    "effective_date",
    "decision_date",
    "date",
)
RETRIEVAL_DATE_FIELDS = (
    "retrieval_date",
    "retrieved_at",
    "retrieved",
    "last_successful_retrieval",
)
TYPED_RESULT_FIELDS = (
    "assessment_id",
    "system_name",
    "substantive_date",
    "retrieval_date",
    "source_class",
    "requirement_id",
    "module_id",
    "module",
    "priority",
    "status",
)
SEARCH_SCORE_NOTE = (
    "Score is a deterministic lexical retrieval score only; it is not evidence strength, "
    "finding status, scientific importance, or programme priority."
)


def _flatten(value: Any, *, prefix: str = "") -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in sorted(value.items()):
            path = f"{prefix}.{key}" if prefix else str(key)
            rows.extend(_flatten(item, prefix=path))
    elif isinstance(value, list):
        for item in value:
            rows.extend(_flatten(item, prefix=prefix))
    elif value is not None and value != "":
        rows.append((prefix, str(value)))
    return rows


def _record_id(record: dict[str, Any], fallback: str) -> str:
    for field in ID_FIELDS:
        if record.get(field):
            return str(record[field])
    return fallback


def _title(record: dict[str, Any], record_id: str) -> str:
    for field in TITLE_FIELDS:
        if record.get(field):
            return str(record[field])
    return record_id


def _first(record: dict[str, Any], fields: tuple[str, ...]) -> Any | None:
    for field in fields:
        value = record.get(field)
        if value is not None and value != "":
            return value
    return None


def _normalize_date(value: Any) -> str | None:
    if value is None or value == "":
        return None
    text = str(value).strip()
    if len(text) < 10:
        return None
    candidate = text[:10]
    try:
        return date.fromisoformat(candidate).isoformat()
    except ValueError:
        return None


def _typed_metadata(record: dict[str, Any]) -> dict[str, Any]:
    status = _first(record, ("finding_status", "status", "current_status", "evidence_state", "verification_state"))
    return {
        "assessment_id": record.get("assessment_id"),
        "system_name": record.get("system_name", record.get("system")),
        "substantive_date": _normalize_date(_first(record, SUBSTANTIVE_DATE_FIELDS)),
        "retrieval_date": _normalize_date(_first(record, RETRIEVAL_DATE_FIELDS)),
        "source_class": record.get("source_class", record.get("evidence_class")),
        "requirement_id": record.get("requirement_id"),
        "module_id": record.get("module_id"),
        "module": record.get("module"),
        "priority": record.get("priority", record.get("urgency")),
        "status": status,
    }


def _index_one(
    *,
    record_type: str,
    record: dict[str, Any],
    ordinal: int,
    origin: str,
    record_id: str | None = None,
) -> dict[str, Any]:
    resolved_id = record_id or _record_id(record, f"{record_type}:{ordinal}")
    return {
        "record_type": record_type,
        "record_id": resolved_id,
        "title": _title(record, resolved_id),
        "origin": origin,
        **_typed_metadata(record),
        "fields": _flatten(record),
    }


def _priority_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        for key in ("priorities", "research_agenda", "agenda", "records"):
            if isinstance(payload.get(key), list):
                records = payload[key]
                break
        else:
            records = [payload] if payload.get("requirement_id") or payload.get("priority_id") else []
    else:
        records = []
    if not records or any(not isinstance(record, dict) for record in records):
        raise ValueError("Evidence-priority input must contain one or more JSON object records")
    return records


def build_search_index(
    *,
    release: Any | None = None,
    registry: Any | None = None,
    assessments: list[Any] | None = None,
    evidence_priorities: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """Build one deterministic index across observatory and assessment research records."""
    if release is None and registry is None and not assessments and not evidence_priorities:
        raise ValueError("At least one release, registry, assessment, or evidence-priority input is required")
    indexed: list[dict[str, Any]] = []
    if release is not None and not isinstance(release, dict):
        raise ValueError("Observatory release must be a JSON object")
    if isinstance(release, dict):
        for section, value in sorted(release.items()):
            if section in {"metadata", "methodology", "coverage"}:
                continue
            if isinstance(value, list):
                for ordinal, record in enumerate(value):
                    if isinstance(record, dict):
                        indexed.append(
                            _index_one(
                                record_type=section,
                                record=record,
                                ordinal=ordinal,
                                origin="release",
                            )
                        )
            elif section == "delta" and isinstance(value, dict):
                for delta_section, values in sorted(value.items()):
                    if not isinstance(values, list):
                        continue
                    for ordinal, record in enumerate(values):
                        if isinstance(record, dict):
                            indexed.append(
                                _index_one(
                                    record_type=f"delta.{delta_section}",
                                    record=record,
                                    ordinal=ordinal,
                                    origin="release",
                                )
                            )
            elif section == "assessment_successor_delta" and isinstance(value, dict):
                indexed.append(
                    _index_one(
                        record_type=section,
                        record=value,
                        ordinal=0,
                        origin="release",
                    )
                )
    if registry is not None:
        for ordinal, record in enumerate(registry_records(registry)):
            indexed.append(
                _index_one(
                    record_type="source_monitor",
                    record=record,
                    ordinal=ordinal,
                    origin="registry",
                )
            )
    if assessments:
        analysis = build_assessment_evidence_analysis(assessments)
        for ordinal, record in enumerate(analysis["evidence"]):
            assessment_id = str(record.get("assessment_id") or "UNRESOLVED")
            evidence_id = str(record.get("evidence_id") or ordinal)
            indexed.append(
                _index_one(
                    record_type="assessment_evidence",
                    record=record,
                    ordinal=ordinal,
                    origin="assessment",
                    record_id=f"{assessment_id}:{evidence_id}",
                )
            )
        for ordinal, record in enumerate(analysis["findings"]):
            assessment_id = str(record.get("assessment_id") or "UNRESOLVED")
            requirement_id = str(record.get("requirement_id") or ordinal)
            indexed.append(
                _index_one(
                    record_type="assessment_finding",
                    record=record,
                    ordinal=ordinal,
                    origin="assessment",
                    record_id=f"{assessment_id}:{requirement_id}",
                )
            )
    if evidence_priorities:
        ordinal = 0
        for payload in evidence_priorities:
            for record in _priority_records(payload):
                indexed.append(
                    _index_one(
                        record_type="evidence_priority",
                        record=record,
                        ordinal=ordinal,
                        origin="research_agenda",
                    )
                )
                ordinal += 1
    indexed.sort(key=lambda item: (str(item["record_type"]), str(item["record_id"])))
    return indexed


def _tokens(value: str) -> list[str]:
    return [match.group(0).casefold() for match in TOKEN_RE.finditer(value)]


def _field_weight(path: str) -> int:
    leaf = path.rsplit(".", 1)[-1]
    if leaf == "requirement_id":
        return 16
    if leaf in ID_FIELDS or leaf.endswith("_id"):
        return 12
    return FIELD_WEIGHTS.get(leaf, 1)


def _filter_value(item: dict[str, Any], field: str, accepted: set[str] | None) -> bool:
    if not accepted:
        return True
    value = item.get(field)
    if value is None:
        return False
    normalized = {str(candidate).casefold() for candidate in accepted}
    return str(value).casefold() in normalized


def _filter_date(value: str | None, *, name: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid {name} date {value!r}; expected YYYY-MM-DD") from exc


def _matches_filters(
    item: dict[str, Any],
    *,
    record_types: set[str] | None,
    systems: set[str] | None,
    assessments: set[str] | None,
    source_classes: set[str] | None,
    priorities: set[str] | None,
    statuses: set[str] | None,
    after_date: date | None,
    before_date: date | None,
) -> bool:
    if not _filter_value(item, "record_type", record_types):
        return False
    if not _filter_value(item, "system_name", systems):
        return False
    if not _filter_value(item, "assessment_id", assessments):
        return False
    if not _filter_value(item, "source_class", source_classes):
        return False
    if not _filter_value(item, "priority", priorities):
        return False
    if not _filter_value(item, "status", statuses):
        return False
    if after_date is None and before_date is None:
        return True
    substantive = item.get("substantive_date")
    if not substantive:
        return False
    try:
        substantive_date = date.fromisoformat(str(substantive))
    except ValueError:
        return False
    if after_date is not None and substantive_date <= after_date:
        return False
    if before_date is not None and substantive_date >= before_date:
        return False
    return True


def _score_field(path: str, value: str, *, phrase: str, query_tokens: list[str]) -> tuple[int, list[str]]:
    normalized = value.casefold()
    field_tokens = set(_tokens(value))
    weight = _field_weight(path)
    score = 0
    signals: list[str] = []
    if normalized == phrase:
        score += 24 * weight
        signals.append("EXACT_VALUE")
    elif phrase in normalized:
        score += 8 * weight
        signals.append("PHRASE_SUBSTRING")
    exact = sum(1 for token in query_tokens if token in field_tokens)
    prefix = sum(
        1
        for token in query_tokens
        if token not in field_tokens and any(candidate.startswith(token) for candidate in field_tokens)
    )
    if exact:
        score += exact * 3 * weight
        signals.append(f"EXACT_TOKENS:{exact}")
    if prefix:
        score += prefix * weight
        signals.append(f"PREFIX_TOKENS:{prefix}")
    return score, signals


def search_index(
    index: list[dict[str, Any]],
    query: str,
    *,
    record_types: set[str] | None = None,
    systems: set[str] | None = None,
    assessments: set[str] | None = None,
    source_classes: set[str] | None = None,
    priorities: set[str] | None = None,
    statuses: set[str] | None = None,
    after: str | None = None,
    before: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Search the unified index with deterministic lexical ranking and typed filters."""
    phrase = query.strip().casefold()
    query_tokens = _tokens(query)
    if not phrase or not query_tokens:
        raise ValueError("Search query must contain searchable text")
    if limit <= 0:
        raise ValueError("Search limit must be positive")
    after_date = _filter_date(after, name="after")
    before_date = _filter_date(before, name="before")
    if after_date is not None and before_date is not None and after_date >= before_date:
        raise ValueError("Search --after date must be earlier than --before date")

    results: list[dict[str, Any]] = []
    for item in index:
        if not _matches_filters(
            item,
            record_types=record_types,
            systems=systems,
            assessments=assessments,
            source_classes=source_classes,
            priorities=priorities,
            statuses=statuses,
            after_date=after_date,
            before_date=before_date,
        ):
            continue
        score = 0
        matched_fields: set[str] = set()
        previews: list[str] = []
        score_explanation: list[dict[str, Any]] = []
        fields = item.get("fields", [])
        if not isinstance(fields, list):
            continue
        for raw_path, raw_value in fields:
            path = str(raw_path)
            value = str(raw_value)
            field_score, signals = _score_field(path, value, phrase=phrase, query_tokens=query_tokens)
            if field_score:
                score += field_score
                matched_fields.add(path)
                previews.append(value)
                score_explanation.append(
                    {
                        "field": path,
                        "weight": _field_weight(path),
                        "signals": signals,
                        "contribution": field_score,
                    }
                )
        if score <= 0:
            continue
        coverage = sum(1 for token in query_tokens if any(token in str(value).casefold() for _, value in fields))
        if coverage == len(query_tokens):
            score += 12
            score_explanation.append(
                {
                    "field": "__record__",
                    "weight": 1,
                    "signals": ["FULL_QUERY_TOKEN_COVERAGE"],
                    "contribution": 12,
                }
            )
        result = {
            "record_type": item.get("record_type"),
            "record_id": item.get("record_id"),
            "title": item.get("title"),
            "origin": item.get("origin"),
            **{field: item.get(field) for field in TYPED_RESULT_FIELDS},
            "score": score,
            "score_explanation": score_explanation,
            "matched_fields": sorted(matched_fields),
            "preview": " | ".join(dict.fromkeys(previews))[:300],
        }
        results.append(result)
    results.sort(key=lambda item: (-int(item["score"]), str(item["record_type"]), str(item["record_id"])))
    return results[:limit]


def render_search_markdown(query: str, results: list[dict[str, Any]]) -> str:
    lines = [
        f"# NeuroAI search: {query}",
        "",
        SEARCH_SCORE_NOTE,
        "",
        "| Rank | Type | ID | Title | Origin | System | Date | Priority | Status | Score | Matched fields |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- | ---: | --- |",
    ]
    if not results:
        lines.append("| — | — | — | No matches | — | — | — | — | — | — | — |")
    else:
        for rank, item in enumerate(results, start=1):
            lines.append(
                "| {rank} | {record_type} | {record_id} | {title} | {origin} | {system} | {date} | "
                "{priority} | {status} | {score} | {fields} |".format(
                    rank=rank,
                    record_type=item.get("record_type"),
                    record_id=item.get("record_id"),
                    title=item.get("title"),
                    origin=item.get("origin"),
                    system=item.get("system_name") or "—",
                    date=item.get("substantive_date") or "—",
                    priority=item.get("priority") or "—",
                    status=item.get("status") or "—",
                    score=item.get("score"),
                    fields=", ".join(item.get("matched_fields", [])),
                )
            )
    return "\n".join(lines).rstrip() + "\n"


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        if value and isinstance(value[0], dict):
            return json.dumps(value, sort_keys=True, separators=(",", ":"))
        return ";".join(str(item) for item in value)
    return str(value)


def write_search_outputs(query: str, results: list[dict[str, Any]], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "search-results.json"
    csv_path = output_dir / "search-results.csv"
    markdown_path = output_dir / "search-results.md"
    atomic_write_json(json_path, {"query": query, "scoring_note": SEARCH_SCORE_NOTE, "results": results})
    buffer = io.StringIO()
    fields = (
        "rank",
        "record_type",
        "record_id",
        "title",
        "origin",
        *TYPED_RESULT_FIELDS,
        "score",
        "score_explanation",
        "matched_fields",
        "preview",
    )
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for rank, item in enumerate(results, start=1):
        writer.writerow(
            {
                "rank": rank,
                **{field: _csv_value(item.get(field)) for field in fields if field != "rank"},
            }
        )
    csv_path.write_text(buffer.getvalue(), encoding="utf-8")
    markdown_path.write_text(render_search_markdown(query, results), encoding="utf-8")
    return {"json": str(json_path), "csv": str(csv_path), "markdown": str(markdown_path)}
