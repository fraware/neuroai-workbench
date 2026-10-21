"""Frozen A3/A4 source queue invariants and honest completion boundary."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from scripts.r1_7_a3_a4_source_queue import F6, F8, RESOURCE_DIR, ROUTING, build_queue


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
