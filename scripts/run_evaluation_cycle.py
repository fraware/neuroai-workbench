#!/usr/bin/env python3
"""Run a non-canonical full evaluation operating cycle (Wave 3).

Offline (default): fixture snapshot pairs → compare → candidate → adjudicate →
refresh → delta → apply → reopening → depth=full publications. No network.

Live: requires NEUROAI_LIVE_COLLECTION=1 and NEUROAI_OPS_WORKSPACE. Collects into
quarantine only, then evaluation-only handoff of records already APPROVED_FOR_HANDOFF
(--approve-handoff consents to that handoff; it does not auto-approve). Collector
monitoring handoff stays disabled for the remaining stages.

Artifacts remain SHADOW_EVALUATION_NOT_CANONICAL. Does not forge dual review or GO.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from neuroai_workbench.shadow_refresh import LIVE_COLLECTION_ENV, SHADOW_EVALUATION_STATUS
from neuroai_workbench.shadow_refresh.cycle import (
    CycleAdjudicationSpec,
    SnapshotPairFixture,
    run_live_evaluation_cycle,
    run_offline_snapshot_cycle,
)
from neuroai_workbench.util import atomic_write_json

OPS_ENV = "NEUROAI_OPS_WORKSPACE"


def _offline_default_pairs() -> list[SnapshotPairFixture]:
    return [
        SnapshotPairFixture(
            source_id="SRC-0001",
            baseline_bytes=b"<html>baseline-eval-cycle</html>",
            current_bytes=b"<html>changed-eval-cycle</html>",
            media_type="text/html",
            retrieval_url="https://example.org/regulatory",
        )
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("offline", "live"),
        default="offline",
        help="offline uses fixtures (CI-safe); live requires ops + live-collection gates",
    )
    parser.add_argument("--ops-workspace", type=Path, default=None)
    parser.add_argument("--workbench-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--evaluation-workspace", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--registry", type=Path, default=None)
    parser.add_argument(
        "--predecessor",
        type=Path,
        default=None,
        help="Defaults to tests/fixtures/delta/synthetic_predecessor_release.json",
    )
    parser.add_argument("--refresh-version", default="eval-cycle-202608")
    parser.add_argument("--evidence-cutoff", default="2026-08-02")
    parser.add_argument("--apply-id", default="apply-eval-cycle-001")
    parser.add_argument("--sample-size", type=int, default=5)
    parser.add_argument(
        "--approve-handoff",
        action="store_true",
        help=(
            "Required for live mode: consent to evaluation-only handoff of quarantine "
            "records that are already APPROVED_FOR_HANDOFF (does not auto-approve pending records)"
        ),
    )
    parser.add_argument(
        "--public-summary",
        type=Path,
        default=None,
        help="Optional path to write a public (no capture bodies) summary JSON",
    )
    args = parser.parse_args(argv)

    root = args.workbench_root
    predecessor = args.predecessor or (root / "tests" / "fixtures" / "delta" / "synthetic_predecessor_release.json")
    if not predecessor.is_file():
        sys.stderr.write(f"ERROR predecessor not found: {predecessor}\n")
        return 2

    predecessor = predecessor.resolve()
    if args.mode == "offline":
        evaluation_workspace = (
            args.evaluation_workspace or (root / "runs" / "eval-cycle-offline" / "workspace")
        ).resolve()
        output_dir = (args.output_dir or (root / "runs" / "eval-cycle-offline" / "output")).resolve()
        registry = args.registry.resolve() if args.registry is not None else None
        if registry is None:
            # Write a tiny registry beside the evaluation workspace for offline proof.
            registry = (evaluation_workspace.parent / "registry.json").resolve()
            if not registry.is_file():
                from neuroai_workbench.util import atomic_write_json as _write

                _write(
                    registry,
                    [
                        {
                            "monitor_id": "MON-SRC-0001",
                            "source_id": "SRC-0001",
                            "url": "https://example.org/regulatory",
                            "publisher": "Example regulator",
                            "source_class": "REGULATORY_RECORD",
                            "cadence": "WEEKLY",
                            "last_successful_retrieval": "2026-07-01",
                            "baseline_evidence_state": "CURRENT_SOURCE_RETRIEVED",
                            "baseline_verification_state": "CURRENT_VERIFIED",
                            "baseline_claim_boundary": (
                                "Official pages establish representations only; "
                                "human adjudication controls all substantive effects."
                            ),
                            "network_access_required": True,
                            "current_status": "BASELINE_REGISTERED",
                            "next_action": "RETRIEVE_AND_COMPARE",
                        }
                    ],
                )
        package = run_offline_snapshot_cycle(
            evaluation_workspace=evaluation_workspace,
            registry_path=registry,
            predecessor_path=predecessor,
            output_dir=output_dir,
            snapshot_pairs=_offline_default_pairs(),
            refresh_version=args.refresh_version,
            evidence_cutoff=args.evidence_cutoff,
            apply_id=args.apply_id,
            adjudication=CycleAdjudicationSpec(),
        )
    else:
        ops = (args.ops_workspace or Path(os.environ.get(OPS_ENV, ""))).resolve()
        if not ops.is_dir():
            sys.stderr.write(f"ERROR {OPS_ENV} must point at Operations Starter extract\n")
            return 2
        if os.environ.get(LIVE_COLLECTION_ENV, "").strip() != "1":
            sys.stderr.write(f"ERROR {LIVE_COLLECTION_ENV}=1 is required for --mode live\n")
            return 2
        if not args.approve_handoff:
            sys.stderr.write(
                "ERROR live mode requires --approve-handoff after per-record quarantine "
                "approval (APPROVED_FOR_HANDOFF); the flag consents to handoff of those "
                "pre-approved records only and does not auto-approve pending captures\n"
            )
            return 2
        registry = (args.registry or (ops / "01_CONFIG" / "source_monitor_registry_v1.5.json")).resolve()
        if not registry.is_file():
            sys.stderr.write(f"ERROR registry not found: {registry}\n")
            return 2
        run_root = ops / "runs" / "shadow-refresh-eval-cycle"
        evaluation_workspace = (args.evaluation_workspace or (run_root / "evaluation_workspace")).resolve()
        output_dir = (args.output_dir or (run_root / "output")).resolve()
        quarantine_root = (run_root / "captures" / "quarantine").resolve()
        package = run_live_evaluation_cycle(
            evaluation_workspace=evaluation_workspace,
            registry_path=registry,
            predecessor_path=predecessor,
            quarantine_root=quarantine_root,
            output_dir=output_dir,
            refresh_version=args.refresh_version,
            evidence_cutoff=args.evidence_cutoff,
            apply_id=args.apply_id,
            sample_size=args.sample_size,
            adjudication=CycleAdjudicationSpec(),
            approve_handoff=True,
        )

    if args.public_summary is not None:
        public = {
            "metadata": {
                "title": "Public evaluation-cycle summary",
                "status": SHADOW_EVALUATION_STATUS,
                "mode": package["metadata"]["mode"],
            },
            "stats": package.get("stats"),
            "source_outcome_counts": package.get("stats", {}).get("retrieval", {}).get("by_type"),
            "canonical_successor_written": False,
            "formal_go_authorized": False,
            "withheld_claims": package.get("withheld_claims"),
            "status": SHADOW_EVALUATION_STATUS,
            "boundary": package.get("boundary"),
        }
        atomic_write_json(args.public_summary, public)

    sys.stdout.write(json.dumps({"report_path": package.get("report_path"), "status": package["status"]}, indent=2))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
