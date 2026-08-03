# AI-agent development protocol

AI coding agents are treated as untrusted implementation assistants operating under repository controls. This guide is the durable handoff and development protocol for Cursor and similar agents. It complements `AGENTS.md` and the rules under `.cursor/rules/`.

## Operating model

Each engineering task receives:

- one GitHub issue;
- one `agent/<bounded-scope>` branch;
- one draft pull request.

Agents must read `AGENTS.md` and every applicable rule in `.cursor/rules/` before editing.

## Required opening response

Before editing, the agent must state:

1. the GitHub issue number and bounded objective;
2. the governing invariant from `AGENTS.md`;
3. the files it expects to change;
4. the tests it will add or run;
5. whether schema, migration, evidence, authority, network, privacy, or security semantics could change;
6. any protected data or external-service risk.

Do not permit implementation until this response is concrete.

## Required closing response

A task is complete only when the draft PR contains:

1. a concise implementation summary and semantic-impact statement;
2. the exact checks run and their results;
3. a diff review for generated data, private data, remote dependencies, and unsupported claims;
4. migration and compatibility notes when applicable;
5. security and data-governance notes when applicable;
6. explicit confirmation that no private evidence or credential entered the branch;
7. remaining risks or deliberately deferred work;
8. a draft pull request linked to the issue.

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

## Background-agent boundary

Background agents may access the network and execute commands. Use them only with the public source tree and synthetic or explicitly public fixtures. Never mount or disclose private assessment workspaces, participant-level records, credentials, confidential evidence, regulator correspondence, protected security findings, or encryption material.

## Review gates by file

Changes to these surfaces require domain or security review beyond ordinary code review:

- `src/neuroai_workbench/resources/v4_2/**`
- `src/neuroai_workbench/validation.py`
- `src/neuroai_workbench/migration.py`
- `src/neuroai_workbench/programme_adapter.py`
- `src/neuroai_workbench/assistance.py`
- `src/neuroai_workbench/review.py`
- `src/neuroai_workbench/exchange.py`
- `src/neuroai_workbench/reports.py`
- `src/neuroai_workbench/evidence.py`
- `src/neuroai_workbench/events.py`
- `src/neuroai_workbench/server.py`
- `THREAT_MODEL.md`
- `DATA_GOVERNANCE.md`
- release workflows and verification scripts.

## Collaborative-review changes

Changes to review assignments, statements, dispositions, or reports must demonstrate that:

- reviewer identity and role remain explicitly unauthenticated in the local reference profile;
- disagreement and abstention records remain visible after disposition;
- only a covering recorded decision role can create a disposition;
- statements and dispositions never mutate `assessment.json`;
- evidence references resolve to the assessment register;
- record and event-chain tampering is detected;
- private evidence and credentials remain outside free-text fixtures and prompts;
- any later application of an accepted proposal is a separate human-controlled assessment edit.

## Protected-evidence exchange changes

Changes to custodian requests or response records must demonstrate that no evidence bytes, local paths, credentials, private excerpts, or access tokens enter the exchange package; every evidence and gap ID resolves; response state and material references are consistent; out-of-band material remains `NOT_VERIFIED_BY_WORKBENCH`; tampering is detected; and no exchange record mutates the assessment.

## Assessment-facing language-model assistance

Engineering-agent use and assessment-facing model assistance are separate trust domains. Product features that use language models must follow ADR 0005. The first supported pattern is bounded prompt-package export and candidate-response import with field-level human disposition, provenance, and an offline fallback. Direct external model calls remain disabled in the default workbench.

A provider integration is not part of the default workbench. Any future integration requires a separate ADR and must define explicit user opt-in, provider and model allowlists, data classification and redaction, zero-retention and training-use requirements where applicable, network isolation, prompt-injection and exfiltration tests, size and rate limits, immutable provenance, human disposition and non-mutation guarantees, a kill switch, and complete offline fallback.

## Agent evaluation harness

Repository-native behavioral checks live in `scripts/agent_eval_harness.py` and run in CI quality:

```bash
python scripts/agent_eval_harness.py
python scripts/agent_eval_harness.py --json
```

Cases cover version consistency, NOT ASSESSED preservation, event-chain tampering, evidence replacement, loopback network binding, migration preservation checks, generated-artifact hygiene, report claim-boundary language, and an explicit prohibited shortcut that would convert missing/unresolved evidence into FAIL.

Harness pass/fail is engineering evidence only. It does not establish scientific truth, regulatory authorization, security acceptance, or release authority. Pull requests must complete the AI provenance field in `.github/PULL_REQUEST_TEMPLATE.md` when an agent materially affected the change.
