#!/usr/bin/env python3
"""Execute a non-canonical shadow refresh rehearsal against an ops workspace.

Offline-first: plans monitoring and records observed plan/freeze metrics without
network retrieval. Artifacts are always SHADOW_EVALUATION_NOT_CANONICAL.
"""

from __future__ import annotations

import argparse
import json
import os
import re
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
    SHADOW_EVALUATION_STATUS,
    SHADOW_REFRESH_BOUNDARY,
    compute_go_no_go_metrics,
)
from neuroai_workbench.util import atomic_write_json, canonical_json_bytes, sha256_bytes, sha256_file, utc_now

OPS_ENV = "NEUROAI_OPS_WORKSPACE"
CATEGORY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("PRIMA_SCIENCE", re.compile(r"prima|science\.xyz", re.I)),
    ("SYNCHRON", re.compile(r"synchron|stentrode", re.I)),
    ("PARADROMICS", re.compile(r"paradromics|connexus", re.I)),
    ("BRAIN2QWERTY", re.compile(r"brain2qwerty", re.I)),
    ("FDA_ADBS", re.compile(r"adaptive|dbs|deep.?brain|neuromodulation", re.I)),
    ("BRAINGATE2", re.compile(r"braingate", re.I)),
    ("REGISTRY", re.compile(r"clinicaltrials|fda\.gov|eudamed|registry", re.I)),
    ("OWNERSHIP_FUNDING", re.compile(r"investor|funding|acquisition|ownership|tether", re.I)),
    ("SAFETY_SUPPLIER", re.compile(r"safety|adverse|supplier|recall|heraeus|mfds", re.I)),
]


def _blob(record: dict[str, Any]) -> str:
    return " ".join(str(record.get(key, "")) for key in ("publisher", "url", "source_id", "source_class", "monitor_id"))


def select_cohort(registry: dict[str, Any], *, target_count: int = 25) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    used: set[str] = set()
    for category, pattern in CATEGORY_PATTERNS:
        hits = [
            record
            for record in registry["sources"]
            if isinstance(record, dict) and record.get("source_id") not in used and pattern.search(_blob(record))
        ]
        for record in hits[:3]:
            used.add(str(record["source_id"]))
            selected.append({**record, "cohort_category": category})
            if len(selected) >= target_count:
                return selected
    for record in registry["sources"]:
        if len(selected) >= target_count:
            break
        if not isinstance(record, dict):
            continue
        source_id = str(record.get("source_id"))
        if source_id in used:
            continue
        used.add(source_id)
        selected.append({**record, "cohort_category": "DIVERSITY_PAD"})
    return selected


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
    parser.add_argument("--target-count", type=int, default=25)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Defaults to <ops>/runs/shadow-refresh-<month>/",
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

    if not (workspace / "observatory" / "monitoring" / "registry" / "registry.json").is_file():
        initialize_monitoring(workspace, registry_path, actor="shadow-refresh")

    cohort_records = select_cohort(registry, target_count=args.target_count)
    source_ids = [str(item["source_id"]) for item in cohort_records]
    plan = plan_monitoring_run(workspace, as_of=args.as_of, source_ids=source_ids)

    cohort_doc = {
        "metadata": {
            "title": "Shadow refresh high-value source cohort (ops-derived)",
            "cohort_id": f"SHADOW-COHORT-{args.run_month}",
            "version": args.run_month,
            "status": SHADOW_EVALUATION_STATUS,
            "source_count": len(cohort_records),
            "evaluation_issue": "#43",
            "boundary": SHADOW_REFRESH_BOUNDARY,
        },
        "sources": [
            {
                "source_id": item["source_id"],
                "monitor_id": item["monitor_id"],
                "url": item.get("url"),
                "publisher": item.get("publisher"),
                "source_class": item.get("source_class"),
                "cohort_category": item.get("cohort_category"),
                "cadence": item.get("cadence"),
            }
            for item in cohort_records
        ],
    }
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
    run_results = observed_run_results_from_plan(plan, run_id=run_id)
    metrics = compute_go_no_go_metrics(
        run_results,
        generated_at=utc_now(),
        generated_by="run_shadow_refresh.py",
    )
    observed_context = {
        "cohort_size": len(cohort_records),
        "plan_counts": plan["counts"],
        "network_retrieval": "NOT_EXECUTED_OFFLINE_FIRST",
        "status": SHADOW_EVALUATION_STATUS,
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }

    atomic_write_json(output_root / "cohort.json", cohort_doc)
    atomic_write_json(output_root / "freeze_manifest.json", freeze)
    atomic_write_json(output_root / "monitor_plan.json", {**plan, "status": SHADOW_EVALUATION_STATUS})
    atomic_write_json(output_root / "run_results.json", run_results)
    atomic_write_json(output_root / "observed_context.json", observed_context)
    atomic_write_json(output_root / "go_no_go_metrics.json", metrics)

    public_summary = {
        "run_id": run_id,
        "status": SHADOW_EVALUATION_STATUS,
        "cohort_size": len(cohort_records),
        "source_ids": source_ids,
        "plan_counts": plan["counts"],
        "recommendation": metrics["evaluation"]["recommendation"],
        "network_retrieval": "NOT_EXECUTED_OFFLINE_FIRST",
        "freeze_hashes": freeze["configuration_hashes"],
        "withheld_claims": metrics["withheld_claims"],
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }
    atomic_write_json(output_root / "public_metrics_summary.json", public_summary)
    json.dump(public_summary, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
