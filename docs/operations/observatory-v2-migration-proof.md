# Observatory v2 predecessor migration proof

Status: **noncanonical migration engineering**. This procedure does not authorize an Observatory v2 successor.

## Purpose

`observatory_v2_migration_proof.py` answers a narrower question than semantic migration:

> Has every predecessor JSON field occurrence been content-addressed and assigned an explicit migration disposition, without silently deleting or manufacturing predecessor state?

Field preservation and native-materialization readiness are orthogonal. A field can have a reviewed native destination while the complete native object remains blocked by a missing required target field or unresolved identity.

## Frozen input roles

The proof binds the immutable public-governing records:

- `V14` — `canonical_observatory_release_v1.4.json`
- `V16` — `canonical_live_refresh_release_v1.6.json`
- `DELTA16` — `adjudicated_delta_v1.6.json`
- `V17` — `canonical_successor_snapshot_v1.7.json`
- `MONITOR15` — `source_monitor_registry_v1.5.json`

Published S2 input SHA-256 values are:

```text
V14       00985fa168b26c4e02df485895d728ee30191aea436b4e3956c60657e2ffc3be
V16       937b2fcd807392e64f946f88a89756cc91890cc6db9f98e519035725e46c7035
DELTA16   49ef4944e4dd7e5d4b3534926e41220a1493ef12d68965a7b6caa4431524b0c5
V17       9cc36aacb4c791c9830990b58e144f223925f3ad492016abaea44727b48a0b70
MONITOR15 1d1f9774a3ad559792fa2bc7e459a4a65c6574ec14fa0b1501240bbb18dcc315
```

The v1.4 source register is already represented by the bound v1.4 `sources` array. The PRIMA v1.7 successor delta is embedded in the bound v1.7 successor and must not be double-counted as new logical state.

## Field dispositions

Every predecessor field occurrence receives one of:

- `MAPPED_NATIVE_V2` — reviewed native object class and target field;
- `PRESERVED_LEGACY_FIELD` — exact predecessor semantics retained until a governed native mapping exists;
- `PRESERVED_UNRESOLVED_PREDECESSOR_STATE` — explicit absence/unresolved predecessor state preserved without synthesis;
- `OUT_OF_SCOPE_GENERATED_PRODUCT`;
- `BLOCKED_REQUIRES_GOVERNED_SCHEMA_CHANGE`.

A family-level native class never makes all predecessor fields native automatically. `organization_type` is a controlling example: values such as `COMPANY`, `REGULATOR`, or `RESEARCH_INSTITUTION` are predecessor descriptive state, not the v2 Entity ontology class. Native organization identities use migration-generated `entity_type=ORGANIZATION`; predecessor subtype remains preserved for later bounded assertion mapping.

Likewise, a v1.6 source check has reviewed correspondences for source identity, retrieval time, and outcome but lacks the transport details required to become an ordinary native `Observation`.

## Current corrected field-preservation accounting

The previous 2,340-native-field result is superseded by the ontology correction above. The frozen corpus now accounts as:

```text
physical predecessor record occurrences: 842
leaf field occurrences:                 11,664
reviewed native-field occurrences:       2,117
preserved legacy field occurrences:      9,399
preserved unresolved occurrences:          148
unmapped required predecessor fields:         0
invented values:                             0
claim-boundary losses:                       0
source-reference losses:                     0
history-lineage losses:                      0
temporal-precision losses:                   0
```

These figures are deterministic consequences of the reviewed field rules and frozen corpus. The prior proof digest `1247c7fc...` is **superseded** because the mapping rules changed. A new proof digest must not be reported until the exact updated script executes against the frozen files.

## Current native/preserved migration state

The composed noncanonical candidate currently establishes the following bounded slices:

```text
native organization Entities                    153
native Sources                                  236
native v1.4 capital/ownership Events              5
native v1.6 change Candidates                     9
native graph/workflow objects total             403
preserved organization records                   70
transport-unresolved predecessor source checks   12
native Observations                                0
```

### Organization identities

