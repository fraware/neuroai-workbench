
# AI-agent development protocol

AI coding agents are treated as untrusted implementation assistants operating under repository controls.

Each task must have one issue, one branch, one bounded objective, declared invariants, test expectations, and a draft pull request. Agents must read `AGENTS.md` and applicable `.cursor/rules/` files before editing.

Background agents may access the network and execute commands. Use them only with the public source tree and synthetic or explicitly public fixtures. Do not expose private evidence workspaces, credentials, participant records, unreleased security findings, or confidential documents.

External model integration is outside the default workbench. Any future language-model capability requires a separate ADR covering data flow, consent, retention, prompt injection, model-provider terms, provenance, reproducibility, and a fully offline fallback.

## Assessment-facing language-model assistance

Engineering-agent use and assessment-facing model assistance are separate trust domains. Product features that use language models must follow ADR 0005. The first supported pattern is bounded prompt-package export and candidate-response import with field-level human disposition, provenance, and an offline fallback. Direct external model calls remain disabled in the default workbench.

## Agent evaluation harness

Repository-native behavioral checks live in `scripts/agent_eval_harness.py` and run in CI quality:

```bash
python scripts/agent_eval_harness.py
python scripts/agent_eval_harness.py --json
```

Cases cover version consistency, NOT ASSESSED preservation, event-chain tampering, evidence replacement, loopback network binding, migration preservation checks, generated-artifact hygiene, report claim-boundary language, and an explicit prohibited shortcut that would convert missing/unresolved evidence into FAIL.

Harness pass/fail is engineering evidence only. It does not establish scientific truth, regulatory authorization, security acceptance, or release authority. Pull requests must complete the AI provenance field in `.github/PULL_REQUEST_TEMPLATE.md` when an agent materially affected the change.
