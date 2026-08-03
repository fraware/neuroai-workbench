"""Non-canonical full evaluation operating cycle (Wave 3).

Orchestrates plan → collect → quarantine handoff → snapshot → compare →
candidate → adjudicate → refresh → delta → apply → reopening → publications.

Artifacts remain SHADOW_EVALUATION_NOT_CANONICAL. Live network steps require
NEUROAI_LIVE_COLLECTION=1. Offline/unit paths use fixtures and never open the
network. No stage grants automation authority to mutate assessments or publish
a canonical successor (#41 remains separate).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ..collector.dns import DnsGuard
from ..collector.http_client import HttpTransport
from ..delta import apply_delta, compile_adjudicated_delta
from ..monitoring import (
    adjudicate_change_candidate,
    build_refresh_candidate,
    compare_snapshots,
    create_change_candidate,
    initialize_monitoring,
    load_source_registry,
    plan_monitoring_run,
    record_snapshot,
)
from ..products.generate import generate_publication_set, reconcile_formats
from ..products.query import query_release
from ..reopening import analyze_observatory_delta
from ..util import atomic_write_json, load_json, sha256_bytes, sha256_file, utc_now
from .closure import (
    classify_retrieval_failure,
    handoff_quarantine_sample_to_evaluation,
    list_quarantine_successes,
)
from .live import (
    require_live_collection_enabled,
    run_live_cohort_collection,
)
from .schemas import SHADOW_EVALUATION_STATUS, SHADOW_REFRESH_BOUNDARY

EVAL_CYCLE_ACTOR = "shadow-eval-cycle"

CYCLE_STAGES = (
    "plan",
    "collect",
    "quarantine_approve_handoff",
    "record_snapshot",
    "compare_snapshots",
    "create_change_candidate",
    "adjudicate",
    "build_refresh_candidate",
    "compile_adjudicated_delta",
    "apply_delta",
    "reopening_analysis",
    "publications",
)

# Per-source retrieval / comparison outcome taxonomy (not findings).
SOURCE_OUTCOME_TAXONOMY = frozenset(
    {
        "SUCCESS",
        "NOT_MODIFIED_304",
        "CONTENT_CHANGED",
        "NO_CHANGE",
        "NON_MATERIAL_REPRESENTATION_CHANGE",
        "REDIRECT_FAILURE",
        "ACCESS_DENIAL",
        "ROBOTS_OR_TERMS_BLOCK",
        "JS_RENDER_REQUIRED",
        "CONTENT_TYPE_REJECTED",
        "TIMEOUT",
        "WITHDRAWAL_OR_GONE",
        "URL_REPLACEMENT_NEEDED",
        "DNS_FAILURE",
        "POLICY_BLOCK",
        "HTTP_ERROR_UNCLASSIFIED",
        "UNRESOLVED_RETRIEVAL",
        "MANUAL_FIRST_CAPTURE",
        "SKIPPED_NO_NETWORK",
    }
)

CycleMode = Literal["offline", "live"]


@dataclass(frozen=True)
class CycleAdjudicationSpec:
    """Explicit human-supplied adjudication for evaluation scaffolding.

    Reviewer IDs remain claimed local workflow identities. Specs do not forge
    dual-review completion or GO authorization.
    """

    decision: str = "ACCEPT"
    change_class: str = "FIELD_UPDATE"
    materiality: str = "NON_MATERIAL"
    reopening_effect: str = "NO_EFFECT"
    rationale: str = (
        "Evaluation-cycle scaffolding adjudication for non-canonical pipeline proof only."
    )


@dataclass(frozen=True)
class SnapshotPairFixture:
    """Offline fixture: baseline then current bytes for mechanical comparison."""

    source_id: str
    baseline_bytes: bytes
    current_bytes: bytes
    media_type: str = "text/html"
    retrieval_url: str | None = None


def classify_cycle_source_outcome(
    *,
    success: dict[str, Any] | None = None,
    failure: dict[str, Any] | None = None,
    comparison: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map retrieval / comparison evidence into the cycle outcome taxonomy.

    Never converts unresolved access into a FAIL finding.
    """
    if failure is not None:
        typed = classify_retrieval_failure(failure)
        outcome_type = str(typed.get("outcome_type") or "UNRESOLVED_RETRIEVAL")
        failure_class = str(failure.get("failure_class") or typed.get("failure_class") or "")
        message = str(failure.get("failure_message") or failure.get("message") or "").casefold()
        http_status = typed.get("http_status")

        if failure_class in {"ROBOTS_DISALLOWED", "TERMS_OF_USE_BLOCKED"} or "robots" in message or "terms" in message:
            outcome_type = "ROBOTS_OR_TERMS_BLOCK"
        elif failure_class == "CONTENT_TYPE_REJECTED" or "content-type" in message or "media type" in message:
            outcome_type = "CONTENT_TYPE_REJECTED"
        elif "javascript" in message or "js-render" in message or "browser required" in message:
            outcome_type = "JS_RENDER_REQUIRED"
        elif http_status == 410 or "withdraw" in message or "gone" in message:
            outcome_type = "WITHDRAWAL_OR_GONE"
        elif outcome_type == "CONTENT_NOT_FOUND_OR_URL_REPLACEMENT_NEEDED":
            outcome_type = "URL_REPLACEMENT_NEEDED"
        elif outcome_type not in SOURCE_OUTCOME_TAXONOMY:
            outcome_type = "UNRESOLVED_RETRIEVAL"

        return {
            "source_id": failure.get("source_id") or typed.get("source_id"),
            "outcome_type": outcome_type,
            "finding_effect": "NONE",
            "http_status": http_status,
            "failure_class": failure_class or None,
            "comparison_classification": None,
            "notes": typed.get("notes"),
            "status": SHADOW_EVALUATION_STATUS,
            "boundary": SHADOW_REFRESH_BOUNDARY,
        }

    if success is not None:
        http_status = success.get("http_status")
        if http_status == 304:
            outcome_type = "NOT_MODIFIED_304"
        elif comparison is not None:
            classification = str(comparison.get("classification") or "")
            if classification == "CONTENT_CHANGED_REQUIRES_REVIEW":
                outcome_type = "CONTENT_CHANGED"
            elif classification == "NO_CHANGE":
                outcome_type = "NO_CHANGE"
            elif classification == "NON_MATERIAL_REPRESENTATION_CHANGE":
                outcome_type = "NON_MATERIAL_REPRESENTATION_CHANGE"
            else:
                outcome_type = "SUCCESS"
        else:
            outcome_type = "SUCCESS"
        return {
            "source_id": success.get("source_id"),
            "outcome_type": outcome_type,
            "finding_effect": "NONE",
            "http_status": http_status,
            "failure_class": None,
            "comparison_classification": (comparison or {}).get("classification"),
            "notes": "Typed retrieval/comparison outcome only; not a substantive finding.",
            "status": SHADOW_EVALUATION_STATUS,
            "boundary": SHADOW_REFRESH_BOUNDARY,
        }

    raise ValueError("classify_cycle_source_outcome requires success or failure evidence")


