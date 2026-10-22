"""Quantitative consistency checks for real two-run Chinese HTTP source receipts."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.r1_7_neo_public_http_receipts import PUBLIC_SOURCES


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs/programme/r1-7-neo-two-run-http-digest-reconciliation-2026-10-22.json"
PROPOSAL = ROOT / "docs/programme/r1-7-neo-china-multilingual-regulatory-and-clinical-evidence-2026-10-22.json"


def test_exact_five_source_ids_counts_and_original_historical_context() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    proposal = json.loads(PROPOSAL.read_text(encoding="utf-8"))
    frozen = report["frozen_context"]
    assert frozen["query_id"] == proposal["frozen_context"]["query_id"]
    assert frozen["capture_id"] == proposal["frozen_context"]["capture_id"]
    assert frozen["original_outcome"] == "ABSTAIN"
    assert frozen["knowledge_time_cutoff"] == "2026-10-24T23:59:59Z"
    sources = report["sources"]
    assert len(sources) == len({r["id"] for r in sources}) == 5
    assert {s["id"] for s in sources} == {s["source_id"] for s in PUBLIC_SOURCES}
    successes = [s for s in sources if s["successful_digest"] is not None]
    assert len(successes) == report["distinct_successful_urls"] == 4
    assert sum(s["bytes"] for s in successes) == report["distinct_successful_response_bytes_total"] == 64109
    assert all(len(s["successful_digest"]) == 64 for s in successes)
    assert report["source_credit"] == {
        "original_frozen_A2_ABSTAIN_preserved": True,
        "source_claims_temporally_accepted": False,
        "terminal_R1_7_work_items": 0,
        "canonical_product_increments": 0,
        "new_human_adjudications": 0,
        "global_saturation_creditted": False,
    }


def test_access_barrier_and_followup_failure_cannot_be_interpreted_as_source_absence() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in report["sources"]}
    nmpa = by_id["NEO-NMPA-20260313"]
    assert [r["status"] for r in nmpa["attempts"]] == [412, 412]
    assert nmpa["successful_digest"] is None
    assert nmpa["acquisition_state"] == "ACCESS_RESTRICTED_HTTP_412_NO_NEGATIVE_INFERENCE"
    nhsa = by_id["NEO-NHSA-20260322"]
    assert [r["status"] for r in nhsa["attempts"]] == [200, None]
    assert nhsa["successful_digest"]
    shanghai = by_id["NEO-SHANGHAI-20260313"]
    assert [r["status"] for r in shanghai["attempts"]] == [200, 200]
    assert shanghai["acquisition_state"] == "INDEPENDENT_TWO_RUN_SHA256_MATCH"
    aug = by_id["NEO-SHANGHAI-CLINICAL-AUG2026"]
    assert aug["article_displayed_publication_date"] == "2026-08-07"
    assert "2026" in aug["last_modified_header"]
