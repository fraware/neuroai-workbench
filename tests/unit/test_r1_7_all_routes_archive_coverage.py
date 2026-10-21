"""Tests for complete, nonterminal R1.7 source/record archive coverage."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.r1_7_all_routes_archive_coverage import (
    ARCHIVE,
    RESOURCE,
    ROUTING,
    build_report,
    main,
)


def test_all_frozen_source_record_routes_accounted_without_completion() -> None:
    report = build_report()
    assert report["status"] == "NONTERMINAL_INVENTORY_ONLY"
    assert report["governed_work_item_count"] == 192
    assert report["governed_capture_count"] == 247
    assert report["work_item_counts_by_route"] == {
        "SOURCE_SURFACE_RESOLUTION": 171,
        "LITERATURE_RECORD_EXTRACTION": 21,
    }
    assert report["capture_counts_by_route"] == {
        "SOURCE_SURFACE_RESOLUTION": 226,
        "LITERATURE_RECORD_EXTRACTION": 21,
    }
    assert report["archive_context_count"] == 26
    assert report["archive_state_counts_by_capture"] == {
        "ALTERNATIVE_ACCESS_BARRIER_UNRESOLVED": 1,
        "ALTERNATIVE_SOURCE_BYTES_SAVED_UNADJUDICATED": 4,
        "DIRECT_SAVED_ARTICLE_XML_UNADJUDICATED": 4,
        "NO_LINKED_ARCHIVE_EVIDENCE_IN_THIS_BOUNDED_INVENTORY": 221,
        "REUSED_SAVED_ARTICLE_XML_NOT_DIRECT_ROUTE_ACQUISITION": 17,
    }
    assert report["work_items_with_terminal_completion_verified"] == 0
    assert report["canonical_product_increments"] == 0
    all_items = report["work_items"]
    assert len({row["work_item_id"] for row in all_items}) == 192
    all_caps = [cap["capture_id"] for row in all_items for cap in row["captures"]]
    assert len(set(all_caps)) == 247
    assert all(row["terminal_completion_verified"] is False for row in all_items)
    assert all(row["canonical_product_count_increment"] == 0 for row in all_items)


def test_source_byte_coverage_differs_from_article_reference_reuse() -> None:
    report = build_report()
    first = [
        row for row in report["work_items"]
        if "DIRECT_SAVED_ARTICLE_XML_UNADJUDICATED" in row["archive_states"]
    ]
    reused = [
        row for row in report["work_items"]
        if "REUSED_SAVED_ARTICLE_XML_NOT_DIRECT_ROUTE_ACQUISITION" in row["archive_states"]
    ]
    assert len(first) == 4
    assert len(reused) == 17
    assert not {row["work_item_id"] for row in first} & {
        row["work_item_id"] for row in reused
    }


def test_report_is_byte_stable_and_does_not_modify_inputs(tmp_path: Path) -> None:
    target = tmp_path / "coverage.json"
    assert main(["--output", str(target)]) == 0
    first = target.read_bytes()
    assert main(["--output", str(target)]) == 0
    assert first == target.read_bytes()
    assert json.loads(first)["work_items_with_terminal_completion_verified"] == 0
    assert len(build_report()["frozen_input_sha256"]) == 2


def test_fails_closed_on_changed_frozen_route_denominator(tmp_path: Path) -> None:
    route = json.loads((RESOURCE / ROUTING).read_text(encoding="utf-8"))
    route["work_item_count"] = 269
    (tmp_path / ROUTING).write_text(json.dumps(route), encoding="utf-8")
    with pytest.raises(ValueError, match="population drift"):
        build_report(tmp_path, ARCHIVE)


def test_fails_closed_on_unreviewed_terminal_assertion(tmp_path: Path) -> None:
    raw = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    changed = deepcopy(raw)
    changed["known_archive_contexts"][0]["terminal_work_item_completion"] = True
    receipt = tmp_path / "report.json"
    receipt.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="completed scientific execution"):
        build_report(RESOURCE, receipt)


def test_fails_closed_on_orphaned_evidence_capture(tmp_path: Path) -> None:
    raw = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    raw["known_archive_contexts"][0]["capture_id"] = "UNKNOWN-FROZEN-CAPTURE"
    receipt = tmp_path / "report.json"
    receipt.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="Orphan archive receipt"):
        build_report(RESOURCE, receipt)
