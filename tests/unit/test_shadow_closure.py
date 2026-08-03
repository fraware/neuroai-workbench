"""Unit tests for Wave 2 shadow refresh closure helpers (network-free)."""

from __future__ import annotations

from pathlib import Path

from neuroai_workbench.collector.handoff import approve_quarantine_record, load_quarantine_record
from neuroai_workbench.shadow_refresh.closure import (
    build_closure_run_results,
    build_source_retry_plan,
    classify_retrieval_failure,
    compute_closure_metrics,
    create_first_capture_candidates,
    handoff_quarantine_sample_to_evaluation,
    record_formal_disposition,
    scaffold_dual_human_review,
)
from neuroai_workbench.shadow_refresh.schemas import validate_shadow_refresh_run_results
from neuroai_workbench.util import atomic_write_json, sha256_bytes


def _mini_registry() -> list[dict[str, object]]:
    boundary = "Official pages establish representations only; human adjudication controls all substantive effects."
    return [
        {
            "monitor_id": "MON-SRC-0001",
            "source_id": "SRC-0001",
            "url": "https://example.org/one",
            "publisher": "Example Org One",
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
        {
            "monitor_id": "MON-SRC-0002",
            "source_id": "SRC-0002",
            "url": "https://example.org/two",
            "publisher": "Example Org Two",
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


def _seed_quarantine(root: Path, *, source_id: str = "SRC-0001", body: bytes = b"<html>hello</html>") -> str:
    digest = sha256_bytes(body)
    qid = "QRN-" + ("ab" * 16)
    rid = "CRES-" + ("cd" * 16)
    relative = f"incoming/{source_id}/{digest[:12]}/index.html"
    bytes_path = root / relative
    bytes_path.parent.mkdir(parents=True, exist_ok=True)
    bytes_path.write_bytes(body)
    (root / "records").mkdir(parents=True, exist_ok=True)
    (root / "results").mkdir(parents=True, exist_ok=True)
    atomic_write_json(
        root / "records" / f"{qid}.json",
        {
            "quarantine_id": qid,
            "source_id": source_id,
            "monitor_id": f"MON-{source_id}",
            "result_id": rid,
            "captured_at": "2026-08-02T23:00:00Z",
            "sha256": digest,
            "size_bytes": len(body),
            "quarantine_path": relative,
            "original_filename": "index.html",
            "approval_state": "PENDING_HUMAN_APPROVAL",
            "approved_at": None,
            "approved_by": None,
            "rejection_reason": None,
            "collector_version": "test",
            "configuration_hash": "a" * 64,
            "boundary": "test",
        },
    )
    atomic_write_json(
        root / "results" / f"{rid}.json",
        {
            "result_id": rid,
            "request_id": "CREQ-" + ("ef" * 16),
            "source_id": source_id,
            "monitor_id": f"MON-{source_id}",
            "requested_url": "https://example.org/one",
            "final_url": "https://example.org/one",
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
    return qid


def test_classify_retrieval_failure_typed_outcomes() -> None:
    access = classify_retrieval_failure(
        {
            "source_id": "SRC-0041",
            "failure_class": "HTTP_ERROR",
            "failure_message": "Unexpected HTTP status 403",
            "requested_url": "https://www.medtronic.com/",
        }
    )
    assert access["outcome_type"] == "ACCESS_DENIAL"
    assert access["http_status"] == 403
    assert access["finding_effect"] == "NONE"

    missing = classify_retrieval_failure(
        {
            "source_id": "SRC-0115",
            "failure_class": "HTTP_ERROR",
            "failure_message": "Unexpected HTTP status 404",
        }
    )
    assert missing["outcome_type"] == "CONTENT_NOT_FOUND_OR_URL_REPLACEMENT_NEEDED"
    assert missing["finding_effect"] == "NONE"


def test_build_source_retry_plan_limits_due_set() -> None:
    from neuroai_workbench.monitoring import normalize_source_registry

    plan = build_source_retry_plan(normalize_source_registry(_mini_registry()), ["SRC-0001"])
    assert plan["counts"]["due"] == 1
    assert plan["due"][0]["source_id"] == "SRC-0001"
    assert plan["status"] == "SHADOW_EVALUATION_NOT_CANONICAL"


def test_wave2_public_summary_fixture_remains_non_canonical() -> None:
    from pathlib import Path

    from neuroai_workbench.util import load_json

    path = (
        Path(__file__).resolve().parents[2]
        / "examples"
        / "shadow_refresh"
        / "SHADOW_REFRESH_WAVE2_PUBLIC_SUMMARY_v202608.json"
    )
    summary = load_json(path)
    assert summary["metadata"]["status"] == "SHADOW_EVALUATION_NOT_CANONICAL"
    assert summary["formal_disposition"] == "WITHHELD"
    assert summary["dual_review_complete"] is False
    assert summary["metrics_recommendation"] == "NO_GO"
    assert len(summary["retry_outcomes"]) == 3
    assert all(item.get("finding_effect") == "NONE" for item in summary["retry_outcomes"])


def test_formal_disposition_withheld_without_dual_review() -> None:
    formal = record_formal_disposition(
        run_id="SHADOW-RUN-TEST",
        metrics_recommendation="NO_GO",
        dual_review_complete=False,
        owners=["owner"],
        residual_checklist=[{"id": "DUAL_REVIEW_OPINIONS", "state": "BLOCKED_HUMAN"}],
    )
    assert formal["disposition"] == "WITHHELD"
    assert formal["canonical_successor_written"] is False
    assert formal["dual_review_complete"] is False


def test_formal_disposition_no_go_when_dual_review_complete_but_metrics_fail() -> None:
    formal = record_formal_disposition(
        run_id="SHADOW-RUN-TEST",
        metrics_recommendation="NO_GO",
        dual_review_complete=True,
        owners=["owner"],
        residual_checklist=[],
    )
    assert formal["disposition"] == "NO_GO"


def test_closure_run_results_and_metrics_validate() -> None:
    results = build_closure_run_results(
        run_id="SHADOW-RUN-TEST",
        live_succeeded=22,
        live_failed=3,
        live_attempted=25,
        digest_count=22,
        candidate_count=5,
        entity_decisions=5,
        entity_correct=0,
        dual_review_complete=False,
    )
    assert validate_shadow_refresh_run_results(results) == []
    metrics = compute_closure_metrics(results, generated_by="test")
    assert metrics["evaluation"]["recommendation"] in {"GO", "NO_GO", "INCOMPLETE"}
    assert metrics["metadata"]["status"] == "SHADOW_EVALUATION_NOT_CANONICAL"


def test_evaluation_handoff_and_dual_review_scaffold(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.json"
    atomic_write_json(registry_path, _mini_registry())
    quarantine = tmp_path / "quarantine"
    qid = _seed_quarantine(quarantine)
    approve_quarantine_record(quarantine, qid, approved_by="tester")
    evaluation = tmp_path / "eval_ws"
    handoff = handoff_quarantine_sample_to_evaluation(
        quarantine_root=quarantine,
        evaluation_workspace=evaluation,
        registry_path=registry_path,
        sample_size=1,
        approved_by="tester",
    )
    assert len(handoff["handoffs"]) == 1
    assert handoff["canonical_workbench_mutated"] is False
    assert handoff["monitoring_handoff_kill_switch"] == "DISABLED"

    candidates = create_first_capture_candidates(
        evaluation_workspace=evaluation,
        handoffs=handoff["handoffs"],
        actor="tester",
    )
    assert len(candidates["candidates"]) == 1
    assert candidates["baseline_comparison"] == "UNAVAILABLE_NO_PRIOR_SNAPSHOTS"

    out = tmp_path / "wave2"
    review = scaffold_dual_human_review(
        evaluation_workspace=evaluation,
        output_dir=out,
        actor="tester",
    )
    assert review["dual_review_complete"] is False
    assert review["open_item_count"] == 1
    assert (out / "dual_review_instructions.json").is_file()
    assert (out / "human_residual_checklist.json").is_file()


def test_evaluation_handoff_refuses_pending_without_auto_approve(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.json"
    atomic_write_json(registry_path, _mini_registry())
    quarantine = tmp_path / "quarantine"
    qid = _seed_quarantine(quarantine)
    assert load_quarantine_record(quarantine, qid)["approval_state"] == "PENDING_HUMAN_APPROVAL"

    handoff = handoff_quarantine_sample_to_evaluation(
        quarantine_root=quarantine,
        evaluation_workspace=tmp_path / "eval_ws",
        registry_path=registry_path,
        sample_size=1,
        approved_by="tester",
    )
    assert handoff["handoffs"] == []
    assert load_quarantine_record(quarantine, qid)["approval_state"] == "PENDING_HUMAN_APPROVAL"
