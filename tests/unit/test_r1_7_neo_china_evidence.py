"""Frozen-query join and noncanonical source-state checks for NEO (China)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECORD = ROOT / "docs/programme/r1-7-neo-china-multilingual-regulatory-and-clinical-evidence-2026-10-22.json"
SNAPSHOT = ROOT / "docs/programme/r1-7-unlinked-source-capture-snapshot-2026-10-22.json"


def test_neo_candidate_joins_exact_original_f8_query_without_new_identity() -> None:
    packet = json.loads(RECORD.read_text(encoding="utf-8"))
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    frozen = packet["frozen_context"]
    assert packet["frozen_world_time_cutoff"] == snapshot["world_time_cutoff"] == "2026-09-24"
    assert packet["frozen_knowledge_time_cutoff"] == snapshot["knowledge_time_cutoff"]
    matched = [x for x in snapshot["records"] if x["capture_id"] == frozen["capture_id"]]
    assert len(matched) == 1
    ref = matched[0]
    assert ref["work_item_id"] == frozen["work_item_id"]
    assert ref["query_or_seed_id"] == frozen["query_id"] == "F8-R1-CAT-ZH-1"
    assert ref["query_expression"] == frozen["query_expression"] == "脑机接口 产品"
    assert ref["original_outcome"] == frozen["original_frozen_capture_outcome"] == "ABSTAIN"
    assert ref["source_observation_ref"] == frozen["original_source_observation_ref"]
    assert ref["execution_priority_class"] == "A4"
    assert ref["archive_receipt_in_two_archives"] is False
    assert ref["terminal_source_decision"] is False


def test_regulatory_and_clinical_claims_remain_separate_evidence_axes() -> None:
    packet = json.loads(RECORD.read_text(encoding="utf-8"))
    sources = packet["sources"]
    assert len(sources) == len({x["id"] for x in sources}) == 7
    assert all(x["url"].startswith("https://") and x["valid_axis"] and x["not_proof"] for x in sources)
    assert all(x["published_on"] <= "2026-09-24" for x in sources)
    assert next(x for x in sources if x["id"] == "NEO-NMPA-20260313")["source_class"] == ("PRIMARY_NATIONAL_REGULATOR")
    assert next(x for x in sources if x["id"] == "NEO-HUASHAN-20260715")["valid_axis"] == (
        "REPORTED_HISTORICAL_CLINICAL_DEPLOYMENT"
    )
    assert packet["candidate"]["registration_identifier_status"].startswith("IDENTIFIER_REPORTED_BY_DATED")
    assert packet["candidate"]["issuer_product_model_label"] == "NEO-ONE SCI"
    assert packet["adjudication"]["ai_model_capability"].startswith("PRE_CUTOFF_ISSUER_IPO_DISCLOSES")
    issuer = next(x for x in sources if x["id"] == "NEO-SSE-IPO-20260611")
    assert issuer["direct_pdf_read_status"] == "WEB_FETCH_TIMEOUT_SEARCH_INDEX_SNIPPET_ONLY"
    assert issuer["original_file_sha256"] is None
    assert issuer["page_specific_citation"] is None
    assert packet["adjudication"]["terminal_r1_7_review"] is False
    assert packet["adjudication"]["new_canonical_product_identifiers"] == 0
    assert packet["adjudication"]["new_a4_increment"] == 0


def test_web_extracted_text_does_not_masquerade_as_saved_raw_bytes() -> None:
    packet = json.loads(RECORD.read_text(encoding="utf-8"))
    acquisition = packet["source_acquisition"]
    assert acquisition["read_via"] == "PUBLIC_WEB_SEARCH_EXTRACTED_TEXT"
    assert acquisition["raw_http_response_bytes_retained"] is False
    assert acquisition["independently_recomputed_source_response_sha256"] is False
    assert packet["query_attribution_limit"]
