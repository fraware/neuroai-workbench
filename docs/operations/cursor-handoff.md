# Cursor engineering handoff

## Operating model

Each engineering task receives one GitHub issue, one `agent/<bounded-scope>` branch, and one draft pull request. Agents must read `AGENTS.md` and every applicable rule in `.cursor/rules/` before editing.

## Required opening response from an agent

The agent must state:

1. the controlling programme invariant;
2. the exact issue acceptance criteria;
3. the files it expects to change;
4. the tests it will add or run;
5. whether the task can affect schema, migration, evidence, authority, privacy, or security semantics.

## Required closing response from an agent

The agent must provide:

1. a concise implementation summary;
2. the exact checks run and their results;
3. a diff review for generated data, private data, remote dependencies, and unsupported claims;
4. a declaration of semantic impact;
5. remaining risks or deliberately deferred work;
6. a draft pull request linked to the issue.

## Background-agent boundary

Background agents may work only on the public source tree and synthetic or explicitly public fixtures. Never mount or disclose private assessment workspaces, participant-level records, credentials, confidential evidence, regulator correspondence, protected security findings, or encryption material.

## Handoff sequence

1. Complete and merge the v0.2.1 stabilization pull request.
2. Activate the GitHub controls in `github-governance-setup.md`.
3. Publish and verify v0.2.1.
4. Assign v0.3.0 issues individually, beginning with review/disagreement records and report generation.
5. Keep institutional deployment work behind architecture decisions and explicit security review.
