"""Protected comparative live-refresh execution for issue #120.

This module closes the live-to-live comparison gap without weakening existing
collector or governance boundaries. It verifies and seeds first-cycle captures
from an externally supplied protected quarantine bundle, performs exactly one
new live collection, records explicit technical handoff approvals for the new
successful captures, compares new snapshots with the verified baselines, and
then reuses the existing non-canonical downstream refresh/delta/product path.

Capture bodies and protected paths are never emitted by the public report.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from ..collector.dns import DnsGuard
from ..collector.handoff import (
    approve_quarantine_record,
    load_collection_result,
)
from ..collector.http_client import HttpTransport
from ..monitoring import (
    adjudicate_change_candidate,
    compare_snapshots,
    create_change_candidate,
    initialize_monitoring,
    load_snapshot,
    load_source_registry,
    record_snapshot,
)
from ..util import atomic_write_json, canonical_json_bytes, load_json, safe_join, sha256_bytes, sha256_file, utc_now
from .closure import handoff_quarantine_sample_to_evaluation, list_quarantine_successes
from .cycle import (
    EVAL_CYCLE_ACTOR,
    CycleDevelopmentDispositionSpec,
    _finish_cycle_after_adjudication,
    classify_cycle_source_outcome,
)
from .live import require_live_collection_enabled, run_live_cohort_collection
from .schemas import SHADOW_EVALUATION_STATUS, SHADOW_REFRESH_BOUNDARY

COMPARISON_NORMALIZATION_VERSION = "TEXT_NORMALIZATION_v1"
COMPARISON_SCHEMA_VERSION = "1.0"
TECHNICAL_HANDOFF_SCOPE = "EVALUATION_HANDOFF_ONLY_NOT_SUBSTANTIVE_REVIEW"


@dataclass(frozen=True)
class ProtectedBaselineBinding:
    artifact_id: str
    artifact_name: str
    artifact_sha256: str
    workflow_run_id: str
    workbench_commit: str

    def as_dict(self) -> dict[str, str]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_name": self.artifact_name,
            "artifact_sha256": self.artifact_sha256,
            "workflow_run_id": self.workflow_run_id,
            "workbench_commit": self.workbench_commit,
        }


def _public_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return None
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.netloc:
        return None
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.casefold(), parsed.netloc.casefold(), path, parsed.query, ""))


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _capture_index(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    captures = _items(summary.get("capture_digests"))
    if not captures:
        raise ValueError("Baseline summary contains no capture digests")
    by_source: dict[str, dict[str, Any]] = {}
    result_ids: set[str] = set()
    for ordinal, raw in enumerate(captures):
        if not isinstance(raw, dict):
            raise ValueError(f"Baseline capture_digests[{ordinal}] must be an object")
        source_id = str(raw.get("source_id") or "")
        result_id = str(raw.get("result_id") or "")
        digest = str(raw.get("sha256") or "")
        if not source_id or not result_id or len(digest) != 64:
            raise ValueError(f"Baseline capture_digests[{ordinal}] lacks stable identity")
        if source_id in by_source:
            raise ValueError(f"Ambiguous baseline: duplicate source {source_id}")
        if result_id in result_ids:
            raise ValueError(f"Ambiguous baseline: duplicate result {result_id}")
        by_source[source_id] = raw
        result_ids.add(result_id)
    return by_source


def _quarantine_by_result(quarantine_root: Path) -> dict[str, dict[str, Any]]:
    by_result: dict[str, dict[str, Any]] = {}
    for record in list_quarantine_successes(quarantine_root):
        result_id = str(record.get("result_id") or "")
        if not result_id:
            continue
        if result_id in by_result:
            raise ValueError(f"Ambiguous quarantine mapping for result {result_id}")
        by_result[result_id] = record
    return by_result


def _verify_capture_record(
    *,
    quarantine_root: Path,
    digest_record: dict[str, Any],
    quarantine_record: dict[str, Any],
) -> tuple[dict[str, Any], Path]:
    source_id = str(digest_record["source_id"])
    result_id = str(digest_record["result_id"])
    if str(quarantine_record.get("source_id")) != source_id:
        raise ValueError(f"Baseline source mismatch for {source_id}")
    if str(quarantine_record.get("result_id")) != result_id:
        raise ValueError(f"Baseline result mismatch for {source_id}")
    result = load_collection_result(quarantine_root, result_id)
    if str(result.get("source_id")) != source_id:
        raise ValueError(f"Collection result source mismatch for {source_id}")
    expected_sha = str(digest_record["sha256"])
    if str(quarantine_record.get("sha256")) != expected_sha or str(result.get("sha256")) != expected_sha:
        raise ValueError(f"Baseline digest metadata mismatch for {source_id}")
    expected_size = int(digest_record.get("size_bytes") or 0)
    if expected_size <= 0:
        raise ValueError(f"Baseline size missing for {source_id}")
    if (
        int(quarantine_record.get("size_bytes") or 0) != expected_size
        or int(result.get("size_bytes") or 0) != expected_size
    ):
        raise ValueError(f"Baseline size metadata mismatch for {source_id}")
    body_path = safe_join(quarantine_root, str(quarantine_record.get("quarantine_path") or ""))
    if not body_path.is_file():
        raise ValueError(f"Baseline bytes missing for {source_id}")
    if sha256_file(body_path) != expected_sha or body_path.stat().st_size != expected_size:
        raise ValueError(f"Baseline bytes fail integrity verification for {source_id}")
    digest_media = str(digest_record.get("media_type") or "application/octet-stream")
    result_media = str(result.get("media_type") or "application/octet-stream")
    if digest_media != result_media:
        raise ValueError(f"Baseline media-type mismatch for {source_id}")
    digest_target = _public_url(digest_record.get("final_url"))
    result_target = _public_url(result.get("final_url"))
    if digest_target != result_target:
        raise ValueError(f"Baseline retrieval-target mismatch for {source_id}")
    return result, body_path


def seed_verified_baselines(
    *,
    evaluation_workspace: Path,
    registry_path: Path,
    baseline_quarantine_root: Path,
    baseline_summary_path: Path,
    actor: str = EVAL_CYCLE_ACTOR,
) -> dict[str, Any]:
    """Read-only verify protected first-cycle captures and seed snapshot baselines."""
    evaluation_workspace = evaluation_workspace.resolve()
    baseline_quarantine_root = baseline_quarantine_root.resolve()
    baseline_summary_path = baseline_summary_path.resolve()
    if not baseline_summary_path.is_file():
        raise ValueError("Baseline summary is missing")
    initialize_monitoring(evaluation_workspace, registry_path, actor=actor)
    state_path = evaluation_workspace / "observatory" / "monitoring" / "state.json"
    state = load_json(state_path)
    if not isinstance(state, dict) or state.get("sources") not in ({}, None):
        raise ValueError("Baseline seeding requires an evaluation workspace with empty monitoring source state")

    summary = load_json(baseline_summary_path)
    if not isinstance(summary, dict):
        raise ValueError("Baseline summary must be a JSON object")
    capture_by_source = _capture_index(summary)
    record_by_result = _quarantine_by_result(baseline_quarantine_root)
    seeded: list[dict[str, Any]] = []
    for source_id in sorted(capture_by_source):
        digest_record = capture_by_source[source_id]
        result_id = str(digest_record["result_id"])
        quarantine_record = record_by_result.get(result_id)
        if quarantine_record is None:
            raise ValueError(f"Verified baseline quarantine record missing for {source_id} / {result_id}")
        result, body_path = _verify_capture_record(
            quarantine_root=baseline_quarantine_root,
            digest_record=digest_record,
            quarantine_record=quarantine_record,
        )
        snapshot = record_snapshot(
            evaluation_workspace,
            source_id,
            body_path.read_bytes(),
            media_type=str(result.get("media_type") or "application/octet-stream"),
            retrieved_at=str(result.get("retrieved_at") or quarantine_record.get("captured_at") or ""),
            retrieval_url=str(result.get("final_url") or result.get("requested_url") or ""),
            original_filename=str(
                quarantine_record.get("original_filename") or result.get("original_filename") or "capture.bin"
            ),
            actor=actor,
        )
        if snapshot["sha256"] != digest_record["sha256"]:
            raise ValueError(f"Seeded baseline snapshot digest mismatch for {source_id}")
        seeded.append(
            {
                "source_id": source_id,
                "baseline_result_id": result_id,
                "baseline_snapshot_id": snapshot["snapshot_id"],
                "sha256": snapshot["sha256"],
                "size_bytes": snapshot["size_bytes"],
                "media_type": snapshot["media_type"],
                "retrieved_at": snapshot["retrieved_at"],
                "retrieval_target": _public_url(snapshot.get("retrieval_url")),
                "collector_version": result.get("collector_version"),
                "collector_configuration_hash": result.get("configuration_hash"),
            }
        )
    return {
        "count": len(seeded),
        "source_ids": [row["source_id"] for row in seeded],
        "baseline_collection_run_id": _mapping(summary.get("collection_run")).get("run_id"),
        "baseline_summary_sha256": sha256_file(baseline_summary_path),
        "records": seeded,
        "protected_bytes_emitted": False,
        "status": SHADOW_EVALUATION_STATUS,
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }


def approve_collection_for_evaluation(
    *,
    live_package: dict[str, Any],
    quarantine_root: Path,
    actor: str,
) -> dict[str, Any]:
    """Approve only the current successful captures for technical evaluation handoff."""
    capture_by_source = _capture_index(live_package)
    record_by_result = _quarantine_by_result(quarantine_root)
    approvals: list[dict[str, Any]] = []
    for source_id in sorted(capture_by_source):
        digest_record = capture_by_source[source_id]
        result_id = str(digest_record["result_id"])
        record = record_by_result.get(result_id)
        if record is None:
            raise ValueError(f"Current quarantine record missing for {source_id} / {result_id}")
        _verify_capture_record(
            quarantine_root=quarantine_root,
            digest_record=digest_record,
            quarantine_record=record,
        )
        approved = approve_quarantine_record(
            quarantine_root,
            str(record["quarantine_id"]),
            approved_by=actor,
        )
        approvals.append(
            {
                "source_id": source_id,
                "result_id": result_id,
                "quarantine_id": approved["quarantine_id"],
                "sha256": approved["sha256"],
                "size_bytes": approved["size_bytes"],
                "captured_at": approved["captured_at"],
                "approval_state": approved["approval_state"],
                "approval_scope": TECHNICAL_HANDOFF_SCOPE,
            }
        )
    return {
        "count": len(approvals),
        "records": approvals,
        "approval_scope": TECHNICAL_HANDOFF_SCOPE,
        "substantive_authority": False,
        "status": SHADOW_EVALUATION_STATUS,
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }


def _json_changed_paths(older_bytes: bytes, newer_bytes: bytes) -> list[str]:
    try:
        older = json.loads(older_bytes)
        newer = json.loads(newer_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []
    changed: list[str] = []

    def walk(old: Any, new: Any, path: str) -> None:
        if type(old) is not type(new):
            changed.append(path or "$")
            return
        if isinstance(old, dict):
            keys = sorted(set(old) | set(new))
            for key in keys:
                child = f"{path}.{key}" if path else str(key)
                if key not in old or key not in new:
                    changed.append(child)
                else:
                    walk(old[key], new[key], child)
        elif isinstance(old, list):
            if len(old) != len(new):
                changed.append(path or "$")
                return
            for index, (old_item, new_item) in enumerate(zip(old, new)):
                walk(old_item, new_item, f"{path}[{index}]" if path else f"[{index}]")
        elif old != new:
            changed.append(path or "$")

    walk(older, newer, "")
    return changed[:200]


def classify_capture_pair(
    *,
    evaluation_workspace: Path,
    source_id: str,
    older_snapshot_id: str,
    newer_snapshot_id: str,
    older_collector_configuration_hash: str | None,
    newer_collector_configuration_hash: str | None,
) -> dict[str, Any]:
    """Return an issue-#120 comparison classification richer than the core candidate gate."""
    older = load_snapshot(evaluation_workspace, source_id, older_snapshot_id)
    newer = load_snapshot(evaluation_workspace, source_id, newer_snapshot_id)
    older_target = _public_url(older.get("retrieval_url"))
    newer_target = _public_url(newer.get("retrieval_url"))
    older_media = str(older.get("media_type") or "")
    newer_media = str(newer.get("media_type") or "")
    changed_paths: list[str] = []

    if older_target != newer_target:
        classification = "INCOMPARABLE_RETRIEVAL_TARGET_TRANSITION"
    elif older_media != newer_media:
        classification = "INCOMPARABLE_CONTENT_TYPE_TRANSITION"
    elif older["sha256"] == newer["sha256"]:
        classification = "BYTE_IDENTICAL"
    elif older.get("normalized_text_sha256") and older.get("normalized_text_sha256") == newer.get(
        "normalized_text_sha256"
    ):
        classification = "REPRESENTATION_ONLY_CHANGE"
    elif "json" in older_media.casefold() and "json" in newer_media.casefold():
        older_path = safe_join(evaluation_workspace, str(older["stored_path"]))
        newer_path = safe_join(evaluation_workspace, str(newer["stored_path"]))
        changed_paths = _json_changed_paths(older_path.read_bytes(), newer_path.read_bytes())
        classification = "STRUCTURED_RECORD_FIELD_CHANGE" if changed_paths else "SUBSTANTIVE_NORMALIZED_TEXT_CHANGE"
    elif older.get("normalized_text_sha256") and newer.get("normalized_text_sha256"):
        classification = "SUBSTANTIVE_NORMALIZED_TEXT_CHANGE"
    else:
        classification = "COMPARISON_BLOCKED_NORMALIZER_UNAVAILABLE"

    return {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "source_id": source_id,
        "older_snapshot_id": older_snapshot_id,
        "newer_snapshot_id": newer_snapshot_id,
        "older_sha256": older["sha256"],
        "newer_sha256": newer["sha256"],
        "older_size_bytes": older["size_bytes"],
        "newer_size_bytes": newer["size_bytes"],
        "older_media_type": older_media,
        "newer_media_type": newer_media,
        "older_retrieved_at": older["retrieved_at"],
        "newer_retrieved_at": newer["retrieved_at"],
        "retrieval_target": older_target if older_target == newer_target else None,
        "classification": classification,
        "normalization_version": COMPARISON_NORMALIZATION_VERSION,
        "collector_configuration": {
            "older": older_collector_configuration_hash,
            "newer": newer_collector_configuration_hash,
            "same": older_collector_configuration_hash == newer_collector_configuration_hash,
        },
        "changed_structured_paths": changed_paths,
        "comparison_timestamp": utc_now(),
        "protected_bytes_emitted": False,
        "status": SHADOW_EVALUATION_STATUS,
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }


