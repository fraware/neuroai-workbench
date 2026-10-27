# Contributing to NeuroAI Workbench

Contributions to NeuroAI's local-first assessment tools and separately authorized Observatory acquisition tools are welcome. Keep changes focused, testable, reproducible, and consistent with the project's evidence and security boundaries.

## Development

Requires Python 3.11 or later. From a checkout of the repository:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
make quality
make test
```

On Windows, activate the virtual environment using `.venv\Scripts\Activate.ps1`.

See the [architecture overview](docs/architecture/overview.md), [CLI reference](docs/reference/cli.md) and [contributor guidance](docs/operations/extending-observatory.md) for supported extension points.

## Proposing a change

Open an issue or refer to an existing issue describing the user-visible problem. Keep pull requests small enough for independent review. Include a description of the intended behaviour, affected interfaces, relevant tests and any compatibility or migration implications.

- Add regression tests for behaviour changes and avoid altering normative assessment identifiers incidentally.
- Document new public interfaces and commands alongside the implementation.
- Preserve provenance, source identity, and the distinction between evidence observations and human judgments.
- Update security assumptions when the trust boundary changes.
- Avoid new outbound network calls, telemetry, model-provider dependencies, or third-party assets in the offline interface.
- Keep examples synthetic or demonstrably cleared for redistribution.

Passing CI validates software checks, not scientific validity, clinical effectiveness, conformity, data-licensing rights, or permission to publish.

## Handling sensitive material

Never commit identifiable participant or neural data, credentials, tokens, private regulatory records, confidential review packets, licensed source captures, or unreleased evidence. Use privately authorized evidence custody and public synthetic fixtures for tests.

Report security vulnerabilities privately following [SECURITY.md](SECURITY.md). See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community expectations.

## License

Contributions are submitted under the repository's [Apache-2.0 license](LICENSE) unless expressly agreed otherwise.
