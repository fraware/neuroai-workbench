# Data storage boundaries

## Purpose

Separate software, public canonical observatory data, protected evidence, generated artifacts, and immutable historical archives so daily operations never require navigating a mixed programme archive.

This document defines storage roles only. It does not establish scientific truth, redistribution rights, regulatory authorization, clinical value, or UNESCO endorsement.

## Five stores

| Store | Name | Contents | Write posture |
|-------|------|----------|---------------|
| S1 | Software repository (`neuroai-workbench`) | Code, schemas, normative v4.2 resources, synthetic/public fixtures, docs, release tooling | Ordinary engineering PRs |
| S2 | Public canonical data (`neuroai-observatory-data`) | Public observatory JSON/CSV, credential-free source registry, aliases, adjudicated deltas permitted for publication, assessment dependency manifests, reopening decisions, release manifests | Versioned public releases only |
| S3 | Protected evidence | Restricted captures, licensed documents, private regulatory/sponsor materials, participant-related evidence, credentials outside record content | Custodian-controlled; workbench holds metadata/digests only |
| S4 | Generated artifacts | Excel, Word, PDF, dashboards, manifests, release ZIPs | Deterministic regeneration from canonical records; never master data |
| S5 | Immutable archive | Predecessor releases, original reports, spreadsheets, packages, verification records | Read-only for daily operations |

## Relationship to workbench paths

```text
neuroai-workbench/          -> S1
neuroai-observatory-data/   -> S2 (separate repository; see ADR-0009)
protected ops workspace/    -> S3 (local or institutional; not public GitHub)
artifacts/ / exports/       -> S4
99_ARCHIVE_READ_ONLY/       -> S5 (external archive; inventory in migration/)
```

Monitoring state under a workbench workspace (`observatory/monitoring`) is operational state derived from S2 inputs and S3 captures. It is not a sixth canonical store.

## Migration posture

Phase A (this change) inventories archive and governing public fixtures without moving bytes.

Phase B bootstraps S2.

Phase C migrates governing inputs through versioned adapters without inventing missing values.

## Enforcement rules

1. Do not commit protected evidence bytes, credentials, or unnecessary binaries to S1 or S2.
2. Treat combined Excel/Word products as S4 views, not operational databases.
3. Mark S5 read-only for daily ops; cite archive inventory paths and SHA-256 when referencing history.
4. Absence of an archive object is recorded as `INACCESSIBLE` / `UNRESOLVED`, never as automatic substantive `FAIL`.
