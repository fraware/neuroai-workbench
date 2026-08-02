from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from ..observatory import load_release, release_kind, summarize_release, validate_release
from ..util import canonical_json_bytes, sha256_bytes

FULL_RELEASE = "FULL_OBSERVATORY_RELEASE"
COMPACT_SUCCESSOR = "COMPACT_SUCCESSOR_SNAPSHOT"
DEFAULT_PREVIEW_LIMIT = 50
QueryDepth = Literal["summary", "full"]

FULL_ORG_FIELDS = (
    "organization_id",
    "canonical_name",
    "verification_state",
    "roles",
    "countries",
    "regions",
    "aliases",
    "evidence_state",
    "claim_boundary",
)
FULL_SOURCE_FIELDS = (
    "source_id",
    "publisher",
    "source_class",
    "url",
    "evidence_state",
    "verification_state",
    "claim_boundary",
    "jurisdiction",
)


def _cell(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return value


def _project_rows(items: list[Any], fields: tuple[str, ...]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rows.append({field: _cell(item.get(field)) for field in fields})
    return rows


def _project_dict_list(items: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rows.append({str(key): _cell(value) for key, value in sorted(item.items())})
    return rows


def query_release(
    release_path: Path,
    *,
    depth: QueryDepth = "summary",
    limit: int | None = DEFAULT_PREVIEW_LIMIT,
) -> dict[str, Any]:
    """Shared query layer projecting canonical release records for product generation.

    ``depth="summary"`` keeps compact preview projections. ``depth="full"`` expands
    available canonical fields for publication builds. ``limit`` caps list
    projections for interactive previews; pass ``limit=None`` for authorized
    release builds so products are not silently truncated.
    """
    if depth not in {"summary", "full"}:
        raise ValueError("depth must be 'summary' or 'full'")

    release = load_release(release_path)
    summary = summarize_release(release)
    validation = validate_release(release)
    kind = release_kind(release)
    metadata = release.get("metadata", {})

    def _slice(items: list[Any]) -> list[Any]:
        if limit is None:
            return items
        return items[:limit]

    rows: dict[str, list[dict[str, Any]]] = {
        "release_summary": [
            {
                "release_version": metadata.get("version", "UNRESOLVED"),
                "release_kind": kind,
                "valid": validation["valid"],
                "status": metadata.get("status", "UNRESOLVED"),
                "effective_as_of": metadata.get("effective_as_of", metadata.get("generated_at", "UNRESOLVED")),
                "query_depth": depth,
            }
        ],
        "verification": [],
    }

    if kind == COMPACT_SUCCESSOR:
        rows["successor_counts"] = [
            {"metric": key, "value": value} for key, value in sorted(summary.get("counts", {}).items())
        ]
        if depth == "summary":
            rows["reopening_decisions"] = [
                {
                    "object": item.get("object"),
                    "decision": item.get("decision"),
                    "decision_id": item.get("decision_id"),
                }
                for item in release.get("reopening_decisions", [])
                if isinstance(item, dict)
            ]
        else:
            rows["reopening_decisions"] = _project_dict_list(
                [item for item in release.get("reopening_decisions", []) if isinstance(item, dict)]
            )
            rows["delta_records"] = []
            delta = release.get("delta")
            if isinstance(delta, dict):
                for section, values in sorted(delta.items()):
                    if not isinstance(values, list):
                        continue
                    for item in values:
                        if not isinstance(item, dict):
                            continue
                        row = {"delta_section": section}
                        row.update({str(key): _cell(value) for key, value in sorted(item.items())})
                        rows["delta_records"].append(row)
            if isinstance(release.get("delta_counts"), dict):
                rows["delta_counts"] = [
                    {"metric": key, "value": value} for key, value in sorted(release["delta_counts"].items())
                ]
            assessment = release.get("assessment_successor_delta")
            if isinstance(assessment, dict):
                rows["assessment_successor_delta"] = _project_dict_list([assessment])
    else:
        rows["coverage_counts"] = [
            {"metric": key, "value": value}
            for key, value in sorted(summary.get("coverage", {}).items())
            if not isinstance(value, dict)
        ]
        if depth == "summary":
            organizations = [
                {
                    "organization_id": item.get("organization_id"),
                    "canonical_name": item.get("canonical_name"),
                    "verification_state": item.get("verification_state"),
                }
                for item in release.get("organizations", [])
                if isinstance(item, dict)
            ]
            sources = [
                {
                    "source_id": item.get("source_id"),
                    "publisher": item.get("publisher"),
                    "source_class": item.get("source_class"),
                }
                for item in release.get("sources", [])
                if isinstance(item, dict)
            ]
        else:
            organizations = _project_rows(
                [item for item in release.get("organizations", []) if isinstance(item, dict)],
                FULL_ORG_FIELDS,
            )
            sources = _project_rows(
                [item for item in release.get("sources", []) if isinstance(item, dict)],
                FULL_SOURCE_FIELDS,
            )
            for sheet_name, key in (
                ("system_relationships", "system_relationships"),
                ("ownership_capital_events", "capital_and_ownership_events"),
                ("models_datasets", "models"),
                ("trial_sites", "trial_site_relationships"),
                ("participant_authority", "participant_authority_relationships"),
                ("suppliers", "supplier_dependency_relationships"),
                ("data_quality_findings", "data_quality"),
            ):
                values = release.get(key)
                if isinstance(values, list):
                    rows[sheet_name] = _slice(_project_dict_list(values))
            for sheet_name, key in (
                ("v16_change_candidates", "change_candidates"),
                ("v16_source_checks", "source_checks"),
                ("v16_adjudications", "adjudications"),
            ):
                values = release.get(key)
                if isinstance(values, list):
                    rows[sheet_name] = _slice(_project_dict_list(values))
            for sheet_name, key in (
                ("assessment_findings", "findings"),
                ("assessment_evidence", "evidence"),
                ("assessment_gaps", "gaps"),
                ("requirement_results", "requirement_results"),
                ("provenance_links", "provenance"),
            ):
                values = release.get(key)
                if isinstance(values, list):
                    rows[sheet_name] = _slice(_project_dict_list(values))
                elif isinstance(values, dict):
                    rows[sheet_name] = _project_dict_list([values])

        rows["organizations"] = _slice(organizations)
        rows["sources"] = _slice(sources)
        rows["projection_limits"] = [
            {
                "field": "list_limit",
                "value": "NONE" if limit is None else str(limit),
            },
            {
                "field": "organizations_total",
                "value": len(organizations),
            },
            {
                "field": "sources_total",
                "value": len(sources),
            },
            {
                "field": "depth",
                "value": depth,
            },
        ]

    release_sha256 = sha256_bytes(canonical_json_bytes(release))
    rows["verification"] = [
        {"field": "release_sha256", "value": release_sha256},
        {"field": "query_depth", "value": depth},
        {"field": "list_limit", "value": "NONE" if limit is None else str(limit)},
        {"field": "record_boundary", "value": "Projection only; no new finding or authority."},
        {"field": "format_note", "value": "Merged verification metadata; generators are views only."},
    ]
    for claim in [
        "No regulatory authorization",
        "No clinical effectiveness or safety conclusion",
        "No system conformance determination",
        "No UNESCO endorsement or institutional authority",
    ]:
        rows["verification"].append({"field": "withheld_claim", "value": claim})

    return {
        "release_path": str(release_path),
        "release_sha256": release_sha256,
        "release_kind": kind,
        "metadata": metadata,
        "summary": summary,
        "rows": rows,
        "limit": limit,
        "depth": depth,
        "withheld_claims": [
            "No regulatory authorization",
            "No clinical effectiveness or safety conclusion",
            "No system conformance determination",
            "No UNESCO endorsement or institutional authority",
        ],
        "boundary": "Queries restate canonical records; they do not upgrade evidence or resolve unknowns.",
    }
