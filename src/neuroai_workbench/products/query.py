from __future__ import annotations

from pathlib import Path
from typing import Any

from ..observatory import load_release, release_kind, summarize_release, validate_release
from ..util import canonical_json_bytes, sha256_bytes

FULL_RELEASE = "FULL_OBSERVATORY_RELEASE"
COMPACT_SUCCESSOR = "COMPACT_SUCCESSOR_SNAPSHOT"
DEFAULT_PREVIEW_LIMIT = 50


def query_release(release_path: Path, *, limit: int | None = DEFAULT_PREVIEW_LIMIT) -> dict[str, Any]:
    """Shared query layer projecting canonical release records for product generation.

    ``limit`` caps list projections for interactive previews. Pass ``limit=None`` for
    authorized release builds so products are not silently truncated.
    """
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
            }
        ],
        "verification": [],
    }

    if kind == COMPACT_SUCCESSOR:
        rows["successor_counts"] = [
            {"metric": key, "value": value} for key, value in sorted(summary.get("counts", {}).items())
        ]
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
        rows["coverage_counts"] = [
            {"metric": key, "value": value}
            for key, value in sorted(summary.get("coverage", {}).items())
            if not isinstance(value, dict)
        ]
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
        ]

    release_sha256 = sha256_bytes(canonical_json_bytes(release))
    rows["verification"] = [
        {"field": "release_sha256", "value": release_sha256},
        {"field": "record_boundary", "value": "Projection only; no new finding or authority."},
    ]

    return {
        "release_path": str(release_path),
        "release_sha256": release_sha256,
        "release_kind": kind,
        "metadata": metadata,
        "summary": summary,
        "rows": rows,
        "limit": limit,
        "withheld_claims": [
            "No regulatory authorization",
            "No clinical effectiveness or safety conclusion",
            "No system conformance determination",
            "No UNESCO endorsement or institutional authority",
        ],
        "boundary": "Queries restate canonical records; they do not upgrade evidence or resolve unknowns.",
    }
