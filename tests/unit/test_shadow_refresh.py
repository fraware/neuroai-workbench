from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from neuroai_workbench.shadow_refresh import (
    SHADOW_EVALUATION_STATUS,
    compute_go_no_go_metrics,
    validate_shadow_artifact_status,
    validate_shadow_refresh_cohort,
    validate_shadow_refresh_freeze_manifest,
    validate_shadow_refresh_go_no_go_metrics,
    validate_shadow_refresh_run_results,
)
from neuroai_workbench.util import load_json

ROOT = Path(__file__).resolve().parents[2]
COHORT = ROOT / "examples" / "shadow_refresh" / "SHADOW_REFRESH_COHORT_v202608.json"
FREEZE = ROOT / "examples" / "shadow_refresh" / "SHADOW_REFRESH_FREEZE_MANIFEST_v202608.example.json"
RUN_RESULTS = ROOT / "tests" / "fixtures" / "shadow_refresh" / "synthetic_run_results.json"


def test_cohort_fixture_validates_and_is_noncanonical() -> None:
    cohort = load_json(COHORT)
    assert validate_shadow_refresh_cohort(cohort) == []
    assert validate_shadow_artifact_status(cohort) == []
    assert cohort["metadata"]["status"] == SHADOW_EVALUATION_STATUS
    assert cohort["metadata"]["source_count"] == len(cohort["sources"]) == 25


def test_freeze_manifest_fixture_validates_and_is_noncanonical() -> None:
    manifest = load_json(FREEZE)
    assert validate_shadow_refresh_freeze_manifest(manifest) == []
    assert validate_shadow_artifact_status(manifest) == []
    assert manifest["metadata"]["status"] == SHADOW_EVALUATION_STATUS
    assert manifest["cohort_reference"]["source_count"] == 25


def test_run_results_fixture_validates_and_is_noncanonical() -> None:
    results = load_json(RUN_RESULTS)
    assert validate_shadow_refresh_run_results(results) == []
    assert validate_shadow_artifact_status(results) == []
    assert results["metadata"]["status"] == SHADOW_EVALUATION_STATUS


def test_cohort_rejects_canonical_status() -> None:
    cohort = load_json(COHORT)
    cohort["metadata"]["status"] = "CANONICAL"
    assert validate_shadow_refresh_cohort(cohort)
    assert any(item["code"] == "SCHEMA_ERROR" for item in validate_shadow_refresh_cohort(cohort))
    assert any(item["code"] == "INVALID_STATUS" for item in validate_shadow_artifact_status(cohort))


def test_freeze_manifest_rejects_missing_hash() -> None:
    manifest = load_json(FREEZE)
    manifest["configuration_hashes"].pop("collector_sha256")
    assert validate_shadow_refresh_freeze_manifest(manifest)


def test_go_no_go_metrics_rejects_canonical_status() -> None:
    results = load_json(RUN_RESULTS)
    metrics = compute_go_no_go_metrics(results)
    metrics["metadata"]["status"] = "CANONICAL"
    assert validate_shadow_refresh_go_no_go_metrics(metrics)
    assert any(item["code"] == "INVALID_STATUS" for item in validate_shadow_artifact_status(metrics))


@pytest.mark.parametrize(
    "field,expected",
    [
        ("retrieval_success_rate", 0.92),
        ("candidate_precision", 0.8),
        ("provenance_closure_rate", 1.0),
    ],
)
def test_compute_go_no_go_metrics_stub_values(field: str, expected: float) -> None:
    results = load_json(RUN_RESULTS)
    metrics = compute_go_no_go_metrics(results)
    assert metrics["metadata"]["status"] == SHADOW_EVALUATION_STATUS
    assert validate_shadow_refresh_go_no_go_metrics(metrics) == []
    assert metrics["metrics"][field] == pytest.approx(expected)


def test_compute_go_no_go_metrics_recommendation() -> None:
    results = load_json(RUN_RESULTS)
    metrics = compute_go_no_go_metrics(results)
    assert metrics["evaluation"]["recommendation"] == "GO"
    assert len(metrics["evaluation"]["criteria_results"]) == 7


def test_compute_go_no_go_metrics_no_go_on_threshold_failure() -> None:
    results = load_json(RUN_RESULTS)
    results["captures"]["succeeded"] = 10
    results["captures"]["failed"] = 15
    results["captures"]["unchanged"] = 8
    results["captures"]["changed"] = 2
    metrics = compute_go_no_go_metrics(
        results,
        thresholds={"minimum_retrieval_success_rate": 0.95},
    )
    assert metrics["evaluation"]["recommendation"] == "NO_GO"
    retrieval = next(
        item for item in metrics["evaluation"]["criteria_results"] if item["criterion_id"] == "retrieval_success"
    )
    assert retrieval["passed"] is False


def test_compute_go_no_go_metrics_rejects_invalid_run_results() -> None:
    results: dict[str, Any] = json.loads(RUN_RESULTS.read_text(encoding="utf-8"))
    results["captures"].pop("attempted")
    with pytest.raises(ValueError, match="Invalid shadow run results"):
        compute_go_no_go_metrics(results)
