"""Fail-closed source-lineage checks for composite review hints."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.r1_7_compare_review_registry import EXPECTED_COMPARISON_COUNTS
from scripts.r1_7_composite_designation_review import literal_parts, make_composite_review
from scripts.r1_7_extract_review_device_tables import RAW_SOURCE_SHA256

COMPOSITES = (
    "Wearable SensingDSI-24/DSI-7",
    "B-Alert X/Stat X",
    "BrainBit Hero/Diamond",
    "BitBrain Ikon/Ikon sleep",
    "ANT Neuro Eego sports/Mylab cap",
    "BrainBit Flex/Flex8",
)


def fixture_crosswalk() -> dict:
    rows = []
    for index in range(57):
        designation = COMPOSITES[index] if index < 6 else f"Mock EEG device {index}"
        rows.append(
            {
                "table_number": 1 + index // 13,
                "row_number_1_based": index % 13 + 1,
                "raw_row_content_sha256": f"{index:064x}",
                "source_raw_xml_sha256": RAW_SOURCE_SHA256,
                "raw_device_designation": designation,
                "form_factor": "synthetic_form_factor",
                "composite_name_needs_splitting_review": "/" in designation,
            }
        )
    return {
        "source_pmid": "42505450",
        "raw_table_row_count": 57,
        "comparison_counts": dict(EXPECTED_COMPARISON_COUNTS),
        "new_canonical_entities_created": 0,
        "r1_7_terminal_extractions_credited": 0,
        "source_primary_xml_sha256": RAW_SOURCE_SHA256,
        "registry_file_sha256": "b" * 64,
        "rows": rows,
    }


def test_lexical_splits_do_not_expand_models() -> None:
    assert literal_parts("BitBrain Ikon/Ikon sleep") == ["BitBrain Ikon", "Ikon sleep"]
    assert literal_parts("Wearable SensingDSI-24/DSI-7") == ["Wearable SensingDSI-24", "DSI-7"]
    for name in ("", "No slash", "/Missing", "Missing/", "A/B/C"):
        with pytest.raises(ValueError, match="slash|Empty"):
            literal_parts(name)


def test_all_six_composites_keep_original_row_provenance() -> None:
    report = make_composite_review(fixture_crosswalk())
    assert report["status"] == "NONTERMINAL_SOURCE_TEXT_ONLY"
    assert report["original_raw_table_rows"] == 57
    assert report["slash_composite_row_count"] == 6
    assert report["literal_segment_count"] == 12
    assert report["new_product_identifiers"] == 0
    assert report["terminal_extractions"] == 0
    assert report["product_count_inference"] is None
    assert [r["original_designation"] for r in report["review_rows"]] == list(COMPOSITES)
    assert all(r["prefix_expansion"] == "UNRESOLVED_DO_NOT_INFER" for r in report["review_rows"])
    assert all(r["canonical_entity_id_allocated"] is None for r in report["review_rows"])


def test_composite_source_provenance_tampering_is_rejected() -> None:
    crosswalk = fixture_crosswalk()
    bad_source = deepcopy(crosswalk)
    bad_source["source_primary_xml_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="frozen source digest mismatch"):
        make_composite_review(bad_source)
    bad = deepcopy(crosswalk)
    bad["rows"][0]["source_raw_xml_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="source table-row lineage"):
        make_composite_review(bad)
    bad = deepcopy(crosswalk)
    bad["rows"][0]["composite_name_needs_splitting_review"] = False
    with pytest.raises(ValueError, match="composite flag"):
        make_composite_review(bad)


def test_spurious_product_credit_fails_closed() -> None:
    data = fixture_crosswalk()
    data["new_canonical_entities_created"] = 1
    with pytest.raises(ValueError, match="product or execution credit"):
        make_composite_review(data)


def test_vendor_model_reference_conflict_does_not_rewrite_published_identity() -> None:
    root = Path(__file__).resolve().parents[2]
    record = json.loads(
        (root / "docs/programme/r1-7-review-brainbit-bitbrain-citation-discrepancy-2026-10-22.json").read_text(
            encoding="utf-8"
        )
    )
    original = record["publication"]
    assert original["source_xml_sha256"] == RAW_SOURCE_SHA256
    assert original["original_table"] == "Table 1"
    assert original["original_row_1_based"] == 9
    assert original["raw_designation"] == "BrainBit Hero/Diamond"
    assert original["original_row_content_sha256"] == (
        "1dd400a0a26d2b5003432b2bd52fbecd1d9bacdf39a66f406522936e87ade2d2"
    )
    assert original["original_citation_numbers"] == [66, 67]
    assert [x["citation_number"] for x in record["reference_links"]] == [66, 67]
    assert all("bitbrain.com/" in x["url"] for x in record["reference_links"])
    assert record["separate_vendor_identity"]["distinct_vendor_identity_is_not_auto_resolution"] is True
    assert record["original_label_rewritten"] is False
    assert record["no_published_row_mutation"] is True
    assert record["canonical_offerings_allocated"] == 0
    assert record["r1_7_terminal_extractions_credited"] == 0
