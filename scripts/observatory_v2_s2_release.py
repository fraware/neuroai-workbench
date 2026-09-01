#!/usr/bin/env python3
"""Operate the Observatory-v2 S2 candidate -> authorization -> publication lifecycle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from neuroai_workbench.observatory_publication import (
    DESIGNATED_OPERATOR,
    record_s2_authorization,
    record_s2_publication,
    verify_s2_authorizations,
    verify_s2_publication_binding,
)
from neuroai_workbench.observatory_s2_release import (
    verify_observatory_v2_s2_candidate,
    write_observatory_v2_s2_candidate,
)


def _print(value) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    candidate = sub.add_parser("candidate", help="compile a Gate-A PASS into a noncanonical S2 candidate")
    candidate.add_argument("--gate-a-package", required=True, type=Path)
    candidate.add_argument("--gate-a-decision", required=True, type=Path)
    candidate.add_argument("--output", required=True, type=Path)
    candidate.add_argument("--release-tag", required=True)
    candidate.add_argument("--s2-predecessor-release-tag", required=True)

    authorize = sub.add_parser("authorize", help="record an explicit operator release decision")
    authorize.add_argument("--release-dir", required=True, type=Path)
    authorize.add_argument("--decision", required=True, choices=("AUTHORIZE", "WITHHOLD"))
    authorize.add_argument("--rationale", required=True)
    authorize.add_argument("--supersedes-authorization-id")
    authorize.add_argument("--actor", default=DESIGNATED_OPERATOR)

    publish = sub.add_parser("publish", help="bind active authorization to public publication evidence")
    publish.add_argument("--release-dir", required=True, type=Path)
    publish.add_argument("--evidence-reference", required=True)
    publish.add_argument("--evidence-sha256", required=True)
    publish.add_argument("--actor", default=DESIGNATED_OPERATOR)

    verify = sub.add_parser("verify", help="verify candidate or published release state")
    verify.add_argument("--release-dir", required=True, type=Path)
    verify.add_argument("--mode", choices=("candidate", "authorization", "published"), default="published")

    args = parser.parse_args(argv)
    if args.command == "candidate":
        result = write_observatory_v2_s2_candidate(
            args.gate_a_package,
            args.gate_a_decision,
            args.output,
            release_tag=args.release_tag,
            s2_predecessor_release_tag=args.s2_predecessor_release_tag,
        )
        _print(result)
        return 0
    if args.command == "authorize":
        result = record_s2_authorization(
            args.release_dir,
            decision=args.decision,
            decision_rationale=args.rationale,
            supersedes_authorization_id=args.supersedes_authorization_id,
            actor=args.actor,
        )
        _print(result)
        return 0
    if args.command == "publish":
        result = record_s2_publication(
            args.release_dir,
            publication_evidence={
                "reference": args.evidence_reference,
                "sha256": args.evidence_sha256,
            },
            actor=args.actor,
        )
        _print(result)
        return 0

    if args.mode == "candidate":
        errors = verify_observatory_v2_s2_candidate(args.release_dir)
        result = {"valid": not errors, "errors": errors, "mode": "candidate"}
    elif args.mode == "authorization":
        result = {**verify_s2_authorizations(args.release_dir), "mode": "authorization"}
    else:
        result = {**verify_s2_publication_binding(args.release_dir), "mode": "published"}
    _print(result)
    return 0 if result.get("valid") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
