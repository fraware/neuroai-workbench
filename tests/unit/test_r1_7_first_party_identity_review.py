"""Fail-closed tests for the noncanonical R1.7 first-party identity review packet."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

PACKET = (
    Path(__file__).resolve().parents[2]
    / "docs/programme/r1-7-literature-manufacturer-corroboration-2026-10-23.json"
)
CUTOFF = datetime.fromisoformat("2026-10-24T23:59:59+00:00")
SOURCE_DIGEST = "9b6552f265236c2c65dedde840d5cf0de0472ba607aed68d93dd61ee248d6c5f"
EXPECTED_ROWS = {
    ("BrainBit Hero/Diamond", 1, 9): "1dd400a0a26d2b5003432b2bd52fbecd1d9bacdf39a66f406522936e87ade2d2",
    ("Muse S ATHENA", 2, 1): "01f16d1a4aba8603ecace3cdf431b876b1d6dba061702dbc94ec959edcdfc10f",
    ("Neuro-electrics Startsim", 3, 10): "86fb714714006fd70b756376cb7095e292e16a4f224e39cc6cecf5928b02b285",
    ("Neurable", 5, 5): "51490afd478d54ce5c19273551746e1a25ba043fc7b312a21af3ac2034232843",
}


def _packet() -> dict:
    return json.loads(PACKET.read_text(encoding="utf-8"))


def test_identity_review_freeze_and_row_provenance() -> None:
    packet = _packet()
    assert packet["world_time_cutoff"] == "2026-09-24"
    assert packet["knowledge_time_cutoff"] == "2026-10-24T23:59:59Z"
    assert packet["frozen_review_xml_sha256"] == SOURCE_DIGEST
    cases = packet["identity_cases"]
    assert len(cases) == 4
    assert {
        (c["table_original"], c["table_number"], c["table_row_1based"]): c["source_row_sha256"]
        for c in cases
    } == EXPECTED_ROWS
    assert all(c["frozen_article_xml_sha256"] == SOURCE_DIGEST for c in cases)
    assert datetime.fromisoformat(packet["generated_utc"].replace("Z", "+00:00")) <= CUTOFF


def test_unarchived_web_observations_never_promote_to_ledger_or_truth() -> None:
    packet = _packet()
    sources = packet["first_party_evidence"]
    assert len(sources) == 9
    assert len({s["evidence_id"] for s in sources}) == 9
    assert packet["source_web_observation_method"] == "PUBLIC_WEB_EXTRACTED_TEXT_ONLY_NO_ORIGINAL_HTTP_ARCHIVE"
    for source in sources:
        assert urlsplit(source["source_url"]).scheme == "https"
        assert source["source_kind"] == "PUBLIC_FIRST_PARTY_WEB_EXTRACTED_TEXT"
        assert source["raw_http_bytes_retained"] is False
        assert source["replayable_archived_evidence"] is False
        assert source["request_headers_retained"] is False
        assert source["response_headers_retained"] is False
        assert source["does_not_establish"]
    assert packet["no_new_product_count_credit"] == 0
    assert packet["no_r1_7_completed_work_item_credit"] == 0
    assert packet["remaining_r1_7_work_items_pending"] == 192
    assert packet["no_automated_canonical_or_ledger_mutation"] is True
    for case in packet["identity_cases"]:
        assert set(case["first_party_evidence_ids"]).issubset({s["evidence_id"] for s in sources})
        assert case["new_canonical_product_id"] is None
        assert case["new_product_count_credited"] == 0
        assert case["r1_7_governed_route_completion"] == "NOT_ESTABLISHED"
        assert case["human_review_state"] == "NOT_PERFORMED"
        assert case["eligible_at_world_cutoff"] == "UNDETERMINED"
        assert case["raw_first_party_html_captured"] is False


def test_neurable_post_world_cutoff_control_is_excluded() -> None:
    packet = _packet()
    control = packet["post_world_cutoff_negative_control"]
    assert control["entity_label"] == "Neurable One"
    assert control["announced_on"] == "2026-10-01"
    assert control["announced_on"] > packet["world_time_cutoff"]
    assert control["admissible_as_new_release_a_world_time_2026_09_24_product"] is False
    sources = {s["evidence_id"]: s for s in packet["first_party_evidence"]}
    assert sources["NEUR-LT-ANN-2025"]["claimed_publication_date"] == "2025-09-30"
    assert sources["NEUR-LT-DELAY-2026"]["claimed_publication_date"] == "2026-02-04"
    assert sources["NEUR-ONE-POST"]["claimed_publication_date"] == "2026-10-01"
    assert all(c["new_canonical_product_id"] is None for c in packet["identity_cases"])
