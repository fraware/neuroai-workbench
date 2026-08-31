#!/usr/bin/env python3
"""Classify GitHub Actions job payloads without treating empty steps as test results.

A job whose ``steps`` list is empty did not execute repository workflow steps. That
condition is infrastructure failure (runner assignment / org Actions), not pytest
failure and not success. This classifier does not contact GitHub.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

NOT_EXECUTED = "NOT_EXECUTED"
INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"
EXECUTED_FAILURE = "EXECUTED_FAILURE"
EXECUTED_SUCCESS = "EXECUTED_SUCCESS"

TERMINAL_JOB_STATUSES = frozenset({"completed", "cancelled", "failure", "success"})
FAILURE_STEP_CONCLUSIONS = frozenset({"failure", "timed_out", "cancelled", "action_required"})
SUCCESS_STEP_CONCLUSIONS = frozenset({"success", "skipped"})


def classify_hosted_job(job: dict[str, Any]) -> dict[str, Any]:
    """Return a classification record for one GitHub Actions job object."""
    if not isinstance(job, dict):
        raise ValueError("GitHub Actions job payload must be an object")
    status = str(job.get("status") or "").strip().lower()
    conclusion = str(job.get("conclusion") or "").strip().lower()
    name = str(job.get("name") or job.get("id") or "unknown-job")
    steps = job.get("steps")

    base = {
        "job_name": name,
        "status": status or None,
        "conclusion": conclusion or None,
        "not_a_test_result": False,
        "step_count": None,
    }

    if steps is None:
        return {
            **base,
            "classification": NOT_EXECUTED,
            "reason": "Job payload has no steps field; hosted execution evidence is absent",
        }

    if not isinstance(steps, list):
        raise ValueError("GitHub Actions job steps must be an array when present")

    base["step_count"] = len(steps)
    if len(steps) == 0:
        return {
            **base,
            "classification": INFRASTRUCTURE_FAILURE,
            "not_a_test_result": True,
            "reason": (
                "Job has empty steps: []. A GitHub-hosted runner did not execute workflow "
                "steps. This is infrastructure failure, not a test failure and not success."
            ),
        }

    failed = [
        str(step.get("name") or step.get("number") or "unnamed")
        for step in steps
        if isinstance(step, dict) and str(step.get("conclusion") or "").lower() in FAILURE_STEP_CONCLUSIONS
    ]
    if failed:
        return {
            **base,
            "classification": EXECUTED_FAILURE,
            "failed_steps": failed,
            "reason": "Hosted runner executed steps and at least one required step failed",
        }

    if status in TERMINAL_JOB_STATUSES or all(
        isinstance(step, dict) and str(step.get("conclusion") or "").lower() in SUCCESS_STEP_CONCLUSIONS
        for step in steps
    ):
        return {
            **base,
            "classification": EXECUTED_SUCCESS,
            "reason": "Hosted runner executed a non-empty step list without step-level failure",
        }

    return {
        **base,
        "classification": NOT_EXECUTED,
        "reason": "Steps are present but execution has not reached a terminal classification",
    }


def classify_jobs(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("jobs"), list):
        jobs = payload["jobs"]
    elif isinstance(payload, list):
        jobs = payload
    elif isinstance(payload, dict):
        jobs = [payload]
    else:
        raise ValueError("Payload must be a job object, a job list, or an object with a jobs array")
    return [classify_hosted_job(job) for job in jobs]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path, help="JSON file containing a job, job list, or {jobs: [...]}")
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.payload.read_text(encoding="utf-8"))
        results = classify_jobs(payload)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: hosted CI payload could not be classified: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(results, indent=2))
    if any(item["classification"] == INFRASTRUCTURE_FAILURE for item in results):
        print(
            "INFRASTRUCTURE_FAILURE: empty steps are not a test result. "
            "Do not report hosted success or hosted test failure.",
            file=sys.stderr,
        )
        return 2
    if any(item["classification"] == EXECUTED_FAILURE for item in results):
        return 1
    if any(item["classification"] == NOT_EXECUTED for item in results):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
