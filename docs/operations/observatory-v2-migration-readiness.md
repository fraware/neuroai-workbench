# Observatory v2 predecessor family readiness ledger

Status: **representationally complete noncanonical migration evidence; exact mechanical Gate-A execution pending**. This ledger distinguishes native graph readiness from governed predecessor preservation.

The controlling checkpoint is `docs/operations/observatory-v2-gate-a-checkpoint.md`.

## Readiness states

- `NATIVE_COMPLETE` — complete predecessor family materialized as native v2 objects with exact trace verification.
- `PARTIAL_NATIVE_WITH_EXPLICIT_PRESERVATION` — identity-safe records are native and all excluded records have an explicit governed migration class.
- `GOVERNED_PREDECESSOR_STATE` — family is losslessly retained as content-addressed migration state because native conversion would invent identity, collapse semantics, or weaken claim boundaries.
- `PRESERVED_REQUIRED_NATIVE_FIELDS_ABSENT` — predecessor evidence is exact, but ordinary native schema requires facts the predecessor never governed.
- `PRESERVED_RELEASE_LEVEL_STATE` — release/methodology/quality/provenance semantics remain release-level state rather than graph claims.
- `DUPLICATE_CONTAINER_PRESERVED` — governing container duplicates another bound predecessor payload for lineage and is verified but not double-materialized.

A family does **not** need to become `NATIVE_COMPLETE` to satisfy the first-v2 lossless-representation milestone. It must have either a native destination or an explicit governed preservation destination with deterministic predecessor recovery.

## Current frozen-corpus readiness

| Role/family | Records | State | Current representation |
| --- | ---: | --- | --- |
| V14 `organizations` | 223 | `PARTIAL_NATIVE_WITH_EXPLICIT_PRESERVATION` | 153 exact current organization identities become `ORGANIZATION` Entities; 63 legacy endpoints, 6 provenance nodes, and 1 historical/current-identity-unresolved record remain exact predecessor state. |
| V14 `sources` | 224 | `NATIVE_COMPLETE` | All native Sources with exact trace sidecars. |
| V16 `new_sources` | 12 | `NATIVE_COMPLETE` | All native Sources; publication precision preserved. |
| V16 `source_checks` | 12 | `PRESERVED_REQUIRED_NATIVE_FIELDS_ABSENT` | Transport-unresolved observation evidence; no invented `retrieval_method` or `requested_locator`. |
| V14 `capital_and_ownership_events` | 5 | `NATIVE_COMPLETE` | Native Events with exact subject/source binding, unresolved-literal counterparties, and DATE/YEAR/null temporal preservation. |
| V16 `change_candidates` | 9 | `NATIVE_COMPLETE` | Native Candidates retaining exact predecessor payload and source references. |
| V14 `organization_resolution` | 26 | `GOVERNED_PREDECESSOR_STATE` | Identity-resolution history sidecar with exact organization/source binding and after-state reconciliation. |
| V14 `regional_expansion` | 13 | `GOVERNED_PREDECESSOR_STATE` | Coverage-acquisition history sidecar preserving contemporaneous verification state. |
| V14 `representative_model_records` | 13 | `GOVERNED_PREDECESSOR_STATE` | Exact payload retained; native model-family/checkpoint identity remains deliberately unresolved. |
| V14 `model_and_dataset_registry` | 5 | `GOVERNED_PREDECESSOR_STATE` | Aggregate registry semantics retained without coercion into one object class. |
| V14 `trial_site_relationships` | 7 | `GOVERNED_PREDECESSOR_STATE` | Exact relationships retained until both endpoints have controlled identities. |
| V14 `participant_authority_relationships` | 6 | `GOVERNED_PREDECESSOR_STATE` | Exact authority records retained pending identity/privacy-safe endpoint model. |
| V14 `supplier_dependency_relationships` | 9 | `GOVERNED_PREDECESSOR_STATE` | Exact dependency records retained pending controlled endpoint identities. |
| V14 `data_quality` | 6 | `PRESERVED_RELEASE_LEVEL_STATE` | Exact programme quality state; not promoted into substantive Assertions. |
| V16 `adjudicated_delta` | 1 container | `DUPLICATE_CONTAINER_PRESERVED` | Verified exact equality with standalone DELTA16. |
| V16 `reopening_decisions` | 6 | `GOVERNED_PREDECESSOR_STATE` | Exact decisions/basis/actions retained; migration performs no assessment mutation. |
| V16 `no_change_confirmations` | 2 | `GOVERNED_PREDECESSOR_STATE` | Scoped comparison evidence with `global_absence_claimed=false`. |
| V16 `withheld_claims` | 9 | `GOVERNED_PREDECESSOR_STATE` | Explicit non-claims with no negative Assertion creation. |
| DELTA16 `regulatory_and_market_events` | 2 | `GOVERNED_PREDECESSOR_STATE` | Exact payload retained pending controlled System identity. |
| DELTA16 `capital_and_ownership_events` | 2 | `GOVERNED_PREDECESSOR_STATE` | Exact payload retained; no inferred native evidence-state semantics. |
| DELTA16 `model_records` | 2 | `GOVERNED_PREDECESSOR_STATE` | Exact roadmap/preprint state retained pending model identity-level resolution. |
| DELTA16 `supplier_dependency_relationships` | 1 | `GOVERNED_PREDECESSOR_STATE` | Exact payload retained pending endpoint identity resolution. |
| DELTA16 `governance_and_leadership_events` | 2 | `GOVERNED_PREDECESSOR_STATE` | Exact payload retained pending governed event/evidence mapping. |
| V17 `delta` | 1 container | `DUPLICATE_CONTAINER_PRESERVED` | Verified exact equality with standalone DELTA16. |
| V17 `reopening_decisions` | 6 | `GOVERNED_PREDECESSOR_STATE` | Exact successor reopening set with explicit ROP-16-001 → ROP-17-001 lineage and five unchanged decisions. |
| V17 `assessment_successor_delta` | 1 container | `DUPLICATE_CONTAINER_PRESERVED` | Verified exact equality with standalone PRIMA17. |
| V17 metadata/count/provenance/predecessor fields | release-level | `PRESERVED_RELEASE_LEVEL_STATE` | Exact successor/release lineage state. |
| PRIMA17 successor package | 1 package | `GOVERNED_PREDECESSOR_STATE` | Exact assessment-successor payload, reopening transition, bounded system record, and prohibited inferences retained. |
| SOURCE_REGISTER14 | 224 | `DUPLICATE_CONTAINER_PRESERVED` | Verified exact equality with V14 `sources`; no duplicate Source materialization. |
| MONITOR15 | 224 | `GOVERNED_PREDECESSOR_STATE` | One-to-one operational monitor registry over V14 Source identities with baseline field reconciliation. |

