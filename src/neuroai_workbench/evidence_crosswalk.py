"""Deterministic assessment-evidence crosswalks into a current source universe."""

from __future__ import annotations

import csv
import io
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .assessment_evidence import build_assessment_evidence_analysis, normalize_checksum, normalize_public_url
from .util import atomic_write_json

CHECKSUM_FIELDS = ("checksum", "sha256", "content_sha256", "content_hash")
MATCHED_STATES = frozenset({"EXPLICIT_SOURCE_ID", "EXACT_URL", "EXACT_CHECKSUM", "EXACT_URL_AND_CHECKSUM"})


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _first(record: dict[str, Any], fields: tuple[str, ...]) -> Any:
    for field in fields:
        value = record.get(field)
        if value is not None and value != "":
            return value
    return None


def _source_record(raw: dict[str, Any]) -> dict[str, Any] | None:
    source_id = raw.get("source_id")
    if source_id is None or str(source_id).strip() == "":
        return None
    return {
        "source_id": str(source_id),
        "title": raw.get("title"),
        "publisher": raw.get("publisher", raw.get("source")),
        "source_class": raw.get("source_class", raw.get("evidence_class")),
        "normalized_public_url": normalize_public_url(raw.get("url", raw.get("url_or_path"))),
        "checksum": normalize_checksum(_first(raw, CHECKSUM_FIELDS)),
    }


def _walk_source_records(value: Any) -> list[dict[str, Any]]:
    """Collect explicit source records without treating plural source_ids as records."""
    records: list[dict[str, Any]] = []
    if isinstance(value, dict):
        record = _source_record(value)
        if record is not None:
            records.append(record)
        for child in value.values():
            if isinstance(child, (dict, list)):
                records.extend(_walk_source_records(child))
    elif isinstance(value, list):
        for child in value:
            if isinstance(child, (dict, list)):
                records.extend(_walk_source_records(child))
    return records


def build_source_universe(payloads: list[Any]) -> list[dict[str, Any]]:
    """Materialize and validate a source universe from one or more controlled payloads."""
    if not payloads:
        raise ValueError("At least one source-universe payload is required")
    deduped: dict[str, dict[str, Any]] = {}
    for payload_index, payload in enumerate(payloads):
        if not isinstance(payload, (dict, list)):
            raise ValueError(f"Source-universe payload {payload_index} must be a JSON object or array")
        for source in _walk_source_records(payload):
            source_id = str(source["source_id"])
            existing = deduped.get(source_id)
            if existing is None:
                deduped[source_id] = source
                continue
            for field in ("normalized_public_url", "checksum"):
                old = existing.get(field)
                new = source.get(field)
                if old and new and old != new:
                    raise ValueError(f"Conflicting {field} for source_id {source_id!r}")
                if not old and new:
                    existing[field] = new
            for field in ("title", "publisher", "source_class"):
                if not existing.get(field) and source.get(field):
                    existing[field] = source[field]
    if not deduped:
        raise ValueError("Source-universe payloads contain no source_id records")
    return [deduped[source_id] for source_id in sorted(deduped)]


def _index_sources(sources: list[dict[str, Any]], field: str) -> dict[str, set[str]]:
    index: dict[str, set[str]] = defaultdict(set)
    for source in sources:
        value = source.get(field)
        if value:
            index[str(value)].add(str(source["source_id"]))
    return dict(index)