Only 153 current identity-safe organization records become Entities. Their exact `ORG-*` IDs, canonical labels, and aliases are preserved. `entity_type=ORGANIZATION`, `status=ACTIVE`, empty identifiers, and empty lineage are explicit migration metadata. Sixty-three legacy endpoints, six provenance-only nodes, and one historical/current-identity-unresolved record remain exact predecessor state.

### Sources

All 224 v1.4 Sources plus 12 v1.6 new Sources materialize as 236 unique native Sources. `retrieved` is never promoted to publication time. Explicit v1.6 publication dates retain DATE precision; null publication dates remain absent. Access/redistribution state is explicitly migration-unknown, and each native Source is bound to the complete predecessor record digest.

### Predecessor source-check evidence

All 12 v1.6 source checks bind one-to-one to materialized Sources and preserve exact TIMESTAMP knowledge time and predecessor outcome/digests. They remain migration sidecars with:

```text
migration_state = PREDECESSOR_OBSERVATION_TRANSPORT_UNRESOLVED
native_observation_created = false
unresolved_native_observation_fields = [retrieval_method, requested_locator]
```

Any attempt to fill those transport fields by guess is rejected.

### v1.4 capital/ownership events

All five records are native-ready under exact identity rules. Subjects resolve by exact unique canonical label to materialized Entities; source IDs resolve to materialized Sources; counterparties remain `UNRESOLVED_LITERAL` when no controlled entity ID exists. Time is preserved exactly: three DATE records, one YEAR record, and one null date with no `occurred_at` field. `MIGRATED_PREDECESSOR_STATE` is explicit migration verification metadata, not a claim that predecessor verification occurred. Amount/currency/ownership-effect fields without native Event slots remain exact trace state.

### v1.6 change candidates

All nine stable candidate IDs materialize as native `Candidate` objects. `candidate_class` and adjudication status are exact predecessor values; the complete predecessor record is retained as `payload`; source IDs are checked against the 236-Source set. `OFFLINE_REPLAY` describes the migration execution path only and does not re-adjudicate the candidate or resolve its free-text subject into a graph entity.

## Deterministic packaging and identity binding

The migration packages separately bind:

```text
workbench_compatibility_version
producer_workbench_commit
runtime_execution_pin
observatory_graph_schema_version
s2_predecessor_commit
input SHA-256 values
```

Package-line equality is not execution evidence. Manifest equality is not publication authority. All package surfaces remain `NONCANONICAL_CANDIDATE`, `release_authorized=false`, and `native_v2_materialization_complete=false`.

## Relationship and reopening blockers

The v1.4 trial-site, participant-authority, and supplier-dependency families encode endpoints as system/study/site/participant/provider literals. The native Relationship contract requires resolved controlled entities on both sides. Migration therefore does not invent endpoint entities from display strings.

The v1.6/v1.7 reopening records likewise contain free-text target objects and basis identifiers that are not yet typed as native assertion/event references, and some successor records lack a governed decision timestamp. They remain blocked pending exact target identity, trigger typing, and temporal representation.

Model records remain preserved until model-family/checkpoint identity semantics are explicit; a model-family record must not be silently promoted to a checkpoint or validated model entity.

## Validation state

The frozen predecessor corpus has been analyzed directly for the counts and identity/time constraints above. The current execution environment cannot clone GitHub because outbound DNS is unavailable. Hosted GitHub Actions also continue to fail before executing steps. Therefore no claim is made that the current PR head has passed pytest, Ruff, mypy, CodeQL, dependency review, or package checks. Those remain mandatory before merge.

## Gate A remaining work

Gate A remains open. The remaining families must each receive either an exact native representation or an explicit governed migration state: organization-resolution/regional history; models/datasets; three relationship families; v1.6 delta regulatory/governance/dependency state; reopening and no-change state; v1.7/PRIMA successor semantics; and release-level methodology, quality, provenance, and withheld-claim state.

The final candidate must then pass candidate-wide typed referential and mixed-precision temporal integrity, materialized-output zero-loss reconciliation, representative human domain review, and separately executed engineering/security gates. Canonical publication remains a distinct release-attestation/publication decision.
