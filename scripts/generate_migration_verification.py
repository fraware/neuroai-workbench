#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from neuroai_workbench.migration_ops.verification import write_migration_verification
from neuroai_workbench.util import utc_now

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "migration/MIGRATION_VERIFICATION.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate governing-input migration verification from public fixtures and inventory.",
    )
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--ambiguities", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--recorded-at",
        default="2026-08-02T14:00:00Z",
        help="Fixed timestamp for deterministic verification templates.",
    )
    parser.add_argument(
        "--now",
        action="store_true",
        help="Use the current UTC timestamp instead of the fixed template default.",
    )
    args = parser.parse_args(argv)
    recorded_at = utc_now() if args.now else args.recorded_at
    document = write_migration_verification(
        args.repo_root,
        args.output,
        inventory_path=args.inventory,
        ambiguities_path=args.ambiguities,
        recorded_at=recorded_at,
    )
    sys.stdout.write(f"Wrote {args.output} ({document['verification_id']})\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
