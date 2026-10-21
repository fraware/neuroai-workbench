"""Generate a nonterminal, exact-capture R1.7 A3/A4 source investigation queue.

This read-only report is a prioritized worklist, not new source evidence or
completed extraction. It preserves the frozen route and capture provenance.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

RESOURCE_DIR = Path(__file__).resolve().parents[1] / "src/neuroai_workbench/resources/discovery"
ROUTING = "RELEASE_A_R1_EXECUTION_UNIT_ROUTING_REFINEMENT_CHECKPOINT.v1.0.json"
F6 = "RELEASE_A_R1_CANDIDATE_RESOLUTION_SOURCE_LEDGER_F6.v1.0.json"
F8 = "RELEASE_A_R1_CANDIDATE_RESOLUTION_SOURCE_LEDGER_F8.v1.0.json"


def build_queue(resource_dir: Path = RESOURCE_DIR) -> dict[str, Any]:
    checkpoint = json.loads((resource_dir / ROUTING).read_text(encoding="utf-8"))
    if checkpoint.get("work_item_count") != 270:
        raise ValueError("Frozen 270-item routing population changed")
    source_records: dict[str, dict[str, Any]] = {}
    for name, frame in [(F6, "F6"), (F8, "F8")]:
        shard = json.loads((resource_dir / name).read_text(encoding="utf-8"))
        if shard.get("frame_id") != frame:
            raise ValueError("Source-shard frame identity changed")
        for source in shard["source_records"]:
            capture = source["capture_id"]
            if capture in source_records:
                raise ValueError("Duplicate frozen capture identity")
            source_records[capture] = source
    queue: list[dict[str, Any]] = []
    for item in checkpoint["route_table"]:
        if item["execution_route"] != "SOURCE_SURFACE_RESOLUTION":
            continue
        a3, a4 = item["could_change_a3_increment"], item["could_change_a4_increment"]
        if not (a3 or a4):
            continue
        if a3 == a4:
            raise ValueError("Priority work item expected in exactly one of A3 or A4")
        captures: list[dict[str, Any]] = []
        for capture_id in item["capture_ids"]:
            source = source_records.get(capture_id)
            if source is None:
                raise ValueError("Priority route cannot be joined to exact F6/F8 capture")
            if source["frame_id"] != ("F6" if a3 else "F8"):
                raise ValueError("Priority capture frame differs from route semantics")
            if source["candidate_cluster_id"] != item["candidate_cluster_id"]:
                raise ValueError("Priority capture cluster identity mismatch")
            if source["could_change_a3_increment"] != a3 or source["could_change_a4_increment"] != a4:
                raise ValueError("Priority capture analytical flag mismatch")
            captures.append(
                {
                    "capture_id": capture_id,
                    "source_observation_ref": source["source_observation_ref"],
                    "source_packet_id": source["source_packet_id"],
                    "query_or_seed_id": source["query_or_seed_id"],
                    "query_family": source["query_family"],
                    "frame_id": source["frame_id"],
                    "round_id": source["round_id"],
                    "language": source["language"],
                    "jurisdiction": source["jurisdiction"],
                    "source_class": source["source_class"],
                    "source_outcome_at_frozen_capture": source["outcome"],
                    "frozen_observed_at": source["observed_at"],
                    "world_time_alignment": source["world_time_alignment"],
                }
            )
        queue.append(
            {
                "work_item_id": item["work_item_id"],
                "candidate_cluster_id": item["candidate_cluster_id"],
                "priority_analysis": "A3_CAPABILITY" if a3 else "A4_MULTILINGUAL",
                "selection_reasons": item["selection_reasons"],
                "capture_count": len(captures),
                "captures": captures,
                "execution_state": "PENDING_FRESH_SOURCE_VERIFICATION",
                "evidence_artifact_refs": [],
                "product_identities_established": [],
                "terminal_r1_7_decision": None,
            }
        )
    queue.sort(key=lambda item: (item["priority_analysis"], item["work_item_id"]))
    counts = Counter(item["priority_analysis"] for item in queue)
    if len(queue) != 69 or counts != {"A3_CAPABILITY": 18, "A4_MULTILINGUAL": 51}:
        raise ValueError("Frozen A3/A4 source-route population drift")
    if len({item["work_item_id"] for item in queue}) != 69:
        raise ValueError("Priority work item duplicated")
    return {
        "report_id": "R1_7_A3_A4_SOURCE_SURFACE_QUEUE_v0.1",
        "frozen_route_checkpoint_id": checkpoint["checkpoint_id"],
        "world_time_cutoff": checkpoint["world_time_cutoff"],
        "knowledge_time_cutoff": checkpoint["knowledge_time_cutoff"],
        "source_surface_total_work_items": 171,
        "priority_work_items": len(queue),
        "priority_counts": dict(sorted(counts.items())),
        "pending_work_items": 69,
        "completed_work_items": 0,
        "items": queue,
        "boundary": (
            "Frozen ABSTAIN source capture provenance only. No new external sources "
            "were retrieved, no evidence or terminal decisions were accepted, "
            "and no product or analytical increment was inferred."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    report = build_queue()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("69 pending source items: 18 A3 capability, 51 A4 multilingual; zero completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
