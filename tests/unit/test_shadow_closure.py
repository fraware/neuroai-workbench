"""Unit tests for Wave 2 shadow refresh closure helpers (network-free)."""

from __future__ import annotations

from pathlib import Path

import pytest

from neuroai_workbench.collector.handoff import approve_quarantine_record, load_quarantine_record
from neuroai_workbench.shadow_refresh.closure import (
    GOVERNANCE_ISSUE,
    assess_dual_human_review,
    build_closure_run_results,
    build_source_retry_plan,
    classify_retrieval_failure,
    compute_closure_metrics,
    create_first_capture_candidates,
    handoff_quarantine_sample_to_evaluation,
    retry_failed_sources,
    record_formal_disposition,
    record_human_review_opinion,
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
    assert summary["formal_disposition"] == "NO_GO"
    assert summary["dual_review_complete"] is True
    assert summary["metrics_recommendation"] == "NO_GO"
    assert summary.get("url_owner_disposition") == "KEEP_AS_TYPED_FAILURE"
    assert summary["metadata"]["governance_issue"] == "#101"
    assert len(summary["retry_outcomes"]) == 3
    assert all(item.get("finding_effect") == "NONE" for item in summary["retry_outcomes"])
    post = summary.get("post_integrity_http_error_retry") or {}
    assert post.get("outcomes_unchanged") is True


def test_post_integrity_retry_public_digest_remains_non_canonical() -> None:
    from neuroai_workbench.util import load_json

    path = (
        Path(__file__).resolve().parents[2]
        / "examples"
        / "shadow_refresh"
        / "SHADOW_REFRESH_POST_INTEGRITY_RETRY_PUBLIC_v202608.json"
    )
    digest = load_json(path)
    assert digest["metadata"]["status"] == "SHADOW_EVALUATION_NOT_CANONICAL"
    assert digest["metadata"]["governance_issue"] == "#101"
    assert digest["live_retry_executed"] is True
    assert len(digest["retry_outcomes"]) == 3
    assert all(item.get("finding_effect") == "NONE" for item in digest["retry_outcomes"])


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
    from neuroai_workbench.util import load_json

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
    instructions = load_json(out / "dual_review_instructions.json")
    residual = load_json(out / "human_residual_checklist.json")
    assert instructions["metadata"]["governance_issue"] == GOVERNANCE_ISSUE
    assert residual["metadata"]["governance_issue"] == GOVERNANCE_ISSUE
    assert "record_shadow_dual_review.py" in instructions["recording_cli"]


def test_dual_review_recording_and_assessment_without_forged_go(tmp_path: Path) -> None:
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
    create_first_capture_candidates(
        evaluation_workspace=evaluation,
        handoffs=handoff["handoffs"],
        actor="tester",
    )
    out = tmp_path / "wave2"
    scaffold_dual_human_review(evaluation_workspace=evaluation, output_dir=out, actor="tester")

    incomplete = assess_dual_human_review(evaluation)
    assert incomplete["dual_review_complete"] is False
    assert incomplete["incomplete_item_count"] == 1
    item_id = incomplete["items"][0]["item_id"]

    first = record_human_review_opinion(
        evaluation,
        item_id=item_id,
        reviewer_profile_id="REV-SHADOW-A",
        position="SUPPORT",
        rationale="Human A supports the first-capture candidate for shadow evaluation only.",
    )
    assert first["dual_review_complete"] is False

    second = record_human_review_opinion(
        evaluation,
        item_id=item_id,
        reviewer_profile_id="REV-SHADOW-B",
        position="OPPOSE",
        rationale="Human B records disagreement; dissent must remain visible.",
    )
    assert second["dual_review_complete"] is True
    assert second["assessment"]["review_disagreements"] == 1

    withheld = record_formal_disposition(
        run_id="SHADOW-RUN-TEST",
        metrics_recommendation="GO",
        dual_review_complete=False,
        owners=["owner"],
        residual_checklist=[],
    )
    assert withheld["disposition"] == "WITHHELD"
    assert withheld["metadata"]["governance_issue"] == GOVERNANCE_ISSUE

    after_dual = record_formal_disposition(
        run_id="SHADOW-RUN-TEST",
        metrics_recommendation="NO_GO",
        dual_review_complete=True,
        owners=["owner"],
        residual_checklist=[],
    )
    assert after_dual["disposition"] == "NO_GO"


def test_record_shadow_dual_review_cli_refuses_forged_go(tmp_path: Path) -> None:
    import importlib.util
    from pathlib import Path as PathType

    script_path = PathType(__file__).resolve().parents[2] / "scripts" / "record_shadow_dual_review.py"
    spec = importlib.util.spec_from_file_location("record_shadow_dual_review_cli", script_path)
    assert spec is not None and spec.loader is not None
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)

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
    create_first_capture_candidates(
        evaluation_workspace=evaluation,
        handoffs=handoff["handoffs"],
        actor="tester",
    )
    scaffold_dual_human_review(
        evaluation_workspace=evaluation,
        output_dir=tmp_path / "out",
        actor="tester",
    )

    assert (
        cli.main(
            [
                "--evaluation-workspace",
                str(evaluation),
                "formal-disposition",
                "--run-id",
                "SHADOW-RUN-CLI",
                "--owners",
                "owner-a",
                "--metrics-recommendation",
                "GO",
                "--disposition-override",
                "GO",
                "--allow-incomplete",
            ]
        )
        == 2
    )
    assert (
        cli.main(
            [
                "--evaluation-workspace",
                str(evaluation),
                "assess",
            ]
        )
        == 1
    )


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


