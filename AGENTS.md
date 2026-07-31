
# Engineering instructions for humans and AI agents

This repository implements evidence and decision infrastructure. It does not determine scientific truth, legal authorization, clinical value, ethical acceptability, deployment readiness, or substantive conformance.

## Mandatory invariants

1. Preserve the exact system, configuration, population, task, endpoint, context, jurisdiction, evidence freeze, and observation period attached to every conclusion.
2. Keep capability, authorization, deployment, commercial availability, and conformance as separate typed states.
3. Never convert missing, inaccessible, or unresolved public evidence into an automatic `FAIL`.
4. Never infer substantive truth from schema validation, file hashes, event-chain validity, test success, or software-generated counts.
5. Preserve all 78 v4.2 requirement identifiers and their meanings. A normative change requires a dedicated ADR, migration analysis, domain review, and major-version decision.
6. Preserve historical findings exactly during migration. Add successor records instead of silently overwriting prior determinations.
7. Use synthetic or explicitly public fixtures. Never commit private neural data, participant records, credentials, confidential regulator files, protected security findings, or decryption material.
8. Keep the default application local and offline-first. Do not introduce remote assets, telemetry, analytics, external model calls, or network exposure without a separate reviewed architecture.
9. Add tests for every behavioral change and adversarial tests for every integrity or security boundary change.
10. Update documentation, threat analysis, data-governance controls, and release verification when the affected boundary changes.
11. Treat reviewer names and roles as claimed local workflow identities unless an external authenticated deployment explicitly establishes otherwise. Preserve disagreement and abstention records; never erase dissent through a convenience edit.
12. Keep protected-evidence exchange metadata-only. A request or holder response must never imply evidence receipt, custody, authenticity, completeness, disclosure duty, or decision weight.
13. Treat model output as an untrusted draft. Record provider, model, selected context, hashes, and human disposition; never grant a model authority to alter findings, dispositions, conformance, security acceptance, or releases.

## Required task protocol

Before editing, read the applicable files under `.cursor/rules/`, `docs/architecture/overview.md`, `docs/governance/evidence-boundary.md`, `THREAT_MODEL.md`, and `DATA_GOVERNANCE.md`.

For each task:

1. State the invariant that governs the change.
2. Propose a file-level plan.
3. Identify tests before implementation.
4. Implement only the issue scope.
5. Run the relevant test subset and the full release gates when practical.
6. Review the diff for generated files, protected data, semantic drift, and unsupported claims.
7. Explain whether schema, migration, evidence, authority, or security semantics changed.
8. Open a draft pull request linked to one bounded issue.

## Repository commands

```bash
python -m pip install -e .[dev]
make quality
make test
make verify
make package
```

## Prohibited shortcuts

- Do not ask an agent to “make the repository production ready” or “improve everything.”
- Do not add authentication directly to the local `ThreadingHTTPServer` and call it an institutional deployment.
- Do not edit normative JSON resources as an incidental refactor.
- Do not commit generated wheels, source distributions, bundles, SBOMs, coverage output, caches, or release-verification output.
- Do not expose protected workspaces to background agents or third-party services.
- Do not describe local review-role records as authentication, legal delegation, institutional authority, or identity proof.
- Do not apply a model suggestion or review disposition by editing historical records in place.