def _resolve_without_explicit_ids(
    *,
    url_candidates: set[str],
    checksum_candidates: set[str],
    has_url: bool,
    has_checksum: bool,
) -> tuple[str, list[str], str | None]:
    if has_url and has_checksum:
        intersection = url_candidates & checksum_candidates
        if len(intersection) == 1:
            return "EXACT_URL_AND_CHECKSUM", sorted(intersection), "URL_AND_CHECKSUM"
        if url_candidates and checksum_candidates and url_candidates != checksum_candidates:
            return "AMBIGUOUS_EXACT", sorted(url_candidates | checksum_candidates), "CONFLICTING_EXACT_KEYS"
        combined = url_candidates | checksum_candidates
        if len(combined) > 1:
            return "AMBIGUOUS_EXACT", sorted(combined), "MULTIPLE_EXACT_CANDIDATES"
        if len(url_candidates) == 1:
            return "EXACT_URL", sorted(url_candidates), "URL"
        if len(checksum_candidates) == 1:
            return "EXACT_CHECKSUM", sorted(checksum_candidates), "CHECKSUM"
        return "UNRESOLVED", [], None
    if has_url:
        if len(url_candidates) == 1:
            return "EXACT_URL", sorted(url_candidates), "URL"
        if len(url_candidates) > 1:
            return "AMBIGUOUS_EXACT", sorted(url_candidates), "MULTIPLE_URL_CANDIDATES"
        return "UNRESOLVED", [], None
    if has_checksum:
        if len(checksum_candidates) == 1:
            return "EXACT_CHECKSUM", sorted(checksum_candidates), "CHECKSUM"
        if len(checksum_candidates) > 1:
            return "AMBIGUOUS_EXACT", sorted(checksum_candidates), "MULTIPLE_CHECKSUM_CANDIDATES"
    return "UNRESOLVED", [], None


def _resolve_evidence(
    evidence: dict[str, Any],
    *,
    source_ids: set[str],
    url_index: dict[str, set[str]],
    checksum_index: dict[str, set[str]],
) -> dict[str, Any]:
    explicit = sorted({str(item) for item in _items(evidence.get("source_ids"))})
    valid_explicit = sorted(source_id for source_id in explicit if source_id in source_ids)
    missing_explicit = sorted(source_id for source_id in explicit if source_id not in source_ids)
    url = evidence.get("normalized_public_url")
    checksum = evidence.get("checksum")
    url_candidates = set(url_index.get(str(url), set())) if url else set()
    checksum_candidates = set(checksum_index.get(str(checksum), set())) if checksum else set()

    if explicit:
        exact_candidates = url_candidates | checksum_candidates
        incompatible = sorted(exact_candidates - set(valid_explicit))
        if valid_explicit and not missing_explicit and not incompatible:
            state = "EXPLICIT_SOURCE_ID"
            candidates = valid_explicit
            rule = "SOURCE_ID"
        elif valid_explicit or incompatible:
            state = "AMBIGUOUS_EXACT"
            candidates = sorted(set(valid_explicit) | exact_candidates)
            rule = "EXPLICIT_ID_CONFLICT"
        else:
            state = "UNRESOLVED"
            candidates = []
            rule = None
    else:
        state, candidates, rule = _resolve_without_explicit_ids(
            url_candidates=url_candidates,
            checksum_candidates=checksum_candidates,
            has_url=bool(url),
            has_checksum=bool(checksum),
        )

    safe_migration = (
        evidence.get("namespace_state") != "SHARED_SOURCE_ID" and state in MATCHED_STATES and len(candidates) == 1
    )
    registration_candidate = state == "UNRESOLVED" and bool(url or checksum) and not valid_explicit
    return {
        "assessment_id": evidence.get("assessment_id"),
        "system_name": evidence.get("system_name"),
        "evidence_id": evidence.get("evidence_id"),
        "title": evidence.get("title"),
        "namespace_state": evidence.get("namespace_state"),
        "normalized_public_url": url,
        "checksum": checksum,
        "existing_source_ids": explicit,
        "valid_explicit_source_ids": valid_explicit,
        "missing_explicit_source_ids": missing_explicit,
        "url_candidate_source_ids": sorted(url_candidates),
        "checksum_candidate_source_ids": sorted(checksum_candidates),
        "candidate_source_ids": candidates,
        "match_rule": rule,
        "crosswalk_state": state,
        "safe_migration_candidate": safe_migration,
        "source_registration_candidate": registration_candidate,
        "cited_requirement_count": evidence.get("cited_requirement_count", 0),
    }


