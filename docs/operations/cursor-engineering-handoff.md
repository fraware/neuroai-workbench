# Cursor engineering handoff

## Purpose

This playbook governs the transition from the verified local implementation to issue-scoped engineering through Cursor. It complements `AGENTS.md` and the rules under `.cursor/rules/`.

## Branch sequence

1. Import the canonical Git bundle and preserve `main`, `v0.1.0`, and `v0.2.0`.
2. Review `agent/v0.2.1-stabilization` as a bounded stabilization pull request.
3. Merge stabilization only after all protected checks pass.
4. Rebase `agent/v0.3.0-foundations` onto the merged stabilization result when required.
5. Review the v0.3 foundation in a separate pull request. Keep package version `0.2.1` until a release decision authorizes `0.3.0`.

## Mandatory first response from every Cursor agent

Before editing, the agent must provide:

1. the GitHub issue number and bounded objective;
2. the governing invariant from `AGENTS.md`;
3. the files it expects to change;
4. the tests it will add or run;
5. whether schema, migration, evidence, authority, network, or security semantics could change;
6. any protected data or external-service risk.

Do not permit implementation until this response is concrete.

## Standard task prompt

```text
Work only on GitHub issue #<NUMBER> in fraware/neuroai-workbench.

Read AGENTS.md, every applicable .cursor/rules file, docs/architecture/overview.md,
docs/governance/evidence-boundary.md, THREAT_MODEL.md, DATA_GOVERNANCE.md, and the issue.

First report the governing invariant, file-level plan, tests, semantic impact, and data/security risks.
Then implement only the issue scope on branch agent/<issue-number>-<short-name>.

Requirements:
- preserve exact system, configuration, population, endpoint, jurisdiction, and evidence-freeze boundaries;
- do not infer substantive truth from validation or hashes;
- do not convert unavailable evidence into FAIL;
- do not change the 78-requirement kernel without a dedicated ADR and domain review;
- use public or synthetic fixtures only;
- add adversarial tests for every integrity boundary;
- update documentation and release verification;
- run the relevant test subset and the full required checks;
- inspect the final diff for generated files, sensitive data, unsupported claims, and semantic drift;
- disclose every command, failure, unresolved risk, and model-assisted contribution;
- open a draft PR linked to the issue.
```

## Immediate issue order

### Repository activation

- Issue #1 imports canonical history and tags.
- Issue #2 reviews v0.2.1 stabilization.
- Issue #3 activates protected-main governance.
- Issue #4 reproduces and enforces CI and security gates.
- Issue #5 publishes v0.2.1 from a clean tagged commit.

### v0.3 foundation review

- Issue #13 reviews the integrated foundation.
- Issue #7 reviews the PRIMA adapter and its lossy mappings.
- Issue #8 reviews observatory v1.7 successor semantics.
- Issue #11 reviews model-assistance provenance and authority controls.

### Subsequent product work

- Issue #6 reviews and decomposes the collaborative assignment, disagreement, disposition, review-report, and gap-report foundation into separate follow-on issues and PRs.
- Issue #9 defines the separate institutional deployment architecture.
- Issue #10 commissions independent methodological, security, and accessibility review.

## Review gates by file

Changes to these surfaces require domain or security review beyond ordinary code review:

- `src/neuroai_workbench/resources/v4_2/**`
- `src/neuroai_workbench/validation.py`
- `src/neuroai_workbench/migration.py`
- `src/neuroai_workbench/programme_adapter.py`
- `src/neuroai_workbench/assistance.py`
- `src/neuroai_workbench/review.py`
- `src/neuroai_workbench/reports.py`
- `src/neuroai_workbench/evidence.py`
- `src/neuroai_workbench/events.py`
- `src/neuroai_workbench/server.py`
- `THREAT_MODEL.md`
- `DATA_GOVERNANCE.md`
- release workflows and verification scripts.

## Model-assistance review

A provider integration is not part of the present foundation. Any future integration requires a separate ADR and must define:

- explicit user opt-in;
- provider and model allowlists;
- data classification and redaction policy;
- zero-retention and training-use requirements where applicable;
- network isolation and egress controls;
- prompt-injection and data-exfiltration tests;
- request and response size limits;
- retry, timeout, cost, and rate-limit controls;
- immutable provenance records;
- human disposition and non-mutation guarantees;
- a kill switch and complete offline fallback.

## Completion evidence

A Cursor task is complete only when the draft PR contains:

- linked issue;
- concise architecture and semantic-impact statement;
- tests added and commands run;
- exact test and coverage results;
- screenshots only when UI behavior changed;
- migration and compatibility statement;
- security and data-governance statement;
- explicit confirmation that no private evidence or credential entered the branch;
- unresolved risks and follow-up issues.

## Collaborative-review review

Changes to review assignments, statements, dispositions, or reports must demonstrate that:

- reviewer identity and role remain explicitly unauthenticated in the local reference profile;
- disagreement and abstention records remain visible after disposition;
- only a covering recorded decision role can create a disposition;
- statements and dispositions never mutate `assessment.json`;
- evidence references resolve to the assessment register;
- record and event-chain tampering is detected;
- private evidence and credentials remain outside free-text fixtures and prompts;
- any later application of an accepted proposal is a separate human-controlled assessment edit.
