"""Project all unlinked original R1.7 source captures into executable research leads.

This is a read-only queue. It joins the R1.6.1 route checkpoint, existing
immutable original source records, and a strictly BOUNDED saved-archive
inventory. A missing receipt in the two named archives is NOT evidence of
a missing source, an empty search, or an absent eligible product.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from neuroai_workbench.release_a_r1_resolution import (
    compile_r1_source_records,
    load_r1_candidate_resolution_manifest,
)
from scripts.r1_7_all_routes_archive_coverage import build_report

UNLINKED = "NO_LINKED_ARCHIVE_EVIDENCE_IN_THIS_BOUNDED_INVENTORY"


def build_unlinked_source_queue() -> dict[str, Any]:
    """Create 221 source-capture tasks without inventing query results."""
    report = build_report()
    if report["governed_work_item_count"] != 192 or report["governed_capture_count"] != 247:
        raise ValueError("R1.7 complete frozen source/record denominator drift")
    if report["archive_state_counts_by_capture"].get(UNLINKED) != 221:
        raise ValueError("Two-archive nonmatching source capture count drift")
    source_rows = compile_r1_source_records(load_r1_candidate_resolution_manifest())
    by_capture = {row["capture_id"]: row for row in source_rows}
    if len(by_capture) != len(source_rows):
        raise ValueError("Original source ledger duplicated a capture identifier")

    pending: list[dict[str, Any]] = []
    counts_by_frame: Counter[str] = Counter()
    counts_by_historical_outcome: Counter[str] = Counter()
    for work in report["work_items"]:
        for cap in work["captures"]:
            if cap["archive_state"] != UNLINKED:
                continue
            if work["execution_route"] != "SOURCE_SURFACE_RESOLUTION":
                raise ValueError("Unexpected archived-literature context without matching article")
            source = by_capture.get(cap["capture_id"])
            if source is None:
                raise ValueError("No immutable first-party A2 capture record for a frozen R1.7 task")
            record = {
                "work_item_id": work["work_item_id"],
                "capture_id": cap["capture_id"],
                "execution_route": work["execution_route"],
                "frame_id": source["frame_id"],
                "round_id": source["round_id"],
                "frozen_query_or_seed_id": source["query_or_seed_id"],
                "source_packet_id": source["source_packet_id"],
                "source_observation_ref": source["source_observation_ref"],
                "original_source_outcome": source["outcome"],
                "original_raw_candidate_key": source["raw_candidate_key"],
                "original_normalized_candidate_label": source["normalized_candidate_label"],
                "matched_saved_evidence_receipt_in_two_archives": False,
                "attributable_new_source_retrieval_performed_by_queue": False,
                "terminal_source_completion": False,
                "canonical_offering_identity": None,
                "eligible_product_increment": 0,
            }
            if not record["frozen_query_or_seed_id"] or not record["source_observation_ref"]:
                raise ValueError("Immutable source capture lacks query or observation identity")
            pending.append(record)
            counts_by_frame[str(source["frame_id"])] += 1
            counts_by_historical_outcome[str(source["outcome"])] += 1
    if len(pending) != 221 or len({r["capture_id"] for r in pending}) != 221:
        raise ValueError("R1.7 unlinked source capture identity or count drift")
    pending.sort(key=lambda r: (r["frame_id"], r["round_id"], r["work_item_id"], r["capture_id"]))
    return {
        "report_type": "RELEASE_A_R1_7_UNLINKED_FROZEN_SOURCE_CAPTURE_QUEUE_v0.1",
        "status": "PENDING_ATTRIBUTABLE_SOURCE_EXECUTION_NOT_SOURCE_ABSENCE",
        "analysis_universe_id": report["analysis_universe_id"],
        "world_time_cutoff": report["world_time_cutoff"],
        "knowledge_time_cutoff": report["knowledge_time_cutoff"],
        "covered_source_record_work_items": report["governed_work_item_count"],
        "covered_frozen_capture_population": report["governed_capture_count"],
        "unlinked_capture_count": len(pending),
        "frame_counts": dict(sorted(counts_by_frame.items())),
        "historical_outcome_counts": dict(sorted(counts_by_historical_outcome.items())),
        "records": pending,
        "terminal_source_completions": 0,
        "new_canonical_entities": 0,
        "scope": (
            "Only captures without links in two specified acquisition archives. "
            "Other independent evidence may already exist elsewhere. "
            "No network access, live search, absence inference, completed review, "
            "product inclusion, or publication was performed."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = build_unlinked_source_queue()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print("221 original source capture references, all nonterminal and uncredited")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
