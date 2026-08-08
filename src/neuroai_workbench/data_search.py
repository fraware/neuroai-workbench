"""Deterministic cross-record search for NeuroAI observatory data."""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Any

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
    "candidate_id",
    "adjudication_id",
    "id",
)
TITLE_FIELDS = (
    "canonical_name",
    "title",
    "name",
    "system",
    "subject",
    "organization",
    "developer",
    "publisher",
    "event",
)
FIELD_WEIGHTS = {
    "canonical_name": 6,
    "title": 6,
    "name": 6,
    "system": 6,
    "subject": 5,
    "organization": 5,
    "developer": 5,
    "publisher": 5,
    "source_class": 4,
    "event_type": 4,
    "relationship_type": 4,
    "roles": 3,
    "url": 3,
}


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


def _index_one(*, record_type: str, record: dict[str, Any], ordinal: int, origin: str) -> dict[str, Any]:
    record_id = _record_id(record, f"{record_type}:{ordinal}")
    return {
        "record_type": record_type,
        "record_id": record_id,
        "title": _title(record, record_id),
        "origin": origin,
        "fields": _flatten(record),
    }


def build_search_index(*, release: Any | None = None, registry: Any | None = None) -> list[dict[str, Any]]:
    if release is None and registry is None:
        raise ValueError("At least one release or registry is required")
    indexed: list[dict[str, Any]] = []
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
    indexed.sort(key=lambda item: (str(item["record_type"]), str(item["record_id"])))
    return indexed


def _tokens(value: str) -> list[str]:
    return [match.group(0).casefold() for match in TOKEN_RE.finditer(value)]


def _field_weight(path: str) -> int:
    leaf = path.rsplit(".", 1)[-1]
    if leaf in ID_FIELDS or leaf.endswith("_id"):
        return 8
    return FIELD_WEIGHTS.get(leaf, 1)


def search_index(
    index: list[dict[str, Any]],
    query: str,
    *,
    record_types: set[str] | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    phrase = query.strip().casefold()
    query_tokens = _tokens(query)
    if not phrase or not query_tokens:
        raise ValueError("Search query must contain searchable text")
    if limit <= 0:
        raise ValueError("Search limit must be positive")
    results: list[dict[str, Any]] = []
    for item in index:
        record_type = str(item.get("record_type") or "")
        if record_types and record_type not in record_types:
            continue
        score = 0
        matched_fields: set[str] = set()
        previews: list[str] = []
        fields = item.get("fields", [])
        if not isinstance(fields, list):
            continue
        for raw_path, raw_value in fields:
            path = str(raw_path)
            value = str(raw_value)
            normalized = value.casefold()
            field_tokens = set(_tokens(value))
            weight = _field_weight(path)
            field_score = 0
            if normalized == phrase:
                field_score += 24 * weight
            elif phrase in normalized:
                field_score += 8 * weight
            exact = sum(1 for token in query_tokens if token in field_tokens)
            prefix = sum(
                1
                for token in query_tokens
                if token not in field_tokens and any(candidate.startswith(token) for candidate in field_tokens)
            )
            field_score += exact * 3 * weight
            field_score += prefix * weight
            if field_score:
                score += field_score
                matched_fields.add(path)
                previews.append(value)
        if score <= 0:
            continue
        coverage = sum(1 for token in query_tokens if any(token in str(value).casefold() for _, value in fields))
        if coverage == len(query_tokens):
            score += 12
        results.append(
            {
                "record_type": record_type,
                "record_id": item.get("record_id"),
                "title": item.get("title"),
                "origin": item.get("origin"),
                "score": score,
                "matched_fields": sorted(matched_fields),
                "preview": " | ".join(dict.fromkeys(previews))[:300],
            }
        )
    results.sort(key=lambda item: (-int(item["score"]), str(item["record_type"]), str(item["record_id"])))
    return results[:limit]


def render_search_markdown(query: str, results: list[dict[str, Any]]) -> str:
    lines = [
        f"# NeuroAI search: {query}",
        "",
        "| Rank | Type | ID | Title | Score | Matched fields |",
        "| ---: | --- | --- | --- | ---: | --- |",
    ]
    if not results:
        lines.append("| — | — | — | No matches | — | — |")
    else:
        for rank, item in enumerate(results, start=1):
            lines.append(
                "| {rank} | {record_type} | {record_id} | {title} | {score} | {fields} |".format(
                    rank=rank,
                    record_type=item.get("record_type"),
                    record_id=item.get("record_id"),
                    title=item.get("title"),
                    score=item.get("score"),
                    fields=", ".join(item.get("matched_fields", [])),
                )
            )
    return "\n".join(lines).rstrip() + "\n"


def write_search_outputs(query: str, results: list[dict[str, Any]], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "search-results.json"
    csv_path = output_dir / "search-results.csv"
    markdown_path = output_dir / "search-results.md"
    atomic_write_json(json_path, {"query": query, "results": results})
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=("rank", "record_type", "record_id", "title", "origin", "score", "matched_fields", "preview"),
        lineterminator="\n",
    )
    writer.writeheader()
    for rank, item in enumerate(results, start=1):
        writer.writerow(
            {
                "rank": rank,
                "record_type": item.get("record_type"),
                "record_id": item.get("record_id"),
                "title": item.get("title"),
                "origin": item.get("origin"),
                "score": item.get("score"),
                "matched_fields": ";".join(item.get("matched_fields", [])),
                "preview": item.get("preview"),
            }
        )
    csv_path.write_text(buffer.getvalue(), encoding="utf-8")
    markdown_path.write_text(render_search_markdown(query, results), encoding="utf-8")
    return {"json": str(json_path), "csv": str(csv_path), "markdown": str(markdown_path)}
