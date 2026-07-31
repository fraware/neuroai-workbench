# GitHub governance activation

This document records repository controls that require an administrator to activate in GitHub. Committed policy files support these controls but do not activate them.

## Repository settings

- Keep the repository private during stabilization. Revisit public visibility only after the v0.2.1 release review.
- Enable squash merging.
- Disable merge commits.
- Disable rebase merging unless release management adopts an explicit exception.
- Delete head branches automatically after merge.
- Enable issues and vulnerability reporting.
- Set GitHub Actions workflow permissions to read repository contents by default and allow write permissions only where a workflow declares them.

## Main-branch ruleset

Target the default branch `main` and configure the ruleset as active.

Required controls:

1. Require pull requests for every change.
2. Require one approval for ordinary changes.
3. Require Code Owner review.
4. Dismiss stale approvals when new commits are pushed.
5. Require approval of the latest reviewable push by someone other than its author when the reviewer pool permits it.
6. Require all review conversations to be resolved.
7. Require branches to be current with `main` before merge.
8. Require linear history.
9. Block force pushes and branch deletion.
10. Do not grant routine bypass authority.

Required status checks after the first successful pull-request run:

- `quality`
- `tests-python-3.10`
- `tests-python-3.11`
- `tests-python-3.12`
- `tests-python-3.13`
- `tests-python-3.14`
- `package`
- `release-verification`
- `container`
- the CodeQL analysis check
- dependency review

## Elevated review boundary

GitHub supports one minimum approval count per branch rule. Changes in the following paths therefore require a second substantive approval through CODEOWNERS policy and the pull-request checklist, even if the platform rule is initially set to one:

- `src/neuroai_workbench/resources/v4_2/**`
- `src/neuroai_workbench/validation.py`
- `src/neuroai_workbench/migration.py`
- `src/neuroai_workbench/events.py`
- `src/neuroai_workbench/evidence.py`
- `SECURITY.md`
- `THREAT_MODEL.md`
- `.github/workflows/**`
- `scripts/verify_release.py`

Add named domain and security reviewers to `.github/CODEOWNERS` once their GitHub identities are known. The repository owner is the temporary sole Code Owner and must not represent self-review as independent review.

## Security controls

Activate, where available for the repository plan:

- Dependabot alerts and security updates;
- dependency graph;
- secret scanning;
- push protection;
- private vulnerability reporting;
- CodeQL default or advanced setup, without duplicating the committed workflow;
- artifact attestations for release workflows.

## Release protection

- Protect tags matching `v*` from deletion or update.
- Create release tags only from reviewed commits on `main`.
- Require `scripts/check_version_consistency.py --tag <tag>` and the complete release workflow.
- Publish generated distributions, SBOMs, manifests, bundles, verification records, and attestations as release assets, never as source-tree files.