def test_retry_failed_sources_and_review_opinion_validation_edges(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registry = {"sources": _mini_registry()}
    quarantine = tmp_path / "retry"
    (quarantine / "failures").mkdir(parents=True, exist_ok=True)
    (quarantine / "failures" / "corrupt.json").write_text("{not-json", encoding="utf-8")
    atomic_write_json(
        quarantine / "failures" / "failure.json",
        {
            "source_id": "SRC-0001",
            "failure_class": "HTTP_ERROR",
            "failure_message": "Unexpected HTTP status 404",
        },
    )
    monkeypatch.setattr(
        "neuroai_workbench.shadow_refresh.closure.run_live_cohort_collection",
        lambda **_: {
            "collection_run": {
                "outcomes": [
                    {"source_id": "", "status": "FAILURE"},
                    {"source_id": "SRC-0002", "status": "FAILURE", "failure_class": "DNS_FAILURE"},
                ]
            }
        },
    )
    retried = retry_failed_sources(
        registry=registry,
        registry_sha256="a" * 64,
        quarantine_root=quarantine,
        source_ids=["SRC-0001", "SRC-0002"],
    )
    assert [item["outcome_type"] for item in retried["typed_outcomes"]] == [
        "CONTENT_NOT_FOUND_OR_URL_REPLACEMENT_NEEDED",
        "DNS_FAILURE",
    ]

    registry_path = tmp_path / "registry.json"
    atomic_write_json(registry_path, _mini_registry())
    qid = _seed_quarantine(tmp_path / "quarantine-review")
    approve_quarantine_record(tmp_path / "quarantine-review", qid, approved_by="tester")
    handoff = handoff_quarantine_sample_to_evaluation(
        quarantine_root=tmp_path / "quarantine-review",
        evaluation_workspace=tmp_path / "eval",
        registry_path=registry_path,
        sample_size=1,
        approved_by="tester",
    )
    create_first_capture_candidates(
        evaluation_workspace=tmp_path / "eval",
        handoffs=handoff["handoffs"],
        actor="tester",
    )
    item_id = assess_dual_human_review(tmp_path / "eval")["items"][0]["item_id"]

    with pytest.raises(ValueError, match="accepts only"):
        record_human_review_opinion(
            tmp_path / "eval",
            item_id=item_id,
            reviewer_profile_id="REV-OTHER",
            position="SUPPORT",
            rationale="x",
        )
    with pytest.raises(ValueError, match="Unsupported opinion position"):
        record_human_review_opinion(
            tmp_path / "eval",
            item_id=item_id,
            reviewer_profile_id="REV-SHADOW-A",
            position="MAYBE",
            rationale="x",
        )
    with pytest.raises(ValueError, match="must not be empty"):
        record_human_review_opinion(
            tmp_path / "eval",
            item_id=item_id,
            reviewer_profile_id="REV-SHADOW-A",
            position="SUPPORT",
            rationale="   ",
        )
    with pytest.raises(ValueError, match="Unknown queue item"):
        record_human_review_opinion(
            tmp_path / "eval",
            item_id="QUEUE-UNKNOWN",
            reviewer_profile_id="REV-SHADOW-A",
            position="SUPPORT",
            rationale="Known reviewer.",
        )
