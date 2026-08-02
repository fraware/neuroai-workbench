
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
- Observatory storage boundaries, ADR-0009 five-store model, archive inventory schema/JSONL, unresolved-ambiguity register, and retention/access notes for phase-A migration (no byte moves).
- Public data repository bootstrap scaffold (`templates/neuroai-observatory-data/`), deterministic manifest scripts, synthetic release descriptor, governance templates, and operator bootstrap documentation for `fraware/neuroai-observatory-data` (S2; no protected bytes).
- Versioned governing-input migration adapters, lineage digests, archive inventory integration, and deterministic `MIGRATION_VERIFICATION.json` generation for public fixtures (#44 phase C).
- Collector threat model, deployment-boundary ADR, and versioned collection/quarantine JSON schemas with adversarial contract tests. Retrieval contracts record provenance only; they do not establish authenticity or substantive truth.
- Hardened HTTP collector core (`neuroai_workbench.collector`) with DNS and redirect SSRF controls, DNS rebinding detection, timeouts, size and decompression-ratio limits, per-host rate limiting, conditional GET handling for unchanged captures, and quarantine-only writes validated against PR-05 schemas.
- Entity registry schemas, exact-ID resolution, append-only alias and identifier registration, synthetic fixtures, and adversarial refusal of fuzzy merge, overwrite, and path traversal under `neuroai_workbench.entities`.
- Offline extraction contract, disclosure policy, preregistered benchmark stubs, citation-required field validation, and protected disclosure refusal for bounded model-assisted observatory source extraction.

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
- Entity registry resolution is exact-ID only; it does not merge entities on name similarity or establish substantive correspondence without human disposition in follow-on workflows.
- Extraction contract validation establishes schema and disclosure controls only; it does not execute providers, score benchmarks, or mutate canonical observatory state.

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