def run_comparative_live_refresh(
    *,
    evaluation_workspace: Path,
    registry_path: Path,
    predecessor_path: Path,
    baseline_quarantine_root: Path,
    baseline_summary_path: Path,
    quarantine_root: Path,
    output_dir: Path,
    plan: dict[str, Any],
    refresh_version: str,
    evidence_cutoff: str,
    apply_id: str,
    baseline_binding: ProtectedBaselineBinding,
    development_disposition: CycleDevelopmentDispositionSpec | None = None,
    transport: HttpTransport | None = None,
    dns_guard: DnsGuard | None = None,
    actor: str = "issue-120-comparative-refresh",
) -> dict[str, Any]:
    """Run one second collection and compare it against protected verified baselines."""
    require_live_collection_enabled()
    disposition = development_disposition or CycleDevelopmentDispositionSpec(
        rationale=(
            "Issue #120 development-only disposition used solely to exercise deterministic candidate/delta mechanics; "
            "it carries no substantive, governance, assessment, publication, or release authority."
        )
    )
    evaluation_workspace = evaluation_workspace.resolve()
    registry_path = registry_path.resolve()
    predecessor_path = predecessor_path.resolve()
    quarantine_root = quarantine_root.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    quarantine_root.mkdir(parents=True, exist_ok=True)

    baseline = seed_verified_baselines(
        evaluation_workspace=evaluation_workspace,
        registry_path=registry_path,
        baseline_quarantine_root=baseline_quarantine_root,
        baseline_summary_path=baseline_summary_path,
        actor=actor,
    )
    registry = load_source_registry(registry_path)
    registry_sha256 = sha256_file(registry_path)
    live_package = run_live_cohort_collection(
        plan=plan,
        registry=registry,
        registry_sha256=registry_sha256,
        quarantine_root=quarantine_root,
        transport=transport,
        dns_guard=dns_guard,
    )
    technical_approvals = approve_collection_for_evaluation(
        live_package=live_package,
        quarantine_root=quarantine_root,
        actor=actor,
    )
    handoff = handoff_quarantine_sample_to_evaluation(
        quarantine_root=quarantine_root,
        evaluation_workspace=evaluation_workspace,
        registry_path=registry_path,
        sample_size=max(1, technical_approvals["count"]),
        approved_by=actor,
    )
    if len(handoff.get("handoffs", [])) != technical_approvals["count"]:
        raise ValueError("Second-cycle handoff count does not match technically approved successful captures")

    stage_results: dict[str, Any] = {
        "plan": {
            "plan_id": plan.get("plan_id"),
            "counts": plan.get("counts"),
            "status": SHADOW_EVALUATION_STATUS,
        },
        "baseline_seed": {
            **baseline,
            "protected_artifact_binding": baseline_binding.as_dict(),
        },
        "collect": {
            "mode": "live",
            "network_retrieval": "EXECUTED_LIVE_QUARANTINE_ONLY",
            "collection_run": live_package.get("collection_run"),
            "capture_digest_count": len(_items(live_package.get("capture_digests"))),
            "failure_summary_count": len(_items(live_package.get("failure_summaries"))),
            "status": SHADOW_EVALUATION_STATUS,
        },
        "technical_handoff_approval": technical_approvals,
        "quarantine_approve_handoff": {
            "handoffs": handoff.get("handoffs", []),
            "monitoring_handoff_kill_switch": handoff.get("monitoring_handoff_kill_switch"),
            "canonical_workbench_mutated": handoff.get("canonical_workbench_mutated"),
            "status": SHADOW_EVALUATION_STATUS,
        },
        "record_snapshot": {
            "handoffs": handoff.get("handoffs", []),
            "count": len(handoff.get("handoffs", [])),
        },
    }

    source_outcomes: list[dict[str, Any]] = []
    current_result_by_source: dict[str, dict[str, Any]] = {}
    for digest in _items(live_package.get("capture_digests")):
        if not isinstance(digest, dict):
            continue
        source_id = str(digest.get("source_id") or "")
        source_outcomes.append(
            classify_cycle_source_outcome(success={"source_id": source_id, "http_status": digest.get("http_status")})
        )
        if source_id:
            current_result_by_source[source_id] = load_collection_result(quarantine_root, str(digest["result_id"]))
    for failure in _items(live_package.get("failure_summaries")):
        if isinstance(failure, dict):
            source_outcomes.append(classify_cycle_source_outcome(failure=failure))

    baseline_by_source = {row["source_id"]: row for row in baseline["records"]}
    state = load_json(evaluation_workspace / "observatory" / "monitoring" / "state.json")
    sources_state = _mapping(_mapping(state).get("sources"))
    core_comparisons: list[dict[str, Any]] = []
    detailed_comparisons: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    adjudications: list[dict[str, Any]] = []

    for item in handoff.get("handoffs", []):
        source_id = str(item["source_id"])
        current_id = str(item["snapshot_id"])
        source_state = _mapping(sources_state.get(source_id))
        previous_id = source_state.get("previous_snapshot_id")
        baseline_row = baseline_by_source.get(source_id)
        if baseline_row is not None:
            if previous_id != baseline_row["baseline_snapshot_id"]:
                raise ValueError(f"Baseline chain binding mismatch for {source_id}")
            comparison = compare_snapshots(evaluation_workspace, source_id, str(previous_id), current_id)
            core_comparisons.append(comparison)
            current_result = current_result_by_source[source_id]
            detailed = classify_capture_pair(
                evaluation_workspace=evaluation_workspace,
                source_id=source_id,
                older_snapshot_id=str(previous_id),
                newer_snapshot_id=current_id,
                older_collector_configuration_hash=baseline_row.get("collector_configuration_hash"),
                newer_collector_configuration_hash=(
                    str(current_result.get("configuration_hash")) if current_result.get("configuration_hash") else None
                ),
            )
            detailed_comparisons.append(detailed)
            for outcome in source_outcomes:
                if outcome.get("source_id") == source_id and outcome.get("outcome_type") in {
                    "SUCCESS",
                    "NOT_MODIFIED_304",
                }:
                    outcome.update(
                        classify_cycle_source_outcome(
                            success={"source_id": source_id, "http_status": outcome.get("http_status")},
                            comparison=comparison,
                        )
                    )
                    break
            if comparison["candidate_required"]:
                candidates.append(
                    create_change_candidate(
                        evaluation_workspace,
                        source_id,
                        current_id,
                        previous_snapshot_id=str(previous_id),
                        actor=actor,
                    )
                )
        else:
            for outcome in source_outcomes:
                if outcome.get("source_id") == source_id:
                    outcome["outcome_type"] = "MANUAL_FIRST_CAPTURE"
                    outcome["comparison_classification"] = None
                    outcome["notes"] = (
                        "Source had no successful protected #43 baseline; current success is a first valid comparison capture."
                    )
                    break
            candidates.append(
                create_change_candidate(
                    evaluation_workspace,
                    source_id,
                    current_id,
                    previous_snapshot_id=None,
                    summary="First valid capture after unresolved protected #43 baseline; no live-to-live comparison is claimed.",
                    actor=actor,
                )
            )

    for candidate in candidates:
        adjudications.append(
            adjudicate_change_candidate(
                evaluation_workspace,
                candidate["candidate_id"],
                disposition.decision,
                rationale=disposition.rationale,
                change_class=disposition.change_class,
                materiality=disposition.materiality,
                reopening_effect=disposition.reopening_effect,
                actor=actor,
            )
        )

    stage_results["compare_snapshots"] = {
        "comparisons": [
            {
                "source_id": item["source_id"],
                "classification": item["classification"],
                "candidate_required": item["candidate_required"],
                "older_sha256": item["older_sha256"],
                "newer_sha256": item["newer_sha256"],
            }
            for item in core_comparisons
        ],
        "detailed_comparisons": detailed_comparisons,
        "count": len(core_comparisons),
        "first_capture_without_baseline": sum(
            1 for item in source_outcomes if item.get("outcome_type") == "MANUAL_FIRST_CAPTURE"
        ),
        "normalization_version": COMPARISON_NORMALIZATION_VERSION,
    }
    stage_results["create_change_candidate"] = {
        "candidates": [{"candidate_id": c["candidate_id"], "source_id": c["source_id"]} for c in candidates],
        "count": len(candidates),
    }
    stage_results["development_disposition"] = {
        "records": [
            {
                "adjudication_id": item["adjudication_id"],
                "candidate_id": item["candidate_id"],
                "decision": item["decision"],
            }
            for item in adjudications
        ],
        "count": len(adjudications),
        "scope": "DEVELOPMENT_PIPELINE_ONLY",
        "governance_layer_applied": False,
        "substantive_authority": False,
        "assessment_mutation_performed": False,
    }

    package = _finish_cycle_after_adjudication(
        evaluation_workspace=evaluation_workspace,
        predecessor_path=predecessor_path,
        output_dir=output_dir,
        refresh_version=refresh_version,
        evidence_cutoff=evidence_cutoff,
        apply_id=apply_id,
        stage_results=stage_results,
        source_outcomes=source_outcomes,
        candidates=candidates,
        operation_specs=None,
        actor=actor,
        mode="live",
        registry_source_count=len(registry.get("sources", [])),
    )
    package["comparative_execution"] = {
        "baseline_artifact_binding": baseline_binding.as_dict(),
        "baseline_count": baseline["count"],
        "second_cycle_success_count": technical_approvals["count"],
        "true_comparison_count": len(core_comparisons),
        "detailed_comparison_count": len(detailed_comparisons),
        "normalization_version": COMPARISON_NORMALIZATION_VERSION,
        "protected_bytes_emitted": False,
    }
    return package


