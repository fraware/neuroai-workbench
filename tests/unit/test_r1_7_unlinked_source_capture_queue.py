"""Read-only validation of all 221 non-archived source-capture task bindings."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import r1_7_unlinked_source_capture_queue as queue
from scripts.r1_7_all_routes_archive_coverage import build_report


def test_all_original_unlinked_source_captures_are_attributable() -> None:
    report = queue.build_unlinked_source_queue()
    assert report["status"] == "PENDING_ATTRIBUTABLE_SOURCE_EXECUTION_NOT_SOURCE_ABSENCE"
    assert report["covered_source_record_work_items"] == 192
    assert report["covered_frozen_capture_population"] == 247
    assert report["unlinked_capture_count"] == 221
    assert sum(report["frame_counts"].values()) == 221
    assert sum(report["historical_outcome_counts"].values()) == 221
    assert report["execution_priority_class_counts"] == {
        "A3_FROZEN_CAPABILITY_SENSITIVITY": 18,
        "A4_FROZEN_MULTILINGUAL_SENSITIVITY": 46,
        "OTHER_FROZEN_SOURCE_ROUTE": 157,
    }
    assert report["terminal_source_completions"] == 0
    assert report["new_canonical_entities"] == 0
    rows = report["records"]
    assert len(rows) == len({r["capture_id"] for r in rows}) == 221
    assert all(row["execution_priority_class"] == "A3_FROZEN_CAPABILITY_SENSITIVITY" for row in rows[:18])
    assert all(row["execution_priority_class"] == "A4_FROZEN_MULTILINGUAL_SENSITIVITY" for row in rows[18:64])
    assert all(row["execution_priority_class"] == "OTHER_FROZEN_SOURCE_ROUTE" for row in rows[64:])
    assert all(row["execution_route"] == "SOURCE_SURFACE_RESOLUTION" for row in rows)
    assert all(row["matched_saved_evidence_receipt_in_two_archives"] is False for row in rows)
    assert all(row["attributable_new_source_retrieval_performed_by_queue"] is False for row in rows)
    assert all(row["canonical_offering_identity"] is None for row in rows)
    assert all(row["source_packet_id"] and row["source_observation_ref"] for row in rows)
    assert all(row["registered_query_expression"] for row in rows[:64])
    assert all(row["registered_query_expression"] is None for row in rows[64:])
    assert all(row["query_family"] and row["source_class"] for row in rows)
    assert all(row["language"] and row["jurisdiction"] for row in rows)
    assert all(type(row["could_change_a3_increment"]) is bool for row in rows)
    assert all(type(row["could_change_a4_increment"]) is bool for row in rows)
    assert all(type(row["source_or_abstention_barrier"]) is bool for row in rows)
    frozen = {
        item["work_item_id"]: item
        for item in build_report()["work_items"]
        if item["execution_route"] == "SOURCE_SURFACE_RESOLUTION"
    }
    assert all(
        row["capture_id"] in [capture["capture_id"] for capture in frozen[row["work_item_id"]]["captures"]]
        for row in rows
    )


def test_queue_cli_is_deterministic_without_network(tmp_path: Path) -> None:
    target = tmp_path / "queue.json"
    assert queue.main(["--output", str(target)]) == 0
    raw = target.read_bytes()
    assert len(json.loads(raw)["records"]) == 221
    assert queue.main(["--output", str(target)]) == 0
    assert target.read_bytes() == raw


def test_missing_immutable_source_capture_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    records = queue.compile_r1_source_records(queue.load_r1_candidate_resolution_manifest())
    original = queue.compile_r1_source_records
    queue_report = build_report()
    missing_id = next(
        cap["capture_id"]
        for work in queue_report["work_items"]
        for cap in work["captures"]
        if cap["archive_state"] == queue.UNLINKED
    )
    monkeypatch.setattr(
        queue,
        "compile_r1_source_records",
        lambda _manifest: [row for row in records if row["capture_id"] != missing_id],
    )
    with pytest.raises(ValueError, match="No immutable first-party A2 capture"):
        queue.build_unlinked_source_queue()
    monkeypatch.setattr(queue, "compile_r1_source_records", original)
