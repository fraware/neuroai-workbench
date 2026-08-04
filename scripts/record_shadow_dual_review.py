#!/usr/bin/env python3
"""Record or assess dual human review for shadow evaluation candidates.

Humans must supply opinions. This script never forges reviewer content, never
writes a canonical successor, and refuses formal GO unless dual review is
complete. Core engineering for #43 is complete; governance remains under #101.

Requires an evaluation workspace that already has monitoring candidates and
scaffolded REV-SHADOW-A / REV-SHADOW-B profiles (Wave 2 closure or equivalent).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from neuroai_workbench.review_queue import (
    claim_lease,
    render_queue_markdown,
    review_queue_status,
)
from neuroai_workbench.shadow_refresh.closure import (
    ALLOWED_OPINION_POSITIONS,
    GOVERNANCE_ISSUE,
    REQUIRED_SHADOW_REVIEWERS,
    assess_dual_human_review,
    build_human_residual_checklist,
    record_formal_disposition,
    record_human_review_opinion,
)
from neuroai_workbench.shadow_refresh.schemas import SHADOW_EVALUATION_STATUS
from neuroai_workbench.util import atomic_write_json

OPS_ENV = "NEUROAI_OPS_WORKSPACE"


def _default_evaluation_workspace(ops: Path | None) -> Path:
    if ops is None:
        raise FileNotFoundError(f"{OPS_ENV} is unset and --evaluation-workspace was not provided")
    candidates = [
        ops / "runs" / "shadow-refresh-202608-live" / "wave2-closure" / "evaluation_workspace",
        ops / "runs" / "shadow-refresh-202608-live" / "core-closure" / "evaluation_workspace",
    ]
    for path in candidates:
        if (path / "observatory" / "review_queue").is_dir():
            return path
    raise FileNotFoundError(
        "No shadow evaluation workspace with a review queue found under "
        + ", ".join(str(path) for path in candidates)
    )


def _resolve_workspace(args: argparse.Namespace) -> Path:
    if args.evaluation_workspace is not None:
        workspace = args.evaluation_workspace
    else:
        ops_raw = os.environ.get(OPS_ENV, "")
        ops = Path(ops_raw) if ops_raw else None
        if args.ops_workspace is not None:
            ops = args.ops_workspace
        workspace = _default_evaluation_workspace(ops)
    if not workspace.is_dir():
        raise FileNotFoundError(f"Evaluation workspace not found: {workspace}")
    return workspace


def _print_json(value: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(value, indent=2, sort_keys=True) + "\n")


def cmd_status(args: argparse.Namespace) -> int:
    workspace = _resolve_workspace(args)
    status = review_queue_status(workspace)
    assessment = assess_dual_human_review(workspace)
    payload = {
        "evaluation_workspace": str(workspace),
        "queue_status": status,
        "dual_review": {
            "dual_review_complete": assessment["dual_review_complete"],
            "open_item_count": assessment["open_item_count"],
            "complete_item_count": assessment["complete_item_count"],
            "incomplete_item_count": assessment["incomplete_item_count"],
            "required_reviewers": assessment["required_reviewers"],
            "governance_issue": GOVERNANCE_ISSUE,
        },
        "items": assessment["items"],
        "status": SHADOW_EVALUATION_STATUS,
    }
    if args.markdown:
        sys.stdout.write(render_queue_markdown(workspace))
        sys.stdout.write("\n## Dual-review assessment\n\n")
        sys.stdout.write(
            f"- dual_review_complete: `{assessment['dual_review_complete']}`\n"
            f"- incomplete_item_count: `{assessment['incomplete_item_count']}`\n"
            f"- governance_issue: `{GOVERNANCE_ISSUE}`\n"
        )
    else:
        _print_json(payload)
    return 0


def cmd_claim(args: argparse.Namespace) -> int:
    workspace = _resolve_workspace(args)
    if args.profile not in REQUIRED_SHADOW_REVIEWERS:
        sys.stderr.write(
            f"ERROR profile must be one of {REQUIRED_SHADOW_REVIEWERS}; got {args.profile!r}\n"
        )
        return 2
    result = claim_lease(
        workspace,
        args.item_id,
        args.profile,
        ttl_seconds=args.ttl_seconds,
        actor=args.profile,
    )
    _print_json(
        {
            "lease": result["lease"],
            "path": result["path"],
            "status": SHADOW_EVALUATION_STATUS,
            "identity_boundary": (
                "Claimed local workflow identity only; not authenticated institutional authority."
            ),
        }
    )
    return 0


def cmd_opinion(args: argparse.Namespace) -> int:
    workspace = _resolve_workspace(args)
    if args.position not in ALLOWED_OPINION_POSITIONS:
        sys.stderr.write(
            f"ERROR position must be one of {sorted(ALLOWED_OPINION_POSITIONS)}; "
            f"got {args.position!r}\n"
        )
        return 2
    result = record_human_review_opinion(
        workspace,
        item_id=args.item_id,
        reviewer_profile_id=args.profile,
        position=args.position,
        rationale=args.rationale,
        ttl_seconds=args.ttl_seconds,
        role=args.role,
    )
    if args.output_dir is not None:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(args.output_dir / "dual_review_assessment.json", result["assessment"])
        atomic_write_json(
            args.output_dir / "human_residual_checklist.json",
            result["assessment"]["residual"],
        )
    _print_json(
        {
            "opinion_id": result["opinion"]["opinion_id"],
            "item_id": result["opinion"]["item_id"],
            "position": result["opinion"]["position"],
            "reviewer_profile_id": result["opinion"]["reviewer_profile_id"],
            "dual_review_complete": result["dual_review_complete"],
            "incomplete_item_count": result["assessment"]["incomplete_item_count"],
            "status": SHADOW_EVALUATION_STATUS,
        }
    )
    return 0


def cmd_assess(args: argparse.Namespace) -> int:
    workspace = _resolve_workspace(args)
    assessment = assess_dual_human_review(workspace)
    if args.output_dir is not None:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(args.output_dir / "dual_review_assessment.json", assessment)
        atomic_write_json(args.output_dir / "human_residual_checklist.json", assessment["residual"])
    _print_json(assessment)
    return 0 if assessment["dual_review_complete"] else 1


def cmd_formal_disposition(args: argparse.Namespace) -> int:
    workspace = _resolve_workspace(args)
    assessment = assess_dual_human_review(workspace)
    dual_complete = bool(assessment["dual_review_complete"])
    if args.require_dual_review and not dual_complete:
        sys.stderr.write(
            "ERROR dual human review is incomplete; refusing formal disposition "
            "(pass --allow-incomplete only to record WITHHELD/NO_GO explicitly).\n"
        )
        return 2
    if args.disposition_override == "GO" and not dual_complete:
        sys.stderr.write("ERROR refusing forged GO while dual human review is incomplete.\n")
        return 2

    owners = [owner.strip() for owner in args.owners.split(",") if owner.strip()]
    if not owners:
        sys.stderr.write("ERROR --owners must list at least one claimed local owner id\n")
        return 2

    metrics_recommendation = args.metrics_recommendation
    formal = record_formal_disposition(
        run_id=args.run_id,
        metrics_recommendation=metrics_recommendation,
        dual_review_complete=dual_complete,
        owners=owners,
        residual_checklist=build_human_residual_checklist(
            dual_review_complete=dual_complete
        )["checklist"],
    )
    if args.disposition_override:
        if args.disposition_override == "GO" and formal["disposition"] != "GO":
            sys.stderr.write(
                "ERROR cannot override to GO unless dual review is complete and "
                "metrics_recommendation is GO.\n"
            )
            return 2
        if args.disposition_override == "GO":
            formal["disposition"] = "GO"
        elif args.disposition_override in {"NO_GO", "WITHHELD"}:
            # Owners may explicitly record NO_GO or WITHHELD; never escalate to GO here.
            formal["disposition"] = args.disposition_override
            formal["owner_override"] = args.disposition_override

    if args.output_dir is not None:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(args.output_dir / "formal_disposition.json", formal)
        atomic_write_json(args.output_dir / "dual_review_assessment.json", assessment)

    _print_json(formal)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ops-workspace", type=Path, default=None)
    parser.add_argument("--evaluation-workspace", type=Path, default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="Show queue and dual-review completeness")
    status.add_argument("--markdown", action="store_true")
    status.set_defaults(func=cmd_status)

    claim = sub.add_parser("claim", help="Claim a review lease on one OPEN item")
    claim.add_argument("--profile", required=True, choices=list(REQUIRED_SHADOW_REVIEWERS))
    claim.add_argument("--item-id", required=True)
    claim.add_argument("--ttl-seconds", type=int, default=3600)
    claim.set_defaults(func=cmd_claim)

    opinion = sub.add_parser("opinion", help="Record one human opinion (claims lease if needed)")
    opinion.add_argument("--profile", required=True, choices=list(REQUIRED_SHADOW_REVIEWERS))
    opinion.add_argument("--item-id", required=True)
    opinion.add_argument("--position", required=True, choices=sorted(ALLOWED_OPINION_POSITIONS))
    opinion.add_argument("--rationale", required=True)
    opinion.add_argument("--role", default=None)
    opinion.add_argument("--ttl-seconds", type=int, default=3600)
    opinion.add_argument("--output-dir", type=Path, default=None)
    opinion.set_defaults(func=cmd_opinion)

    assess = sub.add_parser("assess", help="Assess dual-review completeness without forging opinions")
    assess.add_argument("--output-dir", type=Path, default=None)
    assess.set_defaults(func=cmd_assess)

    formal = sub.add_parser(
        "formal-disposition",
        help="Record GO/NO_GO/WITHHELD from observed dual-review state (no forged GO)",
    )
    formal.add_argument("--run-id", required=True)
    formal.add_argument("--owners", required=True, help="Comma-separated claimed local owner ids")
    formal.add_argument(
        "--metrics-recommendation",
        default="NO_GO",
        choices=["GO", "NO_GO", "INCOMPLETE"],
    )
    formal.add_argument(
        "--disposition-override",
        default=None,
        choices=["GO", "NO_GO", "WITHHELD"],
        help="Owners may force NO_GO/WITHHELD; GO only when dual review + metrics allow it",
    )
    formal.add_argument(
        "--require-dual-review",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Refuse disposition when dual review is incomplete (default: true)",
    )
    formal.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Alias for --no-require-dual-review (records WITHHELD when incomplete)",
    )
    formal.add_argument("--output-dir", type=Path, default=None)
    formal.set_defaults(func=cmd_formal_disposition)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "allow_incomplete", False):
        args.require_dual_review = False
    try:
        return int(args.func(args))
    except (OSError, ValueError, TypeError, KeyError, FileNotFoundError) as exc:
        sys.stderr.write(f"ERROR {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
