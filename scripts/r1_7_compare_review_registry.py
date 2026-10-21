"""Nonterminal comparison of a frozen PMC EEG review with the Release-A registry.

Read exact archived full-text JATS XML, reproduce its six device tables, and
compare raw names to explicit literal expansions of the six frozen registry IDs.
No canonical entity identity, world-time eligibility, or commercial currentness
is inferred.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.r1_7_extract_review_device_tables import extract_table_rows

REGISTRY_RESOURCE = (
    Path(__file__).resolve().parents[1]
    / "src/neuroai_workbench/resources/product_registry/RELEASE_A_R1_PRODUCT_REGISTRY.v1.1.json"
)
EXPECTED_ENTITY_IDS = frozenset(
    {
        "PRD-NEXTSENSE-SMARTBUDS",
        "PRD-FLOW-FL-100",
        "PRD-MUSE-S-ATHENA",
        "PRD-EMOTIV-EPOC-X",
        "PRD-SYNCHRON-STENTRODE",
        "PRD-MODIUS-SPERO",
    }
)
EXACT_LABEL_CANDIDATES = {
    "Emotiv EPOC X": "PRD-EMOTIV-EPOC-X",
    "Muse S ATHENA": "PRD-MUSE-S-ATHENA",
}
AMBIGUOUS_LABEL_CANDIDATES = {
    "Smartbuds": "PRD-NEXTSENSE-SMARTBUDS",
}
EXPECTED_COMPARISON_COUNTS = {
    "EXACT_TEXTUAL_REGISTRY_ID_LABEL_CANDIDATE": 2,
    "PARTIAL_NAME_OVERLAP_IDENTITY_AMBIGUOUS": 1,
    "NO_TEXTUAL_REGISTRY_ID_MATCH": 54,
}


def load_frozen_registry(path: Path = REGISTRY_RESOURCE) -> tuple[dict[str, Any], str]:
    data = path.read_bytes()
    registry = json.loads(data)
    rows = registry.get("rows")
    metadata = registry.get("metadata")
    if not isinstance(rows, list) or not isinstance(metadata, dict):
        raise ValueError("Frozen Product Registry must have rows and metadata")
    ids = [row["canonical_entity_id"] for row in rows]
    if len(ids) != 6 or len(set(ids)) != len(ids) or set(ids) != EXPECTED_ENTITY_IDS:
        raise ValueError("Frozen six-entry Product Registry identity set changed")
    if metadata.get("row_count") != 6 or metadata.get("world_time_cutoff") != "2026-09-24":
        raise ValueError("Frozen Product Registry metadata changed")
    return registry, hashlib.sha256(data).hexdigest()


def classify_designation(name: str, registry_ids: set[str]) -> dict[str, Any]:
    if name in EXACT_LABEL_CANDIDATES:
        category = "EXACT_TEXTUAL_REGISTRY_ID_LABEL_CANDIDATE"
        candidate = EXACT_LABEL_CANDIDATES[name]
        rationale = "Literal full label matches an explicit expansion of the frozen canonical identifier."
    elif name in AMBIGUOUS_LABEL_CANDIDATES:
        category = "PARTIAL_NAME_OVERLAP_IDENTITY_AMBIGUOUS"
        candidate = AMBIGUOUS_LABEL_CANDIDATES[name]
        rationale = "Unqualified name omits the registered manufacturer/model distinction."
    else:
        category = "NO_TEXTUAL_REGISTRY_ID_MATCH"
        candidate = None
        rationale = "The published designation has no exact match to an expanded frozen registry ID."
    if candidate is not None and candidate not in registry_ids:
        raise ValueError("A proposed registry candidate is missing from the frozen registry")
    return {
        "registry_comparison_category": category,
        "potential_registry_entity_id": candidate,
        "comparison_reason": rationale,
        "composite_name_needs_splitting_review": "/" in name,
        "identity_adjudication": "UNRESOLVED",
        "new_offering_status": "UNDETERMINED",
        "world_time_currentness_2026_09_24": "UNDETERMINED",
        "commercial_availability_2026_09_24": "UNDETERMINED",
        "canonical_entity_id_allocated": None,
    }


def make_crosswalk(raw_xml: bytes, registry: dict[str, Any], registry_sha256: str) -> dict[str, Any]:
    ids = {row["canonical_entity_id"] for row in registry["rows"]}
    if ids != EXPECTED_ENTITY_IDS:
        raise ValueError("Frozen registry identity set changed")
    publication = extract_table_rows(raw_xml)
    records: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    designations: set[str] = set()
    for row in publication["rows"]:
        key = (row["table_number"], row["row_number_1_based"])
        name = row["raw_device_designation"]
        if key in seen or name in designations:
            raise ValueError("Duplicate frozen source table/row or designation")
        seen.add(key)
        designations.add(name)
        records.append(
            {
                "source_pmid": row["source_pmid"],
                "source_raw_xml_sha256": row["source_raw_xml_sha256"],
                "table_number": row["table_number"],
                "row_number_1_based": row["row_number_1_based"],
                "form_factor": row["form_factor"],
                "raw_device_designation": name,
                "raw_row_content_sha256": row["raw_row_content_sha256"],
                **classify_designation(name, ids),
            }
        )
    counts = Counter(item["registry_comparison_category"] for item in records)
    if dict(counts) != EXPECTED_COMPARISON_COUNTS or len(records) != 57:
        raise ValueError("Review crosswalk counts drifted from the frozen evidence")
    if sum(row["composite_name_needs_splitting_review"] for row in records) != 6:
        raise ValueError("Composite published designation count changed")
    return {
        "artifact_type": "R1_7_PUBLICATION_DEVICE_REGISTRY_TEXTUAL_CROSSWALK_v0.1",
        "source_pmid": "42505450",
        "source_primary_xml_sha256": publication["source_evidence_sha256"],
        "source_run_url": publication["source_run_url"],
        "registry_resource": str(REGISTRY_RESOURCE.relative_to(Path(__file__).resolve().parents[1])),
        "registry_file_sha256": registry_sha256,
        "registry_comparison_entity_ids": sorted(ids),
        "study_world_time_cutoff": "2026-09-24",
        "raw_table_row_count": len(records),
        "comparison_counts": dict(counts),
        "composite_designation_count": 6,
        "rows": records,
        "identity_conclusion": "NONE_ESTABLISHED_BY_TEXTUAL_MATCH",
        "new_canonical_entities_created": 0,
        "new_eligible_products_established": 0,
        "r1_7_terminal_extractions_credited": 0,
        "boundary": (
            "Raw published names are candidate mentions only; textual matches and nonmatches "
            "do not establish offering identity, existence at the world-time cutoff, "
            "commercial availability, or global population changes."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-xml", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=REGISTRY_RESOURCE)
    args = parser.parse_args(argv)
    registry, registry_sha256 = load_frozen_registry(args.registry)
    report = make_crosswalk(args.source_xml.read_bytes(), registry, registry_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"{report['raw_table_row_count']} publication rows; "
        f"{report['comparison_counts']}; 0 identities allocated"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