def build_evidence_crosswalk(source_payloads: list[Any], assessments: list[Any]) -> dict[str, Any]:
    """Build a read-only deterministic crosswalk from assessment evidence to current sources."""
    sources = build_source_universe(source_payloads)
    analysis = build_assessment_evidence_analysis(assessments)
    source_ids = {str(source["source_id"]) for source in sources}
    url_index = _index_sources(sources, "normalized_public_url")
    checksum_index = _index_sources(sources, "checksum")

    requirements_by_evidence: dict[tuple[str, str], list[str]] = defaultdict(list)
    for link in analysis["links"]:
        key = (str(link["assessment_id"]), str(link["evidence_id"]))
        requirement_id = str(link["requirement_id"])
        if requirement_id not in requirements_by_evidence[key]:
            requirements_by_evidence[key].append(requirement_id)

    rows: list[dict[str, Any]] = []
    for evidence in analysis["evidence"]:
        row = _resolve_evidence(evidence, source_ids=source_ids, url_index=url_index, checksum_index=checksum_index)
        key = (str(row["assessment_id"]), str(row["evidence_id"]))
        requirement_ids = sorted(requirements_by_evidence.get(key, []))
        row["cited_requirement_ids"] = requirement_ids
        row["cited_requirement_count"] = len(requirement_ids)
        rows.append(row)
    rows.sort(key=lambda row: (str(row["assessment_id"]), str(row["evidence_id"])))

    by_assessment: list[dict[str, Any]] = []
    all_findings_by_assessment: dict[str, set[str]] = defaultdict(set)
    for finding in analysis["findings"]:
        all_findings_by_assessment[str(finding["assessment_id"])].add(str(finding["requirement_id"]))
    for assessment_id in sorted({str(row["assessment_id"]) for row in rows}):
        subset = [row for row in rows if row["assessment_id"] == assessment_id]
        matched = [row for row in subset if row["crosswalk_state"] in MATCHED_STATES]
        reached = sorted({rid for row in matched for rid in row["cited_requirement_ids"]})
        total_requirements = all_findings_by_assessment.get(assessment_id, set())
        by_assessment.append(
            {
                "assessment_id": assessment_id,
                "system_name": subset[0].get("system_name") if subset else None,
                "evidence_count": len(subset),
                "matched_evidence_count": len(matched),
                "ambiguous_evidence_count": sum(row["crosswalk_state"] == "AMBIGUOUS_EXACT" for row in subset),
                "unresolved_evidence_count": sum(row["crosswalk_state"] == "UNRESOLVED" for row in subset),
                "safe_migration_candidate_count": sum(bool(row["safe_migration_candidate"]) for row in subset),
                "source_registration_candidate_count": sum(
                    bool(row["source_registration_candidate"]) for row in subset
                ),
                "missing_explicit_source_reference_count": sum(
                    bool(row["missing_explicit_source_ids"]) for row in subset
                ),
                "matched_requirement_count": len(reached),
                "requirement_count": len(total_requirements),
                "matched_requirement_ids": reached,
            }
        )

    state_counts = Counter(str(row["crosswalk_state"]) for row in rows)
    matched_rows = [row for row in rows if row["crosswalk_state"] in MATCHED_STATES]
    matched_requirement_ids = sorted({rid for row in matched_rows for rid in row["cited_requirement_ids"]})
    duplicate_urls = [
        {"normalized_public_url": url, "source_ids": sorted(ids), "count": len(ids)}
        for url, ids in sorted(url_index.items())
        if len(ids) > 1
    ]
    duplicate_checksums = [
        {"checksum": checksum, "source_ids": sorted(ids), "count": len(ids)}
        for checksum, ids in sorted(checksum_index.items())
        if len(ids) > 1
    ]
    return {
        "metadata": {
            "title": "NeuroAI deterministic assessment-evidence crosswalk",
            "source_count": len(sources),
            "assessment_count": analysis["metadata"]["assessment_count"],
            "evidence_count": len(rows),
            "fuzzy_matching": False,
        },
        "summary": {
            "state_counts": {state: state_counts[state] for state in sorted(state_counts)},
            "matched_evidence_count": len(matched_rows),
            "ambiguous_evidence_count": state_counts.get("AMBIGUOUS_EXACT", 0),
            "unresolved_evidence_count": state_counts.get("UNRESOLVED", 0),
            "safe_migration_candidate_count": sum(bool(row["safe_migration_candidate"]) for row in rows),
            "source_registration_candidate_count": sum(bool(row["source_registration_candidate"]) for row in rows),
            "missing_explicit_source_reference_count": sum(bool(row["missing_explicit_source_ids"]) for row in rows),
            "matched_requirement_count": len(matched_requirement_ids),
            "matched_requirement_ids": matched_requirement_ids,
        },
        "by_assessment": by_assessment,
        "crosswalk": rows,
        "source_diagnostics": {
            "duplicate_normalized_urls": duplicate_urls,
            "duplicate_checksums": duplicate_checksums,
        },
    }


