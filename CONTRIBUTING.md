
# Contributing

## Development setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .[dev]
make quality
make test
```

Read `AGENTS.md`, [AI-agent development](docs/operations/ai-agent-development.md), and the applicable `.cursor/rules/` files before changing code or controlled resources.

## Pull-request contract

- Link one bounded issue.
- State the exact problem and affected controlled objects.
- Identify whether schema, migration, evidence, authority, security, or normative semantics changed.
- Add tests for every behavior change.
- Preserve all 78 requirement identifiers unless the proposal is explicitly a major instrument change.
- Provide migration and regression fixtures for model changes.
- Update the threat model when the attack surface changes.
- Do not add remote analytics, telemetry, model calls, or third-party assets to the offline interface.
- Do not describe validation as certification or conformance.
- Do not commit generated artifacts or protected information.

## Commit and branch style

Use `agent/<bounded-objective>` for agent branches. Use imperative, scoped commits such as `workspace: centralize version metadata`.

## Sensitive material

Never commit private neural data, participant records, confidential regulatory files, protected security findings, credentials, tokens, keys, or decryption material. Use synthetic or explicitly public fixtures.
