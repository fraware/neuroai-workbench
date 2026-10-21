"""Read-only account of all 192 Release-A R1.7 source and literature routes.

Uses the immutable R1.6.1 routing checkpoint and the independently checked
nonterminal archive-coverage inventory. This script neither retrieves new
sources nor writes to an execution ledger or Product Registry. Saved bytes,
reused publication text, and a completed substantive extraction are three
different states.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESOURCE = ROOT / "src/neuroai_workbench/resources/discovery"
ROUTING = "RELEASE_A_R1_EXECUTION_UNIT_ROUTING_REFINEMENT_CHECKPOINT.v1.0.json"
ARCHIVE = ROOT / "docs/programme/r1-7-saved-source-archive-coverage-2026-10-21.json"
GOVERNED = ("SOURCE_SURFACE_RESOLUTION", "LITERATURE_RECORD_EXTRACTION")
EXPECTED_ITEMS = {"SOURCE_SURFACE_RESOLUTION": 171, "LITERATURE_RECORD_EXTRACTION": 21}
EXPECTED_CAPTURES = {"SOURCE_SURFACE_RESOLUTION": 226, "LITERATURE_RECORD_EXTRACTION": 21}


def _load(path: Path) -> tuple[dict[str, Any], str]:
    data = path.read_bytes()
    parsed = json.loads(data)
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected JSON object: {path.name}")
    return parsed, hashlib.sha256(data).hexdigest()


def build_report(
    resource_dir: Path = RESOURCE,
    archive_path: Path = ARCHIVE,
) -> dict[str, Any]:
    """Create an exhaustive route inventory with no inferred terminal outcomes."""
    routing, route_sha256 = _load(resource_dir / ROUTING)
    archive, evidence_sha256 = _load(archive_path)
    if routing.get("work_item_count") != 270 or routing.get("capture_count") != 389:
        raise ValueError("Frozen R1.6.1 population drift")
    if routing.get("work_item_counts_by_route") != {
        **EXPECTED_ITEMS,
        "EMPIRICAL_CANDIDATE_ADJUDICATION": 76,
        "A_P1_TEMPORAL_STATE_REVIEW": 2,
        "MIXED_OR_UNRESOLVED_UNIT_REVIEW": 0,
    }:
        raise ValueError("Unexpected R1.6.1 route classification")
    for route, n in EXPECTED_CAPTURES.items():
        if routing.get("capture_counts_by_route", {}).get(route) != n:
            raise ValueError(f"Frozen {route} capture denominator drift")
    for field in ("analysis_universe_id", "world_time_cutoff", "knowledge_time_cutoff"):
        if routing[field] != archive[field]:
            raise ValueError(f"Archive/{field} freeze mismatch")
    inventory: dict[str, dict[str, Any]] = {}
    for receipt in archive["known_archive_contexts"]:
        capture_id = receipt["capture_id"]
        if capture_id in inventory:
            raise ValueError("Duplicate archived evidence-context capture identity")
        if receipt.get("terminal_work_item_completion") is not False:
            raise ValueError("Archive may not assert completed scientific execution")
        if receipt.get("canonical_identity_allocated") is not False:
            raise ValueError("Archive may not assert canonical product allocation")
        inventory[capture_id] = receipt

    all_capture_ids: set[str] = set()
    rows: list[dict[str, Any]] = []
    observed_archive_ids: set[str] = set()
    route_counts: Counter[str] = Counter()
    capture_counts: Counter[str] = Counter()
    states: Counter[str] = Counter()
    for route in routing["route_table"]:
        kind = route["execution_route"]
        if kind not in GOVERNED:
            continue
        wid = route["work_item_id"]
        if not route["capture_ids"]:
            raise ValueError("Missing frozen capture for governed work item")
        kinds: set[str] = set()
        receipt_count = 0
        provenance = []
        for capture in route["capture_ids"]:
            if capture in all_capture_ids:
                raise ValueError("A frozen capture occurs in multiple route items")
            all_capture_ids.add(capture)
            context = inventory.get(capture)
            if context is not None:
                observed_archive_ids.add(capture)
                if context["work_item_id"] != wid or context["execution_route"] != kind:
                    raise ValueError("Archive receipt does not match frozen capture route")
                if kind == "LITERATURE_RECORD_EXTRACTION":
                    relation = context.get("source_relation_to_archive")
                    if relation == "ARCHIVE_SAVED_FOR_THIS_EXACT_CAPTURE":
                        state = "DIRECT_SAVED_ARTICLE_XML_UNADJUDICATED"
                    elif relation == "SAME_PUBLICATION_XML_AVAILABLE_REFERENCED_FROM_SEPARATE_CAPTURE":
                        state = "REUSED_SAVED_ARTICLE_XML_NOT_DIRECT_ROUTE_ACQUISITION"
                    else:
                        raise ValueError("Unknown literature archive relationship")
                else:
                    if context["observed_state"] == "ALTERNATIVE_RESPONSES_SAVED_PENDING_CONTENT_REVIEW":
                        state = "ALTERNATIVE_SOURCE_BYTES_SAVED_UNADJUDICATED"
                    elif context["observed_state"] == "TWO_ALTERNATIVE_HTTP_403_FAILURES":
                        state = "ALTERNATIVE_ACCESS_BARRIER_UNRESOLVED"
                    else:
                        raise ValueError("Unknown source archive observation state")
                receipt_count += 1
            else:
                state = "NO_LINKED_ARCHIVE_EVIDENCE_IN_THIS_BOUNDED_INVENTORY"
            kinds.add(state)
            provenance.append({"capture_id": capture, "archive_state": state})
            states[state] += 1
            capture_counts[kind] += 1
        route_counts[kind] += 1
        rows.append(
            {
                "work_item_id": wid,
                "execution_route": kind,
                "frozen_capture_count": len(route["capture_ids"]),
                "linked_archive_context_count": receipt_count,
                "archive_states": sorted(kinds),
                "captures": provenance,
                "terminal_completion_verified": False,
                "canonical_product_count_increment": 0,
            }
        )
    if dict(route_counts) != EXPECTED_ITEMS or dict(capture_counts) != EXPECTED_CAPTURES:
        raise ValueError("Governed R1.7 work-item or capture denominator changed")
    if len(rows) != 192 or len(all_capture_ids) != 247:
        raise ValueError("Governed Release-A source/record population drift")
    if observed_archive_ids != set(inventory):
        raise ValueError("Orphan archive receipt outside the 192 governed routes")
    if len(inventory) != 26:
        raise ValueError("Bounded archive context population changed")
    if (
        states["DIRECT_SAVED_ARTICLE_XML_UNADJUDICATED"] != 4
        or states["REUSED_SAVED_ARTICLE_XML_NOT_DIRECT_ROUTE_ACQUISITION"] != 17
        or states["ALTERNATIVE_SOURCE_BYTES_SAVED_UNADJUDICATED"] != 4
        or states["ALTERNATIVE_ACCESS_BARRIER_UNRESOLVED"] != 1
    ):
        raise ValueError("Saved evidence or access-barrier distribution drift")
    rows.sort(key=lambda r: (r["execution_route"], r["work_item_id"]))
    return {
        "report_type": "RELEASE_A_R1_7_ALL_SOURCE_RECORD_ROUTE_ARCHIVE_COVERAGE_v0.1",
        "status": "NONTERMINAL_INVENTORY_ONLY",
        "frozen_input_sha256": {
            ROUTING: route_sha256,
            archive_path.name: evidence_sha256,
        },
        "analysis_universe_id": routing["analysis_universe_id"],
        "world_time_cutoff": routing["world_time_cutoff"],
        "knowledge_time_cutoff": routing["knowledge_time_cutoff"],
        "governed_work_item_count": len(rows),
        "governed_capture_count": len(all_capture_ids),
        "work_item_counts_by_route": dict(sorted(route_counts.items())),
        "capture_counts_by_route": dict(sorted(capture_counts.items())),
        "archive_context_count": len(inventory),
        "archive_state_counts_by_capture": dict(sorted(states.items())),
        "work_items_with_terminal_completion_verified": 0,
        "canonical_product_increments": 0,
        "work_items": rows,
        "scientific_boundary": (
            "Only a read-only crosswalk of frozen routes and two named saved-source "
            "archives. Absent archive receipts are not evidence of absent sources or "
            "products. Reused article XML is not an independent historical capture "
            "or a route-level terminal extraction. No release or population claim."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("192 nonterminal source/record work items; 247 captures; 26 archive contexts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