def _ensure_monitoring(workspace: Path, registry_path: Path, *, actor: str) -> None:
    marker = workspace / "observatory" / "monitoring" / "registry" / "registry.json"
    if not marker.is_file():
        initialize_monitoring(workspace, registry_path, actor=actor)


def _default_operation_specs(candidates: list[dict[str, Any]], predecessor: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Build minimal ADD_EVENT specs for accepted candidates when none are supplied."""
    known_sources = {
        str(item.get("source_id"))
        for item in predecessor.get("sources", [])
        if isinstance(item, dict) and item.get("source_id")
    }
    specs: dict[str, list[dict[str, Any]]] = {}
    for index, candidate in enumerate(candidates, start=1):
        candidate_id = str(candidate["candidate_id"])
        source_id = str(candidate["source_id"])
        if source_id in known_sources:
            specs[candidate_id] = [
                {
                    "operation_type": "UPDATE_FIELD_WITH_PREDECESSOR",
                    "target_section": "sources",
                    "record_id_field": "source_id",
                    "record_id": source_id,
                    "field": "baseline_verification_state",
                    "before_value": "CURRENT_VERIFIED",
                    "after_value": "CURRENT_PARTIAL",
                }
            ]
        else:
            specs[candidate_id] = [
                {
                    "operation_type": "ADD_EVENT",
                    "target_section": "regulatory_and_market_events",
                    "record": {
                        "event_id": f"REG-EVAL-{index:03d}",
                        "event_date": "2026-08-02",
                        "source_ids": [source_id],
                        "evidence_state": "EVALUATION_CYCLE_NON_CANONICAL",
                        "summary": f"Non-canonical evaluation-cycle event for {source_id}.",
                    },
                }
            ]
    return specs


def run_offline_snapshot_cycle(
    *,
    evaluation_workspace: Path,
    registry_path: Path,
    predecessor_path: Path,
    output_dir: Path,
    snapshot_pairs: list[SnapshotPairFixture],
    refresh_version: str,
    evidence_cutoff: str,
    apply_id: str,
    adjudication: CycleAdjudicationSpec | None = None,
    operation_specs: dict[str, list[dict[str, Any]]] | None = None,
    actor: str = EVAL_CYCLE_ACTOR,
    as_of: str = "2026-08-02",
) -> dict[str, Any]:
    """Execute the full evaluation cycle from fixture snapshot pairs (network-free)."""
    if not snapshot_pairs:
        raise ValueError("snapshot_pairs must be non-empty for the offline cycle")
    adj = adjudication or CycleAdjudicationSpec()
    evaluation_workspace = evaluation_workspace.resolve()
    registry_path = registry_path.resolve()
    predecessor_path = predecessor_path.resolve()
    output_dir = output_dir.resolve()
    evaluation_workspace.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    _ensure_monitoring(evaluation_workspace, registry_path, actor=actor)

    registry = load_source_registry(registry_path)
    plan = plan_monitoring_run(evaluation_workspace, as_of=as_of)
    stage_results: dict[str, Any] = {
        "plan": {
            "plan_id": plan.get("plan_id"),
            "counts": plan.get("counts"),
            "status": SHADOW_EVALUATION_STATUS,
        },
        "collect": {
            "mode": "offline",
            "network_retrieval": "SKIPPED_FIXTURE_SNAPSHOTS",
            "status": SHADOW_EVALUATION_STATUS,
        },
    }

    source_outcomes: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    adjudications: list[dict[str, Any]] = []
    handoffs: list[dict[str, Any]] = []

    for pair in snapshot_pairs:
        baseline = record_snapshot(
            evaluation_workspace,
            pair.source_id,
            pair.baseline_bytes,
            media_type=pair.media_type,
            retrieved_at="2026-08-01T12:00:00Z",
            retrieval_url=pair.retrieval_url,
            actor=actor,
        )
        current = record_snapshot(
            evaluation_workspace,
            pair.source_id,
            pair.current_bytes,
            media_type=pair.media_type,
            retrieved_at="2026-08-02T12:00:00Z",
            retrieval_url=pair.retrieval_url,
            actor=actor,
        )
        handoffs.append(
            {
                "source_id": pair.source_id,
                "baseline_snapshot_id": baseline["snapshot_id"],
                "snapshot_id": current["snapshot_id"],
                "sha256": current["sha256"],
                "size_bytes": current["size_bytes"],
                "media_type": pair.media_type,
            }
        )
        comparison = compare_snapshots(
            evaluation_workspace,
            pair.source_id,
            baseline["snapshot_id"],
            current["snapshot_id"],
        )
        comparisons.append(comparison)
        outcome = classify_cycle_source_outcome(
            success={
                "source_id": pair.source_id,
                "http_status": 200,
            },
            comparison=comparison,
        )
        source_outcomes.append(outcome)

        if comparison["candidate_required"]:
            candidate = create_change_candidate(
                evaluation_workspace,
                pair.source_id,
                current["snapshot_id"],
                previous_snapshot_id=baseline["snapshot_id"],
                summary=(
                    "Evaluation-cycle mechanical content change; "
                    "substantive classification pending human review."
                ),
                actor=actor,
            )
            candidates.append(candidate)
            adjudication_record = adjudicate_change_candidate(
                evaluation_workspace,
                candidate["candidate_id"],
                adj.decision,
                rationale=adj.rationale,
                change_class=adj.change_class,
                materiality=adj.materiality,
                reopening_effect=adj.reopening_effect,
                actor=actor,
            )
            adjudications.append(adjudication_record)

    stage_results["quarantine_approve_handoff"] = {
        "mode": "offline_fixture_snapshots",
        "monitoring_handoff_kill_switch": "DISABLED",
        "canonical_workbench_mutated": False,
        "status": SHADOW_EVALUATION_STATUS,
    }
    stage_results["record_snapshot"] = {"handoffs": handoffs, "count": len(handoffs)}
    stage_results["compare_snapshots"] = {
        "comparisons": [
            {
                "source_id": item["source_id"],
                "classification": item["classification"],
                "candidate_required": item["candidate_required"],
            }
            for item in comparisons
        ],
        "count": len(comparisons),
    }
    stage_results["create_change_candidate"] = {
        "candidates": [{"candidate_id": c["candidate_id"], "source_id": c["source_id"]} for c in candidates],
        "count": len(candidates),
    }
    stage_results["adjudicate"] = {
        "adjudications": [
            {
                "adjudication_id": item["adjudication_id"],
                "candidate_id": item["candidate_id"],
                "decision": item["decision"],
            }
            for item in adjudications
        ],
        "count": len(adjudications),
        "dual_review_forged": False,
    }

    return _finish_cycle_after_adjudication(
        evaluation_workspace=evaluation_workspace,
        predecessor_path=predecessor_path,
        output_dir=output_dir,
        refresh_version=refresh_version,
        evidence_cutoff=evidence_cutoff,
        apply_id=apply_id,
        stage_results=stage_results,
        source_outcomes=source_outcomes,
        candidates=candidates,
        operation_specs=operation_specs,
        actor=actor,
        mode="offline",
        registry_source_count=len(registry.get("sources", [])),
    )


def run_live_evaluation_cycle(
    *,
    evaluation_workspace: Path,
    registry_path: Path,
    predecessor_path: Path,
    quarantine_root: Path,
    output_dir: Path,
    refresh_version: str,
    evidence_cutoff: str,
    apply_id: str,
    plan: dict[str, Any] | None = None,
    sample_size: int = 5,
    adjudication: CycleAdjudicationSpec | None = None,
    operation_specs: dict[str, list[dict[str, Any]]] | None = None,
    transport: HttpTransport | None = None,
    dns_guard: DnsGuard | None = None,
    actor: str = EVAL_CYCLE_ACTOR,
    as_of: str = "2026-08-02",
    approve_handoff: bool = False,
) -> dict[str, Any]:
    """Ops-gated live collect then evaluation handoff and downstream cycle stages.

    Requires NEUROAI_LIVE_COLLECTION=1. Keeps collector monitoring handoff disabled;
    ``approve_handoff=True`` consents only to handoff of quarantine records that are
    already ``APPROVED_FOR_HANDOFF`` (per-record). It does not auto-approve pending
    records.
    """
    require_live_collection_enabled()
    if not approve_handoff:
        raise PermissionError(
            "Live evaluation cycle refuses automatic monitoring mutation; "
            "pass approve_handoff=True only after per-record quarantine approval "
            "(APPROVED_FOR_HANDOFF) to consent to handoff of those pre-approved records."
        )
    adj = adjudication or CycleAdjudicationSpec()
    evaluation_workspace = evaluation_workspace.resolve()
    registry_path = registry_path.resolve()
    predecessor_path = predecessor_path.resolve()
    quarantine_root = quarantine_root.resolve()
    output_dir = output_dir.resolve()
    evaluation_workspace.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    quarantine_root.mkdir(parents=True, exist_ok=True)
    _ensure_monitoring(evaluation_workspace, registry_path, actor=actor)

    registry = load_source_registry(registry_path)
    registry_sha256 = sha256_file(registry_path)
    effective_plan = plan or plan_monitoring_run(evaluation_workspace, as_of=as_of)
    stage_results: dict[str, Any] = {
        "plan": {
            "plan_id": effective_plan.get("plan_id"),
            "counts": effective_plan.get("counts"),
            "status": SHADOW_EVALUATION_STATUS,
        }
    }

    live_package = run_live_cohort_collection(
        plan=effective_plan,
        registry=registry,
        registry_sha256=registry_sha256,
        quarantine_root=quarantine_root,
        transport=transport,
        dns_guard=dns_guard,
    )
    stage_results["collect"] = {
        "mode": "live",
        "network_retrieval": "EXECUTED_LIVE_QUARANTINE_ONLY",
        "collection_run": live_package.get("collection_run"),
        "capture_digest_count": len(live_package.get("capture_digests", [])),
        "failure_summary_count": len(live_package.get("failure_summaries", [])),
        "status": SHADOW_EVALUATION_STATUS,
    }

    source_outcomes: list[dict[str, Any]] = []
    for digest in live_package.get("capture_digests", []):
        if not isinstance(digest, dict):
            continue
        source_outcomes.append(
            classify_cycle_source_outcome(
                success={
                    "source_id": digest.get("source_id"),
                    "http_status": digest.get("http_status"),
                }
            )
        )
    for failure in live_package.get("failure_summaries", []):
        if isinstance(failure, dict):
            source_outcomes.append(classify_cycle_source_outcome(failure=failure))

    handoff = handoff_quarantine_sample_to_evaluation(
        quarantine_root=quarantine_root,
        evaluation_workspace=evaluation_workspace,
        registry_path=registry_path,
        sample_size=sample_size,
        approved_by=actor,
    )
    stage_results["quarantine_approve_handoff"] = {
        "handoffs": handoff.get("handoffs", []),
        "monitoring_handoff_kill_switch": handoff.get("monitoring_handoff_kill_switch"),
        "canonical_workbench_mutated": handoff.get("canonical_workbench_mutated"),
        "status": SHADOW_EVALUATION_STATUS,
    }
    stage_results["record_snapshot"] = {
        "handoffs": handoff.get("handoffs", []),
        "count": len(handoff.get("handoffs", [])),
    }

    comparisons: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    adjudications: list[dict[str, Any]] = []
    state_path = evaluation_workspace / "observatory" / "monitoring" / "state.json"
    state = load_json(state_path) if state_path.is_file() else {}
    sources_state = state.get("sources", {}) if isinstance(state, dict) else {}

    for item in handoff.get("handoffs", []):
        source_id = str(item["source_id"])
        current_id = str(item["snapshot_id"])
        prior = sources_state.get(source_id, {}) if isinstance(sources_state, dict) else {}
        previous_id = prior.get("previous_snapshot_id") if isinstance(prior, dict) else None
        if previous_id:
            comparison = compare_snapshots(evaluation_workspace, source_id, str(previous_id), current_id)
            comparisons.append(comparison)
            for outcome in source_outcomes:
                if outcome.get("source_id") == source_id and outcome.get("outcome_type") in {
                    "SUCCESS",
                    "NOT_MODIFIED_304",
                }:
                    refined = classify_cycle_source_outcome(
                        success={"source_id": source_id, "http_status": outcome.get("http_status")},
                        comparison=comparison,
                    )
                    outcome.update(refined)
            if comparison["candidate_required"]:
                candidate = create_change_candidate(
                    evaluation_workspace,
                    source_id,
                    current_id,
                    previous_snapshot_id=str(previous_id),
                    actor=actor,
                )
                candidates.append(candidate)
        else:
            updated = False
            for outcome in source_outcomes:
                if outcome.get("source_id") == source_id:
                    outcome["outcome_type"] = "MANUAL_FIRST_CAPTURE"
                    outcome["comparison_classification"] = None
                    outcome["notes"] = "No prior snapshot; mechanical comparison unavailable."
                    updated = True
                    break
            if not updated:
                source_outcomes.append(
                    {
                        "source_id": source_id,
                        "outcome_type": "MANUAL_FIRST_CAPTURE",
                        "finding_effect": "NONE",
                        "http_status": None,
                        "failure_class": None,
                        "comparison_classification": None,
                        "notes": "No prior snapshot; mechanical comparison unavailable.",
                        "status": SHADOW_EVALUATION_STATUS,
                        "boundary": SHADOW_REFRESH_BOUNDARY,
                    }
                )
            candidate = create_change_candidate(
                evaluation_workspace,
                source_id,
                current_id,
                previous_snapshot_id=None,
                summary="First evaluation snapshot; no baseline for mechanical comparison.",
                actor=actor,
            )
            candidates.append(candidate)

    for candidate in candidates:
        adjudication_record = adjudicate_change_candidate(
            evaluation_workspace,
            candidate["candidate_id"],
            adj.decision,
            rationale=adj.rationale,
            change_class=adj.change_class,
            materiality=adj.materiality,
            reopening_effect=adj.reopening_effect,
            actor=actor,
        )
        adjudications.append(adjudication_record)

    stage_results["compare_snapshots"] = {
        "comparisons": [
            {
                "source_id": item["source_id"],
                "classification": item["classification"],
                "candidate_required": item["candidate_required"],
            }
            for item in comparisons
        ],
        "count": len(comparisons),
        "first_capture_without_baseline": sum(
            1 for item in source_outcomes if item.get("outcome_type") == "MANUAL_FIRST_CAPTURE"
        ),
    }
    stage_results["create_change_candidate"] = {
        "candidates": [{"candidate_id": c["candidate_id"], "source_id": c["source_id"]} for c in candidates],
        "count": len(candidates),
    }
    stage_results["adjudicate"] = {
        "adjudications": [
            {
                "adjudication_id": item["adjudication_id"],
                "candidate_id": item["candidate_id"],
                "decision": item["decision"],
            }
            for item in adjudications
        ],
        "count": len(adjudications),
        "dual_review_forged": False,
    }

    # Quarantine success count retained for provenance reporting.
    _ = list_quarantine_successes(quarantine_root)

    return _finish_cycle_after_adjudication(
        evaluation_workspace=evaluation_workspace,
        predecessor_path=predecessor_path,
        output_dir=output_dir,
        refresh_version=refresh_version,
        evidence_cutoff=evidence_cutoff,
        apply_id=apply_id,
        stage_results=stage_results,
        source_outcomes=source_outcomes,
        candidates=candidates,
        operation_specs=operation_specs,
        actor=actor,
        mode="live",
        registry_source_count=len(registry.get("sources", [])),
    )


def _finish_cycle_after_adjudication(
    *,
    evaluation_workspace: Path,
    predecessor_path: Path,
    output_dir: Path,
    refresh_version: str,
    evidence_cutoff: str,
    apply_id: str,
    stage_results: dict[str, Any],
    source_outcomes: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    operation_specs: dict[str, list[dict[str, Any]]] | None,
    actor: str,
    mode: CycleMode,
    registry_source_count: int,
) -> dict[str, Any]:
    refresh = build_refresh_candidate(
        evaluation_workspace,
        refresh_version,
        evidence_cutoff,
        actor=actor,
    )
    stage_results["build_refresh_candidate"] = {
        "version": refresh["manifest"]["version"],
        "status": refresh["manifest"]["status"],
        "counts": refresh["package"]["counts"],
        "path": refresh["manifest"]["path"],
    }

    predecessor = load_json(predecessor_path)
    if not isinstance(predecessor, dict):
        raise ValueError("Predecessor release must be a JSON object")
    specs = operation_specs or _default_operation_specs(candidates, predecessor)
    delta = compile_adjudicated_delta(
        refresh["package"],
        predecessor,
        predecessor_release_id=str(predecessor.get("metadata", {}).get("version") or "UNRESOLVED"),
        operation_specs=specs,
        actor=actor,
    )
    delta_path = output_dir / "adjudicated-delta.json"
    atomic_write_json(delta_path, delta)
    stage_results["compile_adjudicated_delta"] = {
        "delta_id": delta["metadata"]["delta_id"],
        "status": delta["metadata"]["status"],
        "operation_count": len(delta.get("operations", [])),
        "path": str(delta_path),
    }

    apply_root = output_dir / "apply"
    apply_result = apply_delta(
        predecessor,
        delta,
        apply_root,
        apply_id=apply_id,
        actor=actor,
    )
    successor_path = apply_root / "candidate-successor.json"
    stage_results["apply_delta"] = {
        "apply_id": apply_result["apply_id"],
        "status": apply_result["manifest"]["status"],
        "predecessor_unchanged": apply_result["predecessor_unchanged"],
        "successor_path": str(successor_path),
    }

    recommendations = analyze_observatory_delta(delta)
    reopening_path = output_dir / "reopening-recommendations.json"
    reopening_package = {
        "metadata": {
            "title": "Evaluation-cycle reopening recommendations",
            "status": SHADOW_EVALUATION_STATUS,
            "generated_at": utc_now(),
            "generated_by": actor,
        },
        "recommendation_count": len(recommendations),
        "recommendations": recommendations,
        "assessment_mutation_performed": False,
        "status": SHADOW_EVALUATION_STATUS,
        "boundary": SHADOW_REFRESH_BOUNDARY,
        "withheld_claims": [
            "Reopening recommendations are advisory only and do not mutate assessments.",
            "No automatic observatory decision is applied from this evaluation cycle.",
        ],
    }
    atomic_write_json(reopening_path, reopening_package)
    stage_results["reopening_analysis"] = {
        "recommendation_count": len(recommendations),
        "path": str(reopening_path),
        "assessment_mutation_performed": False,
    }

    publications_dir = output_dir / "publications"
    publication_report = generate_publication_set(
        successor_path,
        publications_dir,
        limit=None,
        depth="full",
    )
    query = query_release(successor_path, depth="full", limit=None)
    reconciliation = reconcile_formats(query, publication_report["products"])
    stage_results["publications"] = {
        "release_sha256": publication_report["release_sha256"],
        "products": {key: meta.get("output") for key, meta in publication_report["products"].items()},
        "reconciled": reconciliation["reconciled"],
        "depth": "full",
        "path": str(publications_dir),
    }

    stats = {
        "retrieval": {
            "outcome_count": len(source_outcomes),
            "by_type": _count_by(source_outcomes, "outcome_type"),
        },
        "candidates": {
            "generated": len(candidates),
            "accepted": sum(
                1
                for item in stage_results.get("adjudicate", {}).get("adjudications", [])
                if item.get("decision") == "ACCEPT"
            ),
        },
        "review": {
            "adjudications": stage_results.get("adjudicate", {}).get("count", 0),
            "dual_review_forged": False,
            "note": "Claimed local workflow identities only; dual human review remains open unless recorded elsewhere.",
        },
        "reopening": {
            "recommended": len(recommendations),
            "assessment_mutation_performed": False,
        },
        "publication": {
            "reconciled": reconciliation["reconciled"],
            "reconciliation_errors": 0 if reconciliation["reconciled"] else 1,
        },
        "registry_source_count": registry_source_count,
    }

    package = {
        "metadata": {
            "title": "Non-canonical full evaluation operating cycle",
            "status": SHADOW_EVALUATION_STATUS,
            "mode": mode,
            "executed_at": utc_now(),
            "executed_by": actor,
            "stages": list(CYCLE_STAGES),
        },
        "stage_results": stage_results,
        "source_outcomes": source_outcomes,
        "stats": stats,
        "evaluation_workspace": str(evaluation_workspace),
        "output_dir": str(output_dir),
        "canonical_successor_written": False,
        "monitoring_handoff_kill_switch": "DISABLED",
        "assessment_mutation_performed": False,
        "formal_go_authorized": False,
        "withheld_claims": [
            "Cycle artifacts remain SHADOW_EVALUATION_NOT_CANONICAL.",
            "Candidate successor is not an AUTHORIZED or PUBLISHED observatory release (#41).",
            "Adjudication scaffolding does not forge dual human review or GO disposition.",
            "Retrieval/comparison outcomes are typed operations evidence, not FAIL findings.",
            "Reopening analysis does not mutate assessments.",
            "Publication products are views of the candidate successor only.",
        ],
        "status": SHADOW_EVALUATION_STATUS,
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }
    package_path = output_dir / "evaluation-cycle-report.json"
    atomic_write_json(package_path, package)
    package["report_path"] = str(package_path)
    package["report_sha256"] = sha256_bytes(
        # Recompute from stored file to avoid self-reference churn.
        package_path.read_bytes()
    )
    return package


def _count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "UNRESOLVED")
        counts[value] = counts.get(value, 0) + 1
    return counts
