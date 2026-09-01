# Observatory v2 predecessor migration core

Status: **noncanonical migration engineering**. This gate does not authorize a v2 successor.

## Purpose

The migration core is the first composed candidate over predecessor state that can be represented without inventing semantics. It combines three independently verified slices:

1. identity-safe v1.4 organization records materialized as native v2 `Entity` objects;
2. exact v1.4 sources plus v1.6 new sources materialized as native v2 `Source` objects;
3. v1.6 source checks preserved as transport-unresolved predecessor observation evidence when the predecessor did not govern the retrieval method or requested locator required by an ordinary v2 `Observation`.

The core remains:

```text
state = NONCANONICAL_CANDIDATE
release_authorized = false
native_v2_materialization_complete = false
```

A mechanical PASS means only that this bounded core is internally reconciled. It is not Gate A completion.

## v1.4 organization identity partition

The 223 predecessor `organizations` entries are heterogeneous. Exact-state classification over the frozen public governing corpus yields:

```text
MATERIALIZE_ACTIVE_ENTITY                       153
LEGACY_IDENTITY_UNRESOLVED                       63
PROVENANCE_ONLY_NODE                              6
HISTORICAL_CURRENT_IDENTITY_UNRESOLVED             1
TOTAL                                             223
```

### 153 identity-safe current organizations

A record may become a native `Entity` only when its exact controlled `organization_id` is present, its verification state is one of `CURRENT_VERIFIED`, `CURRENT_PARTIAL`, `CURRENT_VERIFIED_RESCOPED`, or `CURRENT_VERIFIED_CORRECTED`, its current status is `ACTIVE_OR_CURRENTLY_REPRESENTED` or `CURRENT`, and its canonical name and aliases are structurally valid.

The exact predecessor `ORG-*` id becomes `Entity.entity_id`, the canonical name becomes `canonical_label`, and aliases are preserved. Native `entity_type` is deliberately the v2 ontology class `ORGANIZATION`; predecessor `organization_type` values such as `COMPANY`, `REGULATOR`, or `RESEARCH_INSTITUTION` remain exact predecessor state for later bounded assertion mapping. They are not substituted for the ontology class. `status=ACTIVE`, empty identifiers, and empty lineage are explicit migration-generated identity metadata bounded to the already-governed current-identity classification.

### 70 records that remain predecessor state

The 63 `LEGACY_ONLY` + `LEGACY_STUB` records remain unresolved relationship endpoints. The six `NON_ORGANIZATION_PROVENANCE_NODE` + `RECLASSIFIED` entries remain provenance nodes and cannot re-enter the organization/entity denominator through migration. The single `HISTORICAL_ARCHIVED` entry remains historical/current-identity-unresolved; migration does not guess `ACTIVE`, `SUPERSEDED`, or `WITHDRAWN`.

Any new or internally inconsistent predecessor state fails closed.

## Source migration

The frozen corpus contains 224 v1.4 sources plus 12 v1.6 new sources, yielding 236 unique native Sources. The narrow mapping is:

```text
source_id      -> Source.source_id
title          -> Source.title
publisher      -> Source.publisher
url            -> Source.canonical_url_or_reference
source_class   -> Source.source_class
v1.6 published -> Source.publication_or_record_date, only when explicit
```

`retrieved` is knowledge-time evidence and is never repurposed as publication time. The ten explicit v1.6 publication values remain DATE precision; two null publication values remain absent. Because predecessor data did not adjudicate access or redistribution rights, migration metadata is explicitly `access_class=UNKNOWN` and `redistribution_state=UNKNOWN_NOT_ADJUDICATED`. Every normalized Source retains the complete predecessor record in a digest-bound trace.

## Transport-unresolved predecessor observations

The 12 v1.6 source checks preserve `check_id`, `source_id`, exact retrieval timestamp, predecessor retrieval outcome, baseline comparison, page-content-hash state, and metadata digest. They bind one-to-one to materialized Sources.

The predecessor does not govern the exact `retrieval_method` or `requested_locator` required by an ordinary v2 `Observation`. Therefore:

```text
migration_state = PREDECESSOR_OBSERVATION_TRANSPORT_UNRESOLVED
native_observation_created = false
unresolved_native_observation_fields = [retrieval_method, requested_locator]
```

The migration rejects attempts to guess `HTTP_GET`, copy a source URL, use a migration-time request, or reconstruct transport behavior after the fact.

## Current core counts

```text
native Entities                              153
native Sources                               236
native core graph objects                    389
preserved organization records                70
predecessor observation evidence records      12
native Observations                             0
```

The core verifier checks complete organization partitioning, every mapped Entity identity field, Source traces, source-check→Source bindings, schema validity, count reconciliation, and noncanonical authority state. Entity verification includes exact predecessor ID, canonical label and aliases plus the migration-generated `entity_type=ORGANIZATION`, `status=ACTIVE`, empty identifiers and empty lineage.

## Deterministic package

`write_predecessor_migration_core_package` emits the Entity and Source JSONL sets, their predecessor traces, preserved organization records, transport-unresolved observation evidence, descriptor, and manifest. The descriptor independently binds Workbench package compatibility, exact producer commit, runtime execution pin, graph schema generation, S2 predecessor commit, and exact v1.4/v1.6 input hashes. Package-version equality is not execution evidence; manifest equality is not release authorization.

## Relationship and observation boundary

The v1.4 trial-site, participant-authority, and supplier-dependency relationships are not native-ready merely because their relationship IDs and evidence fields are usable. Their endpoints are predecessor system/study/site/participant/provider literals, while the native Relationship contract requires controlled resolved entities on both sides. Migration must resolve those identities separately or retain the predecessor relationship state; it cannot manufacture endpoint entities from display strings.

Likewise, field-preservation PASS and native-materialization readiness are separate properties. A predecessor field may have a plausible target field while another required native field is absent from the predecessor. The v1.6 source checks are the controlling example.

## Remaining Gate A work

The composed migration candidate now extends this core with the complete five-record v1.4 capital/ownership-event family and the nine v1.6 change candidates. Remaining work includes organization-resolution/regional history, models and datasets, the three relationship families, delta regulatory/governance/dependency state, reopening/no-change state, v1.7/PRIMA successor semantics, and release-level methodology/quality/provenance/withheld-claim state.

Each family must either receive an exact native representation or an explicit governed migration state. A name match alone cannot establish graph identity, and absent native-required fields cannot be filled with plausible defaults. Gate A can advance to a separate release-attestation decision only after candidate-wide referential/temporal integrity, zero-loss reconciliation, and representative human domain review are complete.
