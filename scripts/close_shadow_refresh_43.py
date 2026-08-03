#!/usr/bin/env python3
"""Prepare issue #43 core shadow-refresh artifacts without activating governance.

Requires NEUROAI_OPS_WORKSPACE. Live retries additionally require
NEUROAI_LIVE_COLLECTION=1. Writes evaluation artifacts under the protected ops
run root. Public outputs contain digests and counts only.

The script does not create reviewer profiles, review opinions, owner approvals,
or release-authority records. Human governance is deferred to issue #101.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from neuroai_workbench.monitoring import load_source_registry
from neuroai_workbench.shadow_refresh import (
    LIVE_COLLECTION_ENV,
    SHADOW_EVALUATION_STATUS,
    SHADOW_REFRESH_BOUNDARY,
)
from neuroai_workbench.shadow_refresh.closure import (
    DEFAULT_FAILED_SOURCE_IDS,
    EVAL_ACTOR,
    classify_retrieval_failure,
    create_first_capture_candidates,
    handoff_quarantine_sample_to_evaluation,
    list_quarantine_successes,
    publisher_mentions_for_sources,
    retry_failed_sources,
    run_offline_entity_sample,
    run_offline_extraction_sample,
)
from neuroai_workbench.util import atomic_write_json, load_json, sha256_file, utc_now

OPS_ENV = "NEUROAI_OPS_WORKSPACE"
GOVERNANCE_ISSUE = "#101"
_FAILED_SOURCE_SET = frozenset(DEFAULT_FAILED_SOURCE_IDS)


def _load_prior_live(run_root: Path) -> dict[str, Any]:
    path = run_root / "live_collection.json"
    if not path.is_file():
        raise FileNotFoundError(f"Missing prior live collection package: {path}")
    value = load_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"Prior live collection package must be an object: {path}")
    return value


def _ordered_unique_outcomes(outcomes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Retain one typed outcome per expected source in deterministic source order."""
    by_source: dict[str, dict[str, Any]] = {}
    for outcome in outcomes:
        source_id = str(outcome.get("source_id") or "")
        if source_id in _FAILED_SOURCE_SET:
            by_source[source_id] = outcome
    return [by_source[source_id] for source_id in DEFAULT_FAILED_SOURCE_IDS if source_id in by_source]


