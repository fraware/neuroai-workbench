# CI and evidence assurance: separate engineering checks from programme authority

**Document status:** Current engineering/assurance guidance (24 October 2026).  
**Repositories:** [NeuroAI Workbench](https://github.com/fraware/neuroai-workbench) (source code, execution and validation); [NeuroAI Observatory Data](https://github.com/fraware/neuroai-observatory-data) (controlled canonical/public data and curation).  
**Current programme authority:** [Release A corrective review](../programme/release-a-completion-status.md) and [Workbench issue #410](https://github.com/fraware/neuroai-workbench/issues/410).  
**Substantive R1.7 execution:** [issue #424](https://github.com/fraware/neuroai-workbench/issues/424).

## What a green check establishes

The version-controlled manifest [`.github/required-checks.json`](../../.github/required-checks.json) defines **12 required PR contexts** across CI quality, Python 3.11–3.14, package, release-verification, container, product-native, pip-audit, dependency review and CodeQL. The GitHub Checks API may return **13 check runs** because an additional `CodeQL`/scanner record is reported beside `CodeQL / codeql`; do not conflate observed run count with manifest context count.

A check is green **only** when the check belongs to the exact current PR-head SHA, its status is `completed`, and its conclusion is `success`. `in_progress`, `pending`, `failure`, `cancelled`, `neutral` and `skipped` are separate observations. Green checks at a previous SHA do not transfer to a new commit; a successful build for a different branch does not validate a combined merge. Verify the head SHA again after review and before merge.

```bash
python scripts/check_github_workflow_contract.py
python -m pytest tests/test_phase3_external_proof_workflow.py -q
python -m pytest --cov=neuroai_workbench --cov-report=term-missing --cov-fail-under=90
python scripts/check_aggregate_coverage.py --coverage-json coverage.json --floor 90.00
python scripts/check_module_coverage.py --coverage-json coverage.json
python scripts/check_workbook_reproducibility.py
python scripts/check_publication_reproducibility.py
```

The actual GitHub CI installs the hashed [dependency lock](../../requirements/constraints.txt), executes the full Python matrix and records package, container, security and reproducibility checks. The commands above explain important controls; use the exact workflow definition for the authoritative command list. Do not bypass failing jobs, lower coverage thresholds or relabel a run's result.

## Immutable action pins and workflow changes

Action references are pinned to complete, 40-character commit SHAs and must be updated as a **workflow-and-contract change**. Search the entire repository for the previous pin, including **tests that explicitly validate a security-sensitive workflow action**. In particular:

- `tests/test_phase3_external_proof_workflow.py` checks the exact pin used to upload a sanitized Phase 3 bundle. When the pinned `actions/upload-artifact` commit is deliberately updated, update this assertion to the reviewed commit without weakening checks on source-byte quarantine, release authority, secrets, workflow triggers, read-only permissions or clean repository state.
- Validate *all* references in CI, Phase 3 proof, monitoring and release workflows; confirm updated actions are pinned to real upstream commits, keep the unchanged actions' version comments accurate and inspect the whole PR patch for unexpected diff lines.
- Confirm the repository-owned workflow contract, CodeQL, dependency review, and the complete Python matrix on the new exact head. A separate release workflow or external-proof workflow not triggered by a PR is **not** exercised merely by green PR checks. Its sensitive execution needs a distinct authorization and verification record.

Historical red Dependabot runs reflect the specific old head and its pinned dependency state. A replacement PR must be evaluated on its own exact head. Close superseded PRs only with an explicit documented disposition; closing them never rewrites the old CI verdict.

## Hosted policy versus repository manifest

At the 24 October 2026 inspection, Workbench `main` reports **`protected=false`** and **no active hosted rulesets**, even though the versioned manifest enumerates required contexts. Thus successful CI is evidence of engineering checks, **not proof that GitHub technically prevents an unreviewed merge**. Previous owner direction did not authorize reinstating hosted protection. A governance-policy change needs the repository owner's explicit, current authorization and separately verified hosted settings.

The Observatory Data `main` is a distinct, protected branch with independent controls. Its review and PATSTAT checks do not grant Workbench release authority.

## Evidence and research control

Cryptographic hashes establish **byte identity**, not authenticity, rights, model equivalence, commercial distribution, independent clinical performance, source exhaustion, AI eligibility or human adjudication.

R1.7's frozen unit checkpoint contains **270** review items: 171 source-surface resolution (226 capture slots), 21 literature-record extraction (21), 76 empirical candidate adjudications (142), and two product temporal reviews (no separate capture slots), totaling **389 historical capture slots**. The source/record subset contains **192 tasks / 247 capture slots**.

The verified four-publication archive replay records four machine-provisional literature receipts with **zero completed source/record items** and **zero active accepted extracted leads**. Matching a source row to an existing product string does not establish an additional product identity. Official pages observed through extracted web text must be distinguished from replayable, raw HTTP response bytes. The three source archives and associated metadata are stored in **noncanonical personal Library staging**, not an approved controlled institutional custodian. Every source observation requires an explicit **valid-time** and **knowledge-time** boundary.

The Release-A world cutoff is **2026-09-24** and its knowledge cutoff is **2026-10-24T23:59:59Z**. A snapshot generated *before* the close is **PRE-CUTOFF**, even if all available data at that time have been inspected. After the deadline, the final closeout must account for **all timely admissible evidence** and retain later evidence separately. Green CI, stable hashes and replay results cannot advance the S2 canonical authority, Product Registry population, G0/G2/G3/G5 or downstream denominator/publication gates.

## What to write in a PR review

Report the exact repository, base and head SHAs; the observed check names/statuses; which tests actually executed; original source archive and payload digests where relevant; significant known failures; any superseded branch; and material remaining risks. Explicitly distinguish:
1. **Code correctness** (unit/integration tests and diff review).
2. **Reproducibility and evidence integrity** (archive hashes, captured bytes, exact frozen engine and replay).
3. **Scientific/rights/eligibility approval** (independent authorized review, normative reference and signed decisions).
4. **Hosted release enforcement** (current GitHub branch settings and permitted merge/release methods).

An independent reviewer must decide whether a specific PR is ready to merge. Even a fully green PR does not establish a Release-A or institutional certification.
