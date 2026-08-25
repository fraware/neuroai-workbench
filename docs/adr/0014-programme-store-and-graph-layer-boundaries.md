# ADR 0014 — Programme store and graph-layer boundaries

## Status

Proposed for programme-boundary reconciliation under #209. This ADR is additive and does not rewrite predecessor ADRs, releases, or historical vNext architecture records.

## Context

The programme uses two independent architectural classifications that currently reuse the same `S*` notation:

1. ADR 0009 and the operational storage architecture use **S1–S5** for physical/authority stores: software, public canonical data, protected evidence, generated artifacts, and immutable archive.
2. The vNext observatory graph design separately used **S0–S5** for source-universe definitions, source observations, canonical graph state, protected/licensed references, derived intelligence, and human products.

Those are different dimensions. Reusing the same labels creates an avoidable ambiguity in implementation reviews, issue language, custody controls, release manifests, and cross-repository contracts.

A second inconsistency emerged during Phase 4. `neuroai-observatory-data` is the public canonical-data authority surface, while `neuroai-workbench` is the software/operational authority surface. The Phase 4 science branch accumulated executable acquisition, transport, retry-custody, provenance-verification, production-runner, storage-preflight, operational-validation, and deployment-infrastructure code in the data repository. That work is useful, but its long-term ownership does not match the programme store boundary.

The supplied complete organized programme archive also demonstrates why physical storage authority and graph processing authority must remain distinct: one immutable archive can contain predecessor software, canonical data, protected or restricted material, and generated products without becoming the live authority for any of them.

## Decision

### 1. Reserve S1–S5 for programme stores

The following store names are authoritative for new programme documentation and implementation:

| Store | Authority class | Primary location |
| --- | --- | --- |
| S1 | Software and executable operational logic | `fraware/neuroai-workbench` |
| S2 | Public canonical machine-readable data | `fraware/neuroai-observatory-data` |
| S3 | Protected/licensed/raw evidence custody | Custodian-controlled storage outside public Git |
| S4 | Generated products and reproducible views | Artifact/output storage; never master input |
| S5 | Immutable historical archive | Read-only predecessor/archive storage |

Historical records using these meanings remain valid.

### 2. Rename graph processing layers to L0–L5

For new work, the vNext graph processing/authority sequence is:

| Layer | Meaning | Authority rule |
| --- | --- | --- |
| L0 | Source-universe definition | Versioned configuration defining what is searched, how, when, and what bounded coverage can mean |
| L1 | Source observation | Provider/source-attributed observation, retrieval metadata, hashes, and access/rights state; not canonical truth |
| L2 | Canonical graph | Human/governance-accepted entities, events, assertions, and relationships |
| L3 | Protected/licensed reference | Metadata/digests/references to material whose bytes or fields remain in S3 |
| L4 | Derived intelligence | Recomputable indicators and analytical projections with explicit input release and algorithm identity |
| L5 | Human/generated products | Reports, tables, dashboards, policy products, and other views derived from controlled inputs |

Historical vNext documents that used graph-layer `S0–S5` terminology are not edited. They are interpreted through this compatibility mapping:

```text
historical graph S0 -> L0
historical graph S1 -> L1
historical graph S2 -> L2
historical graph S3 -> L3
historical graph S4 -> L4
historical graph S5 -> L5
```

This mapping changes notation only. It does not change record semantics, evidence states, rights classes, temporal meaning, or canonical authority.

### 3. Keep repository ownership aligned with store authority

`neuroai-workbench` owns reusable executable operations, including where applicable:

- acquisition/provider adapters and request execution;
- transport and network-safety logic;
- retry and interruption/recovery logic;
- provenance/custody verification;
- review and adjudication workflows;
- monitoring and reopening analysis;
- assessment tooling;
- release-generation logic;
- operational validation harnesses;
- deployment/reference infrastructure and storage preflight logic.

`neuroai-observatory-data` owns the public/declarative publication surface, including:

- canonical public entities, assertions, relationships, and events;
- source-universe definitions and bounded coverage contracts;
- publication-facing schemas and controlled vocabularies;
- frozen discovery/acquisition configuration needed to identify a public release;
- public curation/adjudication metadata permitted for redistribution;
- rights classifications and release declarations;
- release descriptors, manifests, checksums, coverage/quality reports, and limitations;
- permitted normalized candidate/canonical records.

Minimal deterministic validation required to verify the publication surface may remain in the data repository. It must not become the primary operational acquisition runtime.

### 4. Raw acquisition custody remains outside both repositories

Production provider response bytes, licensed/restricted provider fields, protected evidence, participant/private material, credentials, and other non-public custody objects remain in S3.

Git may retain permitted metadata, digests, content-addressed references, and public verification facts where the rights decision allows them.

### 5. The complete organized programme archive is S5

A supplied master/archive package is an immutable predecessor object. Its bytes are not imported into the workbench repository merely because they are available.

Registration of an S5 object establishes byte identity, package structure, and lineage references only. It does not make every contained object current, canonical, redistributable, scientifically valid, or authoritative.

### 6. Cross-repository moves require reconciliation evidence

When capability ownership moves between S1 and S2, preserve a machine-readable crosswalk containing at least:

- original repository/path;
- original blob or content digest;
- destination store;
- destination repository/path where applicable;
- destination commit/digest after migration;
- disposition (`RETAINED`, `MOVED`, `SUPERSEDED`, or `DELETED_AS_DIAGNOSTIC`);
- rationale and authority boundary.

A source PR must not be closed as superseded until every material path is reconciled.

## Consequences

- The store model and graph processing model can be referenced simultaneously without ambiguous labels.
- Phase 4 science work can be split without discarding existing implementation provenance.
- Data publication remains reviewable independently from operational acquisition software.
- Raw/protected custody cannot acquire canonical authority merely by being collected successfully.
- Historical archive material remains usable for provenance and reconciliation without becoming a daily operational workspace.
- Cross-repository integration must use immutable version/commit identities rather than moving branch tips for published operations.

## Non-goals

- No Phase 4 production acquisition is authorized by this ADR.
- No historical release or assessment is modified.
- No old ADR is retroactively rewritten.
- No archive member is declared canonical merely because its hash is registered.
- No generated spreadsheet, document, PDF, dashboard, or report becomes master data.
- No scientific relevance, system capability, safety, conformance, regulatory status, or institutional authority is inferred from retrieval, hashing, migration, or repository location.

## Follow-on

- Register the currently supplied complete organized archive as an S5 predecessor object without committing its bytes.
- Record a successor review of AMB-003 using the newly accessible combined v2.2.0 workbook/document identities; retain the historical `INACCESSIBLE` record as predecessor state.
- Build the Phase 4 path/blob split manifest under data-repository issue #51.
- Move reusable Phase 4 acquisition/verification/deployment software to S1 under independently reviewed changes.
- Retain declarative/publication contracts in S2.
- Restore exact-head executable validation and demonstrate S3 custody before any live Phase 4 provider acquisition.
