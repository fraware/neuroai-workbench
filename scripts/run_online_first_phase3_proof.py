#!/usr/bin/env python3
"""Opt-in runner for the bounded online-first Phase 3 proof harness.

Ordinary invocation performs no network operation. The ``live`` command additionally
requires ``--execute-live``, the existing digest-bound live authorization environment
packet, ``NEUROAI_LIVE_COLLECTION=1``, and an active acquisition policy authorizing
one exact ClinicalTrials.gov source.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from neuroai_workbench.collector.acquisition_policy import (
    ONLINE_REQUIRED,
    REPLAY_ONLY,
    AcquisitionPolicyError,
    require_acquisition_policy,
    validate_acquisition_policy,
)
from neuroai_workbench.collector.authorization import (
    CollectionAuthorizationError,
    load_live_authorization_from_environment,
)
from neuroai_workbench.collector.config import CollectorConfig
from neuroai_workbench.collector.pinned_transport import PinnedSocketHttpTransport
from neuroai_workbench.collector.policy_execution import PolicyBoundCollectionScheduler
from neuroai_workbench.collector.prior_capture_replay import ReplayOnlyCollectionScheduler
from neuroai_workbench.collector.runtime_proof import (
    RuntimeProofError,
    build_runtime_proof,
    verify_runtime_proof,
    write_runtime_proof,
)
from neuroai_workbench.collector.scheduler import SchedulerConfig
from neuroai_workbench.util import atomic_write_json, load_json, utc_now

_NCT_RE = re.compile(r"^NCT\d{8}$")
CTGOV_STUDY_API_PREFIX = "https://clinicaltrials.gov/api/v2/studies/"
PROOF_RUNNER_BOUNDARY = (
    "This runner executes or verifies one bounded operational Phase 3 proof. Its output is non-canonical "
    "operational proof metadata and does not establish source truth, clinical validity, S2 admission, "
    "G0/G1/G2 passage, release authorization, publication, legal authority, or production readiness."
)


def _sha256_text(value: str, field: str) -> str:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{field} must be a 64-character lowercase SHA-256 digest")
    return value


def _load_object(path: Path, field: str) -> dict[str, Any]:
    try:
        value = load_json(path)
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError(f"{field} is unreadable: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{field} must contain a JSON object")
    return value


def _load_policy(path: Path) -> dict[str, Any]:
    return validate_acquisition_policy(_load_object(path, "acquisition policy"))


def _nct_id(value: str) -> str:
    normalized = value.strip().upper()
    if not _NCT_RE.fullmatch(normalized):
        raise ValueError("nct_id must match NCT followed by exactly eight digits")
    return normalized


def _source_and_plan(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], str]:
    nct_id = _nct_id(args.nct_id)
    url = f"{CTGOV_STUDY_API_PREFIX}{nct_id}"
    source = {
        "source_id": args.source_id,
        "monitor_id": args.monitor_id,
        "source_class": "OFFICIAL_TRIAL_REGISTRY",
        "url": url,
        "nct_id": nct_id,
    }
    plan = {
        "plan_id": args.plan_id,
        "as_of": args.as_of,
        "due": [
            {
                "source_id": args.source_id,
                "monitor_id": args.monitor_id,
                "url": url,
            }
        ],
        "manual": [],
        "not_due": [],
    }
    return source, plan, url


def _collector_config(args: argparse.Namespace) -> CollectorConfig:
    return CollectorConfig(
        collector_version=args.collector_version,
        configuration_hash=_sha256_text(args.configuration_hash, "configuration_hash"),
        max_attempts=args.max_attempts,
    )


def _controlled_output_dir(args: argparse.Namespace) -> Path:
    if not args.confirm_noncanonical_output:
        raise ValueError(
            "--confirm-noncanonical-output is required to assert that proof output is outside canonical S2"
        )
    path = args.proof_output_dir
    path.mkdir(parents=True, exist_ok=True)
    return path


def _one_result(summary: dict[str, Any], source_id: str) -> str:
    outcomes = summary.get("outcomes")
    if not isinstance(outcomes, list):
        raise RuntimeProofError("run summary outcomes are unavailable")
    matches = [
        item
        for item in outcomes
        if isinstance(item, dict) and item.get("source_id") == source_id and item.get("status") == "RESULT"
    ]
    if len(matches) != 1 or not isinstance(matches[0].get("record_id"), str):
        raise RuntimeProofError("bounded Phase 3 run did not produce exactly one source RESULT")
    return str(matches[0]["record_id"])


def _run_live(args: argparse.Namespace) -> int:
    if not args.execute_live:
        raise ValueError("live mode requires --execute-live; network execution is never the default")
    output_dir = _controlled_output_dir(args)
    policy = _load_policy(args.policy)
    authorization = load_live_authorization_from_environment()
    source, plan, url = _source_and_plan(args)
    require_acquisition_policy(
        policy,
        programme_id=args.programme_id,
        source_id=args.source_id,
        execution_mode=ONLINE_REQUIRED,
        requested_url=url,
        fallback_to_prior_capture=False,
        at=utc_now(),
    )
    scheduler = PolicyBoundCollectionScheduler(
        acquisition_policy=policy,
        programme_id=args.programme_id,
        execution_mode=ONLINE_REQUIRED,
        collector_config=_collector_config(args),
        transport=PinnedSocketHttpTransport(),
        quarantine_root=args.quarantine_root,
        scheduler_config=SchedulerConfig(max_workers=1, max_workers_per_host=1),
    )
    summary = scheduler.run_plan(
        plan,
        registry_sha256=_sha256_text(args.registry_sha256, "registry_sha256"),
        source_index={args.source_id: source},
    )
    result_id = _one_result(summary, args.source_id)
    record = {
        "kind": "PHASE3_LIVE_RUN_REFERENCE",
        "run_id": summary["run_id"],
        "result_id": result_id,
        "source_id": args.source_id,
        "programme_id": args.programme_id,
        "policy_id": policy["policy_id"],
        "policy_sha256": policy["policy_sha256"],
        "authorization_id": authorization["authorization_id"],
        "authorization_sha256": authorization["authorization_sha256"],
        "semantic_summary_sha256": summary["semantic_summary_sha256"],
        "source_accountability_coverage": summary["slo"]["source_accountability_coverage"],
        "target_execution_coverage": summary["slo"]["target_execution_coverage"],
        "boundary": PROOF_RUNNER_BOUNDARY,
    }
    path = output_dir / "phase3-live-run.json"
    atomic_write_json(path, record)
    print(json.dumps(record, sort_keys=True))
    return 0


def _run_replay(args: argparse.Namespace) -> int:
    output_dir = _controlled_output_dir(args)
    policy = _load_policy(args.policy)
    source, plan, _ = _source_and_plan(args)
    require_acquisition_policy(
        policy,
        programme_id=args.programme_id,
        source_id=args.source_id,
        execution_mode=REPLAY_ONLY,
        requested_url=None,
        fallback_to_prior_capture=False,
        at=utc_now(),
    )
    scheduler = ReplayOnlyCollectionScheduler(
        acquisition_policy=policy,
        programme_id=args.programme_id,
        collector_config=_collector_config(args),
        quarantine_root=args.quarantine_root,
        scheduler_config=SchedulerConfig(max_workers=1, max_workers_per_host=1),
    )
    summary = scheduler.run_plan(
        plan,
        registry_sha256=_sha256_text(args.registry_sha256, "registry_sha256"),
        source_index={args.source_id: source},
    )
    result_id = _one_result(summary, args.source_id)
    record = {
        "kind": "PHASE3_REPLAY_RUN_REFERENCE",
        "run_id": summary["run_id"],
        "result_id": result_id,
        "source_id": args.source_id,
        "programme_id": args.programme_id,
        "policy_id": policy["policy_id"],
        "policy_sha256": policy["policy_sha256"],
        "semantic_summary_sha256": summary["semantic_summary_sha256"],
        "collection_attempts": summary["counts"]["collection_attempts"],
        "source_accountability_coverage": summary["slo"]["source_accountability_coverage"],
        "target_execution_coverage": summary["slo"]["target_execution_coverage"],
        "boundary": PROOF_RUNNER_BOUNDARY,
    }
    path = output_dir / "phase3-replay-run.json"
    atomic_write_json(path, record)
    print(json.dumps(record, sort_keys=True))
    return 0


def _build_proof(args: argparse.Namespace) -> int:
    policy = _load_policy(args.policy)
    proof = build_runtime_proof(
        args.quarantine_root,
        live_run_id=args.live_run_id,
        replay_run_id=args.replay_run_id,
        programme_id=args.programme_id,
        source_id=args.source_id,
        policy_sha256=str(policy["policy_sha256"]),
        result_id=args.result_id,
    )
    verify_runtime_proof(args.quarantine_root, proof)
    write_runtime_proof(args.output, proof)
    print(json.dumps({"proof_id": proof["proof_id"], "proof_semantic_sha256": proof["proof_semantic_sha256"]}))
    return 0


def _verify_proof(args: argparse.Namespace) -> int:
    proof = _load_object(args.proof, "runtime proof")
    verified = verify_runtime_proof(args.quarantine_root, proof)
    print(
        json.dumps(
            {
                "proof_id": verified["proof_id"],
                "proof_semantic_sha256": verified["proof_semantic_sha256"],
                "verified": True,
            }
        )
    )
    return 0


def _add_execution_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--programme-id", required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--monitor-id", required=True)
    parser.add_argument("--nct-id", required=True)
    parser.add_argument("--plan-id", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--registry-sha256", required=True)
    parser.add_argument("--configuration-hash", required=True)
    parser.add_argument("--collector-version", default="0.3.0.dev0-phase3-proof")
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--quarantine-root", type=Path, required=True)
    parser.add_argument("--proof-output-dir", type=Path, required=True)
    parser.add_argument("--confirm-noncanonical-output", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run or verify the bounded online-first Phase 3 proof harness")
    subparsers = parser.add_subparsers(dest="command", required=True)

    live = subparsers.add_parser("live", help="Execute one explicitly authorized single-source live capture")
    _add_execution_args(live)
    live.add_argument("--execute-live", action="store_true")
    live.set_defaults(handler=_run_live)

    replay = subparsers.add_parser("replay", help="Execute zero-network replay over a previously captured source")
    _add_execution_args(replay)
    replay.set_defaults(handler=_run_replay)

    build = subparsers.add_parser("build", help="Build and verify a proof from durable live/replay run IDs")
    build.add_argument("--policy", type=Path, required=True)
    build.add_argument("--programme-id", required=True)
    build.add_argument("--source-id", required=True)
    build.add_argument("--live-run-id", required=True)
    build.add_argument("--replay-run-id", required=True)
    build.add_argument("--result-id", required=True)
    build.add_argument("--quarantine-root", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.set_defaults(handler=_build_proof)

    verify = subparsers.add_parser("verify", help="Verify an existing proof against durable controlled records")
    verify.add_argument("--proof", type=Path, required=True)
    verify.add_argument("--quarantine-root", type=Path, required=True)
    verify.set_defaults(handler=_verify_proof)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (AcquisitionPolicyError, CollectionAuthorizationError, RuntimeProofError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
