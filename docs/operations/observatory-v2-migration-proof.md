# Observatory v2 predecessor migration proof

Status: **noncanonical migration engineering**. This procedure does not authorize an Observatory v2 successor.

## Purpose

`observatory_v2_migration_proof.py` is the first executable gate for the v1.4/v1.6/v1.7 → Observatory v2 transition. It answers a narrower question than semantic migration:

> Has every predecessor JSON field occurrence been content-addressed and assigned an explicit migration disposition, without silently deleting or manufacturing predecessor state?

The proof deliberately distinguishes field preservation from native v2 materialization. A `PASS` means the reviewed predecessor families are completely accounted at the field level. It does **not** mean every field has already been converted into a native Observatory-v2 graph object.

## Input roles

The current public-governing proof uses the immutable S2 records:

- `V14` — `canonical_observatory_release_v1.4.json`
- `V16` — `canonical_live_refresh_release_v1.6.json`
- `DELTA16` — `adjudicated_delta_v1.6.json`
- `V17` — `canonical_successor_snapshot_v1.7.json`
- `MONITOR15` — `source_monitor_registry_v1.5.json`

The v1.4 source register is represented exactly by the `sources` array in the bound v1.4 governing release and is therefore not required as a second logical migration input. The PRIMA v1.7 successor delta is embedded exactly in `canonical_successor_snapshot_v1.7.json` as `assessment_successor_delta`; a standalone duplicate may be audited separately but must not be double-counted as new logical state.

The exact S2 SHA-256 values currently published for the five proof inputs are:

```text
V14       00985fa168b26c4e02df485895d728ee30191aea436b4e3956c60657e2ffc3be
V16       937b2fcd807392e64f946f88a89756cc91890cc6db9f98e519035725e46c7035
DELTA16   49ef4944e4dd7e5d4b3534926e41220a1493ef12d68965a7b6caa4431524b0c5
V17       9cc36aacb4c791c9830990b58e144f223925f3ad492016abaea44727b48a0b70
MONITOR15 1d1f9774a3ad559792fa2bc7e459a4a65c6574ec14fa0b1501240bbb18dcc315
```

## Migration dispositions

Every predecessor field occurrence receives one of:

- `MAPPED_NATIVE_V2` — the field has a reviewed target object class **and target field**;
- `PRESERVED_LEGACY_FIELD` — predecessor semantics are retained exactly until a governed native mapping exists;
- `PRESERVED_UNRESOLVED_PREDECESSOR_STATE` — absent source linkage or knowledge time is preserved as absent and must not be synthesized;
- `OUT_OF_SCOPE_GENERATED_PRODUCT` — generated artifacts are excluded from canonical migration inputs;
- `BLOCKED_REQUIRES_GOVERNED_SCHEMA_CHANGE` — unreviewed predecessor state fails the proof closed.

Family-level membership in a native object class is not enough to mark all fields native. For example, a v1.4 source can map `source_id`, `title`, `publisher`, `url`, and `source_class` directly into the v2 `Source` schema; predecessor `retrieved`, `evidence_state`, `supports`, `claim_boundary`, and legacy-ID fields do not have equivalent slots in that schema and remain preserved explicitly. This is intentional.

Likewise, v1.6 source-check records have several fields that correspond to `Observation`, but they do not encode every required native observation field such as the exact requested locator/retrieval-method contract. The proof identifies reviewed field-level correspondences without claiming that the record is already materializable as a complete native `Observation`.

A new top-level predecessor family is a migration failure until explicitly reviewed. There is no catch-all “ignore” path.

## Current field-preservation result

A controlled execution over the exact public-governing bytes above produced:

```text
physical predecessor record occurrences: 842
leaf field occurrences:                 11,664
reviewed native-field occurrences:       2,340
preserved legacy field occurrences:      9,176
preserved unresolved occurrences:          148
unmapped required fields:                    0
invented values:                             0
claim-boundary losses:                       0
source-reference losses:                     0
history-lineage losses:                      0
temporal-precision losses:                   0
```

The deterministic proof digest for that exact field-specific run, using the public S2 filenames above, was:

```text
1247c7fcbe801db6cc18494c6f60be91cd882ebc864c621106ae9560ba2f9f79
```

These counts are **field occurrences across bound predecessor files**, not counts of unique real-world objects. Governing files intentionally repeat some state (for example v1.6 delta material inside the v1.7 successor) for predecessor/release traceability.

## Command

