"""Exact frozen A3/A4-sensitive source-retrieval worklist for Release-A R1.7.

This is a deterministic *pending-work* projection of existing frozen resource
files. It makes no HTTP requests, credits no source extraction, and creates
no new candidate identities or product-population increments.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

RESOURCES = Path(__file__).resolve().parents[1] / "src/neuroai_workbench/resources/discovery"
ROUTES = "RELEASE_A_R1_EXECUTION_UNIT_ROUTING_REFINEMENT_CHECKPOINT.v1.0.json"
SHARDS = {
    "F6": "RELEASE_A_R1_CANDIDATE_RESOLUTION_SOURCE_LEDGER_F6.v1.0.json",
    "F8": "RELEASE_A_R1_CANDIDATE_RESOLUTION_SOURCE_LEDGER_F8.v1.0.json",
}
UNIVERSES = {
    "F6": "RELEASE_A_F6_OPEN_WORLD_QUERY_UNIVERSE.v1.0.json",
    "F8": "RELEASE_A_F8_OPEN_WORLD_QUERY_UNIVERSE.v1.0.json",
}
EXPECTED_COUNTS = {
    "A3_CAPABILITY": 18,
    "A4_MULTILINGUAL": 51,
}
EXPECTED_F8_FAMILIES = {
    "NATIVE_LANGUAGE_CATEGORY": 21,
    "NATIVE_LANGUAGE_CAPABILITY": 21,
    "LOCAL_PRODUCT_SOURCE": 9,
}


def _load(filename: str, resource_root: Path) -> tuple[dict[str, Any], str]:
    data = (resource_root / filename).read_bytes()
    result = json.loads(data)
    if not isinstance(result, dict):
        raise ValueError(f"Frozen resource must be a JSON object: {filename}")
    return result, hashlib.sha256(data).hexdigest()


def build_priority_source_worklist(resource_root: Path = RESOURCES) -> dict[str, Any]:
    """Bind all 69 priority work items to exact captures and frozen query seeds."""
    routing, route_hash = _load(ROUTES, resource_root)
    sources: dict[str, dict[str, Any]] = {}
    seeds: dict[str, dict[str, Any]] = {}
    input_hashes = {ROUTES: route_hash}
    for frame in ("F6", "F8"):
        shard, shard_hash = _load(SHARDS[frame], resource_root)
        universe, universe_hash = _load(UNIVERSES[frame], resource_root)
        input_hashes[SHARDS[frame]] = shard_hash
        input_hashes[UNIVERSES[frame]] = universe_hash
        if universe.get("frame_id") != frame:
            raise ValueError(f"Frozen query universe mismatches {frame}")
        for source in shard["source_records"]:
            capture_id = source["capture_id"]
            if capture_id in sources:
                raise ValueError("Duplicate source capture identifier")
            sources[capture_id] = source
        for seed in universe["query_seeds"]:
            key = seed["query_or_seed_id"]
            if key in seeds:
                raise ValueError("Duplicate seed query identifier")
            seeds[key] = seed

    result: list[dict[str, Any]] = []
    for route in routing["route_table"]:
        if route["execution_route"] != "SOURCE_SURFACE_RESOLUTION":
            continue
        affects_a3 = route["could_change_a3_increment"]
        affects_a4 = route["could_change_a4_increment"]
        if not (affects_a3 or affects_a4):
            continue
        if affects_a3 == affects_a4:
            raise ValueError("Ambiguous A3/A4-sensitive route")
        if len(route["capture_ids"]) != 1:
            raise ValueError("A3/A4 source work items must bind exactly one frozen capture")
        capture_id = route["capture_ids"][0]
        capture = sources.get(capture_id)
        if capture is None:
            raise ValueError("Missing frozen source capture")
        seed_id = capture["query_or_seed_id"]
        seed = seeds.get(seed_id)
        if seed is None:
            raise ValueError("Missing frozen retrieval seed")
        frame_id = capture["frame_id"]
        if frame_id != ("F6" if affects_a3 else "F8"):
            raise ValueError("Priority route linked to wrong frozen frame")
        if seed["round_id"] != capture["round_id"]:
            raise ValueError("Frozen query round differs from source capture")
        if seed["source_class"] != capture["source_class"]:
            raise ValueError("Frozen source class differs from query contract")
        result.append(
            {
                "work_item_id": route["work_item_id"],
                "priority_analysis": "A3_CAPABILITY" if affects_a3 else "A4_MULTILINGUAL",
                "capture_id": capture_id,
                "frame_id": frame_id,
                "round_id": capture["round_id"],
                "source_observation_ref": capture["source_observation_ref"],
                "source_packet_id": capture["source_packet_id"],
                "query_or_seed_id": seed_id,
                "query_family": seed["query_family"],
                "query_expression": seed["query_expression"],
                "language": seed["language"],
                "jurisdiction": seed["jurisdiction"],
                "source_class": seed["source_class"],
                "historical_capture_outcome": capture["outcome"],
                "historical_capture_label": capture["normalized_candidate_label"],
                "historical_raw_candidate_key": capture["raw_candidate_key"],
                "decision_reasons": route["selection_reasons"],
                "execution_status": "PENDING_FRESH_ATTRIBUTABLE_SOURCE_EXAMINATION",
                "independent_source_acquired": False,
                "verified_product_identity": None,
                "verified_eligibility_at_world_cutoff": None,
                "a3_increment_credited": False,
                "a4_increment_credited": False,
            }
        )
    result.sort(key=lambda r: (r["priority_analysis"], r["query_or_seed_id"], r["work_item_id"]))
    summary = Counter(row["priority_analysis"] for row in result)
    if dict(summary) != EXPECTED_COUNTS or len(result) != 69:
        raise ValueError(f"Frozen A3/A4 work-item population changed: {dict(summary)}")
    if len({row["work_item_id"] for row in result}) != 69:
        raise ValueError("Repeated priority work-item identity")
    if len({row["capture_id"] for row in result}) != 69:
        raise ValueError("Repeated priority capture identity")
    a3 = [row for row in result if row["priority_analysis"] == "A3_CAPABILITY"]
    family_counts = Counter(row["query_family"] for row in a3)
    if len(family_counts) != 6 or set(family_counts.values()) != {3}:
        raise ValueError("Six A3 capability families must each have three rounds")
    if any(row["historical_capture_outcome"] != "ABSTAIN" for row in a3):
        raise ValueError("Historical A3 query outcome changed")
    a4 = [row for row in result if row["priority_analysis"] == "A4_MULTILINGUAL"]
    a4_families = Counter(row["query_family"] for row in a4)
    if dict(a4_families) != EXPECTED_F8_FAMILIES:
        raise ValueError(f"Frozen A4 query families changed: {dict(a4_families)}")
    historical_failures = [row for row in result if row["historical_capture_outcome"] == "FAILED_INACCESSIBLE"]
    if len(historical_failures) != 5:
        raise ValueError("Historical source access failure count changed")
    return {
        "artifact_type": "RELEASE_A_R1_7_A3_A4_PRIORITY_SOURCE_WORKLIST_v0.1",
        "source_resource_sha256": input_hashes,
        "world_time_cutoff": "2026-09-24",
        "knowledge_time_cutoff": "2026-10-24T23:59:59Z",
        "work_item_count": len(result),
        "by_analysis": dict(summary),
        "a3_distinct_capability_families": sorted(family_counts),
        "a3_rounds_per_family": 3,
        "a4_query_family_counts": dict(a4_families),
        "historically_inaccessible_source_items": len(historical_failures),
        "fresh_acquisitions_completed": 0,
        "terminal_source_resolution_decisions_completed": 0,
        "new_canonical_products_established": 0,
        "boundary": (
            "Exact frozen search obligations and historical outcomes, NOT replayed searches, "
            "new source acquisitions, negative product evidence, or scientific completion."
        ),
        "work_items": result,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = build_priority_source_worklist()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"{report['work_item_count']} pending source obligations: "
        f"{report['by_analysis']}; no new sources or product counts credited"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