def _prior_typed_outcomes(run_root: Path, quarantine_root: Path) -> tuple[list[dict[str, Any]], bool]:
    """Load the newest available typed failure record for each expected source."""
    failure_dirs = [
        run_root / "wave2-closure" / "retry-quarantine" / "failures",
        quarantine_root / "failures",
    ]
    for failures_dir in failure_dirs:
        if not failures_dir.is_dir():
            continue
        outcomes: list[dict[str, Any]] = []
        for path in sorted(failures_dir.glob("*.json")):
            record = load_json(path)
            if isinstance(record, dict) and record.get("source_id") in _FAILED_SOURCE_SET:
                outcomes.append(classify_retrieval_failure(record))
        normalized = _ordered_unique_outcomes(outcomes)
        if normalized:
            return normalized, failures_dir == (run_root / "wave2-closure" / "retry-quarantine" / "failures")
    return [], False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ops-workspace", type=Path, default=None)
    parser.add_argument("--workbench-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--run-root", type=Path, default=None)
    parser.add_argument("--sample-size", type=int, default=5)
    parser.add_argument("--skip-live-retry", action="store_true")
    parser.add_argument("--force-live-retry", action="store_true")
    args = parser.parse_args(argv)

    ops = args.ops_workspace or Path(os.environ.get(OPS_ENV, ""))
    if not ops.is_dir():
        sys.stderr.write(f"ERROR {OPS_ENV} must point at Operations Starter extract\n")
        return 2

    registry_path = ops / "01_CONFIG" / "source_monitor_registry_v1.5.json"
    if not registry_path.is_file():
        sys.stderr.write(f"ERROR missing registry at {registry_path}\n")
        return 2

    run_root = args.run_root or (ops / "runs" / "shadow-refresh-202608-live")
    if not run_root.is_dir():
        sys.stderr.write(f"ERROR missing live run root {run_root}\n")
        return 2

    quarantine_root = run_root / "captures" / "quarantine"
    core_root = run_root / "core-closure"
    core_root.mkdir(parents=True, exist_ok=True)
    evaluation_workspace = core_root / "evaluation_workspace"

    try:
        registry = load_source_registry(registry_path)
        prior_live = _load_prior_live(run_root)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        sys.stderr.write(f"ERROR loading core inputs: {exc}\n")
        return 2

    run_id = str(prior_live.get("collection_run", {}).get("run_id") or "SHADOW-RUN-202608-CORE")

    live_enabled = os.environ.get(LIVE_COLLECTION_ENV, "").strip() == "1"
    if args.force_live_retry and not live_enabled:
        sys.stderr.write(f"ERROR --force-live-retry requires {LIVE_COLLECTION_ENV}=1\n")
        return 2

    typed_retry_outcomes: list[dict[str, Any]] = []
    live_retry_executed = False
    retry_root = core_root / "retry-quarantine"
    if live_enabled and not args.skip_live_retry:
        try:
            package = retry_failed_sources(
                registry=registry,
                registry_sha256=sha256_file(registry_path),
                quarantine_root=retry_root,
                source_ids=list(DEFAULT_FAILED_SOURCE_IDS),
            )
        except PermissionError as exc:
            sys.stderr.write(f"ERROR {exc}\n")
            return 2
        except (ValueError, OSError, RuntimeError, TypeError, KeyError) as exc:
            sys.stderr.write(f"ERROR live retry failed: {exc}\n")
            return 1
        typed_retry_outcomes = _ordered_unique_outcomes(list(package.get("typed_outcomes", [])))
        live_retry_executed = True
    else:
        try:
            typed_retry_outcomes, live_retry_executed = _prior_typed_outcomes(run_root, quarantine_root)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            sys.stderr.write(f"ERROR loading prior retry outcomes: {exc}\n")
            return 2

    observed = {str(item.get("source_id")) for item in typed_retry_outcomes}
    for source_id in DEFAULT_FAILED_SOURCE_IDS:
        if source_id not in observed:
            typed_retry_outcomes.append(
                {
                    "source_id": source_id,
                    "outcome_type": "RETRY_NOT_EXECUTED_LIVE_GATE_OFF",
                    "failure_class": "HTTP_ERROR",
                    "finding_effect": "NONE",
                    "status": SHADOW_EVALUATION_STATUS,
                    "boundary": SHADOW_REFRESH_BOUNDARY,
                }
            )
    typed_retry_outcomes = _ordered_unique_outcomes(typed_retry_outcomes)
    retrieval_outcomes_complete = [str(item.get("source_id")) for item in typed_retry_outcomes] == list(
        DEFAULT_FAILED_SOURCE_IDS
    ) and all(item.get("finding_effect") == "NONE" for item in typed_retry_outcomes)

    atomic_write_json(
        core_root / "retrieval_outcomes.json",
        {
            "run_id": run_id,
            "expected_source_ids": list(DEFAULT_FAILED_SOURCE_IDS),
            "live_retry_executed": live_retry_executed,
            "typed_outcomes": typed_retry_outcomes,
            "retrieval_outcomes_complete": retrieval_outcomes_complete,
            "finding_mutation_performed": False,
            "status": SHADOW_EVALUATION_STATUS,
            "boundary": SHADOW_REFRESH_BOUNDARY,
        },
    )

    successes = list_quarantine_successes(quarantine_root)
    approved = [record for record in successes if record.get("approval_state") == "APPROVED_FOR_HANDOFF"]
    if successes and not approved:
        sys.stderr.write("ERROR successful captures exist but none are APPROVED_FOR_HANDOFF\n")
        return 2

    try:
        handoff = handoff_quarantine_sample_to_evaluation(
            quarantine_root=quarantine_root,
            evaluation_workspace=evaluation_workspace,
            registry_path=registry_path,
            sample_size=args.sample_size,
            approved_by=EVAL_ACTOR,
        )
        atomic_write_json(core_root / "evaluation_handoff.json", handoff)

        candidates = create_first_capture_candidates(
            evaluation_workspace=evaluation_workspace,
            handoffs=handoff["handoffs"],
            actor=EVAL_ACTOR,
        )
        atomic_write_json(core_root / "change_candidates.json", candidates)

        source_ids = [str(item["source_id"]) for item in handoff["handoffs"]]
        entity = run_offline_entity_sample(
            evaluation_workspace=evaluation_workspace,
            sample_mentions=publisher_mentions_for_sources(registry, source_ids),
            actor=EVAL_ACTOR,
        )
        atomic_write_json(core_root / "entity_disposition_sample.json", entity)

        extraction = run_offline_extraction_sample(
            evaluation_workspace=evaluation_workspace,
            quarantine_root=quarantine_root,
            handoffs=handoff["handoffs"],
            actor=EVAL_ACTOR,
        )
        atomic_write_json(core_root / "extraction_disposition_sample.json", extraction)
    except (ValueError, OSError, RuntimeError, TypeError, KeyError) as exc:
        sys.stderr.write(f"ERROR core evaluation preparation failed: {exc}\n")
        return 1

    live_counts = dict(prior_live.get("collection_run", {}).get("counts", {}))
    core_complete = (
        int(live_counts.get("total", 0)) == 25
        and retrieval_outcomes_complete
        and len(handoff["handoffs"]) == args.sample_size
        and len(candidates["candidates"]) == args.sample_size
    )
    report = {
        "metadata": {
            "title": "Issue #43 core shadow-refresh preparation report",
            "run_id": run_id,
            "generated_at": utc_now(),
            "status": SHADOW_EVALUATION_STATUS,
        },
        "collection_counts": live_counts,
        "live_retry_executed": live_retry_executed,
        "typed_retry_outcomes": typed_retry_outcomes,
        "retrieval_outcomes_complete": retrieval_outcomes_complete,
        "evaluation_handoffs": len(handoff["handoffs"]),
        "change_candidates": len(candidates["candidates"]),
        "entity_dispositions": int(entity.get("disposition_count", 0)),
        "extraction_dispositions": int(extraction.get("record_count", 0)),
        "core_wave2_complete": core_complete,
        "next_core_step": "RUN_NONCANONICAL_FULL_EVALUATION_CYCLE",
        "governance_layer_applied": False,
        "governance_issue": GOVERNANCE_ISSUE,
        "release_authority_state": "DEFERRED",
        "canonical_successor_written": False,
        "assessment_mutation_performed": False,
        "status": SHADOW_EVALUATION_STATUS,
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }
    atomic_write_json(core_root / "core-preparation-report.json", report)

    public = {
        "metadata": report["metadata"],
        "collection_counts": live_counts,
        "typed_retry_outcomes": [
            {
                "source_id": item.get("source_id"),
                "outcome_type": item.get("outcome_type"),
                "http_status": item.get("http_status"),
                "finding_effect": item.get("finding_effect"),
            }
            for item in typed_retry_outcomes
        ],
        "retrieval_outcomes_complete": retrieval_outcomes_complete,
        "evaluation_handoffs": len(handoff["handoffs"]),
        "change_candidates": len(candidates["candidates"]),
        "core_wave2_complete": core_complete,
        "governance_layer_applied": False,
        "governance_issue": GOVERNANCE_ISSUE,
        "canonical_successor_written": False,
        "capture_bodies_included": False,
        "status": SHADOW_EVALUATION_STATUS,
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }
    atomic_write_json(core_root / "public-core-summary.json", public)
    examples = args.workbench_root / "examples" / "shadow_refresh"
    if examples.is_dir():
        atomic_write_json(examples / "SHADOW_REFRESH_CORE_PUBLIC_SUMMARY_v202608.json", public)

    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if core_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
