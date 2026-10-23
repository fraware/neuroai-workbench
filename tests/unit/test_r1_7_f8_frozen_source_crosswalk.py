"""Nonterminal exact F8 capture-to-work-item evidence accounting tests."""

from __future__ import annotations

import json
from pathlib import Path

RESOURCE = (
    Path(__file__).resolve().parents[2]
    / "docs/programme/r1-7-f8-five-frozen-source-work-items-2026-10-23.json"
)

FROZEN_QUERIES = {
    "F8-R2-CAP-ZH-2",
    "F8-R3-LOC-BITBRAIN-ES",
    "F8-R3-LOC-MOH-IL",
    "F8-R3-LOC-NEUROELECTRICS-ES",
    "F8-R3-LOC-NMPA-ZH",
}


def test_original_f8_capture_route_mapping_stays_frozen_and_nonterminal() -> None:
    packet = json.loads(RESOURCE.read_text(encoding="utf-8"))
    rows = packet["frozen_f8_work_item_mapping"]
    assert packet["frozen_world_time_cutoff"] == "2026-09-24"
    assert packet["frozen_knowledge_time_cutoff"] == "2026-10-24T23:59:59Z"
    assert packet["original_zip_sha256"] == (
        "9d32393e10ef1f7ab2991b72a04e2ba2e6d415837750d3b639dd48332fc08dd2"
    )
    assert len(rows) == packet["frozen_capture_count"] == packet["route_work_item_count"] == 5
    assert {r["frozen_query_or_seed_id"] for r in rows} == FROZEN_QUERIES
    assert len({r["capture_id"] for r in rows}) == 5
    assert len({r["work_item_id"] for r in rows}) == 5
    assert sum(r["saved_http_response_count"] for r in rows) == 8
    assert sum(r["failed_http_attempt_count"] for r in rows) == 2
    assert packet["original_attempt_count"] == 10
    assert packet["original_frozen_failed_inaccessible_outcomes_changed"] == 0
    assert packet["new_frozen_capture_records_created"] == 0
    assert packet["terminal_r1_7_route_completions_credited"] == 0
    assert packet["canonical_product_identifications_credited"] == 0
    assert packet["remaining_full_r1_7_work_items_pending"] == 192

    for row in rows:
        assert row["frame_id"] == "F8"
        assert row["execution_route"] == "SOURCE_SURFACE_RESOLUTION"
        assert row["original_frozen_capture_outcome"] == "FAILED_INACCESSIBLE"
        assert row["covered_capture_count"] == 1
        assert row["decision_sensitivity"]["could_change_a4_increment"] is True
        assert row["decision_sensitivity"]["could_change_a_p1_membership"] is True
        assert row["alternative_responses_promoted_to_terminal_r1_7_execution"] is False
        assert row["original_frozen_capture_state_unchanged"] is True
        assert row["reviewer_state"] == "NOT_HUMAN_REVIEWED"
        assert row["resolved_product_identity_count"] == 0
        assert row["alternative_attempt_count"] == (
            row["saved_http_response_count"] + row["failed_http_attempt_count"]
        )
        assert all(response["raw_sha256"] and response["raw_bytes"] > 0 for response in row["saved_responses"])


def test_f8_403_and_language_barriers_are_not_erased_by_http_200() -> None:
    rows = json.loads(RESOURCE.read_text(encoding="utf-8"))["frozen_f8_work_item_mapping"]
    by_query = {r["frozen_query_or_seed_id"]: r for r in rows}
    blocked = by_query["F8-R3-LOC-MOH-IL"]
    assert blocked["saved_http_response_count"] == 0
    assert blocked["failed_http_attempt_count"] == 2
    assert all("403" in f["failure_detail"] for f in blocked["failed_attempts"])
    alt = by_query["F8-R3-LOC-NEUROELECTRICS-ES"]
    assert alt["saved_http_response_count"] == 2
    assert alt["bounded_review_class"] == "ENGLISH_MANUFACTURER_FALLBACK_SPANISH_UNRESOLVED"
    assert all(not r["alternative_responses_promoted_to_terminal_r1_7_execution"] for r in rows)
