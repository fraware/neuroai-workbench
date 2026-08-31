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

A mechanical PASS therefore means only that this bounded core is internally reconciled. It is not Gate A completion.

## v1.4 organization identity partition

The 223 predecessor `organizations` entries are not homogeneous organization identities. Exact-state classification over the frozen public governing corpus yields:

```text
MATERIALIZE_ACTIVE_ENTITY                       153
LEGACY_IDENTITY_UNRESOLVED                       63
PROVENANCE_ONLY_NODE                              6
HISTORICAL_CURRENT_IDENTITY_UNRESOLVED             1
TOTAL                                             223
```

### 153 identity-safe current entities

A record may become a native `Entity` only when:

- its exact controlled `organization_id` is present;
- `verification_state` is one of `CURRENT_VERIFIED`, `CURRENT_PARTIAL`, `CURRENT_VERIFIED_RESCOPED`, or `CURRENT_VERIFIED_CORRECTED`;
- `current_status` is `ACTIVE_OR_CURRENTLY_REPRESENTED` or `CURRENT`;
- canonical name, organization type, and aliases are structurally valid.

The exact predecessor `ORG-*` id becomes the v2 `entity_id`. The predecessor organization type becomes `entity_type`; canonical name and aliases are preserved. Migration-generated `status=ACTIVE` is bounded strictly to the already-governed current-identity classification. All other predecessor fields remain in the exact content-addressed trace and are not silently promoted into native Entity semantics.

### 63 unresolved legacy endpoints

`LEGACY_ONLY` + `LEGACY_STUB` records are relationship endpoints whose current identity still requires resolution. They do not become active v2 Entities merely because the predecessor retained an `ORG-*` row.

### Six provenance-only nodes

Records with `verification_state=NON_ORGANIZATION_PROVENANCE_NODE` and `current_status=RECLASSIFIED` remain provenance nodes. They are expressly prohibited from re-entering the canonical organization/entity denominator through migration.

### One historical/current-identity-unresolved record

The `HISTORICAL_ARCHIVED` record is preserved exactly because current organizational existence was not established. Migration does not convert it to `ACTIVE`, `SUPERSEDED`, or `WITHDRAWN` by interpretation.

Any new or internally inconsistent predecessor state fails closed instead of falling through to one of these classes.

## Source migration

The frozen corpus contains:

```text
v1.4 sources       224
v1.6 new sources    12
native Sources      236
```

All 236 source IDs are unique across the two predecessor sets and contain the explicit predecessor fields needed for native Source identity.

The mapping is intentionally narrow:

```text
source_id      -> Source.source_id
title          -> Source.title
publisher      -> Source.publisher
url            -> Source.canonical_url_or_reference
source_class   -> Source.source_class
v1.6 published -> Source.publication_or_record_date (only when explicit)
```

`retrieved` is knowledge-time evidence and is never repurposed as publication time. The ten explicit v1.6 `published` values remain DATE precision; two null publication values remain absent.

Because predecessor data did not adjudicate redistribution/access rights, the migration uses explicit migration metadata:

```text
access_class = UNKNOWN
redistribution_state = UNKNOWN_NOT_ADJUDICATED
```

These are not inferred predecessor facts. Every Source retains the exact full predecessor record in a digest-bound trace sidecar.

## Transport-unresolved predecessor observations

The 12 v1.6 source checks have the exact predecessor field set:

```text
check_id
source_id
retrieved
retrieval_outcome
baseline_match
page_content_hash
metadata_digest
```

All 12 bind one-to-one to one of the 12 v1.6 new Source IDs and carry valid metadata SHA-256 digests and explicit timestamp knowledge time.

However, they do **not** govern the exact `retrieval_method` or `requested_locator` required by the ordinary v2 `Observation` schema. The migration therefore records:

```text
migration_state = PREDECESSOR_OBSERVATION_TRANSPORT_UNRESOLVED
native_observation_created = false
unresolved_native_observation_fields = [retrieval_method, requested_locator]
```

The migration must reject any attempt to fill those two fields by guessing `HTTP_GET`, copying a source URL, using a migration-time request, or reconstructing transport behavior after the fact.

## Current composed core

Controlled analysis of the frozen governing corpus yields:

```text
native Entities                              153
native Sources                               236
native core graph objects                    389
preserved organization records                70
predecessor observation evidence records      12
native Observations                             0
```

The native core is currently limited to `Entity` and `Source`. The source-check evidence is a migration sidecar, not a graph `Observation`.

## Deterministic package

`write_predecessor_migration_core_package` emits:

```text
entities.jsonl
entity-predecessor-traces.jsonl
preserved-organizations.jsonl
sources.jsonl
source-predecessor-traces.jsonl
predecessor-observation-evidence.jsonl
descriptor.json
manifest.json
```

The descriptor binds separately:

- Workbench package compatibility version;
- exact producer Workbench commit;
- exact runtime execution pin;
- Observatory graph schema version;
- exact S2 predecessor commit;
- exact v1.4 and v1.6 input SHA-256 values.

Package-version equality is not execution evidence. Manifest equality is not release authorization.

## Verification invariants

The core verifier fails closed if:

- an organization input record is missing from the native/preserved partition or appears twice;
- a legacy/provenance/historical organization is bound to a native Entity;
- a materializable Entity changes the exact predecessor `organization_id`;
- a Source trace is altered or rebound;
- a source check references a non-materialized Source;
- a source check gains an invented retrieval method or requested locator;
- any child surface or the composed core claims publication authority;
- the candidate claims complete native v2 materialization;
- declared counts do not match the actual composed payload;
- a native Entity or Source is schema-invalid.

## Remaining Gate A work

The migration core deliberately leaves these families unresolved:

- organization-resolution and regional-expansion history;
- capital, regulatory, governance, and ownership events;
- model records and model/dataset registry state;
- trial-site, participant-authority, and supplier-dependency relationships;
- change candidates;
- reopening decisions and no-change confirmations;
- v1.7 successor/PRIMA transition state;
- other release-level methodology, quality, provenance, and withheld-claim state.

Each family must be mapped using exact controlled identities and predecessor-native semantics. A name match alone cannot establish a graph subject/object. Required native fields absent from the predecessor cannot be filled with plausible defaults.

Only after every predecessor family is either natively materialized or represented by a governed migration state, candidate-wide typed referential/temporal integrity passes, field-loss counters remain zero, and representative human domain review is complete can Gate A be considered ready for a separate release-attestation decision.
