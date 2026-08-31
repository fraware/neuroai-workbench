
# Changelog

All notable changes are recorded here. Release integrity does not establish substantive evidence validity, institutional adoption, or system conformance.

## Unreleased â€” 0.3.0.dev0

### Added

- Precision-safe `TimeValue` types, observatory-graph object schemas with deterministic digests, missing `ENTITY_REGISTRY.schema.json`, source-universe programme contracts (`SU-TRIAL` executable reference plus offline-executable `SU-PUBS`/`SU-REG`/`SU-GRANTS`/`SU-MODEL` projections), DNS-pinned HTTP transport, authorization-packet collection service, immutable quarantine successors, and a candidate release compiler that never sets `release_authorized=true`.
- Hosted-CI empty-steps classifier and compatibility-identity document (package vs runtime pin vs S2 WORKBENCH_VERSION vs producer commit vs schema).
- Entity identity-relation dispositions (including directed `related_entity_id` for succession/acquisition), typed delta vocabulary expansion (ADR 0017), temporal graph compiler with adversarial integrity checks, and non-authoritative derived loaders.
- Monitor onboarding lifecycle, typed change/no-change classification, reopening service facade with reproducible recommendation/basis ids (no assessment mutation), and public read-only `/v1` API with why/provenance/timeline/diff routes over release artifacts (ADR 0018).
- Assessment-validation cohort manifests, reviewer isolation, and deidentified disagreement export; institutional OIDC/SAML/RBAC/audit/S3 profile adapters with fail-closed LOCAL vs INSTITUTIONAL separation (not ThreadingHTTPServer auth); ops/DR/security runbook hooks; contributor extension guide and offline reference flow script; and a `v1.0` readiness-gate document that authorizes neither a tag nor institutional readiness.
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
- Append-only observatory monitoring review queue API over monitoring projections, with local named profiles, exclusive leases, immutable opinions, and integrity verification.
- Accessible local monitoring review UI (`/review.html`) with rebuildable ops-health counts, sandboxed capture diffs, adjudication form scaffolding, and fixture-driven XSS tests.
- Append-only observatory monitoring review queue: rebuildable projections over candidates and adjudications, local named reviewer profiles, exclusive leases, and immutable multi-opinion records that never mutate canonical monitoring data.
- Entity registry schemas, exact-ID resolution, append-only alias and identifier registration, synthetic fixtures, and adversarial refusal of fuzzy merge, overwrite, and path traversal under `neuroai_workbench.entities`.
- Offline extraction contract, disclosure policy, preregistered benchmark stubs, citation-required field validation, and protected disclosure refusal for bounded model-assisted observatory source extraction.
- Collector source-type adapters (HTML, JSON API, XML/RSS/Atom, clinical/regulatory registry stub, controlled authenticated download stub), plan-driven scheduler consuming `neuroai-monitor plan` output, quarantine approval gate before monitoring handoff, credential-leak refusal, kill switches, and architecture tests forbidding direct monitoring snapshot or adjudication calls from the collector package.
- Layered entity resolver proposals (`NEW_ENTITY`, `EXISTING_ENTITY`, `AMBIGUOUS`, `DUPLICATE_CANDIDATE`), exact-ID auto-confirm only, human disposition records, blinded benchmark stub, and adversarial refusal of automatic fuzzy merge under `neuroai_workbench.entities.resolver`.
- Default-off extraction provider adapters, offline benchmark comparison across at least two explicitly enabled test-only configurations, immutable human disposition records, and adversarial refusal of disabled providers, network endpoints, and aggregate-score selection for extraction evaluation.
- Shadow refresh evaluation scaffolding: synthetic 25-source cohort fixture, freeze manifest schema, go/no-go metrics schema, computation stubs, and non-canonical artifact marking (`SHADOW_EVALUATION_NOT_CANONICAL`). Live refresh over real sources remains blocked pending human approval and dependent workstreams.

### Changed

- Package identity on `main` is unreleased `0.3.0.dev0`; published stabilization remains `v0.2.1`.
- Container and compose defaults bind loopback without `NEUROAI_ALLOW_NETWORK`; network exposure requires `compose.network.yaml`.
- Evidence index verification fails closed on malformed `objects` (`INDEX_SCHEMA_INVALID` and related codes).
- Assistance dispose/verify detect assessment drift; request IDs use UUID4 with collision refusal; final dispositions exclude `PENDING_REVIEW`; model output is secret-scanned before persist.
- Observatory identifier validation reports missing/non-string IDs per row with indexed paths.
- CI adds per-module coverage floors, SHA-pinned Actions, `pip-audit`, and hashed install constraints.
- Issue #10 independent-review track completeness is optional recommended follow-up; it no longer blocks successor `AUTHORIZED` or `PUBLISHED`. Summary field `blocking_tracks` renamed to `incomplete_tracks` with explicit `release_gate_blocked: false`. Named release-authority and technical release gates remain.
- Documentation under `docs/` consolidated into fewer durable guides (agent protocol, observatory automation, public-data release, entities, extraction evaluation) with redirect stubs for moved paths; `docs/README.md` is the documentation index.

### Boundaries

- No direct external model API call is enabled.
- Model output cannot mutate an assessment or exercise decision authority.
- The 78-requirement v4.2 kernel and historical pilot findings remain unchanged.
- Monitoring operations are alpha, offline-first, and non-authoritative for substantive NeuroAI findings, regulatory authorization, clinical value, or conformance.
- Entity registry resolution is exact-ID only; it does not merge entities on name similarity or establish substantive correspondence without human disposition in follow-on workflows.
- Extraction contract validation establishes schema and disclosure controls only; it does not execute providers, score benchmarks, or mutate canonical observatory state.
- Layered resolver proposals never mutate the canonical registry automatically; non-exact matches require human disposition before any follow-on registration workflow.
- Extraction contract validation establishes schema and disclosure controls only; it does not execute external providers, score live benchmarks, or mutate canonical observatory state.
- Extraction evaluation scores synthetic benchmark stubs with test-only offline providers only; scores do not establish provider superiority or release authority.

## 0.2.1 â€” stabilization candidate

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

## 0.1.0 â€” 2026-07-28

- Added the offline-first workspace, v4.2 validation, evidence registry, event history, snapshots, bundles, migration, comparison, browser UI, CLI, public reference cases, governance documents, CI, and release controls.