## Current native checkpoint

```text
native Entities                 153
native Sources                  236
native Events                     5
native Candidates                 9
native Observations               0
native Relationships              0
native Assertions                 0
native ReopeningDecisions         0
------------------------------------
native objects total            403
```

Native count is not the completeness denominator. Separate governed state includes:

```text
preserved organization records                  70
transport-unresolved source checks              12
V14 identity / regional history                 39
V16 adjudication records                        17
residual V14 + DELTA16 records                  55
V17 + PRIMA successor packages                   2
V14 Source Register records                    224
V15 monitor-registry records                   224
release-level predecessor bundles                2
```

The Source Register duplicates the V14 Source array and is therefore a lineage input, not 224 additional logical Source records.

## Representation gate

The frozen predecessor scope currently satisfies:

```text
representational_scope_complete = true
remaining_unresolved_families = []
native_v2_materialization_complete = false
gate_a_complete = false
release_authorized = false
```

`gate_a_complete` remains false in this intermediate checkpoint because the exact operator-bound field proof, candidate-wide typed/temporal validation, and identity-bound deterministic package have not yet all been executed from the selected Workbench runtime. A successful exact operator run may set the mechanical Gate-A decision to complete while keeping `release_authorized=false`.

This means every in-scope predecessor family has a governed destination. It does **not** mean every semantic has a native graph object, that substantive truth has been established, or that a public successor is authorized.

## Remaining Gate-A controls

The remaining engineering controls are orthogonal to family accounting:

1. execute the corrected field-level proof over the exact frozen bytes and bind its deterministic digest;
2. execute candidate-wide class-qualified referential and precision-safe temporal validation;
3. generate and independently verify the exact identity-bound full Gate-A package using the selected producer commit, runtime pin, graph schema generation, and S2 predecessor commit.

Representative human domain review is not a mandatory Gate-A closure condition at this stage. The deterministic review-packet machinery may remain available for later assurance work, but the controlling Gate-A operator does not execute it and does not depend on it.

Native graph expansion for models, systems, sites, participant bodies, dependencies, regulatory events, and similar domains, together with production source-universe evaluation, proceeds after the mechanical migration gate without rewriting predecessor history.

## Authority rule

No readiness state, field count, digest, schema pass, migration package, or mechanical Gate-A decision authorizes publication. Canonical release remains a separate S2 authorization/publication process.