def build_public_comparative_report(
    *,
    package: dict[str, Any],
    predecessor_path: Path,
    registry_path: Path,
) -> dict[str, Any]:
    """Build a digest-only public report from a completed protected comparative run."""
    stages = _mapping(package.get("stage_results"))
    baseline_stage = _mapping(stages.get("baseline_seed"))
    collect_stage = _mapping(stages.get("collect"))
    comparison_stage = _mapping(stages.get("compare_snapshots"))
    candidate_stage = _mapping(stages.get("create_change_candidate"))
    disposition_stage = _mapping(stages.get("development_disposition"))
    delta_stage = _mapping(stages.get("compile_adjudicated_delta"))
    apply_stage = _mapping(stages.get("apply_delta"))
    reopening_stage = _mapping(stages.get("reopening_analysis"))
    publication_stage = _mapping(stages.get("publications"))
    comparison_rows = [item for item in _items(comparison_stage.get("detailed_comparisons")) if isinstance(item, dict)]
    outcome_rows = [item for item in _items(package.get("source_outcomes")) if isinstance(item, dict)]

    comparison_counts: dict[str, int] = {}
    for row in comparison_rows:
        key = str(row.get("classification") or "UNRESOLVED")
        comparison_counts[key] = comparison_counts.get(key, 0) + 1
    outcome_counts: dict[str, int] = {}
    for row in outcome_rows:
        key = str(row.get("outcome_type") or "UNRESOLVED")
        outcome_counts[key] = outcome_counts.get(key, 0) + 1

    public_comparisons = []
    for row in comparison_rows:
        public_comparisons.append(
            {
                key: row.get(key)
                for key in (
                    "source_id",
                    "older_snapshot_id",
                    "newer_snapshot_id",
                    "older_sha256",
                    "newer_sha256",
                    "older_size_bytes",
                    "newer_size_bytes",
                    "older_media_type",
                    "newer_media_type",
                    "older_retrieved_at",
                    "newer_retrieved_at",
                    "retrieval_target",
                    "classification",
                    "normalization_version",
                    "collector_configuration",
                    "changed_structured_paths",
                    "comparison_timestamp",
                )
            }
        )

    return {
        "schema_version": "1.0",
        "artifact": "issue_120_public_comparative_refresh_report",
        "status": SHADOW_EVALUATION_STATUS,
        "generated_at": utc_now(),
        "inputs": {
            "baseline_artifact": baseline_stage.get("protected_artifact_binding"),
            "baseline_summary_sha256": baseline_stage.get("baseline_summary_sha256"),
            "predecessor_sha256": sha256_file(predecessor_path),
            "registry_sha256": sha256_file(registry_path),
        },
        "execution": {
            "baseline_verified_count": baseline_stage.get("count"),
            "second_cycle_collection_run_id": _mapping(collect_stage.get("collection_run")).get("run_id"),
            "second_cycle_capture_count": collect_stage.get("capture_digest_count"),
            "second_cycle_failure_count": collect_stage.get("failure_summary_count"),
            "source_outcome_count": len(outcome_rows),
            "source_outcome_counts": dict(sorted(outcome_counts.items())),
            "true_comparison_count": comparison_stage.get("count"),
            "first_capture_without_baseline": comparison_stage.get("first_capture_without_baseline"),
            "comparison_classification_counts": dict(sorted(comparison_counts.items())),
            "candidate_count": candidate_stage.get("count"),
            "development_disposition_count": disposition_stage.get("count"),
            "development_disposition_scope": disposition_stage.get("scope"),
            "delta_operation_count": delta_stage.get("operation_count"),
            "reopening_recommendation_count": reopening_stage.get("recommendation_count"),
            "publication_reconciled": publication_stage.get("reconciled"),
        },
        "comparisons": public_comparisons,
        "source_outcomes": [
            {
                "source_id": row.get("source_id"),
                "outcome_type": row.get("outcome_type"),
                "finding_effect": row.get("finding_effect"),
                "http_status": row.get("http_status"),
                "failure_class": row.get("failure_class"),
                "comparison_classification": row.get("comparison_classification"),
            }
            for row in sorted(outcome_rows, key=lambda item: str(item.get("source_id") or ""))
        ],
        "safety": {
            "predecessor_unchanged": apply_stage.get("predecessor_unchanged"),
            "assessment_mutation_performed": bool(package.get("assessment_mutation_performed", False)),
            "canonical_successor_written": bool(package.get("canonical_successor_written", False)),
            "governance_layer_applied": bool(package.get("governance_layer_applied", False)),
            "release_authority_state": package.get("release_authority_state"),
            "protected_capture_bytes_in_report": False,
            "protected_paths_in_report": False,
        },
        "development_delta_boundary": (
            "Delta operations, if present, exercise development-only pipeline mechanics. They must not be interpreted "
            "as evidence-derived substantive observatory events or as authorized source/finding changes."
        ),
        "withheld_claims": list(package.get("withheld_claims", []))
        + [
            "This digest-only public report exposes no protected capture bodies or protected filesystem paths.",
            "Comparison evidence does not itself establish scientific materiality, regulatory status, clinical effect, conformance, or publication authority.",
        ],
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }


def write_public_comparative_report(path: Path, report: dict[str, Any]) -> dict[str, Any]:
    atomic_write_json(path, report)
    raw = path.read_bytes()
    return {
        "path": str(path),
        "sha256": sha256_bytes(raw),
        "size_bytes": len(raw),
        "canonical_json_sha256": sha256_bytes(canonical_json_bytes(report)),
    }
