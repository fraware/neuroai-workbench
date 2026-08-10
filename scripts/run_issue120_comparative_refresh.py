#!/usr/bin/env python3
"""Execute issue #120 comparative live refresh from externally supplied protected inputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from neuroai_workbench.shadow_refresh.comparative import (
    ProtectedBaselineBinding,
    build_public_comparative_report,
    run_comparative_live_refresh,
    write_public_comparative_report,
)
from neuroai_workbench.util import atomic_write_json, load_json, sha256_file


def _load_object(path: Path, name: str) -> dict[str, object]:
    value = load_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--predecessor", type=Path, required=True)
    parser.add_argument("--baseline-quarantine-root", type=Path, required=True)
    parser.add_argument("--baseline-summary", type=Path, required=True)
    parser.add_argument("--evaluation-workspace", type=Path, required=True)
    parser.add_argument("--current-quarantine-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--public-output-dir", type=Path, required=True)
    parser.add_argument("--refresh-version", default="v2.3.0-dev")
    parser.add_argument("--evidence-cutoff", required=True)
    parser.add_argument("--apply-id", required=True)
    parser.add_argument("--actor", default="issue-120-comparative-refresh")
    parser.add_argument("--baseline-artifact-id", required=True)
    parser.add_argument("--baseline-artifact-name", required=True)
    parser.add_argument("--baseline-artifact-sha256", required=True)
    parser.add_argument("--baseline-workflow-run-id", required=True)
    parser.add_argument("--baseline-workbench-commit", required=True)
    parser.add_argument("--expected-predecessor-sha256")
    parser.add_argument("--expected-baseline-summary-sha256")
    args = parser.parse_args()

    registry = args.registry.resolve()
    plan_path = args.plan.resolve()
    predecessor = args.predecessor.resolve()
    baseline_summary = args.baseline_summary.resolve()
    if args.expected_predecessor_sha256 and sha256_file(predecessor) != args.expected_predecessor_sha256:
        raise ValueError("Predecessor SHA-256 does not match the issue #120 execution contract")
    if args.expected_baseline_summary_sha256 and sha256_file(baseline_summary) != args.expected_baseline_summary_sha256:
        raise ValueError("Baseline summary SHA-256 does not match the issue #120 execution contract")

    plan = _load_object(plan_path, "Reviewed plan")
    if _load_object(args.registry.resolve(), "Operational registry").get("metadata") is None:
        raise ValueError("Operational registry metadata is required")
    plan_counts = plan.get("counts")
    if not isinstance(plan_counts, dict) or plan_counts != {"due": 25, "manual": 0, "not_due": 0}:
        raise ValueError(f"Issue #120 requires the exact reviewed 25-source cohort; got {plan_counts!r}")

    binding = ProtectedBaselineBinding(
        artifact_id=args.baseline_artifact_id,
        artifact_name=args.baseline_artifact_name,
        artifact_sha256=args.baseline_artifact_sha256,
        workflow_run_id=args.baseline_workflow_run_id,
        workbench_commit=args.baseline_workbench_commit,
    )
    package = run_comparative_live_refresh(
        evaluation_workspace=args.evaluation_workspace.resolve(),
        registry_path=registry,
        predecessor_path=predecessor,
        baseline_quarantine_root=args.baseline_quarantine_root.resolve(),
        baseline_summary_path=baseline_summary,
        quarantine_root=args.current_quarantine_root.resolve(),
        output_dir=args.output_dir.resolve(),
        plan=plan,
        refresh_version=args.refresh_version,
        evidence_cutoff=args.evidence_cutoff,
        apply_id=args.apply_id,
        baseline_binding=binding,
        actor=args.actor,
    )

    public_root = args.public_output_dir.resolve()
    public_root.mkdir(parents=True, exist_ok=True)
    report = build_public_comparative_report(
        package=package,
        predecessor_path=predecessor,
        registry_path=registry,
    )
    report_path = public_root / "comparative-refresh-report.json"
    report_record = write_public_comparative_report(report_path, report)
    projection_manifest = {
        "schema_version": "1.0",
        "artifact": "issue_120_public_projection_manifest",
        "status": "CANDIDATE_PUBLIC_PROJECTION_NOT_CANONICAL",
        "workbench_refresh_version": args.refresh_version,
        "inputs": {
            "registry_sha256": sha256_file(registry),
            "predecessor_sha256": sha256_file(predecessor),
            "baseline_summary_sha256": sha256_file(baseline_summary),
            "baseline_artifact": binding.as_dict(),
        },
        "public_artifacts": {
            "comparative_refresh_report": report_record,
            "candidate_successor_sha256": sha256_file(Path(package["stage_results"]["apply_delta"]["successor_path"])),
            "adjudicated_delta_sha256": sha256_file(
                Path(package["stage_results"]["compile_adjudicated_delta"]["path"])
            ),
            "cycle_report_sha256": sha256_file(Path(package["report_path"])),
        },
        "counts": {
            "source_outcomes": len(package.get("source_outcomes", [])),
            "comparisons": package["stage_results"]["compare_snapshots"]["count"],
            "candidates": package["stage_results"]["create_change_candidate"]["count"],
            "development_dispositions": package["stage_results"]["development_disposition"]["count"],
            "delta_operations": package["stage_results"]["compile_adjudicated_delta"].get("operation_count"),
            "reopening_recommendations": package["stage_results"]["reopening_analysis"].get("recommendation_count"),
        },
        "safety": {
            "contains_protected_capture_bytes": False,
            "contains_protected_paths": False,
            "contains_delta_operations": False,
            "canonical_successor_written": package.get("canonical_successor_written"),
            "assessment_mutation_performed": package.get("assessment_mutation_performed"),
            "governance_layer_applied": package.get("governance_layer_applied"),
            "release_authority_state": package.get("release_authority_state"),
        },
        "boundary": (
            "Public projection manifest contains hashes and digest-level comparison/outcome records only. "
            "It excludes capture bodies, protected paths, credentials, private identities, operations extracts, "
            "and any claim of canonical or institutional authority."
        ),
    }
    projection_path = public_root / "public-projection-manifest.json"
    atomic_write_json(projection_path, projection_manifest)
    public_manifest = {
        "comparative_refresh_report": {
            "path": report_path.name,
            "sha256": sha256_file(report_path),
        },
        "public_projection_manifest": {
            "path": projection_path.name,
            "sha256": sha256_file(projection_path),
        },
    }
    atomic_write_json(public_root / "SHA256_MANIFEST.json", public_manifest)

    print(json.dumps({"cycle": package["stats"], "public": public_manifest}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
