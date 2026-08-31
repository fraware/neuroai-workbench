from __future__ import annotations

import json
from pathlib import Path

from scripts.classify_hosted_ci_execution import (
    EXECUTED_FAILURE,
    EXECUTED_SUCCESS,
    INFRASTRUCTURE_FAILURE,
    classify_hosted_job,
    classify_jobs,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ci"


def test_empty_steps_are_infrastructure_failure_not_test_failure() -> None:
    job = json.loads((FIXTURES / "hosted-job-empty-steps.json").read_text(encoding="utf-8"))
    result = classify_hosted_job(job)
    assert result["classification"] == INFRASTRUCTURE_FAILURE
    assert result["not_a_test_result"] is True
    assert result["step_count"] == 0
    assert result["classification"] != EXECUTED_FAILURE
    assert result["classification"] != EXECUTED_SUCCESS


def test_executed_step_failure_is_test_failure() -> None:
    job = json.loads((FIXTURES / "hosted-job-executed-failure.json").read_text(encoding="utf-8"))
    result = classify_hosted_job(job)
    assert result["classification"] == EXECUTED_FAILURE
    assert result["not_a_test_result"] is False


def test_executed_step_success_is_hosted_execution_evidence() -> None:
    job = json.loads((FIXTURES / "hosted-job-executed-success.json").read_text(encoding="utf-8"))
    result = classify_hosted_job(job)
    assert result["classification"] == EXECUTED_SUCCESS
    assert result["not_a_test_result"] is False


def test_jobs_wrapper_payload() -> None:
    payload = {"jobs": [json.loads((FIXTURES / "hosted-job-empty-steps.json").read_text(encoding="utf-8"))]}
    results = classify_jobs(payload)
    assert results[0]["classification"] == INFRASTRUCTURE_FAILURE
