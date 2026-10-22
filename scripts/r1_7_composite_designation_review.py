"""Read-only slash-composite review hints from SHA-bound EEG publication rows.

Literal text segments are NOT verified models, independently marketed products,
canonical IDs, or Release-A eligibility claims. No inferred prefix expansion.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.r1_7_compare_review_registry import (
    EXPECTED_COMPARISON_COUNTS,
    load_frozen_registry,
    make_crosswalk,
)


def literal_parts(designation: str) -> list[str]:
    if not isinstance(designation, str) or designation.count("/") != 1:
        raise ValueError("Expected exactly one literal slash in review designation")
    pieces = [part.strip() for part in designation.split("/")]
    if len(pieces) != 2 or any(not part for part in pieces):
        raise ValueError("Empty original slash segment")
    return pieces


def make_composite_review(crosswalk: dict[str, Any]) -> dict[str, Any]:
    """Preserve source identity and table/row lineage for six composite labels."""
    if crosswalk.get("source_pmid") != "42505450" or crosswalk.get("raw_table_row_count") != 57:
        raise ValueError("Expected the original 57-row PMID 42505450 source")
    if crosswalk.get("comparison_counts") != EXPECTED_COMPARISON_COUNTS:
        raise ValueError("Textual registry baseline changed")
    if crosswalk.get("new_canonical_entities_created") != 0 or crosswalk.get("r1_7_terminal_extractions_credited") != 0:
        raise ValueError("Unreviewed publication must not assign product or execution credit")
    sha = crosswalk["source_primary_xml_sha256"]
    if not isinstance(sha, str) or len(sha) != 64:
        raise ValueError("Missing original source digest")
    out: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for row in crosswalk["rows"]:
        designation = row["raw_device_designation"]
        if "/" not in designation:
            continue
        key = row["table_number"], row["row_number_1_based"]
        if key in seen or row["source_raw_xml_sha256"] != sha:
            raise ValueError("Duplicated or mismatched source table-row lineage")
        if row["composite_name_needs_splitting_review"] is not True:
            raise ValueError("Inconsistent original composite flag")
        seen.add(key)
        out.append(
            {
                "table_number": key[0],
                "row_number_1_based": key[1],
                "raw_row_content_sha256": row["raw_row_content_sha256"],
                "source_xml_sha256": sha,
                "form_factor": row["form_factor"],
                "original_designation": designation,
                "literal_segments_only": literal_parts(designation),
                "prefix_expansion": "UNRESOLVED_DO_NOT_INFER",
                "distinct_commercial_offerings": None,
                "product_identity": "NOT_ADJUDICATED",
                "world_time_commercial_currentness": "NOT_ASSESSED",
                "canonical_entity_id_allocated": None,
            }
        )
    out.sort(key=lambda x: (x["table_number"], x["row_number_1_based"]))
    if len(out) != 6 or sum(len(x["literal_segments_only"]) for x in out) != 12:
        raise ValueError("Original six slash-composite designations changed")
    return {
        "type": "RELEASE_A_R1_7_SOURCE_COMPOSITE_REVIEW_HINTS_v0.1",
        "status": "NONTERMINAL_SOURCE_TEXT_ONLY",
        "source_pmid": "42505450",
        "source_xml_sha256": sha,
        "registry_sha256": crosswalk["registry_file_sha256"],
        "original_raw_table_rows": 57,
        "slash_composite_row_count": 6,
        "literal_segment_count": 12,
        "product_count_inference": None,
        "new_product_identifiers": 0,
        "terminal_extractions": 0,
        "review_rows": out,
        "caution": "A slash can abbreviate a shared vendor/model prefix; do not count literal segments as distinct offerings.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-xml", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    registry, digest = load_frozen_registry()
    crosswalk = make_crosswalk(args.source_xml.read_bytes(), registry, digest)
    output = make_composite_review(crosswalk)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print("Six source composite rows, 12 literal segments, no new product identities")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
