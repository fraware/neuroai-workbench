"""Deterministic cross-layer propagation tracing for observatory and assessment evidence."""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .data_health import normalize_url
from .util import atomic_write_json

ID_FIELDS = (
    "organization_id",
    "source_id",
    "model_id",
    "event_id",
    "relationship_id",
    "dependency_id",
    "governance_id",
    "decision_id",
    "assessment_id",
    "id",
)
CHECKSUM_FIELDS = ("checksum", "sha256", "content_sha256", "content_hash")
URL_FIELDS = ("url", "url_or_path", "source_url", "official_url", "retrieval_url")


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _record_id(record: dict[str, Any], fallback: str) -> str:
    for field in ID_FIELDS:
        if record.get(field):
            return str(record[field])
    return fallback


def _first(record: dict[str, Any], fields: tuple[str, ...]) -> Any:
    for field in fields:
        value = record.get(field)
        if value is not None and value != "":
            return value
    return None


def _checksum(record: dict[str, Any]) -> str | None:
    value = _first(record, CHECKSUM_FIELDS)
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip().casefold()


def _url(record: dict[str, Any]) -> str | None:
    return normalize_url(_first(record, URL_FIELDS))


def _source_ids(record: dict[str, Any]) -> list[str]:
    values = [str(item) for item in _items(record.get("source_ids")) if item is not None]
    if record.get("source_id"):
        values.append(str(record["source_id"]))
    return sorted(dict.fromkeys(values))


