#!/usr/bin/env python3
"""Copy approved synthetic public records into a neuroai-observatory-data staging tree."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from neuroai_workbench.publish.data import (
    AUTHORIZED_PUBLIC_RELEASE_SET,
    build_publish_plan,
    publish_release,
    verify_publish_staging,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--release-tag",
        default="data-v0.0.1-bootstrap",
        help="Target data release tag directory name",
    )
    parser.add_argument(
        "--staging",
        type=Path,
        required=True,
        help="Staging directory for the data repository content",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=None,
        help="Existing neuroai-observatory-data checkout or templates scaffold path",
    )
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=None,
        help="Approved fixture directory (defaults to scaffold fixtures/ or authorized materialization)",
    )
    parser.add_argument(
        "--release-set",
        default="synthetic",
        choices=("synthetic", AUTHORIZED_PUBLIC_RELEASE_SET),
        help="synthetic CI fixtures, or authorized public governing set from NEUROAI_OPS_WORKSPACE",
    )
    parser.add_argument(
        "--ops-workspace",
        type=Path,
        default=None,
        help="Operations Starter extract root (defaults to NEUROAI_OPS_WORKSPACE)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan, generate manifest, and verify without writing staging output",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify an existing staging tree manifest and descriptor",
    )
    args = parser.parse_args()

    plan = build_publish_plan(
        release_tag=args.release_tag,
        staging_root=args.staging,
        target=args.target,
        fixture_dir=args.fixtures,
        dry_run=args.dry_run,
        release_set=args.release_set,
        ops_workspace=args.ops_workspace,
    )

    if args.verify_only:
        report = verify_publish_staging(plan, target=args.target)
    else:
        report = publish_release(plan, target=args.target)

    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    if not report.get("manifest_verified", False):
        return 1
    if args.verify_only and not report.get("descriptor_verified", False):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
