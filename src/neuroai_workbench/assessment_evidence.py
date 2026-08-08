"""Read-only analytical projection of completed assessment evidence and requirement links."""

from __future__ import annotations

import csv
import io
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .util import atomic_write_json

CHECKSUM_FIELDS = ("checksum", "sha256", "content_sha256", "content_hash")
PUBLICATION_DATE_FIELDS = ("publication_date", "published_at", "published", "event_date", "date")
RETRIEVAL_DATE_FIELDS = ("retrieval_date", "retrieved_at", "retrieved", "evidence_cutoff")


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _first(record: dict[str, Any], fields: tuple[str, ...]) -> Any:
    for field in fields:
        value = record.get(field)
        if value is not None and value != "":
            return value
    return None


def normalize_public_url(value: Any) -> str | None:
    """Return a normalized HTTP(S) URL; local paths remain unclassified."""
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return None
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.netloc:
        return None
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.casefold(), parsed.netloc.casefold(), path, parsed.query, ""))


def normalize_checksum(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    token = value.strip()
    upper = token.upper()
    if upper.startswith("NOT CLAIMED") or upper in {"N/A", "NA", "NONE", "UNKNOWN", "UNAVAILABLE"}:
        return None
    return token.casefold()


def _identity(assessment: dict[str, Any], ordinal: int) -> dict[str, Any]:
    metadata = _mapping(assessment.get("assessment_metadata")) or _mapping(assessment.get("metadata"))
    system = _mapping(assessment.get("system_profile")) or _mapping(assessment.get("system"))
    assessment_id = str(metadata.get("assessment_id") or metadata.get("id") or f"assessment:{ordinal}")
    system_name = str(system.get("system_name") or metadata.get("system") or metadata.get("title") or assessment_id)
    return {
        "assessment_id": assessment_id,
        "system_name": system_name,
        "instrument_version": metadata.get("instrument_version"),
        "assessment_version": metadata.get("assessment_version"),
        "evidence_cutoff": metadata.get("evidence_cutoff"),
    }


def _source_ids(record: dict[str, Any]) -> list[str]:
    values = [str(item) for item in _items(record.get("source_ids")) if item is not None]
    return sorted(dict.fromkeys(values))


def _namespace_state(*, source_ids: list[str], public_url: str | None, checksum: str | None) -> str:
    if source_ids:
        return "SHARED_SOURCE_ID"
    if public_url:
        return "PUBLIC_URL_ONLY"
    if checksum:
        return "HASHED_LOCAL"
    return "ASSESSMENT_LOCAL"


def _evidence_input(assessment: dict[str, Any]) -> list[Any]:
    return _items(assessment.get("evidence_register")) or _items(assessment.get("sources"))


def normalize_assessment_evidence(assessment: Any, *, ordinal: int = 0) -> dict[str, Any]:
    """Project one historical/current assessment into evidence, finding, and link rows."""
    if not isinstance(assessment, dict):
        raise ValueError(f"Assessment {ordinal} must be a JSON object")
    identity = _identity(assessment, ordinal)
    assessment_id = str(identity["assessment_id"])
    raw_evidence = _evidence_input(assessment)
    raw_findings = _items(assessment.get("requirement_findings"))
    if not raw_findings:
        raise ValueError(f"Assessment {assessment_id!r} has no requirement_findings")

    cited_counts: Counter[str] = Counter()
    finding_rows: list[dict[str, Any]] = []
    link_rows: list[dict[str, Any]] = []
    for finding_ordinal, raw in enumerate(raw_findings):
        if not isinstance(raw, dict):
            raise ValueError(f"requirement_findings[{finding_ordinal}] in {assessment_id!r} must be an object")
        requirement_id = str(raw.get("requirement_id") or f"requirement:{finding_ordinal}")
        evidence_ids = [str(item) for item in _items(raw.get("evidence_ids")) if item is not None]
        finding_status = raw.get("status", raw.get("finding_status"))
        finding_row = {
            **identity,
            "requirement_id": requirement_id,
            "module_id": raw.get("module_id"),
            "module": raw.get("module", raw.get("module_id")),
            "priority": raw.get("priority"),
            "finding_status": finding_status,
            "evidence_count": len(evidence_ids),
        }
        finding_rows.append(finding_row)
        for evidence_id in evidence_ids:
            cited_counts[evidence_id] += 1
            link_rows.append({**finding_row, "evidence_id": evidence_id})

    evidence_rows: list[dict[str, Any]] = []
    evidence_ids_seen: Counter[str] = Counter()
    for evidence_ordinal, raw in enumerate(raw_evidence):
        if not isinstance(raw, dict):
            raise ValueError(f"evidence[{evidence_ordinal}] in {assessment_id!r} must be an object")
        evidence_id = str(raw.get("evidence_id") or raw.get("source_id") or f"evidence:{evidence_ordinal}")
        evidence_ids_seen[evidence_id] += 1
        source_ids = _source_ids(raw)
        url_or_path = raw.get("url_or_path", raw.get("url"))
        public_url = normalize_public_url(url_or_path)
        checksum = normalize_checksum(_first(raw, CHECKSUM_FIELDS))
        evidence_rows.append(
            {
                **identity,
                "evidence_ordinal": evidence_ordinal,
                "evidence_id": evidence_id,
                "title": raw.get("title"),
                "publisher_or_source": raw.get("source", raw.get("publisher")),
                "evidence_class": raw.get("evidence_class", raw.get("evidence_type")),
                "publication_date": _first(raw, PUBLICATION_DATE_FIELDS),
                "retrieval_date": _first(raw, RETRIEVAL_DATE_FIELDS),
                "url_or_path": url_or_path,
                "normalized_public_url": public_url,
                "source_ids": source_ids,
                "checksum": checksum,
                "evidence_state": raw.get("evidence_state", raw.get("publication_state")),
                "retrieval_state": raw.get("retrieval_state", raw.get("source_retrieval_state")),
                "access_conditions": raw.get("access_conditions"),
                "namespace_state": _namespace_state(
                    source_ids=source_ids,
                    public_url=public_url,
                    checksum=checksum,
                ),
                "cited_requirement_count": cited_counts[evidence_id],
                "raw": raw,
            }
        )

    declared_ids = {row["evidence_id"] for row in evidence_rows}
    linked_ids = {row["evidence_id"] for row in link_rows}
    duplicate_evidence_ids = [
        {"evidence_id": evidence_id, "count": count}
        for evidence_id, count in sorted(evidence_ids_seen.items())
        if count > 1
    ]
    return {
        "identity": identity,
        "evidence": evidence_rows,
        "findings": finding_rows,
        "links": link_rows,
        "duplicate_evidence_ids": duplicate_evidence_ids,
        "dangling_evidence_ids": sorted(linked_ids - declared_ids),
    }


def _duplicate_groups(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        value = row.get(field)
        if not value:
            continue
        grouped[str(value)].append(
            {
                "assessment_id": str(row["assessment_id"]),
                "evidence_id": str(row["evidence_id"]),
            }
        )
    return [
        {field: value, "count": len(items), "records": items}
        for value, items in sorted(grouped.items())
        if len(items) > 1
    ]


def _source_id_overlaps(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        for source_id in row.get("source_ids", []):
            grouped[str(source_id)].append(
                {
                    "assessment_id": str(row["assessment_id"]),
                    "evidence_id": str(row["evidence_id"]),
                }
            )
    return [
        {"source_id": source_id, "count": len(items), "records": items}
        for source_id, items in sorted(grouped.items())
        if len({item["assessment_id"] for item in items}) > 1
    ]


def build_assessment_evidence_analysis(assessments: list[Any]) -> dict[str, Any]:
    """Build portfolio-wide evidence tables and explicit health diagnostics."""
    if not assessments:
        raise ValueError("At least one completed assessment is required")
    packages = [normalize_assessment_evidence(value, ordinal=index) for index, value in enumerate(assessments)]
    assessment_ids = [str(package["identity"]["assessment_id"]) for package in packages]
    if len(set(assessment_ids)) != len(assessment_ids):
        raise ValueError("Assessment evidence analysis requires unique assessment_id values")

    evidence = [row for package in packages for row in package["evidence"]]
    findings = [row for package in packages for row in package["findings"]]
    links = [row for package in packages for row in package["links"]]
    duplicate_evidence_ids = [
        {"assessment_id": package["identity"]["assessment_id"], **item}
        for package in packages
        for item in package["duplicate_evidence_ids"]
    ]
    dangling_links = [
        {"assessment_id": package["identity"]["assessment_id"], "evidence_id": evidence_id}
        for package in packages
        for evidence_id in package["dangling_evidence_ids"]
    ]

    namespace_counts = Counter(str(row["namespace_state"]) for row in evidence)
    reuse_distribution = Counter(int(row["cited_requirement_count"]) for row in evidence)
    by_assessment: list[dict[str, Any]] = []
    for package in packages:
        assessment_id = str(package["identity"]["assessment_id"])
        evidence_rows = package["evidence"]
        finding_rows = package["findings"]
        link_rows = package["links"]
        by_assessment.append(
            {
                **package["identity"],
                "evidence_count": len(evidence_rows),
                "finding_count": len(finding_rows),
                "link_count": len(link_rows),
                "cited_evidence_count": sum(1 for row in evidence_rows if row["cited_requirement_count"] > 0),
                "orphan_evidence_count": sum(1 for row in evidence_rows if row["cited_requirement_count"] == 0),
                "zero_evidence_requirement_count": sum(1 for row in finding_rows if row["evidence_count"] == 0),
                "shared_source_id_evidence_count": sum(
                    1 for row in evidence_rows if row["namespace_state"] == "SHARED_SOURCE_ID"
                ),
                "public_url_evidence_count": sum(1 for row in evidence_rows if row["normalized_public_url"]),
                "checksum_evidence_count": sum(1 for row in evidence_rows if row["checksum"]),
            }
        )

    return {
        "metadata": {
            "title": "NeuroAI assessment evidence analytical projection",
            "assessment_count": len(packages),
            "evidence_count": len(evidence),
            "finding_count": len(findings),
            "evidence_requirement_link_count": len(links),
            "fuzzy_matching": False,
        },
        "health": {
            "by_assessment": by_assessment,
            "namespace_counts": dict(sorted(namespace_counts.items())),
            "evidence_reuse_distribution": {
                str(count): total for count, total in sorted(reuse_distribution.items())
            },
            "orphan_evidence_count": sum(1 for row in evidence if row["cited_requirement_count"] == 0),
            "zero_evidence_requirement_count": sum(1 for row in findings if row["evidence_count"] == 0),
            "shared_source_id_evidence_count": namespace_counts.get("SHARED_SOURCE_ID", 0),
            "public_url_evidence_count": sum(1 for row in evidence if row["normalized_public_url"]),
            "checksum_evidence_count": sum(1 for row in evidence if row["checksum"]),
            "duplicate_evidence_ids": duplicate_evidence_ids,
            "dangling_evidence_links": dangling_links,
            "duplicate_public_urls": _duplicate_groups(evidence, "normalized_public_url"),
            "cross_assessment_source_id_overlaps": _source_id_overlaps(evidence),
        },
        "evidence": evidence,
        "findings": findings,
        "links": links,
    }


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: tuple[str, ...]) -> None:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _csv_value(row.get(field)) for field in fields})
    path.write_text(buffer.getvalue(), encoding="utf-8")


