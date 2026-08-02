"""Unit tests for ops-gated live shadow collection helpers (network-free)."""

from __future__ import annotations

import pytest

from neuroai_workbench.shadow_refresh import (
    LIVE_COLLECTION_ENV,
    evaluation_collection_plan,
    live_collection_enabled,
    observed_run_results_from_live,
    require_live_collection_enabled,
    validate_shadow_refresh_run_results,
)


def test_live_collection_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(LIVE_COLLECTION_ENV, raising=False)
    assert live_collection_enabled() is False
    with pytest.raises(PermissionError, match=LIVE_COLLECTION_ENV):
        require_live_collection_enabled()


def test_live_collection_enabled_only_for_exact_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIVE_COLLECTION_ENV, "true")
    assert live_collection_enabled() is False
    monkeypatch.setenv(LIVE_COLLECTION_ENV, "1")
    assert live_collection_enabled() is True
    require_live_collection_enabled()


def test_evaluation_collection_plan_promotes_http_not_due_only() -> None:
    plan = {
        "plan_id": "PLAN-TEST",
        "as_of": "2026-08-02",
        "due": [
            {
                "source_id": "SRC-DUE",
                "url": "https://example.org/due",
                "network_access_required": True,
            }
        ],
        "manual": [
            {
                "source_id": "SRC-LOCAL",
                "url": "file:///ops/local.json",
                "network_access_required": False,
                "manual_reason": "CONTROLLED_LOCAL_OR_NO_NETWORK",
            }
        ],
        "not_due": [
            {
                "source_id": "SRC-HTTP",
                "url": "https://example.org/later",
                "network_access_required": True,
            },
            {
                "source_id": "SRC-FILE",
                "url": "C:/ops/local-capture.bin",
                "network_access_required": True,
            },
        ],
        "counts": {"due": 1, "manual": 1, "not_due": 2},
    }
    evaluation = evaluation_collection_plan(plan)
    due_ids = {item["source_id"] for item in evaluation["due"]}
    assert due_ids == {"SRC-DUE", "SRC-HTTP"}
    assert evaluation["counts"]["evaluation_promoted"] == 1
    assert evaluation["counts"]["manual"] == 1
    assert evaluation["manual"][0]["source_id"] == "SRC-LOCAL"
    assert evaluation["not_due"][0]["source_id"] == "SRC-FILE"
    assert evaluation["status"] == "SHADOW_EVALUATION_NOT_CANONICAL"
    assert evaluation["live_evaluation"] is True


def test_public_live_summary_fixture_remains_non_canonical() -> None:
    from pathlib import Path

    from neuroai_workbench.util import load_json

    path = Path(__file__).resolve().parents[2] / "examples" / "shadow_refresh" / "SHADOW_REFRESH_LIVE_PUBLIC_SUMMARY_v202608.json"
    summary = load_json(path)
    assert summary["metadata"]["status"] == "SHADOW_EVALUATION_NOT_CANONICAL"
    assert summary["network_retrieval"] == "EXECUTED_LIVE_QUARANTINE_ONLY"
    assert summary["live_collection_counts"]["total"] == 25
    assert summary["capture_digest_count"] == 22
    assert len(summary["failed_source_ids"]) == 3


def test_observed_run_results_from_live_maps_counts() -> None:
    live_package = {
        "collection_run": {"counts": {"succeeded": 20, "failed": 3, "skipped": 2, "total": 25}},
        "capture_digests": [{"source_id": "SRC-1", "sha256": "a" * 64}] * 20,
    }
    results = observed_run_results_from_live(live_package, run_id="SHADOW-RUN-TEST", planned_total=25)
    assert validate_shadow_refresh_run_results(results) == []
    assert results["captures"]["attempted"] == 25
    assert results["captures"]["succeeded"] == 20
    assert results["captures"]["failed"] == 3
    assert results["captures"]["changed"] == 20
    assert results["captures"]["unchanged"] == 0
    assert results["metadata"]["status"] == "SHADOW_EVALUATION_NOT_CANONICAL"
