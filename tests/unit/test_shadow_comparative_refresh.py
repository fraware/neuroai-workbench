"""Network-free tests for issue #120 comparative live refresh execution."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from neuroai_workbench.collector.dns import DnsGuard
from neuroai_workbench.monitoring import initialize_monitoring, record_snapshot
from neuroai_workbench.shadow_refresh import LIVE_COLLECTION_ENV
from neuroai_workbench.shadow_refresh.comparative import (
    ProtectedBaselineBinding,
    approve_collection_for_evaluation,
    build_public_comparative_report,
    classify_capture_pair,
    run_comparative_live_refresh,
    seed_verified_baselines,
)
from neuroai_workbench.shadow_refresh.live import run_live_cohort_collection
from neuroai_workbench.util import atomic_write_json, load_json, sha256_file
from tests.unit.test_collector_adapters_scheduler import FakeTransport, global_getaddrinfo

FIXTURES = Path(__file__).parents[1] / "fixtures" / "delta"
PREDECESSOR = FIXTURES / "synthetic_predecessor_release.json"


def _registry(source_ids: tuple[str, ...] = ("SRC-0001",)) -> list[dict[str, object]]:
    rows = []
    for index, source_id in enumerate(source_ids, start=1):
        rows.append(
            {
                "monitor_id": f"MON-{source_id}",
                "source_id": source_id,
                "url": f"https://pages.example.org/source-{index}",
                "publisher": "Example publisher",
                "source_class": "OFFICIAL_COMPANY_PAGE",
                "cadence": "WEEKLY",
                "last_successful_retrieval": "2026-07-01",
                "baseline_evidence_state": "CURRENT_SOURCE_RETRIEVED",
                "baseline_verification_state": "CURRENT_VERIFIED",
                "baseline_claim_boundary": "Synthetic test boundary.",
                "network_access_required": True,
                "current_status": "BASELINE_REGISTERED",
                "next_action": "RETRIEVE_AND_COMPARE",
            }
        )
    return rows


def _plan(registry: list[dict[str, object]]) -> dict[str, object]:
    due = [
        {
            "source_id": row["source_id"],
            "monitor_id": row["monitor_id"],
            "url": row["url"],
            "publisher": row["publisher"],
            "source_class": row["source_class"],
            "cadence": row["cadence"],
            "network_access_required": True,
        }
        for row in registry
    ]
    return {
        "plan_id": "PLAN-COMPARATIVE-TEST",
        "as_of": "2026-08-10",
        "due": due,
        "manual": [],
        "not_due": [],
        "counts": {"due": len(due), "manual": 0, "not_due": 0},
    }


def _collect(
    *,
    registry_path: Path,
    registry: list[dict[str, object]],
    plan: dict[str, object],
    quarantine_root: Path,
    bodies: dict[str, bytes],
) -> dict[str, object]:
    responses = {
        str(row["url"]): (
            200,
            {"content-type": "application/json" if bodies[str(row["source_id"])].startswith(b"{") else "text/html"},
            bodies[str(row["source_id"])],
        )
        for row in registry
        if str(row["source_id"]) in bodies
    }
    transport = FakeTransport(responses=responses)
    with patch.dict(os.environ, {LIVE_COLLECTION_ENV: "1"}):
        return run_live_cohort_collection(
            plan=plan,
            registry={"sources": registry},
            registry_sha256=sha256_file(registry_path),
            quarantine_root=quarantine_root,
            transport=transport,
            dns_guard=DnsGuard(getaddrinfo=global_getaddrinfo),
        )


def _write_registry(path: Path, registry: list[dict[str, object]]) -> None:
    atomic_write_json(path, registry)


def _binding() -> ProtectedBaselineBinding:
    return ProtectedBaselineBinding(
        artifact_id="8865433109",
        artifact_name="protected-shadow-cycle-43",
        artifact_sha256="b" * 64,
        workflow_run_id="30837442076",
        workbench_commit="b960baa27f22e4d8d90d6873eed6f18af754af1a",
    )


def test_verified_baseline_seed_is_read_only_and_hash_bound(tmp_path: Path) -> None:
    registry = _registry()
    registry_path = tmp_path / "registry.json"
    _write_registry(registry_path, registry)
    plan = _plan(registry)
    quarantine = tmp_path / "baseline-q"
    package = _collect(
        registry_path=registry_path,
        registry=registry,
        plan=plan,
        quarantine_root=quarantine,
        bodies={"SRC-0001": b"<html>baseline</html>"},
    )
    summary_path = tmp_path / "baseline-summary.json"
    atomic_write_json(summary_path, package)
    before = {path: path.read_bytes() for path in quarantine.rglob("*") if path.is_file()}

    seeded = seed_verified_baselines(
        evaluation_workspace=tmp_path / "ws",
        registry_path=registry_path,
        baseline_quarantine_root=quarantine,
        baseline_summary_path=summary_path,
        actor="tester",
    )
    after = {path: path.read_bytes() for path in quarantine.rglob("*") if path.is_file()}

    assert seeded["count"] == 1
    assert seeded["records"][0]["source_id"] == "SRC-0001"
    assert seeded["records"][0]["sha256"] == package["capture_digests"][0]["sha256"]
    assert seeded["protected_bytes_emitted"] is False
    assert before == after


def test_baseline_seed_rejects_reviewed_registry_target_drift(tmp_path: Path) -> None:
    registry = _registry()
    registry_path = tmp_path / "registry.json"
    _write_registry(registry_path, registry)
    plan = _plan(registry)
    quarantine = tmp_path / "baseline-q"
    package = _collect(
        registry_path=registry_path,
        registry=registry,
        plan=plan,
        quarantine_root=quarantine,
        bodies={"SRC-0001": b"<html>baseline</html>"},
    )
    summary_path = tmp_path / "baseline-summary.json"
    atomic_write_json(summary_path, package)

    drifted = [dict(registry[0])]
    drifted[0]["url"] = "https://pages.example.org/moved-source"
    _write_registry(registry_path, drifted)
    with pytest.raises(ValueError, match="reviewed registry retrieval target mismatch"):
        seed_verified_baselines(
            evaluation_workspace=tmp_path / "ws-drift",
            registry_path=registry_path,
            baseline_quarantine_root=quarantine,
            baseline_summary_path=summary_path,
        )


def test_baseline_seed_rejects_corrupt_or_ambiguous_capture(tmp_path: Path) -> None:
    registry = _registry()
    registry_path = tmp_path / "registry.json"
    _write_registry(registry_path, registry)
    plan = _plan(registry)
    quarantine = tmp_path / "baseline-q"
    package = _collect(
        registry_path=registry_path,
        registry=registry,
        plan=plan,
        quarantine_root=quarantine,
        bodies={"SRC-0001": b"<html>baseline</html>"},
    )
    summary_path = tmp_path / "summary.json"
    atomic_write_json(summary_path, package)

    incoming = next(path for path in quarantine.rglob("*") if path.is_file() and "incoming" in path.parts)
    incoming.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="integrity verification"):
        seed_verified_baselines(
            evaluation_workspace=tmp_path / "ws-corrupt",
            registry_path=registry_path,
            baseline_quarantine_root=quarantine,
            baseline_summary_path=summary_path,
        )

    duplicated = dict(package)
    duplicated["capture_digests"] = [package["capture_digests"][0], dict(package["capture_digests"][0])]
    atomic_write_json(summary_path, duplicated)
    with pytest.raises(ValueError, match="duplicate source"):
        seed_verified_baselines(
            evaluation_workspace=tmp_path / "ws-ambiguous",
            registry_path=registry_path,
            baseline_quarantine_root=quarantine,
            baseline_summary_path=summary_path,
        )


def test_technical_approval_is_scoped_to_current_successes(tmp_path: Path) -> None:
    registry = _registry(("SRC-0001", "SRC-0002"))
    registry_path = tmp_path / "registry.json"
    _write_registry(registry_path, registry)
    plan = _plan(registry)
    quarantine = tmp_path / "q"
    package = _collect(
        registry_path=registry_path,
        registry=registry,
        plan=plan,
        quarantine_root=quarantine,
        bodies={"SRC-0001": b"<html>one</html>", "SRC-0002": b"<html>two</html>"},
    )
    approval = approve_collection_for_evaluation(
        live_package=package,
        quarantine_root=quarantine,
        actor="issue-120-test",
    )
    assert approval["count"] == 2
    assert approval["substantive_authority"] is False
    assert {row["approval_scope"] for row in approval["records"]} == {"EVALUATION_HANDOFF_ONLY_NOT_SUBSTANTIVE_REVIEW"}
    for row in approval["records"]:
        record = load_json(quarantine / "records" / f"{row['quarantine_id']}.json")
        assert record["approval_state"] == "APPROVED_FOR_HANDOFF"
        assert record["approved_by"] == "issue-120-test"


def test_comparison_classifier_distinguishes_byte_representation_json_and_transitions(tmp_path: Path) -> None:
    registry = _registry()
    registry_path = tmp_path / "registry.json"
    _write_registry(registry_path, registry)
    ws = tmp_path / "ws"
    initialize_monitoring(ws, registry_path, actor="tester")
    url = "https://example.org/source-1"

    old = record_snapshot(
        ws,
        "SRC-0001",
        b'{"a":1,"b":2}',
        media_type="application/json",
        retrieved_at="2026-08-01T00:00:00Z",
        retrieval_url=url,
        actor="tester",
    )
    same = record_snapshot(
        ws,
        "SRC-0001",
        b'{"a":1,"b":2}',
        media_type="application/json",
        retrieved_at="2026-08-02T00:00:00Z",
        retrieval_url=url,
        actor="tester",
    )
    byte_result = classify_capture_pair(
        evaluation_workspace=ws,
        source_id="SRC-0001",
        older_snapshot_id=old["snapshot_id"],
        newer_snapshot_id=same["snapshot_id"],
        older_collector_configuration_hash="cfg",
        newer_collector_configuration_hash="cfg",
    )
    assert byte_result["classification"] == "BYTE_IDENTICAL"

    changed = record_snapshot(
        ws,
        "SRC-0001",
        b'{"a":2,"b":2}',
        media_type="application/json",
        retrieved_at="2026-08-03T00:00:00Z",
        retrieval_url=url,
        actor="tester",
    )
    json_result = classify_capture_pair(
        evaluation_workspace=ws,
        source_id="SRC-0001",
        older_snapshot_id=same["snapshot_id"],
        newer_snapshot_id=changed["snapshot_id"],
        older_collector_configuration_hash="cfg",
        newer_collector_configuration_hash="cfg2",
    )
    assert json_result["classification"] == "STRUCTURED_RECORD_FIELD_CHANGE"
    assert json_result["changed_structured_paths"] == ["a"]
    assert json_result["collector_configuration"]["same"] is False

    other_media = record_snapshot(
        ws,
        "SRC-0001",
        b"<html>two</html>",
        media_type="text/html",
        retrieved_at="2026-08-04T00:00:00Z",
        retrieval_url=url,
        actor="tester",
    )
    media_result = classify_capture_pair(
        evaluation_workspace=ws,
        source_id="SRC-0001",
        older_snapshot_id=changed["snapshot_id"],
        newer_snapshot_id=other_media["snapshot_id"],
        older_collector_configuration_hash=None,
        newer_collector_configuration_hash=None,
    )
    assert media_result["classification"] == "INCOMPARABLE_CONTENT_TYPE_TRANSITION"

    other_target = record_snapshot(
        ws,
        "SRC-0001",
        b"<html>three</html>",
        media_type="text/html",
        retrieved_at="2026-08-05T00:00:00Z",
        retrieval_url="https://example.org/moved",
        actor="tester",
    )
    target_result = classify_capture_pair(
        evaluation_workspace=ws,
        source_id="SRC-0001",
        older_snapshot_id=other_media["snapshot_id"],
        newer_snapshot_id=other_target["snapshot_id"],
        older_collector_configuration_hash=None,
        newer_collector_configuration_hash=None,
    )
    assert target_result["classification"] == "INCOMPARABLE_RETRIEVAL_TARGET_TRANSITION"


def test_full_comparative_runner_executes_true_live_to_live_comparison(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(LIVE_COLLECTION_ENV, "1")
    registry = _registry()
    registry_path = tmp_path / "registry.json"
    _write_registry(registry_path, registry)
    plan = _plan(registry)
    baseline_q = tmp_path / "baseline-q"
    baseline_package = _collect(
        registry_path=registry_path,
        registry=registry,
        plan=plan,
        quarantine_root=baseline_q,
        bodies={"SRC-0001": b"<html>baseline</html>"},
    )
    baseline_summary = tmp_path / "baseline-summary.json"
    atomic_write_json(baseline_summary, baseline_package)
    url = str(registry[0]["url"])
    current_transport = FakeTransport(responses={url: (200, {"content-type": "text/html"}, b"<html>changed</html>")})

    package = run_comparative_live_refresh(
        evaluation_workspace=tmp_path / "ws",
        registry_path=registry_path,
        predecessor_path=PREDECESSOR,
        baseline_quarantine_root=baseline_q,
        baseline_summary_path=baseline_summary,
        quarantine_root=tmp_path / "current-q",
        output_dir=tmp_path / "out",
        plan=plan,
        refresh_version="v2.3.0-dev-test",
        evidence_cutoff="2026-08-10",
        apply_id="apply-v23-comparative-test",
        baseline_binding=_binding(),
        transport=current_transport,
        dns_guard=DnsGuard(getaddrinfo=global_getaddrinfo),
        actor="issue-120-test",
    )

    assert package["status"] == "SHADOW_EVALUATION_NOT_CANONICAL"
    assert package["comparative_execution"]["baseline_count"] == 1
    assert package["comparative_execution"]["true_comparison_count"] == 1
    assert package["stage_results"]["compare_snapshots"]["count"] == 1
    detailed = package["stage_results"]["compare_snapshots"]["detailed_comparisons"][0]
    assert detailed["classification"] == "SUBSTANTIVE_NORMALIZED_TEXT_CHANGE"
    assert package["stats"]["candidates"]["generated"] == 1
    assert package["stage_results"]["development_disposition"]["scope"] == "DEVELOPMENT_PIPELINE_ONLY"
    assert package["stage_results"]["development_disposition"]["substantive_authority"] is False
    assert package["stage_results"]["apply_delta"]["predecessor_unchanged"] is True
    assert package["canonical_successor_written"] is False
    assert package["assessment_mutation_performed"] is False

    report = build_public_comparative_report(
        package=package,
        predecessor_path=PREDECESSOR,
        registry_path=registry_path,
    )
    encoded = json.dumps(report, sort_keys=True)
    assert report["execution"]["true_comparison_count"] == 1
    assert report["execution"]["comparison_classification_counts"] == {"SUBSTANTIVE_NORMALIZED_TEXT_CHANGE": 1}
    assert report["safety"]["protected_capture_bytes_in_report"] is False
    assert report["safety"]["protected_paths_in_report"] is False
    assert str(tmp_path) not in encoded
    assert report["safety"]["canonical_successor_written"] is False


def test_runner_records_second_success_without_prior_baseline_as_first_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(LIVE_COLLECTION_ENV, "1")
    registry = _registry(("SRC-0001", "SRC-0002"))
    registry_path = tmp_path / "registry.json"
    _write_registry(registry_path, registry)
    plan = _plan(registry)

    baseline_plan = {
        **plan,
        "due": [plan["due"][0]],
        "counts": {"due": 1, "manual": 0, "not_due": 0},
    }
    baseline_q = tmp_path / "baseline-q"
    baseline_package = _collect(
        registry_path=registry_path,
        registry=registry,
        plan=baseline_plan,
        quarantine_root=baseline_q,
        bodies={"SRC-0001": b"<html>baseline-one</html>"},
    )
    baseline_summary = tmp_path / "baseline-summary.json"
    atomic_write_json(baseline_summary, baseline_package)
    responses = {
        str(registry[0]["url"]): (200, {"content-type": "text/html"}, b"<html>baseline-one</html>"),
        str(registry[1]["url"]): (200, {"content-type": "text/html"}, b"<html>first-two</html>"),
    }
    package = run_comparative_live_refresh(
        evaluation_workspace=tmp_path / "ws",
        registry_path=registry_path,
        predecessor_path=PREDECESSOR,
        baseline_quarantine_root=baseline_q,
        baseline_summary_path=baseline_summary,
        quarantine_root=tmp_path / "current-q",
        output_dir=tmp_path / "out",
        plan=plan,
        refresh_version="v2.3.0-dev-first-retry",
        evidence_cutoff="2026-08-10",
        apply_id="apply-v23-first-retry",
        baseline_binding=_binding(),
        transport=FakeTransport(responses=responses),
        dns_guard=DnsGuard(getaddrinfo=global_getaddrinfo),
        actor="issue-120-test",
    )
    assert package["stage_results"]["compare_snapshots"]["count"] == 1
    assert package["stage_results"]["compare_snapshots"]["first_capture_without_baseline"] == 1
    by_source = {row["source_id"]: row for row in package["source_outcomes"]}
    assert by_source["SRC-0001"]["outcome_type"] == "NO_CHANGE"
    assert by_source["SRC-0002"]["outcome_type"] == "MANUAL_FIRST_CAPTURE"
    assert package["stats"]["candidates"]["generated"] == 0
    assert package["stage_results"]["development_disposition"]["count"] == 0


def test_runner_keeps_identical_capture_out_of_candidate_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIVE_COLLECTION_ENV, "1")
    registry = _registry()
    registry_path = tmp_path / "registry.json"
    _write_registry(registry_path, registry)
    plan = _plan(registry)
    body = b"<html>same</html>"
    baseline_q = tmp_path / "baseline-q"
    baseline_package = _collect(
        registry_path=registry_path,
        registry=registry,
        plan=plan,
        quarantine_root=baseline_q,
        bodies={"SRC-0001": body},
    )
    baseline_summary = tmp_path / "baseline-summary.json"
    atomic_write_json(baseline_summary, baseline_package)
    package = run_comparative_live_refresh(
        evaluation_workspace=tmp_path / "ws",
        registry_path=registry_path,
        predecessor_path=PREDECESSOR,
        baseline_quarantine_root=baseline_q,
        baseline_summary_path=baseline_summary,
        quarantine_root=tmp_path / "current-q",
        output_dir=tmp_path / "out",
        plan=plan,
        refresh_version="v2.3.0-dev-same",
        evidence_cutoff="2026-08-10",
        apply_id="apply-v23-same",
        baseline_binding=_binding(),
        transport=FakeTransport(responses={str(registry[0]["url"]): (200, {"content-type": "text/html"}, body)}),
        dns_guard=DnsGuard(getaddrinfo=global_getaddrinfo),
        actor="issue-120-test",
    )
    detailed = package["stage_results"]["compare_snapshots"]["detailed_comparisons"][0]
    assert detailed["classification"] == "BYTE_IDENTICAL"
    assert package["stats"]["candidates"]["generated"] == 0
    assert package["source_outcomes"][0]["outcome_type"] == "NO_CHANGE"
