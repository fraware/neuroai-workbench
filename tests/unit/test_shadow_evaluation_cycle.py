"""Unit tests for Wave 3 non-canonical evaluation cycle (network-free)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench.collector.authorization import LIVE_AUTHORIZATION_ENV, build_authorization_packet
from neuroai_workbench.collector.dns import DnsGuard
from neuroai_workbench.collector.handoff import approve_quarantine_record
from neuroai_workbench.monitoring import initialize_monitoring, load_source_registry, record_snapshot
from neuroai_workbench.shadow_refresh import LIVE_COLLECTION_ENV
from neuroai_workbench.shadow_refresh.closure import list_quarantine_successes
from neuroai_workbench.shadow_refresh.cycle import (
    CYCLE_STAGES,
    SOURCE_OUTCOME_TAXONOMY,
    CycleDevelopmentDispositionSpec,
    SnapshotPairFixture,
    classify_cycle_source_outcome,
    run_live_evaluation_cycle,
    run_offline_snapshot_cycle,
)
from neuroai_workbench.shadow_refresh.live import run_live_cohort_collection
from neuroai_workbench.util import atomic_write_json, load_json, sha256_bytes, sha256_file
from tests.unit.test_collector_adapters_scheduler import FakeTransport, global_getaddrinfo

FIXTURES = Path(__file__).parents[1] / "fixtures" / "delta"
PREDECESSOR = FIXTURES / "synthetic_predecessor_release.json"


def _authorize_live(monkeypatch: pytest.MonkeyPatch) -> None:
    packet = build_authorization_packet(
        authorization_id="AUTH-EVAL-TEST",
        authorized_by="test-operator",
        purpose="Controlled unit test of live evaluation-cycle quarantine flow.",
        network_mode="AUTHORIZED_NETWORK",
        network_permitted=True,
        authorized_at="2026-09-02T12:00:00Z",
    )
    monkeypatch.setenv(LIVE_COLLECTION_ENV, "1")
    monkeypatch.setenv(LIVE_AUTHORIZATION_ENV, json.dumps(packet))


def _mini_registry() -> list[dict[str, object]]:
    boundary = "Official pages establish representations only; substantive authority is deferred to the final governance overlay."
    return [
        {
            "monitor_id": "MON-SRC-0001",
            "source_id": "SRC-0001",
            "url": "https://example.org/regulatory",
            "publisher": "Example regulator",
            "source_class": "REGULATORY_RECORD",
            "cadence": "WEEKLY",
            "last_successful_retrieval": "2026-07-01",
            "baseline_evidence_state": "CURRENT_SOURCE_RETRIEVED",
            "baseline_verification_state": "CURRENT_VERIFIED",
            "baseline_claim_boundary": boundary,
            "network_access_required": True,
            "current_status": "BASELINE_REGISTERED",
            "next_action": "RETRIEVE_AND_COMPARE",
        },
        {
            "monitor_id": "MON-SRC-0002",
            "source_id": "SRC-0002",
            "url": "https://page.example.org/company",
            "publisher": "Example company",
            "source_class": "OFFICIAL_COMPANY_PAGE",
            "cadence": "MONTHLY",
            "last_successful_retrieval": "2026-07-01",
            "baseline_evidence_state": "CURRENT_SOURCE_RETRIEVED",
            "baseline_verification_state": "CURRENT_VERIFIED",
            "baseline_claim_boundary": boundary,
            "network_access_required": True,
            "current_status": "BASELINE_REGISTERED",
            "next_action": "RETRIEVE_AND_COMPARE",
        },
    ]


def test_classify_cycle_source_outcome_taxonomy() -> None:
    assert classify_cycle_source_outcome(success={"source_id": "S1", "http_status": 200})["outcome_type"] == "SUCCESS"
    assert (
        classify_cycle_source_outcome(success={"source_id": "S1", "http_status": 304})["outcome_type"]
        == "NOT_MODIFIED_304"
    )
    changed = classify_cycle_source_outcome(
        success={"source_id": "S1", "http_status": 200},
        comparison={"classification": "CONTENT_CHANGED_REQUIRES_REVIEW"},
    )
    assert changed["outcome_type"] == "CONTENT_CHANGED"
    assert changed["finding_effect"] == "NONE"

    robots = classify_cycle_source_outcome(
        failure={"source_id": "S1", "failure_class": "ROBOTS_DISALLOWED", "message": "robots.txt disallows"}
    )
    assert robots["outcome_type"] == "ROBOTS_OR_TERMS_BLOCK"
    assert robots["finding_effect"] == "NONE"

    ctype = classify_cycle_source_outcome(
        failure={"source_id": "S1", "failure_class": "CONTENT_TYPE_REJECTED", "message": "Media type bad"}
    )
    assert ctype["outcome_type"] == "CONTENT_TYPE_REJECTED"

    js = classify_cycle_source_outcome(
        failure={"source_id": "S1", "failure_class": "HTTP_ERROR", "message": "javascript render required"}
    )
    assert js["outcome_type"] == "JS_RENDER_REQUIRED"

    gone = classify_cycle_source_outcome(
        failure={"source_id": "S1", "failure_class": "HTTP_ERROR", "failure_message": "Unexpected HTTP status 410"}
    )
    assert gone["outcome_type"] == "WITHDRAWAL_OR_GONE"

    missing = classify_cycle_source_outcome(
        failure={"source_id": "S1", "failure_class": "HTTP_ERROR", "failure_message": "Unexpected HTTP status 404"}
    )
    assert missing["outcome_type"] == "URL_REPLACEMENT_NEEDED"

    assert "TIMEOUT" in SOURCE_OUTCOME_TAXONOMY
    assert "REDIRECT_FAILURE" in SOURCE_OUTCOME_TAXONOMY
    assert "ACCESS_DENIAL" in SOURCE_OUTCOME_TAXONOMY


def test_classify_cycle_source_outcome_additional_fail_closed_paths() -> None:
    unresolved = classify_cycle_source_outcome(
        failure={"source_id": "S1", "failure_class": "OTHER", "failure_message": "opaque failure"}
    )
    assert unresolved["outcome_type"] == "UNRESOLVED_RETRIEVAL"

    fallback = classify_cycle_source_outcome(
        success={"source_id": "S1", "http_status": 200},
        comparison={"classification": "UNRECOGNIZED_CLASSIFICATION"},
    )
    assert fallback["outcome_type"] == "SUCCESS"

    with pytest.raises(ValueError, match="requires success or failure"):
        classify_cycle_source_outcome()


def test_offline_full_cycle_produces_candidate_successor_and_publications(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.json"
    atomic_write_json(registry_path, _mini_registry())
    workspace = tmp_path / "eval_ws"
    output = tmp_path / "out"

    package = run_offline_snapshot_cycle(
        evaluation_workspace=workspace,
        registry_path=registry_path,
        predecessor_path=PREDECESSOR,
        output_dir=output,
        snapshot_pairs=[
            SnapshotPairFixture(
                source_id="SRC-0001",
                baseline_bytes=b"<html>baseline</html>",
                current_bytes=b"<html>changed</html>",
                media_type="text/html",
                retrieval_url="https://example.org/regulatory",
            )
        ],
        refresh_version="eval-cycle-test",
        evidence_cutoff="2026-08-02",
        apply_id="apply-eval-test-001",
        development_disposition=CycleDevelopmentDispositionSpec(
            decision="ACCEPT",
            change_class="FIELD_UPDATE",
            materiality="NON_MATERIAL",
            reopening_effect="NO_EFFECT",
            rationale="Offline development disposition for pipeline proof only.",
        ),
    )

    assert package["status"] == "SHADOW_EVALUATION_NOT_CANONICAL"
    assert package["canonical_successor_written"] is False
    assert package["core_engineering_complete"] is True
    assert package["governance_layer_applied"] is False
    assert package["governance_issue"] == "#101"
    assert package["release_authority_state"] == "DEFERRED"
    assert package["assessment_mutation_performed"] is False
    assert package["monitoring_handoff_kill_switch"] == "DISABLED"
    assert package["metadata"]["stages"] == list(CYCLE_STAGES)
    assert package["source_outcomes"][0]["outcome_type"] == "CONTENT_CHANGED"
    assert package["stats"]["candidates"]["generated"] == 1
    assert package["stats"]["development_disposition"]["governance_layer_applied"] is False
    assert package["stage_results"]["development_disposition"]["scope"] == "DEVELOPMENT_PIPELINE_ONLY"
    assert not (workspace / "observatory" / "review_queue").exists()
    assert package["stage_results"]["collect"]["network_retrieval"] == "SKIPPED_FIXTURE_SNAPSHOTS"
    assert package["stage_results"]["apply_delta"]["predecessor_unchanged"] is True
    assert package["stage_results"]["reopening_analysis"]["assessment_mutation_performed"] is False
    assert package["stage_results"]["publications"]["depth"] == "full"

    successor = load_json(Path(package["stage_results"]["apply_delta"]["successor_path"]))
    assert successor["metadata"]["status"] == "CANDIDATE_SUCCESSOR_NOT_CANONICAL"
    assert successor["sources"][0]["baseline_verification_state"] == "CURRENT_PARTIAL"

    report = load_json(Path(package["report_path"]))
    assert report["status"] == "SHADOW_EVALUATION_NOT_CANONICAL"
    pubs = Path(package["stage_results"]["publications"]["path"])
    assert (pubs / "analytical-workbook.xlsx").is_file()
    assert (pubs / "current-state-report.md").is_file()


def test_offline_cycle_no_change_skips_candidate(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.json"
    atomic_write_json(registry_path, _mini_registry())
    body = b"<html>same</html>"
    package = run_offline_snapshot_cycle(
        evaluation_workspace=tmp_path / "ws",
        registry_path=registry_path,
        predecessor_path=PREDECESSOR,
        output_dir=tmp_path / "out",
        snapshot_pairs=[
            SnapshotPairFixture(
                source_id="SRC-0001",
                baseline_bytes=body,
                current_bytes=body,
                media_type="text/html",
                retrieval_url="https://example.org/regulatory",
            )
        ],
        refresh_version="eval-cycle-same",
        evidence_cutoff="2026-08-02",
        apply_id="apply-eval-same-001",
    )
    assert package["source_outcomes"][0]["outcome_type"] == "NO_CHANGE"
    assert package["stats"]["candidates"]["generated"] == 0
    assert package["stage_results"]["apply_delta"]["status"] == "CANDIDATE_SUCCESSOR_NOT_CANONICAL"


def test_live_cycle_requires_gate_and_handoff_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(LIVE_COLLECTION_ENV, raising=False)
    registry_path = tmp_path / "registry.json"
    atomic_write_json(registry_path, _mini_registry())
    with pytest.raises(PermissionError, match=LIVE_COLLECTION_ENV):
        run_live_evaluation_cycle(
            evaluation_workspace=tmp_path / "ws",
            registry_path=registry_path,
            predecessor_path=PREDECESSOR,
            quarantine_root=tmp_path / "q",
            output_dir=tmp_path / "out",
            refresh_version="eval-live",
            evidence_cutoff="2026-08-02",
            apply_id="apply-live-001",
            approve_handoff=True,
        )

    _authorize_live(monkeypatch)
    with pytest.raises(PermissionError, match="approve_handoff"):
        run_live_evaluation_cycle(
            evaluation_workspace=tmp_path / "ws",
            registry_path=registry_path,
            predecessor_path=PREDECESSOR,
            quarantine_root=tmp_path / "q",
            output_dir=tmp_path / "out",
            refresh_version="eval-live",
            evidence_cutoff="2026-08-02",
            apply_id="apply-live-001",
        )
    with pytest.raises(PermissionError, match="approve_handoff"):
        run_live_evaluation_cycle(
            evaluation_workspace=tmp_path / "ws",
            registry_path=registry_path,
            predecessor_path=PREDECESSOR,
            quarantine_root=tmp_path / "q",
            output_dir=tmp_path / "out",
            refresh_version="eval-live",
            evidence_cutoff="2026-08-02",
            apply_id="apply-live-001",
            approve_handoff=False,
        )


def test_live_cycle_with_injected_transport_and_baseline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _authorize_live(monkeypatch)
    url = "https://page.example.org/company"
    registry_path = tmp_path / "registry.json"
    atomic_write_json(
        registry_path,
        [
            {
                "monitor_id": "MON-SRC-0002",
                "source_id": "SRC-0002",
                "url": url,
                "publisher": "Example company",
                "source_class": "OFFICIAL_COMPANY_PAGE",
                "cadence": "MONTHLY",
                "last_successful_retrieval": "2026-07-01",
                "baseline_evidence_state": "CURRENT_SOURCE_RETRIEVED",
                "baseline_verification_state": "CURRENT_VERIFIED",
                "baseline_claim_boundary": "Synthetic boundary.",
                "network_access_required": True,
                "current_status": "BASELINE_REGISTERED",
                "next_action": "RETRIEVE_AND_COMPARE",
            }
        ],
    )
    workspace = tmp_path / "ws"
    initialize_monitoring(workspace, registry_path, actor="tester")
    record_snapshot(
        workspace,
        "SRC-0002",
        b"<html>baseline-live</html>",
        media_type="text/html",
        retrieved_at="2026-08-01T10:00:00Z",
        retrieval_url=url,
        actor="tester",
    )

    transport = FakeTransport(responses={url: (200, {"content-type": "text/html"}, b"<html>changed-live</html>")})
    plan = {
        "plan_id": "PLAN-EVAL-LIVE",
        "as_of": "2026-08-02",
        "due": [
            {
                "source_id": "SRC-0002",
                "monitor_id": "MON-SRC-0002",
                "url": url,
                "publisher": "Example company",
                "source_class": "OFFICIAL_COMPANY_PAGE",
                "cadence": "MONTHLY",
                "network_access_required": True,
            }
        ],
        "manual": [],
        "not_due": [],
        "counts": {"due": 1, "manual": 0, "not_due": 0},
    }
    quarantine_root = tmp_path / "quarantine"
    registry = load_source_registry(registry_path)
    run_live_cohort_collection(
        plan=plan,
        registry=registry,
        registry_sha256=sha256_file(registry_path),
        quarantine_root=quarantine_root,
        transport=transport,
        dns_guard=DnsGuard(getaddrinfo=global_getaddrinfo),
    )
    for record in list_quarantine_successes(quarantine_root):
        approve_quarantine_record(
            quarantine_root,
            str(record["quarantine_id"]),
            approved_by="tester",
        )

    package = run_live_evaluation_cycle(
        evaluation_workspace=workspace,
        registry_path=registry_path,
        predecessor_path=PREDECESSOR,
        quarantine_root=quarantine_root,
        output_dir=tmp_path / "out",
        refresh_version="eval-live-injected",
        evidence_cutoff="2026-08-02",
        apply_id="apply-live-injected-001",
        plan=plan,
        sample_size=1,
        transport=transport,
        dns_guard=DnsGuard(getaddrinfo=global_getaddrinfo),
        approve_handoff=True,
        development_disposition=CycleDevelopmentDispositionSpec(
            rationale="Injected-transport live development path proof.",
        ),
    )
    assert package["metadata"]["mode"] == "live"
    assert package["status"] == "SHADOW_EVALUATION_NOT_CANONICAL"
    assert package["stage_results"]["collect"]["network_retrieval"] == "EXECUTED_LIVE_QUARANTINE_ONLY"
    assert package["monitoring_handoff_kill_switch"] == "DISABLED"
    assert any(item["outcome_type"] == "CONTENT_CHANGED" for item in package["source_outcomes"])
    assert package["stats"]["candidates"]["generated"] >= 1
    assert Path(package["stage_results"]["apply_delta"]["successor_path"]).is_file()


def test_live_cycle_without_prior_snapshot_creates_first_capture_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _authorize_live(monkeypatch)
    url = "https://example.org/first-capture"
    registry_path = tmp_path / "registry.json"
    atomic_write_json(
        registry_path,
        [
            {
                "monitor_id": "MON-SRC-0003",
                "source_id": "SRC-0003",
                "url": url,
                "publisher": "Example org",
                "source_class": "OFFICIAL_COMPANY_PAGE",
                "cadence": "MONTHLY",
                "last_successful_retrieval": "2026-07-01",
                "baseline_evidence_state": "CURRENT_SOURCE_RETRIEVED",
                "baseline_verification_state": "CURRENT_VERIFIED",
                "baseline_claim_boundary": "Synthetic boundary.",
                "network_access_required": True,
                "current_status": "BASELINE_REGISTERED",
                "next_action": "RETRIEVE_AND_COMPARE",
            }
        ],
    )
    body = b"<html>first capture</html>"
    digest = sha256_bytes(body)
    quarantine_root = tmp_path / "quarantine"
    relative = f"incoming/SRC-0003/{digest[:12]}/index.html"
    capture_path = quarantine_root / relative
    capture_path.parent.mkdir(parents=True, exist_ok=True)
    capture_path.write_bytes(body)
    atomic_write_json(
        quarantine_root / "records" / "QRN-11111111111111111111111111111111.json",
        {
            "quarantine_id": "QRN-11111111111111111111111111111111",
            "source_id": "SRC-0003",
            "monitor_id": "MON-SRC-0003",
            "result_id": "CRES-11111111111111111111111111111111",
            "captured_at": "2026-08-02T23:00:00Z",
            "sha256": digest,
            "size_bytes": len(body),
            "quarantine_path": relative,
            "original_filename": "index.html",
            "approval_state": "APPROVED_FOR_HANDOFF",
            "approved_at": "2026-08-03T00:00:00Z",
            "approved_by": "tester",
            "rejection_reason": None,
            "collector_version": "test",
            "configuration_hash": "a" * 64,
            "boundary": "test",
        },
    )
    atomic_write_json(
        quarantine_root / "results" / "CRES-11111111111111111111111111111111.json",
        {
            "result_id": "CRES-11111111111111111111111111111111",
            "request_id": "CREQ-11111111111111111111111111111111",
            "source_id": "SRC-0003",
            "monitor_id": "MON-SRC-0003",
            "requested_url": url,
            "final_url": url,
            "retrieved_at": "2026-08-02T23:00:00Z",
            "http_status": 200,
            "media_type": "text/html",
            "sha256": digest,
            "size_bytes": len(body),
            "quarantine_path": relative,
            "original_filename": "index.html",
            "evidence_state": "RETRIEVED_BYTES_NOT_SUBSTANTIVELY_ADJUDICATED",
            "collector_version": "test",
            "configuration_hash": "a" * 64,
            "dns_resolution": [],
            "redirect_chain": [],
            "boundary": "test",
        },
    )
    monkeypatch.setattr(
        "neuroai_workbench.shadow_refresh.cycle.run_live_cohort_collection",
        lambda **_: {
            "collection_run": {
                "run_id": "CRUN-FIRST",
                "status": "COMPLETE",
                "counts": {"total": 1, "succeeded": 1, "failed": 0, "skipped": 0},
                "outcomes": [
                    {
                        "source_id": "SRC-0003",
                        "adapter_id": "json_api",
                        "status": "RESULT",
                        "record_id": "CRES-11111111111111111111111111111111",
                    }
                ],
            },
            "capture_digests": [
                {
                    "source_id": "SRC-0003",
                    "result_id": "CRES-11111111111111111111111111111111",
                    "sha256": digest,
                    "http_status": 200,
                    "size_bytes": len(body),
                    "media_type": "text/html",
                    "final_url": url,
                }
            ],
            "failure_summaries": [],
        },
    )

    package = run_live_evaluation_cycle(
        evaluation_workspace=tmp_path / "ws",
        registry_path=registry_path,
        predecessor_path=PREDECESSOR,
        quarantine_root=quarantine_root,
        output_dir=tmp_path / "out",
        refresh_version="eval-live-first-capture",
        evidence_cutoff="2026-08-02",
        apply_id="apply-live-first-capture-001",
        approve_handoff=True,
    )

    assert package["stage_results"]["compare_snapshots"]["count"] == 0
    assert package["stage_results"]["compare_snapshots"]["first_capture_without_baseline"] == 1
    assert package["stage_results"]["create_change_candidate"]["count"] == 1
    assert package["source_outcomes"][0]["outcome_type"] == "MANUAL_FIRST_CAPTURE"
