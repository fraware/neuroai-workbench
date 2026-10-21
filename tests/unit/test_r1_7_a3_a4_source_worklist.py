"""Frozen A3/A4 workload accounting without fabricated source acquisitions."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.r1_7_a3_a4_source_worklist import (
    EXPECTED_COUNTS,
    EXPECTED_F8_FAMILIES,
    build_priority_source_worklist,
    main,
)


def test_priority_source_population_matches_frozen_query_contract() -> None:
    report = build_priority_source_worklist()
    assert report["work_item_count"] == 69
    assert report["by_analysis"] == EXPECTED_COUNTS
    assert report["a4_query_family_counts"] == EXPECTED_F8_FAMILIES
    assert len(report["a3_distinct_capability_families"]) == 6
    assert report["a3_rounds_per_family"] == 3
    assert report["historically_inaccessible_source_items"] == 5
    assert len(report["source_resource_sha256"]) == 5
    assert all(len(value) == 64 for value in report["source_resource_sha256"].values())


def test_frozen_identity_and_source_query_provenance_are_preserved() -> None:
    rows = build_priority_source_worklist()["work_items"]
    assert len(rows) == 69
    assert len({row["capture_id"] for row in rows}) == 69
    assert len({row["work_item_id"] for row in rows}) == 69
    assert len({row["query_or_seed_id"] for row in rows}) == 69
    assert all(row["query_expression"].strip() for row in rows)
    assert all(row["source_observation_ref"].startswith("OBS-") for row in rows)
    assert all(row["source_packet_id"] for row in rows)
    assert all(row["language"] and row["jurisdiction"] for row in rows)
    assert all(row["execution_status"] == "PENDING_FRESH_ATTRIBUTABLE_SOURCE_EXAMINATION" for row in rows)
    assert all(row["independent_source_acquired"] is False for row in rows)
    assert all(row["verified_product_identity"] is None for row in rows)
    assert all(row["verified_eligibility_at_world_cutoff"] is None for row in rows)
    assert all(row["a3_increment_credited"] is False and row["a4_increment_credited"] is False for row in rows)


def test_a3_exact_six_families_each_have_three_distinct_rounds() -> None:
    rows = build_priority_source_worklist()["work_items"]
    a3 = [row for row in rows if row["priority_analysis"] == "A3_CAPABILITY"]
    for family in {row["query_family"] for row in a3}:
        members = [row for row in a3 if row["query_family"] == family]
        assert {row["round_id"] for row in members} == {"R1", "R2", "R3"}
        assert all(row["frame_id"] == "F6" for row in members)


def test_a4_exact_multilingual_and_historical_failure_counts() -> None:
    rows = build_priority_source_worklist()["work_items"]
    a4 = [row for row in rows if row["priority_analysis"] == "A4_MULTILINGUAL"]
    assert len(a4) == 51
    assert all(row["frame_id"] == "F8" for row in a4)
    failures = [row for row in a4 if row["historical_capture_outcome"] == "FAILED_INACCESSIBLE"]
    assert len(failures) == 5
    assert all(row["execution_status"].startswith("PENDING_") for row in failures)


def test_cli_generates_replayable_identical_pending_worklist(tmp_path: Path) -> None:
    path = tmp_path / "worklist.json"
    assert main(["--output", str(path)]) == 0
    first = path.read_bytes()
    assert main(["--output", str(path)]) == 0
    assert first == path.read_bytes()
    result = json.loads(first)
    assert result["fresh_acquisitions_completed"] == 0
    assert result["terminal_source_resolution_decisions_completed"] == 0
    assert result["new_canonical_products_established"] == 0


def test_corrupted_source_population_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.r1_7_a3_a4_source_worklist as worklist

    original = worklist._load

    def tampered(filename: str, resource_root: Path) -> tuple[dict[str, object], str]:
        document, digest = original(filename, resource_root)
        altered = deepcopy(document)
        if filename == worklist.ROUTES:
            altered["route_table"] = []
        return altered, digest

    monkeypatch.setattr(worklist, "_load", tampered)
    with pytest.raises(ValueError, match="population changed"):
        build_priority_source_worklist()