def render_evidence_health_markdown(analysis: dict[str, Any]) -> str:
    metadata = _mapping(analysis.get("metadata"))
    health = _mapping(analysis.get("health"))
    lines = [
        "# NeuroAI assessment evidence health",
        "",
        f"Assessments: {metadata.get('assessment_count', 0)}  ",
        f"Evidence records: {metadata.get('evidence_count', 0)}  ",
        f"Requirement findings: {metadata.get('finding_count', 0)}  ",
        f"Evidence→requirement links: {metadata.get('evidence_requirement_link_count', 0)}",
        "",
        "## Portfolio diagnostics",
        "",
        f"- Orphan evidence records: {health.get('orphan_evidence_count', 0)}",
        f"- Requirements with zero cited evidence: {health.get('zero_evidence_requirement_count', 0)}",
        f"- Shared-source-ID evidence records: {health.get('shared_source_id_evidence_count', 0)}",
        f"- Public-URL evidence records: {health.get('public_url_evidence_count', 0)}",
        f"- Checksum-bearing evidence records: {health.get('checksum_evidence_count', 0)}",
        "",
        "## By assessment",
        "",
        "| Assessment | System | Evidence | Links | Orphan | Zero-evidence req. | Shared IDs | Public URLs |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in _items(health.get("by_assessment")):
        if not isinstance(row, dict):
            continue
        lines.append(
            "| {assessment} | {system} | {evidence} | {links} | {orphan} | {zero} | {shared} | {urls} |".format(
                assessment=row.get("assessment_id"),
                system=row.get("system_name"),
                evidence=row.get("evidence_count", 0),
                links=row.get("link_count", 0),
                orphan=row.get("orphan_evidence_count", 0),
                zero=row.get("zero_evidence_requirement_count", 0),
                shared=row.get("shared_source_id_evidence_count", 0),
                urls=row.get("public_url_evidence_count", 0),
            )
        )
    lines.append("")
    return "\n".join(lines)


def write_assessment_evidence_outputs(analysis: dict[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence_jsonl = output_dir / "assessment-evidence.jsonl"
    evidence_csv = output_dir / "assessment-evidence.csv"
    links_csv = output_dir / "evidence-requirement-links.csv"
    findings_csv = output_dir / "assessment-findings.csv"
    health_json = output_dir / "evidence-health.json"
    health_markdown = output_dir / "evidence-health.md"

    with evidence_jsonl.open("w", encoding="utf-8", newline="\n") as handle:
        for row in analysis["evidence"]:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n")

    _write_csv(
        evidence_csv,
        analysis["evidence"],
        (
            "assessment_id",
            "system_name",
            "instrument_version",
            "assessment_version",
            "evidence_id",
            "title",
            "publisher_or_source",
            "evidence_class",
            "publication_date",
            "retrieval_date",
            "url_or_path",
            "normalized_public_url",
            "source_ids",
            "checksum",
            "evidence_state",
            "retrieval_state",
            "namespace_state",
            "cited_requirement_count",
        ),
    )
    _write_csv(
        links_csv,
        analysis["links"],
        (
            "assessment_id",
            "system_name",
            "evidence_id",
            "requirement_id",
            "module_id",
            "priority",
            "finding_status",
        ),
    )
    _write_csv(
        findings_csv,
        analysis["findings"],
        (
            "assessment_id",
            "system_name",
            "requirement_id",
            "module_id",
            "module",
            "priority",
            "finding_status",
            "evidence_count",
        ),
    )
    atomic_write_json(health_json, {"metadata": analysis["metadata"], "health": analysis["health"]})
    health_markdown.write_text(render_evidence_health_markdown(analysis), encoding="utf-8")
    return {
        "evidence_jsonl": str(evidence_jsonl),
        "evidence_csv": str(evidence_csv),
        "links_csv": str(links_csv),
        "findings_csv": str(findings_csv),
        "health_json": str(health_json),
        "health_markdown": str(health_markdown),
    }
