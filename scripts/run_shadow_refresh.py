#!/usr/bin/env python3
"""Execute a non-canonical shadow refresh rehearsal against an ops workspace.

Offline-first by default: plans monitoring and records observed plan/freeze
metrics without network retrieval. Optional ``--live`` collection requires
``NEUROAI_LIVE_COLLECTION=1`` and writes quarantine-only under the ops run root.

Artifacts are always SHADOW_EVALUATION_NOT_CANONICAL.

Frozen cohorts must be loaded from a reviewed exact source_id manifest.
Regex discovery remains available only as a non-authoritative helper and cannot
write the freeze artifact.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from neuroai_workbench.monitoring import (
    initialize_monitoring,
    load_source_registry,
    plan_monitoring_run,
    validate_source_registry,
)
from neuroai_workbench.shadow_refresh import (
    LIVE_COLLECTION_ENV,
    SHADOW_EVALUATION_STATUS,
    SHADOW_REFRESH_BOUNDARY,
    bind_reviewed_cohort_to_registry,
    compute_go_no_go_metrics,
    discover_cohort_candidates,
    load_reviewed_cohort_manifest,
    observed_run_results_from_live,
    run_live_cohort_collection,
)
from neuroai_workbench.util import atomic_write_json, canonical_json_bytes, sha256_bytes, sha256_file, utc_now

OPS_ENV = "NEUROAI_OPS_WORKSPACE"


def build_freeze_manifest(
    *,
    registry_path: Path,
    workspace: Path,
    policy_paths: list[Path],
    workbench_root: Path,
    cohort_doc: dict[str, Any],
    run_id: str,
    evidence_cutoff: str,
) -> dict[str, Any]:
    mon_policy = next((path for path in policy_paths if "monitoring_policy" in path.name), None)
    reopen_policy = next((path for path in policy_paths if "reopening_policy" in path.name), None)
    workbench_sha = _git_head(workbench_root)
    if workbench_sha is None or len(workbench_sha) != 40:
        workbench_sha = sha256_bytes(b"workbench-unresolved")
    else:
        # Expand short commit to sha256-shaped pin via hashing the commit id bytes.
        workbench_sha = sha256_bytes(workbench_sha.encode("utf-8"))
    cohort_sha = sha256_bytes(canonical_json_bytes(cohort_doc))
    placeholder = sha256_bytes(b"shadow-offline-not-executed")
    return {
        "metadata": {
            "title": "Shadow refresh freeze manifest",
            "run_id": run_id,
            "frozen_at": utc_now(),
            "status": SHADOW_EVALUATION_STATUS,
            "evidence_cutoff": evidence_cutoff,
            "frozen_by": "run_shadow_refresh.py",
        },
        "configuration_hashes": {
            "registry_sha256": sha256_file(registry_path),
            "monitoring_policy_sha256": sha256_file(mon_policy) if mon_policy and mon_policy.is_file() else placeholder,
            "reopening_policy_sha256": sha256_file(reopen_policy)
            if reopen_policy and reopen_policy.is_file()
            else placeholder,
            "collector_sha256": placeholder,
            "workbench_sha256": workbench_sha,
            "entity_resolution_sha256": placeholder,
            "extraction_sha256": placeholder,
            "reviewer_roster_sha256": placeholder,
        },
        "cohort_reference": {
            "cohort_id": cohort_doc["metadata"]["cohort_id"],
            "sha256": cohort_sha,
            "source_count": int(cohort_doc["metadata"]["source_count"]),
        },
        "withheld_claims": [
            "Freeze hashes identify configuration bytes only; they do not authorize retrieval or a successor release.",
            "Collector/entity/extraction/reviewer hashes may be offline placeholders until those configs are frozen.",
        ],
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }


def _git_head(repo_root: Path) -> str | None:
    git_dir = repo_root / ".git"
    if not git_dir.exists():
        return None
    try:
        import subprocess

        completed = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def observed_run_results_from_plan(plan: dict[str, Any], *, run_id: str) -> dict[str, Any]:
    """Derive observed offline run results from plan coverage (no network retrieval)."""
    due = len(plan.get("due", []))
    manual = len(plan.get("manual", []))
    not_due = len(plan.get("not_due", []))
    planned = due + manual + not_due
    # Offline rehearsal: retrieval not executed; attempted equals planned, succeeded stays 0.
    return {
        "metadata": {
            "title": "Observed offline-first shadow refresh run results",
            "status": SHADOW_EVALUATION_STATUS,
        },
        "run_id": run_id,
        "captures": {
            "attempted": planned,
            "succeeded": 0,
            "failed": 0,
            "unchanged": 0,
            "changed": 0,
        },
        "candidates": {
            "generated": 0,
            "true_positives": 0,
            "false_positives": 0,
            "false_negatives": 0,
            "unsupported": 0,
        },
        "entity_resolution": {"decisions": 0, "correct": 0},
        "review": {
            "agreements": 0,
            "disagreements": 0,
            "sampled_candidates": 0,
            "total_adjudication_minutes": 0,
        },
        "reopening": {"recommended": 0, "true_positives": 0, "false_positives": 0},
        "provenance": {"complete_records": planned, "total_records": planned},
        "publication": {"reconciliation_errors": 0},
        "model_assistance": {"minutes_saved": 0.0, "errors_introduced": 0},
        "cost_by_source_class": {},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ops-workspace", type=Path, default=None)
    parser.add_argument("--workbench-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--as-of", default="2026-08-02")
    parser.add_argument("--run-month", default="202608")
    parser.add_argument(
        "--cohort-manifest",
        type=Path,
        default=None,
        help="Reviewed exact-ID cohort JSON (required for freeze/plan unless --discover-only)",
    )
    parser.add_argument(
        "--discover-only",
        action="store_true",
        help="Emit non-authoritative regex discovery candidates; does not write freeze artifacts",
    )
    parser.add_argument("--target-count", type=int, default=25)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Defaults to <ops>/runs/shadow-refresh-<month>/",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            f"Execute allowlisted live HTTP collection for the reviewed cohort. "
            f"Requires {LIVE_COLLECTION_ENV}=1. Quarantine-only; no monitoring handoff; "
            "remains SHADOW_EVALUATION_NOT_CANONICAL."
        ),
    )
    args = parser.parse_args(argv)

    ops = args.ops_workspace or Path(os.environ.get(OPS_ENV, ""))
    if not ops.is_dir():
        sys.stderr.write(f"ERROR {OPS_ENV} must point at Operations Starter extract\n")
        return 2

    registry_path = ops / "01_CONFIG" / "source_monitor_registry_v1.5.json"
    workspace = ops / "03_WORKBENCH"
    output_root = args.output_root or (ops / "runs" / f"shadow-refresh-{args.run_month}")
    output_root.mkdir(parents=True, exist_ok=True)

    registry = load_source_registry(registry_path)
    validation = validate_source_registry(registry)
    if not validation["valid"]:
        sys.stderr.write("ERROR registry invalid\n")
        return 1

    if args.discover_only:
        candidates = discover_cohort_candidates(registry, target_count=args.target_count)
        discovery_doc = {
            "metadata": {
                "title": "Non-authoritative shadow cohort discovery candidates",
                "status": SHADOW_EVALUATION_STATUS,
                "authoritative": False,
                "source_count": len(candidates),
                "boundary": (
                    "Discovery candidates are regex-assisted suggestions only. "
                    "They cannot be used as a freeze artifact without a reviewed exact-ID manifest."
                ),
            },
            "candidates": [
                {
                    "source_id": item.get("source_id"),
                    "publisher": item.get("publisher"),
                    "url": item.get("url"),
                    "discovery_category": item.get("discovery_category"),
                    "authoritative": False,
                }
                for item in candidates
            ],
        }
        atomic_write_json(output_root / "discovery_candidates.json", discovery_doc)
        json.dump(discovery_doc, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    default_manifest = (
        args.workbench_root / "examples" / "shadow_refresh" / "SHADOW_REFRESH_COHORT_REVIEWED_v202608.json"
    )
    ops_manifest = ops / "04_REVIEW_QUEUE" / "SHADOW_REFRESH_COHORT_REVIEWED_v202608.json"
    cohort_path = args.cohort_manifest
    if cohort_path is None:
        if ops_manifest.is_file():
            cohort_path = ops_manifest
        elif default_manifest.is_file():
            cohort_path = default_manifest
        else:
            sys.stderr.write(
                "ERROR reviewed cohort manifest required (--cohort-manifest). "
                "Use --discover-only for non-authoritative regex candidates.\n"
            )
            return 2

    try:
        cohort_doc = load_reviewed_cohort_manifest(cohort_path)
        bind_reviewed_cohort_to_registry(cohort_doc, registry)
    except ValueError as exc:
        sys.stderr.write(f"ERROR {exc}\n")
        return 1

    if not (workspace / "observatory" / "monitoring" / "registry" / "registry.json").is_file():
        initialize_monitoring(workspace, registry_path, actor="shadow-refresh")

    source_ids = [str(item["source_id"]) for item in cohort_doc["sources"]]
    plan = plan_monitoring_run(workspace, as_of=args.as_of, source_ids=source_ids)

    run_id = f"SHADOW-RUN-{args.run_month}-{sha256_bytes(canonical_json_bytes(plan))[:12]}"
    freeze = build_freeze_manifest(
        registry_path=registry_path,
        workspace=workspace,
        policy_paths=[
            ops / "01_CONFIG" / "monitoring_policy_v1.json",
            ops / "01_CONFIG" / "reopening_policy_v1.json",
        ],
        workbench_root=args.workbench_root,
        cohort_doc=cohort_doc,
        run_id=run_id,
        evidence_cutoff=args.as_of,
    )

    live_package: dict[str, Any] | None = None
    network_retrieval = "NOT_EXECUTED_OFFLINE_FIRST"
    if args.live:
        if os.environ.get(LIVE_COLLECTION_ENV, "").strip() != "1":
            sys.stderr.write(
                f"ERROR --live requires {LIVE_COLLECTION_ENV}=1 (CI and default runs remain network-free)\n"
            )
            return 2
        quarantine_root = output_root / "captures" / "quarantine"
        try:
            live_package = run_live_cohort_collection(
                plan=plan,
                registry=registry,
                registry_sha256=sha256_file(registry_path),
                quarantine_root=quarantine_root,
            )
        except PermissionError as exc:
            sys.stderr.write(f"ERROR {exc}\n")
            return 2
        except (ValueError, OSError, RuntimeError, TypeError, KeyError) as exc:
            sys.stderr.write(f"ERROR live collection failed: {exc}\n")
            return 1
        network_retrieval = "EXECUTED_LIVE_QUARANTINE_ONLY"
        run_results = observed_run_results_from_live(
            live_package,
            run_id=run_id,
            planned_total=len(source_ids),
        )
        freeze["configuration_hashes"]["collector_sha256"] = str(live_package["collector"]["configuration_hash"])
    else:
        run_results = observed_run_results_from_plan(plan, run_id=run_id)

    metrics = compute_go_no_go_metrics(
        run_results,
        generated_at=utc_now(),
        generated_by="run_shadow_refresh.py",
    )
    observed_context = {
        "cohort_size": len(source_ids),
        "cohort_manifest": str(cohort_path),
        "plan_counts": plan["counts"],
        "network_retrieval": network_retrieval,
        "live_collection_env": LIVE_COLLECTION_ENV,
        "status": SHADOW_EVALUATION_STATUS,
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }
    if live_package is not None:
        observed_context["live_collection_counts"] = live_package["collection_run"]["counts"]
        observed_context["capture_digest_count"] = len(live_package.get("capture_digests", []))

    atomic_write_json(output_root / "cohort.json", cohort_doc)
    atomic_write_json(output_root / "freeze_manifest.json", freeze)
    atomic_write_json(output_root / "monitor_plan.json", {**plan, "status": SHADOW_EVALUATION_STATUS})
    atomic_write_json(output_root / "run_results.json", run_results)
    atomic_write_json(output_root / "observed_context.json", observed_context)
    atomic_write_json(output_root / "go_no_go_metrics.json", metrics)
    if live_package is not None:
        atomic_write_json(output_root / "live_collection.json", live_package)

    public_summary = {
        "run_id": run_id,
        "status": SHADOW_EVALUATION_STATUS,
        "cohort_size": len(source_ids),
        "source_ids": source_ids,
        "plan_counts": plan["counts"],
        "recommendation": metrics["evaluation"]["recommendation"],
        "network_retrieval": network_retrieval,
        "freeze_hashes": freeze["configuration_hashes"],
        "withheld_claims": list(metrics["withheld_claims"])
        + [
            "Live capture digests prove retrieval bytes only; they do not establish substantive truth.",
            "Protected capture bodies remain under the ops workspace and must not be committed to git.",
        ],
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }
    if live_package is not None:
        public_summary["live_collection_counts"] = live_package["collection_run"]["counts"]
        public_summary["capture_digest_count"] = len(live_package.get("capture_digests", []))
        public_summary["capture_digests"] = [
            {
                "source_id": item.get("source_id"),
                "sha256": item.get("sha256"),
                "http_status": item.get("http_status"),
                "size_bytes": item.get("size_bytes"),
            }
            for item in live_package.get("capture_digests", [])
        ]
        public_summary["failure_summaries"] = [
            {
                "source_id": item.get("source_id"),
                "failure_class": item.get("failure_class"),
                "http_status": item.get("http_status"),
            }
            for item in live_package.get("failure_summaries", [])
        ]
    atomic_write_json(output_root / "public_metrics_summary.json", public_summary)
    json.dump(public_summary, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
