#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Per-module line-coverage floors (percent). Aggregate remain fail_under=90 in pyproject.
MODULE_FLOORS: dict[str, float] = {
    "neuroai_workbench/assistance.py": 90.0,
    "neuroai_workbench/assessment_evidence.py": 90.0,
    "neuroai_workbench/data_search.py": 90.0,
    "neuroai_workbench/data_trace.py": 90.0,
    "neuroai_workbench/evidence.py": 95.0,
    "neuroai_workbench/evidence_crosswalk.py": 90.0,
    "neuroai_workbench/evidence_transactions.py": 90.0,
    "neuroai_workbench/observatory.py": 95.0,
    "neuroai_workbench/monitoring.py": 95.0,
    "neuroai_workbench/monitoring_accountability.py": 95.0,
    "neuroai_workbench/entities/registry.py": 90.0,
    "neuroai_workbench/entities/resolver.py": 90.0,
    "neuroai_workbench/delta/compiler.py": 95.0,
    "neuroai_workbench/delta/schemas.py": 95.0,
    "neuroai_workbench/delta/apply.py": 95.0,
    "neuroai_workbench/programme_adapter.py": 95.0,
    "neuroai_workbench/presentation_i18n.py": 95.0,
    "neuroai_workbench/proposal_application.py": 95.0,
    "neuroai_workbench/review.py": 95.0,
    "neuroai_workbench/independent_review.py": 95.0,
    "neuroai_workbench/governance_scope.py": 95.0,
    "neuroai_workbench/governance_opinions.py": 95.0,
    "neuroai_workbench/governance_dispositions.py": 95.0,
    "neuroai_workbench/governance_policy.py": 95.0,
    "neuroai_workbench/governance_release.py": 95.0,
    "neuroai_workbench/governance_rehearsal.py": 95.0,
    "neuroai_workbench/governance_transactions.py": 95.0,
    "neuroai_workbench/events.py": 95.0,
    "neuroai_workbench/server.py": 90.0,
    "neuroai_workbench/collector/adapters/auth_download.py": 95.0,
    "neuroai_workbench/collector/dns.py": 95.0,
    "neuroai_workbench/collector/handoff.py": 95.0,
    "neuroai_workbench/collector/host_limit.py": 95.0,
    "neuroai_workbench/collector/http_client.py": 95.0,
    "neuroai_workbench/collector/quarantine.py": 95.0,
    "neuroai_workbench/collector/rate_limit.py": 95.0,
    "neuroai_workbench/collector/run_ledger.py": 95.0,
    "neuroai_workbench/collector/scheduler.py": 95.0,
    "neuroai_workbench/collector/service.py": 95.0,
    "neuroai_workbench/collector/source_lifecycle.py": 95.0,
    "neuroai_workbench/collector/source_routes.py": 95.0,
    "neuroai_workbench/collector/transport.py": 95.0,
    "neuroai_workbench/collector/url_policy.py": 95.0,
}


def _normalize(path: str) -> str:
    return path.replace("\\", "/")


def _module_key(file_path: str) -> str | None:
    normalized = _normalize(file_path)
    for key in MODULE_FLOORS:
        if normalized.endswith(key) or f"/{key}" in normalized or normalized == key:
            return key
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce per-module coverage floors")
    parser.add_argument(
        "--coverage-json",
        type=Path,
        default=ROOT / "coverage.json",
        help="Path to coverage.py JSON report (coverage json)",
    )
    args = parser.parse_args()
    if not args.coverage_json.is_file():
        print(f"ERROR: missing coverage JSON at {args.coverage_json}", file=sys.stderr)
        return 1
    payload = json.loads(args.coverage_json.read_text(encoding="utf-8"))
    files = payload.get("files")
    if not isinstance(files, dict):
        print("ERROR: coverage JSON missing files map", file=sys.stderr)
        return 1

    observed: dict[str, float] = {}
    for file_path, data in files.items():
        key = _module_key(str(file_path))
        if key is None:
            continue
        summary = data.get("summary", {})
        percent = summary.get("percent_covered")
        if not isinstance(percent, int | float):
            print(f"ERROR: missing percent_covered for {file_path}", file=sys.stderr)
            return 1
        observed[key] = float(percent)

    errors: list[str] = []
    for key, floor in sorted(MODULE_FLOORS.items()):
        if key not in observed:
            errors.append(f"{key}: no coverage data (required floor {floor}%)")
            continue
        if observed[key] + 1e-9 < floor:
            errors.append(f"{key}: {observed[key]:.2f}% < floor {floor}%")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    for key, percent in sorted(observed.items()):
        print(f"{key}: {percent:.2f}% (floor {MODULE_FLOORS[key]}%)")
    print("module coverage floors passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
