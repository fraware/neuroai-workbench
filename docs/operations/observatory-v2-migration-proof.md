# Observatory v2 predecessor migration proof

Status: **noncanonical migration engineering**. This procedure does not authorize an Observatory v2 successor.

## Purpose

`observatory_v2_migration_proof.py` is the first executable gate for the v1.4/v1.6/v1.7 → Observatory v2 transition. It answers a narrower question than semantic migration:

> Has every predecessor JSON field occurrence been content-addressed and assigned an explicit migration disposition, without silently deleting or manufacturing predecessor state?

The proof deliberately distinguishes field preservation from native v2 materialization. A `PASS` from this script means the reviewed predecessor families are completely accounted at the field level. It does **not** mean every field has already been converted into a native Observatory-v2 graph object.

## Input roles

The current public-governing proof uses the immutable S2 records:

- `V14` — `canonical_observatory_release_v1.4.json`
- `V16` — `canonical_live_refresh_release_v1.6.json`
- `DELTA16` — `adjudicated_delta_v1.6.json`
- `V17` — `canonical_successor_snapshot_v1.7.json`
- `MONITOR15` — `source_monitor_registry_v1.5.json`

The v1.4 source register is already represented exactly by the `sources` array in the bound v1.4 governing release and is therefore not required as a second logical migration input. The PRIMA v1.7 successor delta is embedded exactly in `canonical_successor_snapshot_v1.7.json` as `assessment_successor_delta`; a standalone duplicate may be audited separately, but must not be double-counted as new logical state.

The exact S2 SHA-256 values currently published for the five proof inputs are:

```text
V14      00985fa168b26c4e02df485895d728ee30191aea436b4e3956c60657e2ffc3be
V16      937b2fcd807392e64f946f88a89756cc91890cc6db9f98e519035725e46c7035
DELTA16  49ef4944e4dd7e5d4b3534926e41220a1493ef12d68965a7b6caa4431524b0c5
V17      9cc36aacb4c791c9830990b58e144f223925f3ad492016abaea44727b48a0b70
MONITOR15 1d1f9774a3ad559792fa2bc7e459a4a65c6574ec14fa0b1501240bbb18dcc315
```

## Migration dispositions

Every predecessor family is assigned one of:

- `MAPPED_NATIVE_V2` — a reviewed native target class exists (`Entity`, `Source`, `Observation`, `Event`, `Relationship`, `Candidate`, or `ReopeningDecision`);
- `PRESERVED_LEGACY_FIELD` — predecessor semantics are retained exactly until a governed native mapping is defined;
- `PRESERVED_UNRESOLVED_PREDECESSOR_STATE` — absent source linkage or knowledge time is preserved as absent and must not be synthesized;
- `OUT_OF_SCOPE_GENERATED_PRODUCT` — generated artifacts are excluded from canonical migration inputs;
- `BLOCKED_REQUIRES_GOVERNED_SCHEMA_CHANGE` — unreviewed predecessor state fails the proof closed.

A new top-level predecessor family is therefore a migration failure until explicitly reviewed. There is no catch-all “ignore” path.

## Current field-preservation result

A controlled execution over the exact public-governing bytes above produced:

```text
physical predecessor record occurrences: 842
leaf field occurrences:                 11,664
native-v2-target field occurrences:      7,801
preserved legacy field occurrences:      3,715
preserved unresolved occurrences:          148
unmapped required fields:                    0
invented values:                             0
claim-boundary losses:                       0
source-reference losses:                     0
history-lineage losses:                      0
temporal-precision losses:                   0
```

The deterministic proof digest for that exact run, using the public S2 filenames above, was:

```text
fac32055c928a9a0b8c8306f7abb6acce3134cd2d81bfa9db3a5365964df707e
```

These counts are **field occurrences across bound predecessor files**, not a claim that 842 unique real-world entities exist. Governing files intentionally repeat some state (for example v1.6 delta material inside the v1.7 successor) for predecessor/release traceability.

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

## Fail-closed behavior

The proof fails if:

- an input role is duplicated;
- an input file is absent;
- an input role is unknown;
- a predecessor family has no reviewed disposition;
- any field occurrence is consequently classified `BLOCKED_REQUIRES_GOVERNED_SCHEMA_CHANGE`.

Empty `source_ids`, unknown observation time, and other predecessor provenance gaps remain explicit unresolved state. They are not converted into failure, and no release date, filesystem timestamp, or migration timestamp is substituted for missing knowledge time.

## What remains before Gate A closes

Field preservation is only the first executable part of issue #239. The remaining migration gate must:

1. materialize every `MAPPED_NATIVE_V2` family into schema-valid v2 objects;
2. preserve every `PRESERVED_LEGACY_FIELD` payload in a deterministic predecessor-traceability structure until a native governed representation exists;
3. bind every native object to exact predecessor record/field provenance;
4. run typed referential-integrity and mixed-precision temporal validation;
5. prove source-reference, claim-boundary, lineage, and temporal-precision preservation against materialized output rather than the input ledger alone;
6. bind package compatibility, producer commit, runtime execution pin, graph schema generation, and S2 predecessor identity separately;
7. undergo representative human domain review before any authorization decision.

Only after those steps can the programme claim a complete lossless Observatory-v2 migration candidate. Canonical publication remains a separate release-attestation and publication decision.
