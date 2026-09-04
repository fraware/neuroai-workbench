#!/usr/bin/env python3
"""Enforce the repository aggregate coverage floor from coverage.py JSON.

This check is intentionally independent of terminal-report rounding. Coverage.py may
render a below-threshold aggregate as an integer percentage that appears to satisfy a
configured floor. The JSON report contains the underlying aggregate percentage, which
this script compares directly against the repository's literal 90.00% contract.
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AGGREGATE_COVERAGE_FLOOR = Decimal("90.00")


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON numeric constant: {value}")


def load_aggregate_percent(path: Path) -> Decimal:
    """Return the exact aggregate percentage, failing closed on malformed input."""
    if not path.is_file():
        raise ValueError(f"missing coverage JSON at {path}")
    try:
        payload: Any = json.loads(
            path.read_text(encoding="utf-8"),
            parse_float=Decimal,
            parse_int=Decimal,
            parse_constant=_reject_json_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"coverage JSON could not be parsed: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("coverage JSON root must be an object")
    totals = payload.get("totals")
    if not isinstance(totals, dict):
        raise ValueError("coverage JSON missing totals object")
    value = totals.get("percent_covered")
    if isinstance(value, bool) or not isinstance(value, Decimal):
        raise ValueError("coverage JSON totals.percent_covered must be numeric")
    try:
        if not value.is_finite():
            raise ValueError("coverage JSON totals.percent_covered must be finite")
    except InvalidOperation as exc:
        raise ValueError("coverage JSON totals.percent_covered is invalid") from exc
    if value < Decimal("0") or value > Decimal("100"):
        raise ValueError("coverage JSON totals.percent_covered must be between 0 and 100")
    return value


def evaluate_aggregate_coverage(
    path: Path,
    *,
    floor: Decimal = AGGREGATE_COVERAGE_FLOOR,
) -> tuple[bool, Decimal]:
    """Evaluate the aggregate floor and return ``(passed, observed_percent)``."""
    if not floor.is_finite() or floor < Decimal("0") or floor > Decimal("100"):
        raise ValueError("aggregate coverage floor must be a finite percentage between 0 and 100")
    observed = load_aggregate_percent(path)
    return observed >= floor, observed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--coverage-json",
        type=Path,
        default=ROOT / "coverage.json",
        help="Path to the coverage.py JSON report",
    )
    parser.add_argument(
        "--floor",
        type=Decimal,
        default=AGGREGATE_COVERAGE_FLOOR,
        help="Literal aggregate coverage floor (default: 90.00)",
    )
    args = parser.parse_args(argv)
    try:
        passed, observed = evaluate_aggregate_coverage(args.coverage_json, floor=args.floor)
    except (ValueError, InvalidOperation) as exc:
        print(f"ERROR: aggregate coverage gate could not be evaluated: {exc}", file=sys.stderr)
        return 1

    print(f"aggregate coverage: {observed:.6f}% (required >= {args.floor:.2f}%)")
    if not passed:
        print(
            f"ERROR: aggregate coverage {observed:.6f}% is below required {args.floor:.2f}%",
            file=sys.stderr,
        )
        return 1
    print("aggregate coverage floor passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
