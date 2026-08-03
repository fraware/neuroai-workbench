# GitHub required checks and workflow security contract

## Purpose

`.github/required-checks.json` is the repository-owned source of truth for pull-request checks and audited GitHub Actions workflows. `scripts/check_github_workflow_contract.py` validates that source of truth during the `CI / quality` job.

The contract addresses repository content. GitHub-hosted branch rules and rulesets remain platform configuration. Their required-check selections must equal the contexts listed below.

## Protected-main reference

Historical issue evidence identifies the active rule as:

- name: `Protect main`;
- ruleset ID: `20116255`;
- observed enforcement: PR #18 was blocked by `REVIEW_REQUIRED`; no bypass was used.

This evidence proves that the rule enforced review at that point. The repository validator has no GitHub Rules API access and does not claim that every current hosted setting matches this document. An administrator must compare the ruleset's current required status checks with `.github/required-checks.json` after any workflow job rename, workflow rename, ruleset edit, or repository transfer.

## Required pull-request contexts

The protected-main ruleset should require exactly these repository checks:

```text
CI / quality
CI / tests-python-3.10
CI / tests-python-3.11
CI / tests-python-3.12
CI / tests-python-3.13
CI / tests-python-3.14
CI / package
CI / release-verification
CI / container
CI / product-native
CI / pip-audit
Dependency review / dependency-review
CodeQL / codeql
```

`CI / quality` includes formatting, lint, static typing, compilation, repository hygiene, this workflow-contract audit, version consistency, and the agent evaluation harness.

## Repository-enforced properties

The validator fails when any of the following conditions occurs:

- a workflow file appears outside the audited manifest;
- an audited workflow disappears;
- a workflow or job name changes without a contract update;
- the Python test matrix changes without an explicit context update;
- a required pull-request trigger disappears;
- `pull_request_target`, `workflow_run`, or `repository_dispatch` enters the workflow set;
- a pull-request workflow references `${{ secrets.* }}`;
- workflow permissions differ from the explicit allowlist;
- an external action is referenced without a full 40-character commit SHA;
- the derived job contexts differ from the required-context list;
- `CI / quality` stops executing the validator.

The validator audits these workflows:

- `.github/workflows/ci.yml`;
- `.github/workflows/dependency-review.yml`;
- `.github/workflows/codeql.yml`;
- `.github/workflows/release.yml`.

## Permission boundaries

Pull-request workflows use read-only repository contents. CodeQL additionally receives `security-events: write`, plus read access to packages and Actions metadata, for analysis upload. The tag-triggered release workflow receives `contents: write`, `id-token: write`, and `attestations: write` for draft release creation and artifact attestation.

The release workflow uses `${{ github.token }}` within a tag-triggered job. Pull-request workflows remain free of repository-secret dependencies.

## Network and protected-data boundary

Ordinary tests and quality gates use no live source collection. Operations-gated tests remain explicitly skipped unless their environment gates and protected workspace are present. Container checks bind to loopback; the explicit network-profile smoke test exposes only `127.0.0.1` on the runner and exercises the opt-in network flag.

Successful CI establishes software-build and test status. It does not establish scientific validity, evidence authenticity, clinical safety, regulatory authorization, conformance, institutional endorsement, UNESCO attribution, or canonical observatory release authority.

## Change procedure

A workflow change that affects a workflow name, job name, matrix value, permission, trigger, or action reference must update the manifest and this document in the same pull request. The pull request must pass the old or transition-compatible protected checks, and an administrator must update the GitHub-hosted ruleset only after the successor check contexts have appeared successfully.

For a context rename, use a two-stage migration:

1. introduce the successor job while retaining the predecessor required context;
2. observe the successor context on a pull request;
3. update the hosted ruleset;
4. remove the predecessor job in a later pull request.

This sequence avoids making `main` unmergeable through a check-name race.

## Verification command

```bash
python scripts/check_github_workflow_contract.py
python -m pytest tests/unit/test_github_workflow_contract.py -q
```
