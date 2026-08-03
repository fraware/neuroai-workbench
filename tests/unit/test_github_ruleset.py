from __future__ import annotations

from scripts.verify_github_ruleset import audit


def _manifest() -> dict:
    return {
        "default_branch": "main",
        "ruleset_reference": {
            "ruleset_id": 20116255,
            "name": "Protect main",
            "hosted_policy": {
                "required_approving_review_count": 0,
                "required_review_thread_resolution": True,
                "allowed_merge_methods": ["squash"],
            },
        },
        "required_pull_request_contexts": [
            "CI / quality",
            "CI / tests-python-3.13",
            "Dependency review / dependency-review",
            "CodeQL / codeql",
        ],
    }


def _ruleset() -> dict:
    return {
        "id": 20116255,
        "name": "Protect main",
        "target": "branch",
        "enforcement": "active",
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "bypass_actors": [],
        "rules": [
            {
                "type": "pull_request",
                "parameters": {
                    "required_approving_review_count": 0,
                    "dismiss_stale_reviews_on_push": True,
                    "require_code_owner_review": False,
                    "require_last_push_approval": False,
                    "required_review_thread_resolution": True,
                    "allowed_merge_methods": ["squash"],
                },
            },
            {
                "type": "required_status_checks",
                "parameters": {
                    "strict_required_status_checks_policy": True,
                    "required_status_checks": [
                        {"context": "quality", "integration_id": 15368},
                        {"context": "tests-python-3.13", "integration_id": 15368},
                        {"context": "dependency-review", "integration_id": 15368},
                        {"context": "codeql", "integration_id": 15368},
                    ],
                },
            },
            {"type": "deletion"},
            {"type": "non_fast_forward"},
        ],
    }


def test_matching_ruleset_passes():
    report = audit(_ruleset(), _manifest())
    assert report["status"] == "PASS"
    assert report["checks_failed"] == 0
    assert report["required_status_check_contexts"] == [
        "codeql",
        "dependency-review",
        "quality",
        "tests-python-3.13",
    ]


def test_missing_context_and_unexpected_context_fail():
    ruleset = _ruleset()
    rows = ruleset["rules"][1]["parameters"]["required_status_checks"]
    rows.pop()
    rows.append({"context": "legacy-check", "integration_id": 15368})
    report = audit(ruleset, _manifest())
    parity = next(item for item in report["checks"] if item["name"] == "Hosted required checks match the repository contract")
    assert parity["status"] == "FAIL"
    assert parity["detail"]["missing"] == ["codeql"]
    assert parity["detail"]["unexpected"] == ["legacy-check"]


def test_inactive_or_wrong_target_ruleset_fails():
    ruleset = _ruleset()
    ruleset["enforcement"] = "evaluate"
    ruleset["conditions"]["ref_name"] = {"include": ["refs/heads/develop"], "exclude": ["refs/heads/main"]}
    report = audit(ruleset, _manifest())
    failed = {item["name"] for item in report["checks"] if item["status"] == "FAIL"}
    assert "Ruleset enforcement is active" in failed
    assert "Ruleset includes the default branch" in failed
    assert "Ruleset does not exclude the default branch" in failed


def test_core_review_and_merge_policy_must_match_exactly():
    ruleset = _ruleset()
    parameters = ruleset["rules"][0]["parameters"]
    parameters["required_approving_review_count"] = 1
    parameters["required_review_thread_resolution"] = False
    parameters["allowed_merge_methods"] = ["merge", "squash"]
    report = audit(ruleset, _manifest())
    failed = {item["name"] for item in report["checks"] if item["status"] == "FAIL"}
    assert "Approving-review count matches the core-development policy" in failed
    assert "Review-thread resolution policy matches" in failed
    assert "Allowed merge methods match" in failed


def test_strict_policy_is_required():
    ruleset = _ruleset()
    ruleset["rules"][1]["parameters"]["strict_required_status_checks_policy"] = False
    report = audit(ruleset, _manifest())
    failed = {item["name"] for item in report["checks"] if item["status"] == "FAIL"}
    assert "Strict required-status-check policy is enabled" in failed


def test_duplicate_hosted_context_is_rejected():
    ruleset = _ruleset()
    rows = ruleset["rules"][1]["parameters"]["required_status_checks"]
    rows.append(dict(rows[0]))
    report = audit(ruleset, _manifest())
    duplicate = next(item for item in report["checks"] if item["name"] == "Required checks have unique contexts")
    assert duplicate["status"] == "FAIL"
