#!/usr/bin/env python3
"""Execute the authorized protected non-canonical core cycle for issue #43."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from neuroai_workbench.collector.handoff import approve_quarantine_record
from neuroai_workbench.monitoring import load_source_registry
from neuroai_workbench.shadow_refresh.closure import list_quarantine_successes
from neuroai_workbench.shadow_refresh.cycle import (
    CycleDevelopmentDispositionSpec,
    run_live_evaluation_cycle,
)
from neuroai_workbench.shadow_refresh.live import run_live_cohort_collection
from neuroai_workbench.util import (
    atomic_write_json,
    canonical_json_bytes,
    load_json,
    sha256_bytes,
    sha256_file,
)

ROOT = Path(__file__).resolve().parents[1]
COHORT_PATH = ROOT / "examples/shadow_refresh/SHADOW_REFRESH_COHORT_REVIEWED_v202608.json"
PREDECESSOR_PATH = ROOT / "examples/observatory/canonical_successor_snapshot_v1.7.json"
PRIOR_SUMMARY_PATH = ROOT / "examples/shadow_refresh/SHADOW_REFRESH_WAVE2_PUBLIC_SUMMARY_v202608.json"
EXPECTED_PREDECESSOR_SHA256 = "9cc36aacb4c791c9830990b58e144f223925f3ad492016abaea44727b48a0b70"
EXPECTED_SOURCE_IDS = {
    "SRC-0004",
    "SRC-0013",
    "SRC-0030",
    "SRC-0031",
    "SRC-0034",
    "SRC-0038",
    "SRC-0040",
    "SRC-0041",
    "SRC-0045",
    "SRC-0046",
    "SRC-0047",
    "SRC-0062",
    "SRC-0063",
    "SRC-0079",
    "SRC-0115",
    "SRC-0121",
    "SRC-0124",
    "SRC-0169",
    "SRC-0174",
    "SRC-14-007",
    "SRC-14-031",
    "SRC-14-032",
    "SRC-14-033",
    "SRC-14-039",
    "SRC-14-041",
}
ACTOR = "shadow-cycle-43-core-operator"
BOUNDARY = (
    "Protected non-canonical core execution only. Retrieval proves access to acquired bytes, not substantive truth. "
    "Development dispositions carry no reviewer, owner, release, scientific, clinical, regulatory, conformance, "
    "institutional, or UNESCO authority. Governance remains deferred to issue #101."
)


def _cohort_sources() -> list[dict[str, Any]]:
    cohort = load_json(COHORT_PATH)
    if not isinstance(cohort, dict) or not isinstance(cohort.get("sources"), list):
        raise ValueError("Reviewed cohort must be an object with a sources array")
    sources = [item for item in cohort["sources"] if isinstance(item, dict)]
    observed = {str(item.get("source_id")) for item in sources}
    if observed != EXPECTED_SOURCE_IDS or len(sources) != 25:
        raise ValueError(
            "Reviewed cohort identity mismatch: "
            f"missing={sorted(EXPECTED_SOURCE_IDS - observed)}, "
            f"unexpected={sorted(observed - EXPECTED_SOURCE_IDS)}, count={len(sources)}"
        )
    return sources


def _build_operational_registry(path: Path) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    for item in _cohort_sources():
        sources.append(
            {
                **item,
                "last_successful_retrieval": "2026-07-29",
                "baseline_evidence_state": str(
                    item.get("baseline_evidence_state") or "CURRENT_SOURCE_RETRIEVED"
                ),
                "baseline_verification_state": str(
                    item.get("baseline_verification_state") or "CURRENT_VERIFIED"
                ),
                "network_access_required": True,
                "current_status": "BASELINE_REGISTERED",
                "next_action": "RETRIEVE_AND_COMPARE",
            }
        )
    registry = {
        "metadata": {
            "title": "Issue #43 reviewed 25-source protected-cycle registry",
            "version": "2026-08-core-cycle",
            "source_release": "v1.5 reviewed exact-ID projection",
            "status": "CONTROLLED_OPERATIONAL_INPUT",
            "record_count": len(sources),
            "boundary": BOUNDARY,
        },
        "sources": sources,
    }
    atomic_write_json(path, registry)
    loaded = load_source_registry(path)
    if len(loaded["sources"]) != 25:
        raise AssertionError("Operational registry did not retain all 25 sources")
    return loaded


def _build_plan(registry: dict[str, Any]) -> dict[str, Any]:
    due = [
        {
            "monitor_id": item["monitor_id"],
            "source_id": item["source_id"],
            "url": item["url"],
            "publisher": item["publisher"],
            "source_class": item["source_class"],
            "cadence": item["cadence"],
            "last_checked": item.get("last_successful_retrieval"),
            "next_action": item["next_action"],
            "network_access_required": True,
            "due_on": "2026-08-03",
            "overdue_days": 0,
        }
        for item in registry["sources"]
    ]
    due.sort(key=lambda item: str(item["source_id"]))
    payload = {"as_of": "2026-08-03", "due": due, "manual": [], "not_due": []}
    return {
        "plan_id": f"PLAN-2026-08-03-{sha256_bytes(canonical_json_bytes(payload))[:12]}",
        **payload,
        "counts": {"due": len(due), "manual": 0, "not_due": 0},
        "boundary": BOUNDARY,
    }


def _approve_deterministic_sample(quarantine_root: Path) -> list[dict[str, Any]]:
    successes = sorted(
        list_quarantine_successes(quarantine_root),
        key=lambda item: (str(item.get("source_id")), str(item.get("quarantine_id"))),
    )
    if len(successes) < 5:
        raise RuntimeError(f"Protected precollection produced only {len(successes)} successful captures; five required")
    selected = successes[:5]
    approvals: list[dict[str, Any]] = []
    for record in selected:
        approval = approve_quarantine_record(
            quarantine_root,
            str(record["quarantine_id"]),
            approved_by=ACTOR,
        )
        approvals.append(
            {
                "source_id": approval.get("source_id"),
                "quarantine_id": approval.get("quarantine_id"),
                "approval_state": approval.get("approval_state"),
            }
        )
    if {str(item["approval_state"]) for item in approvals} != {"APPROVED_FOR_HANDOFF"}:
        raise AssertionError("Every selected capture must be approved for evaluation handoff")
    return approvals


def _sanitize_package(
    package: dict[str, Any],
    *,
    registry_path: Path,
    precollection: dict[str, Any],
    approvals: list[dict[str, Any]],
) -> dict[str, Any]:
    stage_results = package.get("stage_results", {})
    prior_summary = load_json(PRIOR_SUMMARY_PATH)
    if not isinstance(prior_summary, dict):
        raise ValueError("Prior public shadow summary must be an object")
    report = {
        "schema_version": 1,
        "issue": "#43",
        "status": package.get("status"),
        "mode": package.get("metadata", {}).get("mode"),
        "core_engineering_complete": package.get("core_engineering_complete"),
        "governance_layer_applied": package.get("governance_layer_applied"),
        "governance_issue": package.get("governance_issue"),
        "release_authority_state": package.get("release_authority_state"),
        "canonical_successor_written": package.get("canonical_successor_written"),
        "assessment_mutation_performed": package.get("assessment_mutation_performed"),
        "monitoring_handoff_kill_switch": package.get("monitoring_handoff_kill_switch"),
        "predecessor": {
            "path": "examples/observatory/canonical_successor_snapshot_v1.7.json",
            "sha256": sha256_file(PREDECESSOR_PATH),
            "expected_sha256": EXPECTED_PREDECESSOR_SHA256,
            "immutable": bool(stage_results.get("apply_delta", {}).get("predecessor_unchanged")),
        },
        "registry": {
            "source_count": 25,
            "sha256": sha256_file(registry_path),
            "reviewed_cohort_sha256": sha256_file(COHORT_PATH),
            "exact_source_ids": sorted(EXPECTED_SOURCE_IDS),
        },
        "prior_observed_run": {
            "run_id": prior_summary.get("metadata", {}).get("run_id"),
            "live_collection_counts": prior_summary.get("live_collection_counts"),
            "candidate_count": prior_summary.get("candidate_count"),
            "formal_disposition": prior_summary.get("formal_disposition"),
        },
        "fresh_precollection": {
            "collection_run": precollection.get("collection_run"),
            "capture_digest_count": len(precollection.get("capture_digests", [])),
            "failure_count": len(precollection.get("failure_summaries", [])),
            "approved_evaluation_sample": approvals,
        },
        "source_outcomes": package.get("source_outcomes", []),
        "stats": package.get("stats", {}),
        "stages": {
            "plan": stage_results.get("plan"),
            "collect": stage_results.get("collect"),
            "quarantine_approve_handoff": {
                "handoff_count": len(stage_results.get("quarantine_approve_handoff", {}).get("handoffs", [])),
                "monitoring_handoff_kill_switch": stage_results.get("quarantine_approve_handoff", {}).get(
                    "monitoring_handoff_kill_switch"
                ),
                "canonical_workbench_mutated": stage_results.get("quarantine_approve_handoff", {}).get(
                    "canonical_workbench_mutated"
                ),
            },
            "record_snapshot": {"count": stage_results.get("record_snapshot", {}).get("count")},
            "compare_snapshots": stage_results.get("compare_snapshots"),
            "create_change_candidate": stage_results.get("create_change_candidate"),
            "development_disposition": stage_results.get("development_disposition"),
            "build_refresh_candidate": stage_results.get("build_refresh_candidate"),
            "compile_adjudicated_delta": stage_results.get("compile_adjudicated_delta"),
            "apply_delta": {
                "apply_id": stage_results.get("apply_delta", {}).get("apply_id"),
                "status": stage_results.get("apply_delta", {}).get("status"),
                "predecessor_unchanged": stage_results.get("apply_delta", {}).get("predecessor_unchanged"),
            },
            "reopening_analysis": stage_results.get("reopening_analysis"),
            "publications": {
                "release_sha256": stage_results.get("publications", {}).get("release_sha256"),
                "reconciled": stage_results.get("publications", {}).get("reconciled"),
                "depth": stage_results.get("publications", {}).get("depth"),
                "product_types": sorted(stage_results.get("publications", {}).get("products", {})),
            },
        },
        "protected_artifact": {
            "retained_outside_git": True,
            "actions_artifact_name": "protected-shadow-cycle-43",
            "capture_bodies_in_git": False,
        },
        "withheld_claims": [
            "No reviewer or owner opinion is created by this core execution.",
            "No GO authorization or canonical observatory successor is created.",
            "No assessment mutation, scientific validity, clinical safety, regulatory authorization, conformance, institutional endorsement, or official UNESCO status is established.",
        ],
        "boundary": BOUNDARY,
    }
    required_truths = {
        "status": report["status"] == "SHADOW_EVALUATION_NOT_CANONICAL",
        "core_engineering_complete": report["core_engineering_complete"] is True,
        "governance_deferred": report["governance_layer_applied"] is False
        and report["governance_issue"] == "#101",
        "no_canonical_successor": report["canonical_successor_written"] is False,
        "no_assessment_mutation": report["assessment_mutation_performed"] is False,
        "handoff_disabled": report["monitoring_handoff_kill_switch"] == "DISABLED",
        "predecessor_immutable": report["predecessor"]["immutable"] is True,
        "predecessor_hash": report["predecessor"]["sha256"] == EXPECTED_PREDECESSOR_SHA256,
        "five_candidates": report["stats"].get("candidates", {}).get("generated") == 5,
        "five_development_dispositions": report["stats"].get("development_disposition", {}).get("records") == 5,
        "products_reconciled": report["stages"]["publications"].get("reconciled") is True,
    }
    report["acceptance_checks"] = required_truths
    report["acceptance_status"] = "PASS" if all(required_truths.values()) else "FAIL"
    if report["acceptance_status"] != "PASS":
        raise AssertionError(f"Core cycle acceptance failed: {json.dumps(required_truths, sort_keys=True)}")
    return report


def execute(output_root: Path) -> dict[str, Any]:
    output_root = output_root.resolve()
    protected_root = output_root / "protected"
    quarantine_root = protected_root / "quarantine"
    evaluation_workspace = protected_root / "evaluation-workspace"
    cycle_output = protected_root / "cycle-output"
    reports_root = output_root / "reports"
    for path in (quarantine_root, evaluation_workspace, cycle_output, reports_root):
        path.mkdir(parents=True, exist_ok=True)

    predecessor_hash = sha256_file(PREDECESSOR_PATH)
    if predecessor_hash != EXPECTED_PREDECESSOR_SHA256:
        raise ValueError(
            f"v1.7 predecessor hash mismatch: expected {EXPECTED_PREDECESSOR_SHA256}, observed {predecessor_hash}"
        )

    registry_path = protected_root / "operational-registry.json"
    registry = _build_operational_registry(registry_path)
    plan = _build_plan(registry)
    atomic_write_json(protected_root / "reviewed-plan.json", plan)

    precollection = run_live_cohort_collection(
        plan=plan,
        registry=registry,
        registry_sha256=sha256_file(registry_path),
        quarantine_root=quarantine_root,
    )
    atomic_write_json(protected_root / "precollection-summary.json", precollection)
    approvals = _approve_deterministic_sample(quarantine_root)
    atomic_write_json(protected_root / "evaluation-approvals.json", approvals)

    package = run_live_evaluation_cycle(
        evaluation_workspace=evaluation_workspace,
        registry_path=registry_path,
        predecessor_path=PREDECESSOR_PATH,
        quarantine_root=quarantine_root,
        output_dir=cycle_output,
        refresh_version="shadow-cycle-43-20260803",
        evidence_cutoff="2026-08-03",
        apply_id="apply-shadow-cycle-43-20260803",
        plan=plan,
        sample_size=5,
        approve_handoff=True,
        development_disposition=CycleDevelopmentDispositionSpec(
            decision="ACCEPT",
            change_class="FIELD_UPDATE",
            materiality="NON_MATERIAL",
            reopening_effect="NO_EFFECT",
            rationale=(
                "Development-only disposition for the authorized issue #43 core pipeline. "
                "Substantive governance and release authority remain deferred to #101."
            ),
        ),
        actor=ACTOR,
        as_of="2026-08-03",
    )
    atomic_write_json(protected_root / "cycle-package.json", package)
    report = _sanitize_package(
        package,
        registry_path=registry_path,
        precollection=precollection,
        approvals=approvals,
    )
    atomic_write_json(reports_root / "shadow-cycle-43-execution.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    report = execute(args.output_root)
    print(
        json.dumps(
            {
                "issue": report["issue"],
                "status": report["status"],
                "acceptance_status": report["acceptance_status"],
                "candidate_count": report["stats"].get("candidates", {}).get("generated"),
                "products_reconciled": report["stages"]["publications"].get("reconciled"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
