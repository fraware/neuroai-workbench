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
    "organization_type",
    "roles",
    "headquarters_country",
    "jurisdictions",
    "unesco_region",
    "countries",
    "regions",
    "aliases",
    "evidence_state",
    "claim_boundary",
    "current_status",
    "official_url",
)
FULL_SOURCE_FIELDS = (
    "source_id",
    "publisher",
    "source_class",
    "title",
    "url",
    "evidence_state",
    "verification_state",
    "claim_boundary",
    "jurisdiction",
    "supports",
    "retrieved",
)

# First-class full-depth sheets when a named canonical list key yields data.
# Sheet name → release key(s) tried in order. Missing or empty lists fall through to
# later aliases; if every key is missing or empty the sheet is omitted, never invented.
FULL_LIST_PROJECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("system_relationships", ("system_relationships",)),
    ("systems", ("systems",)),
    ("ownership_capital_events", ("capital_and_ownership_events",)),
    ("models", ("representative_model_records", "models")),
    ("models_datasets", ("model_and_dataset_registry", "models_datasets")),
    ("trial_sites", ("trial_site_relationships",)),
    ("participant_authority", ("participant_authority_relationships",)),
    ("suppliers", ("supplier_dependency_relationships",)),
    ("data_quality_findings", ("data_quality",)),
    ("organization_resolution", ("organization_resolution",)),
    ("regional_expansion", ("regional_expansion",)),
    ("captures", ("captures",)),
    ("candidates", ("change_candidates", "candidates")),
    ("adjudications", ("adjudications",)),
    ("source_checks", ("source_checks",)),
    ("evidence_register", ("evidence_register", "evidence_registers")),
    ("assessment_findings", ("findings",)),
    ("assessment_evidence", ("evidence",)),
    ("assessment_gaps", ("gaps",)),
    ("requirement_results", ("requirement_results",)),
    ("provenance_links", ("provenance",)),
)

# Sheets rendered as DOCX/PDF appendices (identity sheets stay in the front matter).
APPENDIX_EXCLUDED_SHEETS = frozenset(
    {
        "verification",
        "projection_limits",
        "release_summary",
    }
)


def _cell(value: Any) -> Any:
    if isinstance(value, dict | list):
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


def _countries_cell(item: dict[str, Any]) -> Any:
    if "countries" in item:
        return _cell(item.get("countries"))
    jurisdictions = item.get("jurisdictions")
    if isinstance(jurisdictions, list) and jurisdictions:
        return _cell(jurisdictions)
    return _cell(item.get("headquarters_country"))


def _regions_cell(item: dict[str, Any]) -> Any:
    if "regions" in item:
        return _cell(item.get("regions"))
    return _cell(item.get("unesco_region"))


def _project_organizations(items: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        row = {field: _cell(item.get(field)) for field in FULL_ORG_FIELDS}
        row["countries"] = _countries_cell(item)
        row["regions"] = _regions_cell(item)
        rows.append(row)
    return rows


def _project_aliases(organizations: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in organizations:
        if not isinstance(item, dict):
            continue
        organization_id = item.get("organization_id")
        aliases = item.get("aliases")
        if not isinstance(aliases, list):
            continue
        for alias in aliases:
            if alias is None or alias == "":
                continue
            rows.append(
                {
                    "organization_id": organization_id,
                    "canonical_name": item.get("canonical_name"),
                    "alias": alias if not isinstance(alias, dict | list) else _cell(alias),
                }
            )
    return rows


def _metric_rows(mapping: Any) -> list[dict[str, Any]]:
    if not isinstance(mapping, dict):
        return []
    return [{"metric": key, "value": value} for key, value in sorted(mapping.items()) if not isinstance(value, dict)]


def _project_optional_dict_as_rows(value: Any, *, section: str | None = None) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return _project_dict_list(value)
    if isinstance(value, dict):
        rows = _project_dict_list([value])
        if section is not None and rows:
            for row in rows:
                row.setdefault("section", section)
        return rows
    return []


def iter_appendix_sheets(query: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    """Return ordered (sheet_name, rows) pairs for substantive DOCX/PDF appendices."""
    rows = query.get("rows")
    if not isinstance(rows, dict):
        return []
    sheets: list[tuple[str, list[dict[str, Any]]]] = []
    for name in sorted(rows):
        if name in APPENDIX_EXCLUDED_SHEETS:
            continue
        values = rows[name]
        if isinstance(values, list) and values:
            sheets.append((name, values))
    return sheets


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

    Missing canonical sections are omitted and never invented.
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
        rows["successor_counts"] = _metric_rows(summary.get("counts", {}))
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
            delta_counts = _metric_rows(release.get("delta_counts"))
            if delta_counts:
                rows["delta_counts"] = delta_counts
            baseline_counts = _metric_rows(release.get("baseline_counts"))
            if baseline_counts:
                rows["baseline_counts"] = baseline_counts
            assessment = release.get("assessment_successor_delta")
            if isinstance(assessment, dict):
                rows["assessment_successor_delta"] = _project_dict_list([assessment])
            provenance = release.get("provenance")
            provenance_rows = _project_optional_dict_as_rows(provenance)
            if provenance_rows:
                # Flatten scalar provenance map into metric-style rows when it is a dict of scalars.
                if isinstance(provenance, dict) and all(not isinstance(v, dict | list) for v in provenance.values()):
                    rows["provenance_links"] = [
                        {"field": key, "value": value} for key, value in sorted(provenance.items())
                    ]
                else:
                    rows["provenance_links"] = provenance_rows
    else:
        rows["coverage_counts"] = _metric_rows(summary.get("coverage", {}))
        organizations_raw = [item for item in release.get("organizations", []) if isinstance(item, dict)]
        sources_raw = [item for item in release.get("sources", []) if isinstance(item, dict)]
        if depth == "summary":
            organizations = [
                {
                    "organization_id": item.get("organization_id"),
                    "canonical_name": item.get("canonical_name"),
                    "verification_state": item.get("verification_state"),
                }
                for item in organizations_raw
            ]
            sources = [
                {
                    "source_id": item.get("source_id"),
                    "publisher": item.get("publisher"),
                    "source_class": item.get("source_class"),
                }
                for item in sources_raw
            ]
        else:
            organizations = _project_organizations(organizations_raw)
            sources = _project_rows(sources_raw, FULL_SOURCE_FIELDS)
            alias_rows = _project_aliases(organizations_raw)
            if alias_rows:
                rows["aliases"] = _slice(alias_rows)
            for sheet_name, keys in FULL_LIST_PROJECTIONS:
                projected: list[dict[str, Any]] | None = None
                for key in keys:
                    values = release.get(key)
                    if isinstance(values, list):
                        if not values:
                            continue
                        dict_items = [item for item in values if isinstance(item, dict)]
                        if dict_items:
                            projected = _slice(_project_dict_list(dict_items))
                            break
                        projected = _slice([{"value": _cell(item)} for item in values])
                        break
                    if isinstance(values, dict):
                        projected = _project_dict_list([values])
                        break
                if projected:
                    rows[sheet_name] = projected
            coverage = release.get("coverage")
            if isinstance(coverage, dict):
                exit_conditions = coverage.get("exit_conditions")
                if isinstance(exit_conditions, list) and exit_conditions:
                    rows["coverage_exit_conditions"] = _slice(_project_dict_list(exit_conditions))
            methodology = release.get("methodology")
            if isinstance(methodology, dict):
                universes = methodology.get("source_universes")
                if isinstance(universes, list) and universes:
                    rows["methodology_source_universes"] = _slice(_project_dict_list(universes))

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
