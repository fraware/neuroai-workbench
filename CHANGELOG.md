
# Changelog

All notable changes are recorded here. Release integrity does not establish substantive evidence validity, institutional adoption, or system conformance.

## Unreleased — 0.3.0.dev0

### Added

- Collaborative review assignments, immutable disagreements, human dispositions, and integrity verification.
- Deterministic review and evidence-gap reports.
- Protected-evidence metadata requests, custodian-response records, path and secret guards, and exchange integrity verification.

- Loss-aware programme completed-assessment adapter with a checked-in native PRIMA v4.2.1 reference case.
- Compact observatory v1.7 successor validation, import, summary, and reopening queue.
- Deterministic Markdown assessment reports.
- Provider-neutral model-assistance request, response, disposition, and integrity records.
- Structured-output validation, evidence-reference checks, secret-pattern guardrails, and tamper detection.
- Alpha offline-first observatory monitoring operations: source-registry validation, content-addressed snapshots, change candidates, immutable adjudications, non-canonical refresh packages, and `neuroai-monitor` CLI. Network collection remains outside the default workbench.
- Versioned governing-input migration adapters, lineage digests, archive inventory integration, and deterministic `MIGRATION_VERIFICATION.json` generation for public fixtures (#44 phase C).

### Changed

- Package identity on `main` is unreleased `0.3.0.dev0`; published stabilization remains `v0.2.1`.
- Container and compose defaults bind loopback without `NEUROAI_ALLOW_NETWORK`; network exposure requires `compose.network.yaml`.
- Evidence index verification fails closed on malformed `objects` (`INDEX_SCHEMA_INVALID` and related codes).
- Assistance dispose/verify detect assessment drift; request IDs use UUID4 with collision refusal; final dispositions exclude `PENDING_REVIEW`; model output is secret-scanned before persist.
- Observatory identifier validation reports missing/non-string IDs per row with indexed paths.
- CI adds per-module coverage floors, SHA-pinned Actions, `pip-audit`, and hashed install constraints.

### Boundaries

- No direct external model API call is enabled.
- Model output cannot mutate an assessment or exercise decision authority.
- The 78-requirement v4.2 kernel and historical pilot findings remain unchanged.
- Monitoring operations are alpha, offline-first, and non-authoritative for substantive NeuroAI findings, regulatory authorization, clinical value, or conformance.

## 0.2.1 — stabilization candidate

### Changed

- Centralized package and workspace version identity.
- Reorganized documentation, examples, and tests for maintainable public development.
- Removed generated build, release, cache, SBOM, and verification artifacts from source control.
- Added repository hygiene and version-consistency gates.
- Added AI-agent and Cursor operating rules that preserve assessment and evidence boundaries.
- Expanded CI into quality, test-matrix, packaging, container, release-verification, and security gates.
- Added reproducible tagged-release workflow with checksums, SBOM generation, Git bundle creation, and provenance attestation.
- Updated security support, release status, and roadmap language.

### Unchanged

- The v4.2 instrument remains at 78 requirements.
- Normative requirement meaning, conformance semantics, and historical assessment findings are unchanged.

## 0.2.0

- Added controlled offline observatory mode.
- Added observatory validation, summary, queue, and CLI coverage.

## 0.1.0 — 2026-07-28

- Added the offline-first workspace, v4.2 validation, evidence registry, event history, snapshots, bundles, migration, comparison, browser UI, CLI, public reference cases, governance documents, CI, and release controls.
