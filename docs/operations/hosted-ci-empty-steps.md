# Hosted CI empty-steps condition

Status: infrastructure documentation. This note is not a test result and does not authorize a software release.

## What is observed

GitHub Actions jobs for this repository have completed in approximately two seconds with an empty step list:

```text
steps: []
```

A job in that state has no checkout, no Python setup, no pytest, and no log blob of executed work. The workflow YAML in `.github/workflows/ci.yml` already declares the required non-empty step lists. The empty-steps outcome is therefore a **runner-assignment / org Actions infrastructure** condition, not a repository test failure and not a passing test.

Software in this repository cannot assign GitHub-hosted runners, repair org billing, or override Actions policy.

## How to classify a hosted job

`scripts/classify_hosted_ci_execution.py` classifies a GitHub Actions job payload as follows:

| Condition | Classification | Meaning |
| --- | --- | --- |
| `steps` is missing or the job is queued / in progress | `NOT_EXECUTED` | No evidence yet |
| `steps` is present and empty (`[]`) | `INFRASTRUCTURE_FAILURE` | Runner did not execute workflow steps |
| `steps` contains executed entries and any required step failed | `EXECUTED_FAILURE` | A real test/quality failure |
| `steps` contains executed entries and required steps succeeded | `EXECUTED_SUCCESS` | Hosted execution evidence |

`INFRASTRUCTURE_FAILURE` must not be reported as `EXECUTED_FAILURE` (red tests) or `EXECUTED_SUCCESS` (green tests). Local `make quality` / `make test` remains the only executable evidence until hosted jobs have non-empty executed steps.

## What this is not

Two other hosted-CI items are separate and must not be collapsed into empty-steps:

1. **Protect-main ruleset gap (issue #4).** Ruleset ID `20116255` has been verified at 13/14 checks. The repository contract in `.github/required-checks.json` still requires `CI / pip-audit` and `CI / product-native`. That is a ruleset-parity gap, not empty-steps. Do not loosen the required-check contract to match the incomplete ruleset.
2. **Historical `v0.2.1` tag peel.** The published `v0.2.1` tag currently peels to the wrong commit ([v0.2.1-release-verification.md](../releases/v0.2.1-release-verification.md)). That is a historical integrity item. It is not M0-blocking for a future `v0.3.0` tag and must not be "repaired" without explicit release authority.

## Repository contract

`scripts/check_github_workflow_contract.py` continues to enforce the audited workflow set and required contexts. It now also refuses workflow YAML that declares `steps: []`. That check proves the repository still asks runners to do work. It cannot prove that GitHub assigned a runner.

Do not treat a missing hosted badge as passing. Do not treat an empty-steps completion as a failed test suite.
