#!/usr/bin/env python3
"""Compare a GitHub repository ruleset with the repository-owned check contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _load_object(path: Path, label: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return value


def _rule_map(ruleset: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rules = ruleset.get("rules")
    if not isinstance(rules, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for rule in rules:
        if isinstance(rule, dict) and isinstance(rule.get("type"), str):
            result[str(rule["type"])] = rule
    return result


def _expected_api_contexts(manifest: dict[str, Any]) -> set[str]:
    contexts = manifest.get("required_pull_request_contexts")
    if not isinstance(contexts, list):
        raise ValueError("required_pull_request_contexts must be a list")
    return {str(context).rsplit(" / ", 1)[-1] for context in contexts}


def _hosted_policy(manifest: dict[str, Any]) -> dict[str, Any]:
    reference = manifest.get("ruleset_reference")
    reference = reference if isinstance(reference, dict) else {}
    policy = reference.get("hosted_policy")
    if not isinstance(policy, dict):
        raise ValueError("ruleset_reference.hosted_policy must be an object")
    return policy


def _observed_contexts(rule: dict[str, Any]) -> tuple[set[str], list[dict[str, Any]]]:
    parameters = rule.get("parameters")
    if not isinstance(parameters, dict):
        return set(), []
    rows = parameters.get("required_status_checks")
    if not isinstance(rows, list):
        return set(), []
    normalized = [row for row in rows if isinstance(row, dict)]
    return {str(row.get("context")) for row in normalized if row.get("context")}, normalized


def audit(ruleset: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, condition: bool, detail: Any) -> None:
        checks.append({"name": name, "status": "PASS" if condition else "FAIL", "detail": detail})

    reference = manifest.get("ruleset_reference")
    reference = reference if isinstance(reference, dict) else {}
    policy = _hosted_policy(manifest)
    expected_id = reference.get("ruleset_id")
    expected_name = reference.get("name")

    check("Ruleset ID", ruleset.get("id") == expected_id, {"expected": expected_id, "observed": ruleset.get("id")})
    check(
        "Ruleset name",
        ruleset.get("name") == expected_name,
        {"expected": expected_name, "observed": ruleset.get("name")},
    )
    check("Ruleset enforcement is active", ruleset.get("enforcement") == "active", ruleset.get("enforcement"))
    check("Ruleset targets branches", ruleset.get("target") == "branch", ruleset.get("target"))

    conditions = ruleset.get("conditions")
    conditions = conditions if isinstance(conditions, dict) else {}
    ref_name = conditions.get("ref_name")
    ref_name = ref_name if isinstance(ref_name, dict) else {}
    includes = {str(item) for item in ref_name.get("include", []) if isinstance(item, str)}
    excludes = {str(item) for item in ref_name.get("exclude", []) if isinstance(item, str)}
    default_branch = str(manifest.get("default_branch") or "main")
    accepted_targets = {"~DEFAULT_BRANCH", f"refs/heads/{default_branch}"}
    check(
        "Ruleset includes the default branch",
        bool(includes & accepted_targets),
        {"include": sorted(includes), "accepted": sorted(accepted_targets)},
    )
    check(
        "Ruleset does not exclude the default branch",
        not bool(excludes & accepted_targets),
        sorted(excludes),
    )

    rules = _rule_map(ruleset)
    pull_request = rules.get("pull_request")
    check("Pull-request rule is present", pull_request is not None, sorted(rules))
    pull_parameters = pull_request.get("parameters") if isinstance(pull_request, dict) else {}
    pull_parameters = pull_parameters if isinstance(pull_parameters, dict) else {}

    expected_approvals = policy.get("required_approving_review_count")
    observed_approvals = pull_parameters.get("required_approving_review_count")
    check(
        "Approving-review count matches the core-development policy",
        isinstance(expected_approvals, int) and observed_approvals == expected_approvals,
        {"expected": expected_approvals, "observed": observed_approvals},
    )
    expected_resolution = policy.get("required_review_thread_resolution")
    observed_resolution = pull_parameters.get("required_review_thread_resolution")
    check(
        "Review-thread resolution policy matches",
        isinstance(expected_resolution, bool) and observed_resolution is expected_resolution,
        {"expected": expected_resolution, "observed": observed_resolution},
    )
    expected_methods = policy.get("allowed_merge_methods")
    expected_methods = [str(item) for item in expected_methods] if isinstance(expected_methods, list) else []
    observed_methods = pull_parameters.get("allowed_merge_methods")
    observed_methods = [str(item) for item in observed_methods] if isinstance(observed_methods, list) else []
    check(
        "Allowed merge methods match",
        sorted(observed_methods) == sorted(expected_methods),
        {"expected": sorted(expected_methods), "observed": sorted(observed_methods)},
    )

    required_checks = rules.get("required_status_checks")
    check("Required-status-check rule is present", required_checks is not None, sorted(rules))
    observed_contexts, observed_rows = _observed_contexts(required_checks or {})
    expected_contexts = _expected_api_contexts(manifest)
    check(
        "Hosted required checks match the repository contract",
        observed_contexts == expected_contexts,
        {
            "expected": sorted(expected_contexts),
            "observed": sorted(observed_contexts),
            "missing": sorted(expected_contexts - observed_contexts),
            "unexpected": sorted(observed_contexts - expected_contexts),
        },
    )

    check(
        "Required checks have unique contexts",
        len(observed_rows) == len(observed_contexts),
        observed_rows,
    )
    strict = None
    if isinstance(required_checks, dict) and isinstance(required_checks.get("parameters"), dict):
        strict = required_checks["parameters"].get("strict_required_status_checks_policy")
    check("Strict required-status-check policy is enabled", strict is True, strict)

    bypass = ruleset.get("bypass_actors")
    bypass_rows = bypass if isinstance(bypass, list) else []
    failed = [item for item in checks if item["status"] == "FAIL"]
    return {
        "schema_version": 1,
        "ruleset_id": ruleset.get("id"),
        "ruleset_name": ruleset.get("name"),
        "status": "PASS" if not failed else "FAIL",
        "checks_total": len(checks),
        "checks_passed": len(checks) - len(failed),
        "checks_failed": len(failed),
        "required_status_check_contexts": sorted(observed_contexts),
        "pull_request_parameters": pull_parameters,
        "expected_hosted_policy": policy,
        "bypass_actors": bypass_rows,
        "observed_rule_types": sorted(rules),
        "checks": checks,
        "boundary": (
            "This report verifies the GitHub-hosted ruleset response acquired for the named repository. "
            "It does not authenticate human reviewers, establish scientific or release authority, or prove "
            "that future settings remain unchanged after the recorded acquisition."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ruleset-json", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=ROOT / ".github/required-checks.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = audit(
            _load_object(args.ruleset_json, "GitHub ruleset response"),
            _load_object(args.manifest, "required-check manifest"),
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        report = {
            "schema_version": 1,
            "status": "FAIL",
            "checks_total": 1,
            "checks_passed": 0,
            "checks_failed": 1,
            "checks": [{"name": "Ruleset audit execution", "status": "FAIL", "detail": str(exc)}],
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report.get(key) for key in ("ruleset_id", "status", "checks_failed")}, indent=2))
    return 0 if report.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
