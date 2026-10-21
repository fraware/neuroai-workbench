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
