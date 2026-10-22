"""Offline checks for bounded temporal-source acquisition."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pytest

from scripts.r1_7_capture_temporal_sources import SOURCE_TARGETS, SameOriginRedirect, capture_target, main


def test_allowlisted_sources_are_distinct_https_urls() -> None:
    assert len(SOURCE_TARGETS) == 6
    assert len({row[0] for row in SOURCE_TARGETS}) == 6
    assert all(row[1].startswith("https://") and row[2] for row in SOURCE_TARGETS)


def test_refuses_network_without_explicit_opt_in(tmp_path: Path) -> None:
    output = tmp_path / "not-created"
    assert not output.exists()
    with pytest.raises(SystemExit, match="2"):
        main(["--output-dir", str(output)])
    assert not output.exists()


def test_unapproved_target_is_rejected_before_network(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unknown source"):
        capture_target("arbitrary", "https://example.com", "fake", tmp_path)
    slug, url, marker = SOURCE_TARGETS[0]
    with pytest.raises(ValueError, match="allowlist"):
        capture_target(slug, url + "&redirect=1", marker, tmp_path)


def test_cross_domain_redirect_is_refused() -> None:
    request = urllib.request.Request(SOURCE_TARGETS[0][1])
    with pytest.raises(ValueError, match="redirect refused"):
        SameOriginRedirect().redirect_request(request, None, 301, "Moved", {}, "https://unrelated.example.org/unsafe")


def test_neu_discontinuation_assertion_is_model_specific_and_noncanonical() -> None:
    root = Path(__file__).resolve().parents[2]
    source = root / "docs/programme/r1-7-neu-exact-model-discontinuation-source-2026-10-21.json"
    record = json.loads(source.read_text(encoding="utf-8"))
    assert record["status"] == "NONTERMINAL_SAVED_PRIMARY_SOURCE_EXTRACTION_UNADJUDICATED"
    assert record["source_document_date"] == "2025-06-04"
    assert record["archived_source"]["raw_sha256"] == "f02c9da3d76d8ca3951365c2af879d369d1b3821a3f26e7dcccf6130e4b506cb"
    assert record["stated_repairs_and_maintenance_end"] == "2026-06-30"
    models = {entry["literal_model_identifier"] for entry in record["named_models"]}
    assert models == {"HOT-2000-BIOSIGNALS", "NX Ver.1.0", "SP-POST01", "WOT-VC1"}
    assert "HOT-2000" not in models
    assert record["sales_cessation_effective_date"] is None
    assert all(value == 0 for value in record["no_scientific_credit"].values())
    routing_path = (
        root
        / "src/neuroai_workbench/resources/discovery"
        / "RELEASE_A_R1_EXECUTION_UNIT_ROUTING_REFINEMENT_CHECKPOINT.v1.0.json"
    )
    routing = json.loads(routing_path.read_text(encoding="utf-8"))
    capture = record["frozen_research_context"]
    match = [row for row in routing["route_table"] if capture["capture_id"] in row["capture_ids"]]
    assert len(match) == 1
    assert match[0]["work_item_id"] == capture["work_item_id"]
    assert match[0]["execution_route"] == "EMPIRICAL_CANDIDATE_ADJUDICATION"


def test_two_temporal_review_packets_separate_dated_claims_from_release_decisions() -> None:
    """Dated manufacturer/media claims must not become terminal A-P1 classifications."""
    root = Path(__file__).resolve().parents[2]
    file = root / "docs/programme/r1-7-flow-modius-temporal-corroboration-2026-10-22.json"
    report = json.loads(file.read_text(encoding="utf-8"))
    assert report["status"] == "NONCANONICAL_SOURCE_CLAIMS_PENDING_INDEPENDENT_TEMPORAL_REVIEW"
    assert report["analysis_dates"]["world_time_cutoff"] == "2026-09-24"
    assert report["analysis_dates"]["knowledge_time_cutoff"] == "2026-10-24T23:59:59Z"
    assert all(value == 0 for value in report["no_credit"].values())
    assert len(report["cases"]) == 2
    by_key = {item["product_key"]: item for item in report["cases"]}
    assert set(by_key) == {"FLOW_FL_100", "MODIUS_SPERO"}
    assert len(by_key["FLOW_FL_100"]["source_observations"]) == 4
    assert len(by_key["MODIUS_SPERO"]["source_observations"]) == 7
    all_sources = [s for case in report["cases"] for s in case["source_observations"]]
    assert len(all_sources) == len({s["source_id"] for s in all_sources}) == 11
    saved_sha = {
        "FLOW-FDA-PMA-P230024": "398d6e3dd7bd1fee79460de54afa293d8578fbeb8920fa895ca850469138ea4d",
        "FLOW-MFR-LAUNCH-SEP16": "2fdcf54c247b5c5a4232c6a5ea8beda8f38bcbc7c6197d18f44580e83193ff75",
        "MODIUS-FDA-DEN250013": "d1f91d82897269ab1e17c93f4fc034152743a16792287c9e48706189587f80a4",
    }
    for source in all_sources:
        assert source["url"].startswith("https://")
        assert source["source_claim"] and source["evidence_axis"]
        if source["collection_state"] == "RAW_PUBLIC_HTML_SAVED_PREVIOUSLY":
            assert source["artifact_id"] == 12323904364
            assert source["sha256"] == saved_sha[source["source_id"]]
        else:
            assert source["collection_state"] == "WEB_INSPECTED_NO_SAVED_RAW_BYTES"
            assert source["sha256"] is None
            assert source["artifact_id"] is None
        if source["document_date"] is not None:
            assert source["document_date"] <= report["analysis_dates"]["world_time_cutoff"]
    modius = by_key["MODIUS_SPERO"]["source_observations"]
    assert next(x for x in modius if x["source_id"] == "MODIUS-BIOWORLD-JUL02")["document_date"] == "2026-07-02"
    assert next(x for x in modius if x["source_id"] == "MODIUS-TV-SEP09")["document_date"] == "2026-09-09"
    assert next(x for x in modius if x["source_id"] == "MODIUS-MFR-VA-CURRENT")["document_date"] is None
    assert next(x for x in modius if x["source_id"] == "MODIUS-PSYCHIATRIC-ASSOCIATION-SUMMER")[
        "document_date"
    ] is None
    assert report["observed_disagreement"]["logic"]
