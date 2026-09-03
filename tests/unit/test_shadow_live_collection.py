"""Unit tests for ops-gated live shadow collection helpers (network-free)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench.collector.authorization import (
    LIVE_AUTHORIZATION_ENV,
    build_authorization_packet,
)
from neuroai_workbench.collector.dns import DnsGuard
from neuroai_workbench.shadow_refresh import (
    LIVE_COLLECTION_ENV,
    default_live_collector_config,
    evaluation_collection_plan,
    live_collection_enabled,
    observed_run_results_from_live,
    require_live_collection_enabled,
    run_live_cohort_collection,
    validate_shadow_refresh_run_results,
)
from neuroai_workbench.util import atomic_write_json
from tests.unit.test_collector_adapters_scheduler import FakeTransport, global_getaddrinfo


def _authorize_live(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    packet = build_authorization_packet(
        authorization_id="AUTH-SHADOW-LIVE-TEST",
        authorized_by="test-operator",
        purpose="Controlled unit test of live shadow collection quarantine outputs.",
        network_mode="AUTHORIZED_NETWORK",
        network_permitted=True,
        authorized_at="2026-09-02T12:00:00Z",
    )
    monkeypatch.setenv(LIVE_COLLECTION_ENV, "1")
    monkeypatch.setenv(LIVE_AUTHORIZATION_ENV, json.dumps(packet))
    return packet


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

    path = (
        Path(__file__).resolve().parents[2]
        / "examples"
        / "shadow_refresh"
        / "SHADOW_REFRESH_LIVE_PUBLIC_SUMMARY_v202608.json"
    )
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


def test_default_live_collector_config_is_deterministic() -> None:
    first = default_live_collector_config()
    second = default_live_collector_config()
    assert first.configuration_hash == second.configuration_hash
    assert first.collector_version.startswith("0.3.0")
    assert first.requests_per_host_per_minute == 12


def test_run_live_cohort_collection_uses_injected_transport(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _authorize_live(monkeypatch)
    url = "https://page.example.org/shadow-live"
    transport = FakeTransport(responses={url: (200, {"content-type": "text/html"}, b"<html>live</html>")})
    plan = {
        "plan_id": "PLAN-LIVE",
        "as_of": "2026-08-02",
        "due": [],
        "manual": [],
        "not_due": [
            {
                "source_id": "SRC-LIVE-1",
                "monitor_id": "MON-LIVE-1",
                "url": url,
                "publisher": "Example",
                "source_class": "OFFICIAL_COMPANY_PAGE",
                "cadence": "QUARTERLY",
                "network_access_required": True,
            }
        ],
        "counts": {"due": 0, "manual": 0, "not_due": 1},
    }
    registry = {
        "sources": [
            {
                "source_id": "SRC-LIVE-1",
                "monitor_id": "MON-LIVE-1",
                "url": url,
                "publisher": "Example",
                "source_class": "OFFICIAL_COMPANY_PAGE",
                "cadence": "QUARTERLY",
                "network_access_required": True,
            }
        ]
    }
    package = run_live_cohort_collection(
        plan=plan,
        registry=registry,
        registry_sha256="a" * 64,
        quarantine_root=tmp_path / "quarantine",
        transport=transport,
        dns_guard=DnsGuard(getaddrinfo=global_getaddrinfo),
    )
    assert package["status"] == "SHADOW_EVALUATION_NOT_CANONICAL"
    assert package["collector"]["handoff_enabled"] is False
    assert package["collection_run"]["counts"]["succeeded"] == 1
    assert len(package["capture_digests"]) == 1
    assert package["capture_digests"][0]["source_id"] == "SRC-LIVE-1"
    assert package["capture_digests"][0]["sha256"]
    assert len(transport.calls) == 1
    assert transport.calls[0].url == url


def test_run_live_cohort_collection_surfaces_failure_summaries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _authorize_live(monkeypatch)
    url = "https://page.example.org/shadow-fail"
    transport = FakeTransport(responses={url: (500, {"content-type": "text/plain"}, b"error")})
    plan = {
        "plan_id": "PLAN-FAIL",
        "as_of": "2026-08-02",
        "due": [
            {
                "source_id": "SRC-FAIL-1",
                "monitor_id": "MON-FAIL-1",
                "url": url,
                "publisher": "Example",
                "source_class": "OFFICIAL_COMPANY_PAGE",
                "cadence": "QUARTERLY",
                "network_access_required": True,
            }
        ],
        "manual": [],
        "not_due": [],
        "counts": {"due": 1, "manual": 0, "not_due": 0},
    }
    registry = {
        "sources": [
            {
                "source_id": "SRC-FAIL-1",
                "monitor_id": "MON-FAIL-1",
                "url": url,
                "publisher": "Example",
                "source_class": "OFFICIAL_COMPANY_PAGE",
                "cadence": "QUARTERLY",
                "network_access_required": True,
            }
        ]
    }
    package = run_live_cohort_collection(
        plan=plan,
        registry=registry,
        registry_sha256="b" * 64,
        quarantine_root=tmp_path / "quarantine",
        transport=transport,
        dns_guard=DnsGuard(getaddrinfo=global_getaddrinfo),
    )
    assert package["collection_run"]["counts"]["failed"] == 1
    assert package["failure_summaries"]
    assert package["failure_summaries"][0]["source_id"] == "SRC-FAIL-1"
    assert package["failure_summaries"][0]["failure_class"]
    failure_outcome = next(item for item in package["collection_run"]["outcomes"] if item["status"] == "FAILURE")
    assert failure_outcome["failure_class"]


def test_live_collection_fails_closed_on_corrupt_durable_quarantine_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _authorize_live(monkeypatch)
    quarantine = tmp_path / "quarantine"
    (quarantine / "results").mkdir(parents=True)
    (quarantine / "failures").mkdir(parents=True)
    (quarantine / "results" / "bad.json").write_text("{not-json", encoding="utf-8")
    (quarantine / "failures" / "bad.json").write_text("{not-json", encoding="utf-8")
    atomic_write_json(
        quarantine / "results" / "ok.json",
        {
            "source_id": "SRC-OK",
            "result_id": "CRES-1",
            "sha256": "c" * 64,
            "http_status": 200,
            "size_bytes": 3,
            "media_type": "text/plain",
            "final_url": "https://example.org/ok",
            "evidence_state": "RETRIEVED_BYTES_NOT_SUBSTANTIVELY_ADJUDICATED",
        },
    )
    with pytest.raises((OSError, ValueError), match="JSON|Expecting|decode|object"):
        run_live_cohort_collection(
            plan={
                "plan_id": "PLAN-EMPTY",
                "as_of": "2026-08-02",
                "due": [],
                "manual": [],
                "not_due": [],
                "counts": {"due": 0, "manual": 0, "not_due": 0},
            },
            registry={"sources": []},
            registry_sha256="d" * 64,
            quarantine_root=quarantine,
            transport=FakeTransport(),
            dns_guard=DnsGuard(getaddrinfo=global_getaddrinfo),
        )