```bash
python scripts/observatory_v2_migration_proof.py \
  --input V14=/path/to/canonical_observatory_release_v1.4.json \
  --input V16=/path/to/canonical_live_refresh_release_v1.6.json \
  --input DELTA16=/path/to/adjudicated_delta_v1.6.json \
  --input V17=/path/to/canonical_successor_snapshot_v1.7.json \
  --input MONITOR15=/path/to/source_monitor_registry_v1.5.json \
  --output /path/to/noncanonical-migration-proof
```

Generated output:

```text
migration-proof.json
input-manifest.json
field-ledger.jsonl
record-ledger.jsonl
```

Operational outputs are not committed automatically.

## First native materialization tranche: Sources

`neuroai_workbench.observatory_migration` materializes the complete predecessor Source identity family that can currently be represented without semantic invention:

- 224 v1.4 sources;
- 12 v1.6 `new_sources`;
- 236 total source identities, with duplicate IDs refused.

The native Source object receives only predecessor fields with direct governed semantics. `published` is mapped to `publication_or_record_date` while preserving YEAR/DATE/TIMESTAMP precision. `retrieved` is explicitly **not** promoted to source publication time because it is knowledge-time evidence.

The native schema requires access/redistribution metadata that the predecessor did not establish. Migration therefore emits controlled metadata:

```text
access_class = UNKNOWN
redistribution_state = UNKNOWN_NOT_ADJUDICATED
```

Those values describe migration knowledge state, not inferred legal rights. The complete original predecessor Source record is retained in a content-addressed trace record. The trace verifier recomputes the predecessor digest and rejects payload tampering, native-ID substitution, role/family mismatch, malformed indexes, and any attempt to set migration authority true.

The deterministic Source package contains:

```text
sources.jsonl
predecessor-traces.jsonl
descriptor.json
manifest.json
```

The descriptor records the following as separate identities:

```text
workbench_compatibility_version
producer_workbench_commit
runtime_execution_pin
observatory_graph_schema_version
s2_predecessor_commit
V14 input SHA-256
V16 input SHA-256
```

These identities are never inferred from each other. In particular, package line `0.3.0.dev0` is not producer-commit evidence.

The package writer rejects malformed digests/commit identities, trace tampering, unequal Source/trace counts, and any `release_authorized=true` input.

## Why predecessor source checks remain legacy observation evidence

All 12 v1.6 source checks preserve `check_id`, `source_id`, exact retrieval time, outcome, baseline match, page-content-hash state, and metadata digest. They record `SUCCESS_VIA_WEB_RESEARCH`, but they do not establish the exact `requested_locator` or a transport-level retrieval method required by the ordinary v2 `Observation` schema.

Migration therefore does not fabricate `HTTP_GET`, a guessed URL, or equivalent transport details. These records remain content-addressed predecessor observation evidence until a governed migration representation can encode unresolved transport/locator state without weakening ordinary v2 Observation requirements.

## Fail-closed behavior

The field proof fails if:

- an input role is duplicated;
- an input file is absent;
- an input role is unknown;
- a predecessor family has no reviewed disposition;
- any field occurrence is consequently classified `BLOCKED_REQUIRES_GOVERNED_SCHEMA_CHANGE`.

Empty `source_ids`, unknown observation time, and other predecessor provenance gaps remain explicit unresolved state. They are not converted into failure, and no release date, filesystem timestamp, or migration timestamp is substituted for missing knowledge time.

## What remains before Gate A closes

Field preservation and Source materialization are only early executable parts of issue #239. The remaining migration gate must:

1. preserve every `PRESERVED_LEGACY_FIELD` payload in deterministic predecessor traceability until a governed native representation exists;
2. adopt an explicit lossless representation for predecessor observation records whose transport/locator details were never governed;
3. resolve entity subjects/objects deterministically before Event/Relationship/Assertion materialization;
4. preserve provenance nodes as provenance nodes and avoid forcing historical/legacy identities into an unsupported ACTIVE status;
5. run typed referential-integrity and mixed-precision temporal validation over the complete materialized candidate;
6. prove source-reference, claim-boundary, lineage, and temporal-precision preservation against materialized output rather than the input ledger alone;
7. bind package compatibility, producer commit, runtime execution pin, graph schema generation, and S2 predecessor identity separately across the complete candidate;
8. undergo representative human domain review before any authorization decision.

Only after those steps can the programme claim a complete lossless Observatory-v2 migration candidate. Canonical publication remains a separate release-attestation and publication decision.
