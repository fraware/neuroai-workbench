
# AI-agent development protocol

AI coding agents are treated as untrusted implementation assistants operating under repository controls.

Each task must have one issue, one branch, one bounded objective, declared invariants, test expectations, and a draft pull request. Agents must read `AGENTS.md` and applicable `.cursor/rules/` files before editing.

Background agents may access the network and execute commands. Use them only with the public source tree and synthetic or explicitly public fixtures. Do not expose private evidence workspaces, credentials, participant records, unreleased security findings, or confidential documents.

External model integration is outside the default workbench. Any future language-model capability requires a separate ADR covering data flow, consent, retention, prompt injection, model-provider terms, provenance, reproducibility, and a fully offline fallback.
