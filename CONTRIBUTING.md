# Contributing

## Development setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .[dev]
pytest
```

## Pull-request requirements

- State the exact problem and affected controlled objects.
- Add tests for every behavior change.
- Preserve all 78 requirement IDs unless the proposal is explicitly a major-version instrument change.
- Provide migration and regression fixtures for schema changes.
- Update the threat model when the attack surface changes.
- Do not add remote analytics, telemetry or third-party assets to the offline interface.
- Do not describe validation as certification or conformance.

## Commit style

Use imperative, scoped commits such as `validation: reject dangling denominator links`.

## Sensitive material

Never commit private neural data, participant records, confidential regulatory files, security findings or credentials. Use synthetic fixtures and controlled metadata.
