"""One-command live observatory refresh for the small NeuroAI research team.

This is a researcher-facing wrapper around the existing shadow-refresh cycle. It
keeps candidate outputs non-canonical, leaves completed assessments untouched,
and turns the detailed cycle report into a compact update summary.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .shadow_refresh import LIVE_COLLECTION_ENV
from .shadow_refresh.cycle import CycleDevelopmentDispositionSpec, run_live_evaluation_cycle
from .util import atomic_write_json, utc_now

OPS_ENV = "NEUROAI_OPS_WORKSPACE"
DEFAULT_REFRESH_VERSION = "v2.3.0-dev"
DEFAULT_REGISTRY_RELATIVE = Path("01_CONFIG") / "source_monitor_registry_v1.5.json"

_STABLE_OUTCOMES = frozenset({"SUCCESS", "NO_CHANGE", "NOT_MODIFIED_304"})
_CHANGED_OUTCOMES = frozenset(
    {
        "CONTENT_CHANGED",
        "NON_MATERIAL_REPRESENTATION_CHANGE",
        "MANUAL_FIRST_CAPTURE",
    }
)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def build_update_summary(package: dict[str, Any]) -> dict[str, Any]:
    """Reduce a full cycle package to the information a researcher needs next."""
    stage_results = _mapping(package.get("stage_results"))
    stats = _mapping(package.get("stats"))
    retrieval = _mapping(stats.get("retrieval"))
    outcomes = [item for item in package.get("source_outcomes", []) if isinstance(item, dict)]

    stable = [item for item in outcomes if item.get("outcome_type") in _STABLE_OUTCOMES]
    changed = [item for item in outcomes if item.get("outcome_type") in _CHANGED_OUTCOMES]
    attention = [
        item
        for item in outcomes
        if item.get("outcome_type") not in _STABLE_OUTCOMES and item.get("outcome_type") not in _CHANGED_OUTCOMES
    ]

    candidate_stage = _mapping(stage_results.get("create_change_candidate"))
    candidates = [item for item in candidate_stage.get("candidates", []) if isinstance(item, dict)]
    snapshot_stage = _mapping(stage_results.get("record_snapshot"))
    reopening_stage = _mapping(stage_results.get("reopening_analysis"))
    publication_stage = _mapping(stage_results.get("publications"))
    apply_stage = _mapping(stage_results.get("apply_delta"))

    changed_source_ids = sorted({str(item.get("source_id")) for item in changed if item.get("source_id")})
    attention_source_ids = sorted({str(item.get("source_id")) for item in attention if item.get("source_id")})
    candidate_source_ids = sorted({str(item.get("source_id")) for item in candidates if item.get("source_id")})
    products = {str(name): str(path) for name, path in _mapping(publication_stage.get("products")).items() if path}

    next_actions: list[str] = []
    handoff_count = int(snapshot_stage.get("count") or 0)
    capture_digest_count = int(_mapping(stage_results.get("collect")).get("capture_digest_count") or 0)
    if capture_digest_count and handoff_count == 0:
        next_actions.append(
            "Approve the successful captures you want to use, then rerun the refresh to compare them with their baselines."
        )
    if attention_source_ids:
        next_actions.append("Review retrieval problems for: " + ", ".join(attention_source_ids))
    if candidate_source_ids:
        next_actions.append("Inspect candidate changes for: " + ", ".join(candidate_source_ids))
    reopening_count = int(reopening_stage.get("recommendation_count") or 0)
    if reopening_count:
        next_actions.append(
            f"Review {reopening_count} assessment-impact recommendation(s); completed assessments were not modified."
        )
    if not bool(publication_stage.get("reconciled", False)):
        next_actions.append("Inspect publication reconciliation before using the regenerated outputs.")
    if not next_actions:
        next_actions.append("Inspect the regenerated v2.3.0-dev outputs; no immediate source follow-up was detected.")

    return {
        "status": package.get("status"),
        "mode": _mapping(package.get("metadata")).get("mode"),
        "executed_at": _mapping(package.get("metadata")).get("executed_at"),
        "sources": {
            "outcome_count": int(retrieval.get("outcome_count") or len(outcomes)),
            "stable_count": len(stable),
            "changed_count": len(changed),
            "attention_count": len(attention),
            "changed_source_ids": changed_source_ids,
            "attention_source_ids": attention_source_ids,
            "outcome_counts": _mapping(retrieval.get("by_type")),
            "snapshots_handed_off": handoff_count,
        },
        "changes": {
            "candidate_count": int(candidate_stage.get("count") or len(candidates)),
            "candidate_source_ids": candidate_source_ids,
            "assessment_impact_recommendations": reopening_count,
            "assessment_mutation_performed": bool(package.get("assessment_mutation_performed", False)),
        },
        "candidate_successor": {
            "path": apply_stage.get("successor_path"),
            "status": apply_stage.get("status"),
            "predecessor_unchanged": apply_stage.get("predecessor_unchanged"),
        },
        "outputs": {
            "publication_dir": publication_stage.get("path"),
            "products": products,
            "reconciled": bool(publication_stage.get("reconciled", False)),
            "full_cycle_report": package.get("report_path"),
        },
        "next_actions": next_actions,
        "canonical_successor_written": bool(package.get("canonical_successor_written", False)),
    }


def render_update_summary(summary: dict[str, Any]) -> str:
    """Render the compact operator summary printed after a refresh."""
    sources = _mapping(summary.get("sources"))
    changes = _mapping(summary.get("changes"))
    successor = _mapping(summary.get("candidate_successor"))
    outputs = _mapping(summary.get("outputs"))
    products = _mapping(outputs.get("products"))

    lines = [
        "NeuroAI refresh complete",
        (
            "Sources: "
            f"{sources.get('outcome_count', 0)} checked | "
            f"{sources.get('changed_count', 0)} changed | "
            f"{sources.get('attention_count', 0)} need attention"
        ),
        (
            "Changes: "
            f"{changes.get('candidate_count', 0)} candidate(s) | "
            f"{changes.get('assessment_impact_recommendations', 0)} assessment-impact recommendation(s)"
        ),
    ]
    if successor.get("path"):
        lines.append(f"Candidate successor: {successor['path']}")
    if outputs.get("publication_dir"):
        lines.append(f"Publications: {outputs['publication_dir']}")
    if products:
        lines.append("Generated: " + ", ".join(sorted(products)))
    lines.append("Next:")
    for action in summary.get("next_actions", []):
        lines.append(f"  - {action}")
    return "\n".join(lines)


def _run_stamp() -> str:
    return utc_now().replace("-", "").replace(":", "").replace("+00:00", "Z")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neuroai-refresh",
        description=(
            "Run the live observatory refresh and produce a compact research-team summary plus v2.3-dev outputs."
        ),
    )
    parser.add_argument(
        "--predecessor",
        type=Path,
        required=True,
        help="Current JSON release/checkpoint to update into a non-canonical candidate successor.",
    )
    parser.add_argument("--ops-workspace", type=Path, default=None)
    parser.add_argument("--registry", type=Path, default=None)
    parser.add_argument("--evaluation-workspace", type=Path, default=None)
    parser.add_argument("--quarantine-root", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--summary-path", type=Path, default=None)
    parser.add_argument("--refresh-version", default=DEFAULT_REFRESH_VERSION)
    parser.add_argument("--evidence-cutoff", default=None)
    parser.add_argument("--apply-id", default=None)
    parser.add_argument("--sample-size", type=int, default=25)
    parser.add_argument("--actor", default="neuroai-refresh")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the compact update summary as JSON instead of the human-readable view.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    raw_ops = args.ops_workspace or os.environ.get(OPS_ENV)
    if not raw_ops:
        sys.stderr.write(f"ERROR provide --ops-workspace or set {OPS_ENV}\n")
        return 2
    ops = Path(raw_ops).expanduser().resolve()
    if not ops.is_dir():
        sys.stderr.write(f"ERROR operations workspace not found: {ops}\n")
        return 2

    predecessor = args.predecessor.expanduser().resolve()
    if not predecessor.is_file():
        sys.stderr.write(f"ERROR predecessor not found: {predecessor}\n")
        return 2

    registry = (args.registry or (ops / DEFAULT_REGISTRY_RELATIVE)).expanduser().resolve()
    if not registry.is_file():
        sys.stderr.write(f"ERROR registry not found: {registry}\n")
        return 2

    stamp = _run_stamp()
    run_root = ops / "runs" / "v23-refresh" / stamp
    evaluation_workspace = (args.evaluation_workspace or (run_root / "workspace")).expanduser().resolve()
    quarantine_root = (args.quarantine_root or (run_root / "captures" / "quarantine")).expanduser().resolve()
    output_dir = (args.output_dir or (run_root / "output")).expanduser().resolve()
    summary_path = (args.summary_path or (output_dir / "UPDATE_SUMMARY.json")).expanduser().resolve()
    evidence_cutoff = args.evidence_cutoff or utc_now()[:10]
    apply_id = args.apply_id or f"apply-v23dev-{stamp.lower()}"

    # Invoking neuroai-refresh is itself the explicit opt-in to a live collection run.
    # The lower-level engine retains its environment gate for callers that use it directly.
    os.environ[LIVE_COLLECTION_ENV] = "1"

    package = run_live_evaluation_cycle(
        evaluation_workspace=evaluation_workspace,
        registry_path=registry,
        predecessor_path=predecessor,
        quarantine_root=quarantine_root,
        output_dir=output_dir,
        refresh_version=args.refresh_version,
        evidence_cutoff=evidence_cutoff,
        apply_id=apply_id,
        sample_size=args.sample_size,
        development_disposition=CycleDevelopmentDispositionSpec(),
        actor=args.actor,
        as_of=evidence_cutoff,
        approve_handoff=True,
    )
    summary = build_update_summary(package)
    atomic_write_json(summary_path, summary)

    if args.json:
        sys.stdout.write(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_update_summary(summary) + "\n")
        sys.stdout.write(f"Summary: {summary_path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
