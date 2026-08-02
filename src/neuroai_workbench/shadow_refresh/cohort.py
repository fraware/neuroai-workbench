"""Shadow cohort discovery helpers and reviewed-manifest loading.

Regex discovery is non-authoritative. Freeze/plan paths must load an exact
reviewed source_id manifest; discovery output cannot write the freeze artifact.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..util import load_json
from .schemas import (
    SHADOW_EVALUATION_STATUS,
    SHADOW_REFRESH_BOUNDARY,
    validate_shadow_refresh_cohort,
)

CATEGORY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("PRIMA_SCIENCE", re.compile(r"prima|science\.xyz", re.I)),
    ("SYNCHRON", re.compile(r"synchron|stentrode", re.I)),
    ("PARADROMICS", re.compile(r"paradromics|connexus", re.I)),
    ("BRAIN2QWERTY", re.compile(r"brain2qwerty", re.I)),
    ("FDA_ADBS", re.compile(r"adaptive|dbs|deep.?brain|neuromodulation", re.I)),
    ("BRAINGATE2_T15", re.compile(r"braingate", re.I)),
    ("REGISTRY", re.compile(r"clinicaltrials|fda\.gov|eudamed|registry", re.I)),
    ("OWNERSHIP_FUNDING", re.compile(r"investor|funding|acquisition|ownership|tether", re.I)),
    ("SAFETY", re.compile(r"safety|adverse|recall|mfds", re.I)),
    ("SUPPLIER_DEPENDENCY", re.compile(r"supplier|heraeus", re.I)),
]


def _blob(record: dict[str, Any]) -> str:
    return " ".join(str(record.get(key, "")) for key in ("publisher", "url", "source_id", "source_class", "monitor_id"))


def discover_cohort_candidates(registry: dict[str, Any], *, target_count: int = 25) -> list[dict[str, Any]]:
    """Optional regex discovery helper.

    Output is non-authoritative candidate listing only. It must not be used as a
    freeze artifact without a separate human-reviewed exact-ID manifest.
    """
    selected: list[dict[str, Any]] = []
    used: set[str] = set()
    for category, pattern in CATEGORY_PATTERNS:
        hits = [
            record
            for record in registry["sources"]
            if isinstance(record, dict) and record.get("source_id") not in used and pattern.search(_blob(record))
        ]
        for record in hits[:3]:
            used.add(str(record["source_id"]))
            selected.append(
                {
                    **record,
                    "discovery_category": category,
                    "discovery_only": True,
                    "authoritative": False,
                }
            )
            if len(selected) >= target_count:
                return selected
    for record in registry["sources"]:
        if len(selected) >= target_count:
            break
        if not isinstance(record, dict):
            continue
        source_id = str(record.get("source_id"))
        if source_id in used:
            continue
        used.add(source_id)
        selected.append(
            {
                **record,
                "discovery_category": "UNLABELED_CANDIDATE",
                "discovery_only": True,
                "authoritative": False,
            }
        )
    return selected


def load_reviewed_cohort_manifest(path: Path) -> dict[str, Any]:
    """Load and validate a reviewed exact-ID cohort freeze manifest."""
    cohort = load_json(path)
    if not isinstance(cohort, dict):
        raise ValueError("Reviewed cohort manifest must be a JSON object")
    errors = validate_shadow_refresh_cohort(cohort)
    if errors:
        raise ValueError(f"Reviewed cohort schema invalid: {errors}")
    if cohort.get("metadata", {}).get("status") != SHADOW_EVALUATION_STATUS:
        raise ValueError("Reviewed cohort must remain SHADOW_EVALUATION_NOT_CANONICAL")

    sources = cohort.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("Reviewed cohort must include a non-empty sources array")

    seen: set[str] = set()
    duplicates: list[str] = []
    for index, item in enumerate(sources):
        if not isinstance(item, dict):
            raise ValueError(f"sources[{index}] must be an object")
        source_id = str(item["source_id"])
        if source_id in seen:
            duplicates.append(source_id)
        seen.add(source_id)
        if item.get("coverage_label") != item.get("cohort_category"):
            raise ValueError(
                f"sources[{index}] coverage_label {item.get('coverage_label')!r} "
                f"must equal cohort_category {item.get('cohort_category')!r}"
            )
        if item.get("cohort_category") == "DIVERSITY_PAD" or item.get("coverage_label") == "DIVERSITY_PAD":
            raise ValueError("Frozen reviewed cohort must not contain DIVERSITY_PAD labels")

    if duplicates:
        raise ValueError(f"Duplicate source_id values in reviewed cohort: {', '.join(sorted(set(duplicates)))}")

    declared = int(cohort["metadata"]["source_count"])
    if declared != len(sources):
        raise ValueError(f"metadata.source_count {declared} does not match sources length {len(sources)}")

    return cohort


def bind_reviewed_cohort_to_registry(
    cohort: dict[str, Any],
    registry: dict[str, Any],
) -> list[dict[str, Any]]:
    """Ensure every reviewed source_id exists in the registry; return bound rows."""
    by_id = {
        str(record["source_id"]): record
        for record in registry.get("sources", [])
        if isinstance(record, dict) and record.get("source_id")
    }
    missing = [str(item["source_id"]) for item in cohort["sources"] if str(item["source_id"]) not in by_id]
    if missing:
        raise ValueError(f"Reviewed cohort source_id values missing from registry: {', '.join(missing)}")
    bound: list[dict[str, Any]] = []
    for item in cohort["sources"]:
        registry_row = by_id[str(item["source_id"])]
        bound.append({**registry_row, **item})
    return bound


def reviewed_cohort_boundary() -> str:
    return SHADOW_REFRESH_BOUNDARY