def _is_public_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlsplit(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _assessment_identity(assessment: dict[str, Any], ordinal: int) -> dict[str, str]:
    metadata = _mapping(assessment.get("assessment_metadata")) or _mapping(assessment.get("metadata"))
    system = _mapping(assessment.get("system_profile")) or _mapping(assessment.get("system"))
    assessment_id = str(metadata.get("assessment_id") or metadata.get("id") or f"assessment:{ordinal}")
    title = str(metadata.get("title") or assessment_id)
    system_name = str(system.get("system_name") or metadata.get("system") or title)
    return {"assessment_id": assessment_id, "title": title, "system_name": system_name}


def _assessment_evidence(assessment: dict[str, Any], assessment_id: str) -> list[dict[str, Any]]:
    evidence = _items(assessment.get("evidence_register")) or _items(assessment.get("sources"))
    rows: list[dict[str, Any]] = []
    for ordinal, raw in enumerate(evidence):
        if not isinstance(raw, dict):
            continue
        rows.append(
            {
                "assessment_id": assessment_id,
                "evidence_id": str(raw.get("evidence_id") or raw.get("source_id") or f"evidence:{ordinal}"),
                "title": raw.get("title"),
                "source_ids": _source_ids(raw),
                "url": _url(raw),
                "checksum": _checksum(raw),
            }
        )
    return rows


def _requirements_by_evidence(assessment: dict[str, Any]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = defaultdict(list)
    for ordinal, raw in enumerate(_items(assessment.get("requirement_findings"))):
        if not isinstance(raw, dict):
            continue
        requirement_id = str(raw.get("requirement_id") or f"requirement:{ordinal}")
        for evidence_id in _items(raw.get("evidence_ids")):
            token = str(evidence_id)
            if requirement_id not in index[token]:
                index[token].append(requirement_id)
    return {key: sorted(values) for key, values in index.items()}


def _source_row(raw: dict[str, Any], fallback: str) -> dict[str, Any]:
    return {
        "source_id": str(raw.get("source_id") or fallback),
        "title": raw.get("title"),
        "publisher": raw.get("publisher"),
        "source_class": raw.get("source_class"),
        "url": _url(raw),
        "checksum": _checksum(raw),
    }


def _release_sources(release: dict[str, Any]) -> list[dict[str, Any]]:
    sources = [
        _source_row(raw, f"source:{ordinal}")
        for ordinal, raw in enumerate(_items(release.get("sources")))
        if isinstance(raw, dict)
    ]
    delta = _mapping(release.get("delta"))
    for section, values in sorted(delta.items()):
        if "source" not in str(section).casefold():
            continue
        sources.extend(
            _source_row(raw, f"delta.{section}:{ordinal}")
            for ordinal, raw in enumerate(_items(values))
            if isinstance(raw, dict) and raw.get("source_id")
        )

    deduped: dict[str, dict[str, Any]] = {}
    for source in sources:
        source_id = str(source["source_id"])
        existing = deduped.get(source_id)
        if existing is None:
            deduped[source_id] = source
        elif existing.get("url") != source.get("url") or existing.get("checksum") != source.get("checksum"):
            raise ValueError(f"Conflicting duplicate source_id {source_id!r}")
    return [deduped[key] for key in sorted(deduped)]


def _dependency_record(record_type: str, raw: dict[str, Any], ordinal: int) -> dict[str, Any] | None:
    ids = _source_ids(raw)
    if not ids:
        return None
    return {
        "record_type": record_type,
        "record_id": _record_id(raw, f"{record_type}:{ordinal}"),
        "name": _first(raw, ("name", "system", "subject", "organization", "canonical_name", "title", "event")),
        "source_ids": ids,
    }


def _records_with_source_ids(release: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    skip = {"metadata", "methodology", "coverage", "sources", "reopening_decisions"}
    for section, values in sorted(release.items()):
        if section in skip:
            continue
        if section == "delta" and isinstance(values, dict):
            for delta_section, delta_values in sorted(values.items()):
                for ordinal, raw in enumerate(_items(delta_values)):
                    if isinstance(raw, dict):
                        row = _dependency_record(f"delta.{delta_section}", raw, ordinal)
                        if row:
                            records.append(row)
            continue
        for ordinal, raw in enumerate(_items(values)):
            if isinstance(raw, dict):
                row = _dependency_record(str(section), raw, ordinal)
                if row:
                    records.append(row)
    return sorted(records, key=lambda row: (str(row["record_type"]), str(row["record_id"])))


def _match_rule(source: dict[str, Any], evidence: dict[str, Any]) -> str | None:
    if str(source["source_id"]) in evidence.get("source_ids", []):
        return "SOURCE_ID"
    url_match = bool(source.get("url") and evidence.get("url") and source["url"] == evidence["url"])
    checksum_match = bool(
        source.get("checksum") and evidence.get("checksum") and source["checksum"] == evidence["checksum"]
    )
    if url_match and checksum_match:
        return "URL_AND_CHECKSUM"
    if checksum_match:
        return "CHECKSUM"
    if url_match:
        return "URL"
    return None


def trace_propagation(release: Any, assessments: list[Any]) -> dict[str, Any]:
    if not isinstance(release, dict):
        raise ValueError("Observatory release must be a JSON object")
    if not assessments:
        raise ValueError("At least one completed assessment is required")

    normalized_assessments: list[dict[str, Any]] = []
    all_evidence: list[dict[str, Any]] = []
    requirements: dict[str, dict[str, list[str]]] = {}
    for ordinal, raw in enumerate(assessments):
        if not isinstance(raw, dict):
            raise ValueError(f"Assessment {ordinal} must be a JSON object")
        identity = _assessment_identity(raw, ordinal)
        assessment_id = identity["assessment_id"]
        if any(item["assessment_id"] == assessment_id for item in normalized_assessments):
            raise ValueError(f"Duplicate assessment_id {assessment_id!r}")
        evidence = _assessment_evidence(raw, assessment_id)
        normalized_assessments.append({**identity, "evidence_count": len(evidence)})
        all_evidence.extend(evidence)
        requirements[assessment_id] = _requirements_by_evidence(raw)

    sources = _release_sources(release)
    paths_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    matched_evidence_keys: set[tuple[str, str]] = set()
    for source in sources:
        for evidence in all_evidence:
            rule = _match_rule(source, evidence)
            if rule is None:
                continue
            assessment_id = str(evidence["assessment_id"])
            evidence_id = str(evidence["evidence_id"])
            matched_evidence_keys.add((assessment_id, evidence_id))
            paths_by_source[str(source["source_id"])].append(
                {
                    "assessment_id": assessment_id,
                    "evidence_id": evidence_id,
                    "match_rule": rule,
                    "requirement_ids": requirements.get(assessment_id, {}).get(evidence_id, []),
                }
            )

    source_rows: list[dict[str, Any]] = []
    for source in sources:
        source_id = str(source["source_id"])
        paths = sorted(
            paths_by_source.get(source_id, []),
            key=lambda row: (str(row["assessment_id"]), str(row["evidence_id"]), str(row["match_rule"])),
        )
        requirement_ids = sorted({req for path in paths for req in path["requirement_ids"]})
        source_rows.append(
            {
                **{key: source.get(key) for key in ("source_id", "title", "publisher", "source_class", "url")},
                "assessment_paths": paths,
                "assessment_count": len({path["assessment_id"] for path in paths}),
                "requirement_ids": requirement_ids,
                "requirement_count": len(requirement_ids),
                "trace_state": "TRACED_TO_REQUIREMENTS"
                if requirement_ids
                else ("TRACED_TO_ASSESSMENT_EVIDENCE" if paths else "UNTRACED"),
            }
        )

    source_index = {str(row["source_id"]): row for row in source_rows}
    record_rows: list[dict[str, Any]] = []
    for record in _records_with_source_ids(release):
        source_paths = [source_index[source_id] for source_id in record["source_ids"] if source_id in source_index]
        requirement_ids = sorted({req for source in source_paths for req in source["requirement_ids"]})
        assessment_ids = sorted(
            {str(path["assessment_id"]) for source in source_paths for path in source["assessment_paths"]}
        )
        untraced = sorted(
            source_id
            for source_id in record["source_ids"]
            if source_id not in source_index or not source_index[source_id]["assessment_paths"]
        )
        record_rows.append(
            {
                **record,
                "assessment_ids": assessment_ids,
                "requirement_ids": requirement_ids,
                "traced_source_count": len(record["source_ids"]) - len(untraced),
                "untraced_source_ids": untraced,
                "trace_state": "TRACED_TO_REQUIREMENTS"
                if requirement_ids
                else ("PARTIAL_OR_EVIDENCE_ONLY" if assessment_ids else "UNTRACED"),
            }
        )

    unmatched_evidence = []
    for evidence in all_evidence:
        evidence_key = (str(evidence["assessment_id"]), str(evidence["evidence_id"]))
        if evidence_key in matched_evidence_keys:
            continue
        if not (_is_public_url(evidence.get("url")) or evidence.get("checksum") or evidence.get("source_ids")):
            continue
        assessment_id, evidence_id = evidence_key
        unmatched_evidence.append(
            {
                "assessment_id": assessment_id,
                "evidence_id": evidence_id,
                "title": evidence.get("title"),
                "source_ids": evidence.get("source_ids", []),
                "url": evidence.get("url"),
                "checksum": evidence.get("checksum"),
                "requirement_ids": requirements.get(assessment_id, {}).get(evidence_id, []),
            }
        )
    unmatched_evidence.sort(key=lambda row: (row["assessment_id"], row["evidence_id"]))

    urls: dict[str, list[str]] = defaultdict(list)
    for source in sources:
        if source.get("url"):
            urls[str(source["url"])].append(str(source["source_id"]))
    ambiguous_source_urls = [
        {"url": url, "source_ids": sorted(ids), "count": len(ids)} for url, ids in sorted(urls.items()) if len(ids) > 1
    ]

    assessment_stats: list[dict[str, Any]] = []
    for assessment in normalized_assessments:
        assessment_id = str(assessment["assessment_id"])
        evidence_keys = {
            (assessment_id, str(evidence["evidence_id"]))
            for evidence in all_evidence
            if evidence["assessment_id"] == assessment_id
        }
        linked_requirements = sorted(
            {
                req
                for source in source_rows
                for path in source["assessment_paths"]
                if path["assessment_id"] == assessment_id
                for req in path["requirement_ids"]
            }
        )
        matched = evidence_keys & matched_evidence_keys
        assessment_stats.append(
            {
                **assessment,
                "matched_observatory_evidence_count": len(matched),
                "unmatched_observatory_evidence_count": len(evidence_keys - matched),
                "linked_requirement_count": len(linked_requirements),
                "linked_requirement_ids": linked_requirements,
            }
        )

    matched_source_count = sum(1 for row in source_rows if row["assessment_paths"])
    requirement_source_count = sum(1 for row in source_rows if row["requirement_ids"])
    metadata = _mapping(release.get("metadata"))
    return {
        "metadata": {
            "title": "NeuroAI cross-layer propagation trace",
            "release_version": metadata.get("version"),
            "source_count": len(source_rows),
            "assessment_count": len(normalized_assessments),
            "matching": ["EXACT_SOURCE_ID", "EXACT_NORMALIZED_URL", "EXACT_CHECKSUM"],
            "fuzzy_matching": False,
        },
        "summary": {
            "sources_traced_to_assessment_evidence": matched_source_count,
            "sources_traced_to_requirements": requirement_source_count,
            "sources_untraced": len(source_rows) - matched_source_count,
            "assessment_evidence_count": len(all_evidence),
            "assessment_evidence_matched_to_observatory": len(matched_evidence_keys),
            "assessment_evidence_unmatched_public_or_hashed": len(unmatched_evidence),
            "records_with_source_dependencies": len(record_rows),
            "records_traced_to_requirements": sum(1 for row in record_rows if row["requirement_ids"]),
        },
        "assessments": assessment_stats,
        "source_traces": source_rows,
        "record_traces": record_rows,
        "unmatched_assessment_evidence": unmatched_evidence,
        "ambiguous_source_urls": ambiguous_source_urls,
    }


def render_trace_markdown(trace: dict[str, Any], *, limit: int = 50) -> str:
    metadata = _mapping(trace.get("metadata"))
    summary = _mapping(trace.get("summary"))
    lines = [
        "# NeuroAI propagation trace",
        "",
        f"Release: {metadata.get('release_version', 'UNRESOLVED')}  ",
        f"Assessments: {metadata.get('assessment_count', 0)}  ",
        f"Observatory sources: {metadata.get('source_count', 0)}",
        "",
        "## Summary",
        "",
        f"- Sources traced to assessment evidence: {summary.get('sources_traced_to_assessment_evidence', 0)}",
        f"- Sources traced through to requirements: {summary.get('sources_traced_to_requirements', 0)}",
        f"- Observatory sources untraced to supplied assessments: {summary.get('sources_untraced', 0)}",
        f"- Assessment evidence matched to observatory: {summary.get('assessment_evidence_matched_to_observatory', 0)} / {summary.get('assessment_evidence_count', 0)}",
        "",
        "## Traced observatory sources",
        "",
        "| Source | Title | Assessments | Requirements | State |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    traced = [
        row for row in _items(trace.get("source_traces")) if isinstance(row, dict) and row.get("assessment_paths")
    ]
    if traced:
        for row in traced[:limit]:
            lines.append(
                f"| {row.get('source_id')} | {row.get('title') or '—'} | {row.get('assessment_count', 0)} | "
                f"{row.get('requirement_count', 0)} | {row.get('trace_state')} |"
            )
    else:
        lines.append("| — | No exact cross-layer matches | — | — | — |")

    lines.extend(["", "## Unmatched assessment evidence", ""])
    unmatched = [row for row in _items(trace.get("unmatched_assessment_evidence")) if isinstance(row, dict)]
    if not unmatched:
        lines.append("No unmatched public/hashed assessment evidence.")
    else:
        lines.extend(["| Assessment | Evidence | Title | Requirements |", "| --- | --- | --- | ---: |"])
        for row in unmatched[:limit]:
            lines.append(
                f"| {row.get('assessment_id')} | {row.get('evidence_id')} | {row.get('title') or '—'} | "
                f"{len(row.get('requirement_ids', []))} |"
            )
    lines.append("")
    return "\n".join(lines)


def write_trace_outputs(trace: dict[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "propagation-trace.json"
    source_csv = output_dir / "propagation-sources.csv"
    record_csv = output_dir / "propagation-records.csv"
    markdown_path = output_dir / "propagation-trace.md"
    atomic_write_json(json_path, trace)

    source_buffer = io.StringIO()
    source_writer = csv.DictWriter(
        source_buffer,
        fieldnames=(
            "source_id",
            "title",
            "publisher",
            "source_class",
            "url",
            "assessment_count",
            "requirement_count",
            "trace_state",
            "assessment_ids",
            "evidence_ids",
            "requirement_ids",
        ),
        lineterminator="\n",
    )
    source_writer.writeheader()
    for row in _items(trace.get("source_traces")):
        if not isinstance(row, dict):
            continue
        paths = [path for path in _items(row.get("assessment_paths")) if isinstance(path, dict)]
        source_writer.writerow(
            {
                "source_id": row.get("source_id"),
                "title": row.get("title"),
                "publisher": row.get("publisher"),
                "source_class": row.get("source_class"),
                "url": row.get("url"),
                "assessment_count": row.get("assessment_count"),
                "requirement_count": row.get("requirement_count"),
                "trace_state": row.get("trace_state"),
                "assessment_ids": ";".join(sorted({str(path["assessment_id"]) for path in paths})),
                "evidence_ids": ";".join(sorted({str(path["evidence_id"]) for path in paths})),
                "requirement_ids": ";".join(str(item) for item in row.get("requirement_ids", [])),
            }
        )
    source_csv.write_text(source_buffer.getvalue(), encoding="utf-8")

    record_buffer = io.StringIO()
    record_writer = csv.DictWriter(
        record_buffer,
        fieldnames=(
            "record_type",
            "record_id",
            "name",
            "source_ids",
            "assessment_ids",
            "requirement_ids",
            "untraced_source_ids",
            "trace_state",
        ),
        lineterminator="\n",
    )
    record_writer.writeheader()
    for row in _items(trace.get("record_traces")):
        if not isinstance(row, dict):
            continue
        record_writer.writerow(
            {
                "record_type": row.get("record_type"),
                "record_id": row.get("record_id"),
                "name": row.get("name"),
                "source_ids": ";".join(str(item) for item in row.get("source_ids", [])),
                "assessment_ids": ";".join(str(item) for item in row.get("assessment_ids", [])),
                "requirement_ids": ";".join(str(item) for item in row.get("requirement_ids", [])),
                "untraced_source_ids": ";".join(str(item) for item in row.get("untraced_source_ids", [])),
                "trace_state": row.get("trace_state"),
            }
        )
    record_csv.write_text(record_buffer.getvalue(), encoding="utf-8")
    markdown_path.write_text(render_trace_markdown(trace), encoding="utf-8")
    return {
        "json": str(json_path),
        "sources_csv": str(source_csv),
        "records_csv": str(record_csv),
        "markdown": str(markdown_path),
    }
