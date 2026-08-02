from __future__ import annotations

from pathlib import Path

from neuroai_workbench.observatory_lineage import (
    detect_v16_package_kind,
    validate_v16_package,
    validate_v16_v17_lineage,
)
from neuroai_workbench.util import load_json

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "observatory_lineage"


def test_miniature_packages_validate_and_lineage_passes() -> None:
    refresh = load_json(FIXTURES / "miniature_refresh.json")
    delta = load_json(FIXTURES / "miniature_delta.json")
    v17 = load_json(FIXTURES / "miniature_v17.json")
    v14_ids = set(load_json(FIXTURES / "miniature_v14_source_ids.json"))
    assert detect_v16_package_kind(refresh) == "OBSERVATORY_V1_6_REFRESH"
    assert detect_v16_package_kind(delta) == "OBSERVATORY_V1_6_ADJUDICATED_DELTA"
    assert validate_v16_package(refresh)["valid"] is True
    assert validate_v16_package(delta)["valid"] is True
    report = validate_v16_v17_lineage(
        refresh=refresh,
        delta=delta,
        v17=v17,
        v14_source_ids=v14_ids,
        expected_new_sources=2,
        expected_candidates=2,
        expected_final_sources=8,
        expected_baseline_sources=4,
        expected_assessment_adds=2,
    )
    assert report["valid"] is True, report["errors"]


def test_lineage_fails_closed_on_source_overlap() -> None:
    refresh = load_json(FIXTURES / "miniature_refresh.json")
    delta = load_json(FIXTURES / "miniature_delta.json")
    v17 = load_json(FIXTURES / "miniature_v17.json")
    report = validate_v16_v17_lineage(
        refresh=refresh,
        delta=delta,
        v17=v17,
        v14_source_ids={"SRC-N1", "SRC-B1"},
        expected_new_sources=2,
        expected_candidates=2,
        expected_final_sources=8,
        expected_baseline_sources=4,
        expected_assessment_adds=2,
    )
    assert report["valid"] is False
    assert any(item["code"] == "NEW_SOURCE_OVERLAP_V14" for item in report["errors"])


def test_lineage_fails_closed_on_delta_mismatch() -> None:
    refresh = load_json(FIXTURES / "miniature_refresh.json")
    delta = load_json(FIXTURES / "miniature_delta.json")
    v17 = load_json(FIXTURES / "miniature_v17.json")
    v14_ids = set(load_json(FIXTURES / "miniature_v14_source_ids.json"))
    broken = dict(delta)
    broken["model_records"] = [{"model_id": "MOD-X", "source_ids": ["SRC-N1"]}]
    report = validate_v16_v17_lineage(
        refresh=refresh,
        delta=broken,
        v17=v17,
        v14_source_ids=v14_ids,
        expected_new_sources=2,
        expected_candidates=2,
        expected_final_sources=8,
        expected_baseline_sources=4,
        expected_assessment_adds=2,
    )
    assert report["valid"] is False
    codes = {item["code"] for item in report["errors"]}
    assert "REFRESH_DELTA_MISMATCH" in codes or "V17_DELTA_MISMATCH" in codes


def test_unknown_package_fails_closed() -> None:
    report = validate_v16_package({"metadata": {"version": "x"}, "hello": True})
    assert report["valid"] is False
    assert report["release_kind"] == "UNKNOWN"
