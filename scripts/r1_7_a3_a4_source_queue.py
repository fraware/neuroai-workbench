"""Generate a nonterminal, exact-capture R1.7 A3/A4 source investigation queue.

This read-only report is a prioritized worklist, not new source evidence or
completed extraction. It preserves the frozen route and capture provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

RESOURCE_DIR = Path(__file__).resolve().parents[1] / "src/neuroai_workbench/resources/discovery"
ROUTING = "RELEASE_A_R1_EXECUTION_UNIT_ROUTING_REFINEMENT_CHECKPOINT.v1.0.json"
F6 = "RELEASE_A_R1_CANDIDATE_RESOLUTION_SOURCE_LEDGER_F6.v1.0.json"
F8 = "RELEASE_A_R1_CANDIDATE_RESOLUTION_SOURCE_LEDGER_F8.v1.0.json"
UNIVERSES = {
    "F6": "RELEASE_A_F6_OPEN_WORLD_QUERY_UNIVERSE.v1.0.json",
    "F8": "RELEASE_A_F8_OPEN_WORLD_QUERY_UNIVERSE.v1.0.json",
}


def _load_frozen(path: Path) -> tuple[dict[str, Any], str]:
    """Read exactly one frozen JSON object and record its raw-byte digest."""
    data = path.read_bytes()
    document = json.loads(data)
    if not isinstance(document, dict):
        raise ValueError(f"Frozen resource must be a JSON object: {path.name}")
    return document, hashlib.sha256(data).hexdigest()


def build_queue(resource_dir: Path = RESOURCE_DIR) -> dict[str, Any]:
    checkpoint, route_sha256 = _load_frozen(resource_dir / ROUTING)
    if checkpoint.get("work_item_count") != 270:
        raise ValueError("Frozen 270-item routing population changed")
    if checkpoint.get("work_item_counts_by_route", {}).get("SOURCE_SURFACE_RESOLUTION") != 171:
        raise ValueError("Frozen source work-item denominator changed")
    if checkpoint.get("capture_counts_by_route", {}).get("SOURCE_SURFACE_RESOLUTION") != 226:
        raise ValueError("Frozen source capture denominator changed")
    hashes = {ROUTING: route_sha256}
    source_records: dict[str, dict[str, Any]] = {}
    query_seeds: dict[str, dict[str, Any]] = {}
    for name, frame in [(F6, "F6"), (F8, "F8")]:
        shard, shard_sha256 = _load_frozen(resource_dir / name)
        universe_name = UNIVERSES[frame]
        universe, universe_sha256 = _load_frozen(resource_dir / universe_name)
        hashes[name] = shard_sha256
        hashes[universe_name] = universe_sha256
        if shard.get("frame_id") != frame or universe.get("frame_id") != frame:
            raise ValueError("Frozen source/query universe frame identity changed")
        if (
            shard.get("analysis_universe_id") != checkpoint.get("analysis_universe_id")
            or universe.get("analysis_universe_id") != checkpoint.get("analysis_universe_id")
            or universe.get("world_time_cutoff") != checkpoint.get("world_time_cutoff")
            or universe.get("knowledge_time_cutoff") != checkpoint.get("knowledge_time_cutoff")
        ):
            raise ValueError("Frozen analysis universe or temporal contract mismatch")
        for source in shard["source_records"]:
            capture = source["capture_id"]
            if capture in source_records:
                raise ValueError("Duplicate frozen capture identity")
            source_records[capture] = source
        for seed in universe["query_seeds"]:
            query_id = seed["query_or_seed_id"]
            if query_id in query_seeds:
                raise ValueError("Duplicate frozen query seed identity")
            query_seeds[query_id] = seed
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
            seed = query_seeds.get(source["query_or_seed_id"])
            if seed is None:
                raise ValueError("Priority capture lacks original frozen query")
            for field in ("round_id", "query_family", "source_class", "language", "jurisdiction"):
                if source[field] != seed[field]:
                    raise ValueError(f"Frozen source/query {field} contract mismatch")
            if not isinstance(seed.get("query_expression"), str) or not seed["query_expression"].strip():
                raise ValueError("Frozen source/query expression missing")
            captures.append(
                {
                    "capture_id": capture_id,
                    "source_observation_ref": source["source_observation_ref"],
                    "source_packet_id": source["source_packet_id"],
                    "query_or_seed_id": source["query_or_seed_id"],
                    "query_expression": seed["query_expression"],
                    "query_family": source["query_family"],
                    "frame_id": source["frame_id"],
                    "round_id": source["round_id"],
                    "language": source["language"],
                    "jurisdiction": source["jurisdiction"],
                    "source_class": source["source_class"],
                    "source_outcome_at_frozen_capture": source["outcome"],
                    "raw_candidate_key_at_frozen_capture": source["raw_candidate_key"],
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
    captures = [cap for item in queue for cap in item["captures"]]
    if len(captures) != 69 or len({cap["capture_id"] for cap in captures}) != 69:
        raise ValueError("Priority one-capture-per-work-item contract changed")
    if len({cap["query_or_seed_id"] for cap in captures}) != 69:
        raise ValueError("Priority original query identity repeated")
    a3_families = Counter(
        cap["query_family"] for item in queue if item["priority_analysis"] == "A3_CAPABILITY"
        for cap in item["captures"]
    )
    if len(a3_families) != 6 or set(a3_families.values()) != {3}:
        raise ValueError("Frozen A3 capability-family/round contract changed")
    a4_families = Counter(
        cap["query_family"] for item in queue if item["priority_analysis"] == "A4_MULTILINGUAL"
        for cap in item["captures"]
    )
    if a4_families != {
        "NATIVE_LANGUAGE_CATEGORY": 21,
        "NATIVE_LANGUAGE_CAPABILITY": 21,
        "LOCAL_PRODUCT_SOURCE": 9,
    }:
        raise ValueError("Frozen A4 multilingual-query family contract changed")
    return {
        "report_id": "R1_7_A3_A4_SOURCE_SURFACE_QUEUE_v0.1",
        "frozen_route_checkpoint_id": checkpoint["checkpoint_id"],
        "frozen_input_sha256": dict(sorted(hashes.items())),
        "a3_capability_family_counts": dict(sorted(a3_families.items())),
        "a4_query_family_counts": dict(sorted(a4_families.items())),
        "world_time_cutoff": checkpoint["world_time_cutoff"],
        "knowledge_time_cutoff": checkpoint["knowledge_time_cutoff"],
        "source_surface_total_work_items": 171,
        "priority_work_items": len(queue),
        "priority_counts": dict(sorted(counts.items())),
        "pending_work_items": 69,
        "completed_work_items": 0,
        "items": queue,
        "boundary": (
            "This queue only projects historical captures and query seeds; it performs "
            "no network retrieval, accepts no terminal evidence or product identity, "
            "and does not incorporate separate October source-capture results."
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