def render_crosswalk_markdown(crosswalk: dict[str, Any], *, limit: int = 100) -> str:
    metadata = crosswalk["metadata"]
    summary = crosswalk["summary"]
    lines = [
        "# NeuroAI evidence crosswalk",
        "",
        f"Current source universe: {metadata['source_count']} records  ",
        f"Assessments: {metadata['assessment_count']}  ",
        f"Assessment evidence: {metadata['evidence_count']}",
        "",
        "## Summary",
        "",
        f"- Deterministically matched evidence: {summary['matched_evidence_count']}",
        f"- Ambiguous exact matches: {summary['ambiguous_evidence_count']}",
        f"- Unresolved evidence: {summary['unresolved_evidence_count']}",
        f"- Safe migration candidates: {summary['safe_migration_candidate_count']}",
        f"- Source-registration candidates: {summary['source_registration_candidate_count']}",
        f"- Missing explicit source references: {summary['missing_explicit_source_reference_count']}",
        "",
        "## By assessment",
        "",
        "| Assessment | Evidence | Matched | Ambiguous | Unresolved | Safe migration | Registration | Requirements reached |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in crosswalk["by_assessment"]:
        lines.append(
            f"| {row['assessment_id']} | {row['evidence_count']} | {row['matched_evidence_count']} | "
            f"{row['ambiguous_evidence_count']} | {row['unresolved_evidence_count']} | "
            f"{row['safe_migration_candidate_count']} | {row['source_registration_candidate_count']} | "
            f"{row['matched_requirement_count']}/{row['requirement_count']} |"
        )
    lines.extend(
        [
            "",
            "## Unresolved or ambiguous evidence",
            "",
            "| Assessment | Evidence | Title | State | Exact candidates | Missing explicit IDs | Requirements |",
            "| --- | --- | --- | --- | --- | --- | ---: |",
        ]
    )
    attention = [row for row in crosswalk["crosswalk"] if row["crosswalk_state"] not in MATCHED_STATES]
    if attention:
        for row in attention[:limit]:
            lines.append(
                f"| {row['assessment_id']} | {row['evidence_id']} | {row.get('title') or '—'} | "
                f"{row['crosswalk_state']} | {', '.join(row['candidate_source_ids']) or '—'} | "
                f"{', '.join(row['missing_explicit_source_ids']) or '—'} | {row['cited_requirement_count']} |"
            )
    else:
        lines.append("| — | — | No unresolved or ambiguous evidence | — | — | — | — |")
    lines.append("")
    return "\n".join(lines)


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    return str(value)


def write_crosswalk_outputs(crosswalk: dict[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "evidence-crosswalk.json"
    csv_path = output_dir / "evidence-crosswalk.csv"
    markdown_path = output_dir / "evidence-crosswalk.md"
    atomic_write_json(json_path, crosswalk)

    fields = (
        "assessment_id",
        "system_name",
        "evidence_id",
        "title",
        "namespace_state",
        "normalized_public_url",
        "checksum",
        "existing_source_ids",
        "valid_explicit_source_ids",
        "missing_explicit_source_ids",
        "url_candidate_source_ids",
        "checksum_candidate_source_ids",
        "candidate_source_ids",
        "match_rule",
        "crosswalk_state",
        "safe_migration_candidate",
        "source_registration_candidate",
        "cited_requirement_count",
        "cited_requirement_ids",
    )
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in crosswalk["crosswalk"]:
        writer.writerow({field: _csv_value(row.get(field)) for field in fields})
    csv_path.write_text(buffer.getvalue(), encoding="utf-8")
    markdown_path.write_text(render_crosswalk_markdown(crosswalk), encoding="utf-8")
    return {"json": str(json_path), "csv": str(csv_path), "markdown": str(markdown_path)}
