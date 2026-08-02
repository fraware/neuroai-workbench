# ADR 0009 — Canonical data and evidence stores

## Status

Accepted for observatory operations programme phase A (storage boundaries). Implementation of the separate public data repository is phase B.

## Context

The programme historically mixed software, canonical JSON, protected captures, generated workbooks, and predecessor packages in one large archive. That layout makes daily operations unsafe: protected bytes risk public disclosure, generated views are mistaken for masters, and archive navigation substitutes for controlled lineage.

## Decision

Adopt five typed stores:

1. **Software** — `fraware/neuroai-workbench` (and successors): code, schemas, normative resources, synthetic/public fixtures, documentation.
2. **Public canonical data** — separate repository named `neuroai-observatory-data`: published machine-readable observatory records, credential-free registries, permitted disposition summaries, dependency manifests, release checksums.
3. **Protected evidence** — custodian-controlled storage for restricted captures and sensitive materials; the workbench stores metadata, digests, custody state, and controlled references only.
4. **Generated artifacts** — Excel, Word, PDF, dashboards, and release packages regenerated from canonical records; never treated as master inputs.
5. **Immutable archive** — organized predecessor packages and historical verification records; read-only for daily operations.

Public data repository governance (branch protection, CODEOWNERS, signed releases, manifests) is specified in phase B bootstrap documentation and does not grant the workbench substantive assessment authority.

## Consequences

- Migration must inventory before moving bytes.
- Missing archive objects are typed (`INACCESSIBLE`, `UNRESOLVED`, `NOT_RECORDED`) rather than invented.
- Independent verification targets S2 releases, not the full archive tree.
- Collectors write quarantine material toward S3/ops paths; monitoring records content identity without implying authenticity.

## Rejected alternatives

- Keeping a single mixed GitHub repository for all stores.
- Treating the combined Excel workbook as the operational database.
- Auto-failing assessments when public archive objects are inaccessible.
