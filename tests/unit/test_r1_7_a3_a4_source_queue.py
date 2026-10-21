"""Frozen A3/A4 source queue invariants and honest completion boundary."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from scripts.r1_7_a3_a4_source_queue import F6, F8, RESOURCE_DIR, ROUTING, UNIVERSES, build_queue


def test_full_queue_exact_population_and_capture_provenance() -> None:
    report = build_queue()
    assert report["source_surface_total_work_items"] == 171
    assert report["priority_counts"] == {"A3_CAPABILITY": 18, "A4_MULTILINGUAL": 51}
    assert report["pending_work_items"] == 69
    assert report["completed_work_items"] == 0
    assert len(report["items"]) == 69
    assert len({item["work_item_id"] for item in report["items"]}) == 69
    for item in report["items"]:
        assert item["capture_count"] == len(item["captures"]) > 0
        assert item["evidence_artifact_refs"] == []
        assert item["terminal_r1_7_decision"] is None
        assert all(
            source["source_outcome_at_frozen_capture"] in {"ABSTAIN", "FAILED_INACCESSIBLE"}
            for source in item["captures"]
        )
        if item["priority_analysis"] == "A3_CAPABILITY":
            assert all(source["frame_id"] == "F6" for source in item["captures"])
        else:
            assert all(source["frame_id"] == "F8" for source in item["captures"])


def test_queue_is_stable_and_does_not_claim_results() -> None:
    assert build_queue() == build_queue()
    report = build_queue()
    counts = Counter(item["priority_analysis"] for item in report["items"])
    assert counts == {"A3_CAPABILITY": 18, "A4_MULTILINGUAL": 51}
    assert report["completed_work_items"] == 0
    outcomes = Counter(c["source_outcome_at_frozen_capture"] for item in report["items"] for c in item["captures"])
    assert outcomes == {"ABSTAIN": 64, "FAILED_INACCESSIBLE": 5}
    assert all(not item["product_identities_established"] for item in report["items"])


def test_worklist_rejects_modified_frozen_route_population(tmp_path: Path) -> None:
    for filename in [ROUTING, F6, F8]:
        (tmp_path / filename).write_bytes((RESOURCE_DIR / filename).read_bytes())
    path = tmp_path / ROUTING
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["work_item_count"] = 269
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="270-item"):
        build_queue(tmp_path)


def test_five_inaccessible_recovery_locators_keep_exact_frozen_identity() -> None:
    # Resolve the external source triage from the repository checkout.
    source = Path(__file__).resolve().parents[2] / "docs/programme/r1-7-five-inaccessible-f8-recovery-candidates.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    assert data["item_count"] == 5
    assert data["evidence_records_accepted"] == 0
    assert data["terminal_extractions_claimed"] == 0
    assert len(data["items"]) == 5
    by_capture = {capture["capture_id"]: capture for work in build_queue()["items"] for capture in work["captures"]}
    assert len({row["capture_id"] for row in data["items"]}) == 5
    for row in data["items"]:
        old = by_capture[row["capture_id"]]
        assert old["source_outcome_at_frozen_capture"] == "FAILED_INACCESSIBLE"
        assert old["query_or_seed_id"] == row["query_or_seed_id"]
        assert old["language"] == row["language"]
        assert old["jurisdiction"] == row["jurisdiction"]
        assert row["source_retrieval_status"] == "ALTERNATIVE_LOCATOR_DISCOVERED;RAW_HTTP_BYTES_NOT_ARCHIVED"
        assert row["source_decision"] == "PENDING_INDEPENDENT_PRIMARY_SOURCE_ACQUISITION"
        assert row["new_product_identity_established"] is False
        assert len(row["locators"]) == 2
        assert all(link["url"].startswith("https://") for link in row["locators"])
        assert all(link["document_date"] is None or link["document_date"] <= "2026-10-24" for link in row["locators"])


def test_exact_query_seed_provenance_and_input_digests() -> None:
    """Every priority capture must retain its original full query and frozen bytes."""
    import hashlib

    report = build_queue()
    sources = report["frozen_input_sha256"]
    expected = [ROUTING, F6, F8, *UNIVERSES.values()]
    assert set(sources) == set(expected)
    for filename in expected:
        assert sources[filename] == hashlib.sha256((RESOURCE_DIR / filename).read_bytes()).hexdigest()
    assert report["a4_query_family_counts"] == {
        "LOCAL_PRODUCT_SOURCE": 9,
        "NATIVE_LANGUAGE_CAPABILITY": 21,
        "NATIVE_LANGUAGE_CATEGORY": 21,
    }
    assert len(report["a3_capability_family_counts"]) == 6
    assert set(report["a3_capability_family_counts"].values()) == {3}

    seed_by_id = {}
    for filename in UNIVERSES.values():
        universe = json.loads((RESOURCE_DIR / filename).read_text(encoding="utf-8"))
        for seed in universe["query_seeds"]:
            assert seed["query_or_seed_id"] not in seed_by_id
            seed_by_id[seed["query_or_seed_id"]] = seed

    captures = [cap for row in report["items"] for cap in row["captures"]]
    assert len(captures) == len({cap["capture_id"] for cap in captures}) == 69
    assert len({cap["query_or_seed_id"] for cap in captures}) == 69
    for capture in captures:
        seed = seed_by_id[capture["query_or_seed_id"]]
        assert capture["query_expression"] == seed["query_expression"]
        assert capture["query_expression"].strip()
        for field in ("round_id", "query_family", "source_class", "language", "jurisdiction"):
            assert capture[field] == seed[field]


def test_queue_rejects_query_contract_mismatch(tmp_path: Path) -> None:
    """A mislabeled seed must fail closed instead of rewriting historic provenance."""
    for filename in [ROUTING, F6, F8, *UNIVERSES.values()]:
        (tmp_path / filename).write_bytes((RESOURCE_DIR / filename).read_bytes())
    f6path = tmp_path / UNIVERSES["F6"]
    universe = json.loads(f6path.read_text(encoding="utf-8"))
    selected = next(
        cap["query_or_seed_id"]
        for item in build_queue()["items"]
        if item["priority_analysis"] == "A3_CAPABILITY"
        for cap in item["captures"]
    )
    next(seed for seed in universe["query_seeds"] if seed["query_or_seed_id"] == selected)["language"] = (
        "tampered-language"
    )
    f6path.write_text(json.dumps(universe), encoding="utf-8")
    with pytest.raises(ValueError, match="Frozen source/query language contract mismatch"):
        build_queue(tmp_path)


def test_queue_rejects_blank_original_query(tmp_path: Path) -> None:
    """Query text is essential to reproducible source execution."""
    for filename in [ROUTING, F6, F8, *UNIVERSES.values()]:
        (tmp_path / filename).write_bytes((RESOURCE_DIR / filename).read_bytes())
    f8path = tmp_path / UNIVERSES["F8"]
    universe = json.loads(f8path.read_text(encoding="utf-8"))
    selected = next(
        cap["query_or_seed_id"]
        for item in build_queue()["items"]
        if item["priority_analysis"] == "A4_MULTILINGUAL"
        for cap in item["captures"]
    )
    next(seed for seed in universe["query_seeds"] if seed["query_or_seed_id"] == selected)["query_expression"] = "   "
    f8path.write_text(json.dumps(universe), encoding="utf-8")
    with pytest.raises(ValueError, match="Frozen source/query expression missing"):
        build_queue(tmp_path)


def test_saved_source_archive_inventory_joins_frozen_routes_without_completion() -> None:
    """Archive receipts are evidence context, never completed R1.7 decisions."""
    inventory_path = (
        Path(__file__).resolve().parents[2]
        / "docs/programme/r1-7-saved-source-archive-coverage-2026-10-21.json"
    )
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    routing = json.loads((RESOURCE_DIR / ROUTING).read_text(encoding="utf-8"))
    assert inventory["analysis_universe_id"] == routing["analysis_universe_id"]
    assert inventory["world_time_cutoff"] == routing["world_time_cutoff"]
    assert inventory["knowledge_time_cutoff"] == routing["knowledge_time_cutoff"]
    assert inventory["frozen_route_population"] == {
        "total_work_items": 270,
        "total_captures": 389,
        "source_record_items": 192,
        "source_record_captures": 247,
    }
    assert inventory["matched_frozen_context_count"] == 9
    assert inventory["contexts_with_any_saved_new_raw_bytes"] == 8
    assert inventory["contexts_with_access_failures_only"] == 1
    assert inventory["terminal_r1_7_completion_records_verified"] == 0
    assert inventory["confirmed_new_eligible_offerings"] == 0
    artifacts = {item["artifact_id"] for item in inventory["archive_inputs"]}
    assert artifacts == {12320317652, 12325963314}
    index = {
        capture: route
        for route in routing["route_table"]
        for capture in route["capture_ids"]
    }
    assert len(index) == 389
    rows = inventory["known_archive_contexts"]
    assert len(rows) == len({row["capture_id"] for row in rows}) == 9
    routes = Counter()
    for row in rows:
        route = index[row["capture_id"]]
        assert route["work_item_id"] == row["work_item_id"]
        assert route["execution_route"] == row["execution_route"]
        assert len(route["capture_ids"]) == 1
        assert row["terminal_work_item_completion"] is False
        assert row["canonical_identity_allocated"] is False
        assert row["artifact_id"] in artifacts
        routes[row["execution_route"]] += 1
        if row["execution_route"] == "SOURCE_SURFACE_RESOLUTION":
            assert row["historical_original_capture_outcome"] == "FAILED_INACCESSIBLE"
    assert routes == {"LITERATURE_RECORD_EXTRACTION": 4, "SOURCE_SURFACE_RESOLUTION": 5}
