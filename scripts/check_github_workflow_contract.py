#!/usr/bin/env python3
"""Validate the repository-owned GitHub Actions and required-check contract."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(".github/required-checks.json")
_ACTION_REF_RE = re.compile(r"(?m)^\s*-\s+uses:\s*([^\s#]+)")
_JOB_ID_RE = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")
_JOB_NAME_RE = re.compile(r"^    name:\s*(.+?)\s*$")
_PERMISSION_RE = re.compile(r"^  ([A-Za-z0-9_-]+):\s*([^#\s]+)\s*$")
_WORKFLOW_NAME_RE = re.compile(r"(?m)^name:\s*(.+?)\s*$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _load_manifest(root: Path) -> dict[str, Any]:
    path = root / MANIFEST
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError(f"Unsupported required-check manifest: {path}")
    workflows = value.get("workflows")
    contexts = value.get("required_pull_request_contexts")
    if not isinstance(workflows, list) or not isinstance(contexts, list):
        raise ValueError("Required-check manifest must contain workflow and context lists")
    return value


def _workflow_files(root: Path) -> set[str]:
    directory = root / ".github" / "workflows"
    return {
        path.relative_to(root).as_posix()
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in {".yml", ".yaml"}
    }


def _workflow_name(text: str) -> str | None:
    match = _WORKFLOW_NAME_RE.search(text)
    return match.group(1).strip("\"'") if match else None


def _permissions(text: str) -> dict[str, str]:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line == "permissions:":
            result: dict[str, str] = {}
            for candidate in lines[index + 1 :]:
                if candidate and not candidate.startswith(" "):
                    break
                match = _PERMISSION_RE.match(candidate)
                if match:
                    result[match.group(1)] = match.group(2).strip("\"'")
            return result
    return {}


def _jobs(text: str) -> dict[str, str | None]:
    lines = text.splitlines()
    in_jobs = False
    current: str | None = None
    result: dict[str, str | None] = {}
    for line in lines:
        if line == "jobs:":
            in_jobs = True
            continue
        if not in_jobs:
            continue
        if line and not line.startswith(" "):
            break
        job_match = _JOB_ID_RE.match(line)
        if job_match:
            current = job_match.group(1)
            result[current] = None
            continue
        name_match = _JOB_NAME_RE.match(line)
        if current and name_match and result[current] is None:
            result[current] = name_match.group(1).strip("\"'")
    return result


def _matrix_values(text: str, key: str) -> list[str] | None:
    match = re.search(rf"(?m)^\s+{re.escape(key)}:\s*\[(.*?)\]\s*$", text)
    if not match:
        return None
    return [part.strip().strip("\"'") for part in match.group(1).split(",") if part.strip()]


def _action_pin_errors(path: str, text: str) -> list[str]:
    errors: list[str] = []
    for reference in _ACTION_REF_RE.findall(text):
        if reference.startswith("./"):
            continue
        if "@" not in reference:
            errors.append(f"{path}: action reference has no immutable revision: {reference}")
            continue
        action, revision = reference.rsplit("@", 1)
        if not action or not _SHA_RE.fullmatch(revision):
            errors.append(f"{path}: action is not pinned to a 40-character commit SHA: {reference}")
    return errors


def validate(root: Path) -> list[str]:
    root = root.resolve()
    manifest = _load_manifest(root)
    errors: list[str] = []

    workflow_specs = manifest["workflows"]
    expected_files = {str(item["path"]) for item in workflow_specs}
    observed_files = _workflow_files(root)
    missing = sorted(expected_files - observed_files)
    unknown = sorted(observed_files - expected_files)
    if missing:
        errors.append(f"Missing audited workflow files: {', '.join(missing)}")
    if unknown:
        errors.append(f"Unaudited workflow files present: {', '.join(unknown)}")

    derived_contexts: list[str] = []
    global_forbidden = [str(item) for item in manifest.get("global_forbidden_markers", [])]

    for spec in workflow_specs:
        relative = str(spec["path"])
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")

        expected_name = str(spec["name"])
        observed_name = _workflow_name(text)
        if observed_name != expected_name:
            errors.append(f"{relative}: workflow name {observed_name!r} != {expected_name!r}")

        for marker in global_forbidden:
            if marker in text:
                errors.append(f"{relative}: forbidden workflow marker present: {marker}")
        for marker in spec.get("required_trigger_markers", []):
            if str(marker) not in text:
                errors.append(f"{relative}: required trigger marker missing: {marker}")

        pull_request_required = bool(spec.get("pull_request_required"))
        if pull_request_required and "  pull_request:" not in text:
            errors.append(f"{relative}: pull_request trigger is required")
        if pull_request_required and bool(spec.get("forbid_secrets")):
            if re.search(r"\$\{\{\s*secrets\.", text, flags=re.IGNORECASE):
                errors.append(f"{relative}: pull-request workflow references repository secrets")

        expected_permissions = {str(key): str(value) for key, value in spec.get("permissions", {}).items()}
        observed_permissions = _permissions(text)
        if observed_permissions != expected_permissions:
            errors.append(f"{relative}: permissions {observed_permissions!r} != contract {expected_permissions!r}")

        errors.extend(_action_pin_errors(relative, text))

        expected_jobs = {str(item["id"]): item for item in spec.get("jobs", [])}
        observed_jobs = _jobs(text)
        if set(observed_jobs) != set(expected_jobs):
            errors.append(f"{relative}: job IDs {sorted(observed_jobs)!r} != contract {sorted(expected_jobs)!r}")
        for job_id, job_spec in expected_jobs.items():
            expected_job_name = str(job_spec["name"])
            observed_job_name = observed_jobs.get(job_id)
            if observed_job_name != expected_job_name:
                errors.append(f"{relative}: job {job_id!r} name {observed_job_name!r} != {expected_job_name!r}")
            matrix_key = job_spec.get("matrix_key")
            if matrix_key:
                expected_values = [str(value) for value in job_spec.get("matrix_values", [])]
                observed_values = _matrix_values(text, str(matrix_key))
                if observed_values != expected_values:
                    errors.append(f"{relative}: matrix {matrix_key!r} {observed_values!r} != {expected_values!r}")
            if pull_request_required:
                derived_contexts.extend(str(value) for value in job_spec.get("required_contexts", []))

    expected_contexts = [str(value) for value in manifest["required_pull_request_contexts"]]
    if len(expected_contexts) != len(set(expected_contexts)):
        errors.append("required_pull_request_contexts contains duplicates")
    if sorted(derived_contexts) != sorted(expected_contexts):
        errors.append(
            "Derived pull-request contexts do not match required_pull_request_contexts: "
            f"derived={sorted(derived_contexts)!r}, expected={sorted(expected_contexts)!r}"
        )

    ci_path = root / ".github" / "workflows" / "ci.yml"
    if ci_path.is_file() and "python scripts/check_github_workflow_contract.py" not in ci_path.read_text(
        encoding="utf-8"
    ):
        errors.append("CI quality job does not execute check_github_workflow_contract.py")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        errors = validate(args.root)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: workflow contract could not be evaluated: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    manifest = _load_manifest(args.root.resolve())
    print(
        "GitHub workflow contract passed: "
        f"{len(manifest['workflows'])} workflows, "
        f"{len(manifest['required_pull_request_contexts'])} required PR contexts"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
