#!/usr/bin/env python3
"""Close shadow-refresh issue #43 software/ops steps without forging dual review.

Requires NEUROAI_OPS_WORKSPACE. Live retries additionally require
NEUROAI_LIVE_COLLECTION=1. Writes evaluation artifacts under the ops run root.
Public digests/metrics may be copied into examples/; capture bodies stay in ops.

Evaluation handoff requires quarantine records already APPROVED_FOR_HANDOFF
(per-record). This script does not auto-approve pending captures.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from neuroai_workbench.shadow_refresh import (
    LIVE_COLLECTION_ENV,
    SHADOW_EVALUATION_STATUS,
    SHADOW_REFRESH_BOUNDARY,
)
from neuroai_workbench.shadow_refresh.closure import (
    DEFAULT_FAILED_SOURCE_IDS,
    EVAL_ACTOR,
    build_closure_run_results,
    build_public_closure_summary,
    compute_closure_metrics,
    create_first_capture_candidates,
    handoff_quarantine_sample_to_evaluation,
    list_quarantine_successes,
    publisher_mentions_for_sources,
    record_formal_disposition,
    retry_failed_sources,
    run_offline_entity_sample,
    run_offline_extraction_sample,
    scaffold_dual_human_review,
)
from neuroai_workbench.monitoring import load_source_registry
from neuroai_workbench.util import atomic_write_json, load_json, sha256_file, utc_now

OPS_ENV = "NEUROAI_OPS_WORKSPACE"


def _load_prior_live(run_root: Path) -> dict[str, Any]:
    path = run_root / "live_collection.json"
    if not path.is_file():
        raise FileNotFoundError(f"Missing prior live collection package: {path}")
    return load_json(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ops-workspace", type=Path, default=None)
    parser.add_argument("--workbench-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--run-root",
        type=Path,
        default=None,
        help="Defaults to <ops>/runs/shadow-refresh-202608-live/",
    )
    parser.add_argument("--sample-size", type=int, default=5)
    parser.add_argument(
        "--skip-live-retry",
        action="store_true",
        help="Skip HTTP_ERROR retry even when NEUROAI_LIVE_COLLECTION=1",
    )
    parser.add_argument(
        "--force-live-retry",
        action="store_true",
        help="Require live retry; fail if NEUROAI_LIVE_COLLECTION is unset",
    )
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
    wave2_root = run_root / "wave2-closure"
    wave2_root.mkdir(parents=True, exist_ok=True)
    evaluation_workspace = wave2_root / "evaluation_workspace"

    registry = load_source_registry(registry_path)
    prior_live = _load_prior_live(run_root)
    run_id = str(prior_live.get("collection_run", {}).get("run_id") or "SHADOW-RUN-202608-WAVE2")

    typed_retry_outcomes: list[dict[str, Any]] = []
    retry_package: dict[str, Any] | None = None
    live_retry_executed = False
    live_enabled = os.environ.get(LIVE_COLLECTION_ENV, "").strip() == "1"
    if args.force_live_retry and not live_enabled:
        sys.stderr.write(f"ERROR --force-live-retry requires {LIVE_COLLECTION_ENV}=1\n")
        return 2

    retry_root = wave2_root / "retry-quarantine"
    if live_enabled and not args.skip_live_retry:
        try:
            retry_package = retry_failed_sources(
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
        typed_retry_outcomes = list(retry_package.get("typed_outcomes", []))
        live_retry_executed = True
        atomic_write_json(wave2_root / "retry_outcomes.json", retry_package)
    else:
        from neuroai_workbench.shadow_refresh.closure import classify_retrieval_failure

        # Prefer typed outcomes from a prior Wave 2 retry quarantine when present.
        failure_dirs = [
            retry_root / "failures",
            quarantine_root / "failures",
        ]
        prior_failures: list[dict[str, Any]] = []
        for failures_dir in failure_dirs:
            if not failures_dir.is_dir():
                continue
            batch: list[dict[str, Any]] = []
            for path in sorted(failures_dir.glob("*.json")):
                record = load_json(path)
                if isinstance(record, dict) and record.get("source_id") in set(DEFAULT_FAILED_SOURCE_IDS):
                    batch.append(record)
            if batch:
                prior_failures = batch
                live_retry_executed = failures_dir == (retry_root / "failures")
                break
        typed_retry_outcomes = [classify_retrieval_failure(item) for item in prior_failures]
        seen = {str(item.get("source_id")) for item in typed_retry_outcomes}
        for sid in DEFAULT_FAILED_SOURCE_IDS:
            if sid not in seen:
                typed_retry_outcomes.append(
                    {
                        "source_id": sid,
                        "outcome_type": "RETRY_NOT_EXECUTED_LIVE_GATE_OFF",
                        "failure_class": "HTTP_ERROR",
                        "finding_effect": "NONE",
                        "status": SHADOW_EVALUATION_STATUS,
                        "boundary": SHADOW_REFRESH_BOUNDARY,
                    }
                )
        atomic_write_json(
            wave2_root / "retry_outcomes.json",
            {
                "metadata": {
                    "title": "Shadow refresh HTTP_ERROR outcomes",
                    "status": SHADOW_EVALUATION_STATUS,
                    "recorded_at": utc_now(),
                },
                "live_retry_executed": live_retry_executed,
                "typed_outcomes": typed_retry_outcomes,
                "status": SHADOW_EVALUATION_STATUS,
                "boundary": SHADOW_REFRESH_BOUNDARY,
            },
        )

    successes = list_quarantine_successes(quarantine_root)
    approved = [r for r in successes if r.get("approval_state") == "APPROVED_FOR_HANDOFF"]
    if successes and not approved:
        sys.stderr.write(
            "ERROR quarantine successes exist but none are APPROVED_FOR_HANDOFF; "
            "approve per-record before evaluation handoff "
            "(handoff does not auto-approve pending captures)\n"
        )
        return 2

    handoff = handoff_quarantine_sample_to_evaluation(
        quarantine_root=quarantine_root,
        evaluation_workspace=evaluation_workspace,
        registry_path=registry_path,
        sample_size=args.sample_size,
        approved_by=EVAL_ACTOR,
    )
    atomic_write_json(wave2_root / "evaluation_handoff.json", handoff)

    candidates = create_first_capture_candidates(
        evaluation_workspace=evaluation_workspace,
        handoffs=handoff["handoffs"],
        actor=EVAL_ACTOR,
    )
    atomic_write_json(wave2_root / "change_candidates.json", candidates)

    review = scaffold_dual_human_review(
        evaluation_workspace=evaluation_workspace,
        output_dir=wave2_root,
        actor=EVAL_ACTOR,
    )
    atomic_write_json(wave2_root / "dual_review_scaffold.json", review)

    mention_source_ids = [str(item["source_id"]) for item in handoff["handoffs"]]
    entity = run_offline_entity_sample(
        evaluation_workspace=evaluation_workspace,
        sample_mentions=publisher_mentions_for_sources(registry, mention_source_ids),
        actor=EVAL_ACTOR,
    )
    atomic_write_json(wave2_root / "entity_disposition_sample.json", entity)

    extraction = run_offline_extraction_sample(
        evaluation_workspace=evaluation_workspace,
        quarantine_root=quarantine_root,
        handoffs=handoff["handoffs"],
        actor=EVAL_ACTOR,
    )
    atomic_write_json(wave2_root / "extraction_disposition_sample.json", extraction)

    live_counts = dict(prior_live.get("collection_run", {}).get("counts", {}))
    digests = list(prior_live.get("capture_digests") or [])
    if retry_package is not None:
        # Merge retry successes into digest view without claiming full cohort re-run.
        digests = digests + list(retry_package.get("live_package", {}).get("capture_digests", []))

    run_results = build_closure_run_results(
        run_id=run_id,
        live_succeeded=int(live_counts.get("succeeded", 0)),
        live_failed=int(live_counts.get("failed", 0)),
        live_attempted=int(live_counts.get("total", 0)),
        digest_count=len(digests),
        candidate_count=len(candidates["candidates"]),
        entity_decisions=int(entity.get("disposition_count", 0)),
        entity_correct=0,
        dual_review_complete=False,
    )
    atomic_write_json(wave2_root / "run_results.json", run_results)

    metrics = compute_closure_metrics(run_results, generated_by="close_shadow_refresh_43.py")
    atomic_write_json(wave2_root / "go_no_go_metrics.json", metrics)
    # Keep legacy filename expected by ops docs.
    atomic_write_json(wave2_root / "go-no-go-metrics.json", metrics)

    residual = load_json(wave2_root / "human_residual_checklist.json")
    formal = record_formal_disposition(
        run_id=run_id,
        metrics_recommendation=str(metrics["evaluation"]["recommendation"]),
        dual_review_complete=False,
        owners=["programme-owner", "monitoring-lead"],
        residual_checklist=list(residual.get("checklist", [])),
        typed_retry_outcomes=typed_retry_outcomes,
    )
    atomic_write_json(wave2_root / "formal_disposition.json", formal)

    evaluation_report = {
        "metadata": {
            "title": "Shadow refresh Wave 2 evaluation report",
            "status": SHADOW_EVALUATION_STATUS,
            "generated_at": utc_now(),
            "evaluation_issue": "#43",
        },
        "summary": {
            "prior_live_counts": live_counts,
            "live_retry_executed": live_retry_executed,
            "typed_retry_outcomes": typed_retry_outcomes,
            "evaluation_handoffs": len(handoff["handoffs"]),
            "change_candidates": len(candidates["candidates"]),
            "baseline_comparison": candidates.get("baseline_comparison"),
            "dual_review_complete": False,
            "entity_dispositions": entity.get("disposition_count", 0),
            "extraction_dispositions": extraction.get("record_count", 0),
            "metrics_recommendation": metrics["evaluation"]["recommendation"],
            "formal_disposition": formal["disposition"],
        },
        "human_blocked": [
            "Dual human review opinions on sampled candidates",
            "Any GO disposition authorization after dual review",
        ],
        "withheld_claims": formal["withheld_claims"],
        "status": SHADOW_EVALUATION_STATUS,
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }
    atomic_write_json(wave2_root / "evaluation-report.md.json", evaluation_report)
    report_md = wave2_root / "evaluation-report.md"
    report_md.write_text(
        "\n".join(
            [
                "# Shadow refresh Wave 2 evaluation report",
                "",
                f"- Status: `{SHADOW_EVALUATION_STATUS}`",
                f"- Formal disposition: `{formal['disposition']}`",
                f"- Metrics recommendation: `{metrics['evaluation']['recommendation']}`",
                f"- Dual human review complete: `false`",
                f"- Live retry executed: `{str(live_retry_executed).lower()}`",
                f"- Evaluation handoffs: `{len(handoff['handoffs'])}`",
                f"- Change candidates: `{len(candidates['candidates'])}`",
                f"- Baseline comparison: `{candidates.get('baseline_comparison')}`",
                "",
                "## Human-blocked residuals",
                "",
                "- Dual human review opinions on sampled candidates",
                "- Formal GO only after dual review (software must not forge completions)",
                "",
                "## Withheld claims",
                "",
                *[f"- {claim}" for claim in formal["withheld_claims"]],
                "",
            ]
        ),
        encoding="utf-8",
    )

    public_summary = build_public_closure_summary(
        run_id=run_id,
        live_counts=live_counts,
        capture_digests=digests,
        typed_retry_outcomes=typed_retry_outcomes,
        candidate_count=len(candidates["candidates"]),
        dual_review_complete=False,
        metrics_recommendation=str(metrics["evaluation"]["recommendation"]),
        formal_disposition=str(formal["disposition"]),
    )
    public_summary["live_retry_executed"] = live_retry_executed
    atomic_write_json(wave2_root / "public_metrics_summary.json", public_summary)

    examples_dir = args.workbench_root / "examples" / "shadow_refresh"
    if examples_dir.is_dir():
        atomic_write_json(examples_dir / "SHADOW_REFRESH_WAVE2_PUBLIC_SUMMARY_v202608.json", public_summary)

    json.dump(
        {
            "wave2_root": str(wave2_root),
            "formal_disposition": formal["disposition"],
            "metrics_recommendation": metrics["evaluation"]["recommendation"],
            "dual_review_complete": False,
            "live_retry_executed": live_retry_executed,
            "typed_retry_outcomes": [
                {"source_id": item.get("source_id"), "outcome_type": item.get("outcome_type")}
                for item in typed_retry_outcomes
            ],
            "status": SHADOW_EVALUATION_STATUS,
        },
        sys.stdout,
        ensure_ascii=False,
        indent=2,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
