# Observatory v2 Gate-A migration checkpoint

Status: **representationally complete noncanonical migration checkpoint; Gate A remains open**.

This document records the current first-v2 migration boundary for the frozen public predecessor corpus. It deliberately separates three claims:

1. **Representational completeness** — every in-scope predecessor family has an exact native or governed-preserved destination.
2. **Native graph completeness** — every predecessor semantic has been converted into a first-class v2 graph object. This is **not** claimed.
3. **Gate-A / publication readiness** — all validation, identity-bound packaging, human review, and release-governance requirements have closed. This is **not** claimed.

## Frozen inputs

The checkpoint binds the following seven governing inputs by exact SHA-256:

```text
V14
00985fa168b26c4e02df485895d728ee30191aea436b4e3956c60657e2ffc3be
CANONICAL_EVIDENCE_DEPTH_AND_OBSERVATORY_RELEASE_v1.4.json

V16
937b2fcd807392e64f946f88a89756cc91890cc6db9f98e519035725e46c7035
CANONICAL_LIVE_REFRESH_RELEASE_v1.6.json

DELTA16
49ef4944e4dd7e5d4b3534926e41220a1493ef12d68965a7b6caa4431524b0c5
ADJUDICATED_DELTA_v1.6.json

V17
9cc36aacb4c791c9830990b58e144f223925f3ad492016abaea44727b48a0b70
CANONICAL_SUCCESSOR_SNAPSHOT_v1.7.json

PRIMA17
f2966b60c3c58bb11bfdd80324e152f6ff3faaf1f632d287e51cdfdccbcde09c
PRIMA_OBSERVATORY_SUCCESSOR_DELTA_v1.7.json

SOURCE_REGISTER14
36dce4ca9f13f8046fca31bfbeabb5c01903eb077594a37aee63749612d2a1a5
SOURCE_REGISTER_v1.4.json

MONITOR15
1d1f9774a3ad559792fa2bc7e459a4a65c6574ec14fa0b1501240bbb18dcc315
SOURCE_MONITOR_REGISTRY_v1.5.json
```

The standalone v1.4 Source Register is exactly the 224-record `sources` array embedded in V14. It is retained as a separately bound governing input, not double-materialized as another set of Source objects.

The v1.5 monitor registry contains exactly 224 unique monitor records and maps one-to-one onto the 224 v1.4 Source IDs. For every monitor record, the baseline URL, publisher, source class, evidence state, verification state, claim boundary, and last successful retrieval match its predecessor Source record.

## Native v2 materialization checkpoint

Current native objects:

```text
Entity       153
Source       236
Event          5
Candidate      9
Observation    0
Relationship   0
Assertion      0
ReopeningDecision 0
------------------
TOTAL        403
```

### 153 organization Entities

The heterogeneous v1.4 organization array partitions exactly into:

```text
MATERIALIZE_ACTIVE_ENTITY                         153
LEGACY_IDENTITY_UNRESOLVED                         63
PROVENANCE_ONLY_NODE                                6
HISTORICAL_CURRENT_IDENTITY_UNRESOLVED               1
TOTAL                                               223
```

Native organization identity uses:

```text
entity_type = ORGANIZATION
```

Predecessor organization subtype such as `COMPANY`, `ACADEMIC_INSTITUTION`, or initiative category remains predecessor descriptive state; it is not incorrectly promoted into the v2 ontology identity class.

### 236 Sources

All 224 v1.4 Sources plus all 12 v1.6 new Sources materialize. `retrieved` remains knowledge-time evidence and is never promoted to publication time. Explicit v1.6 publication dates preserve original DATE precision; null values remain absent. Access and redistribution are explicit migration-unknown metadata, never inferred legal rights.

### Five v1.4 capital/ownership Events

All five records materialize because each subject resolves by exact unique canonical organization label and every Source reference resolves. Counterparties without controlled IDs remain `UNRESOLVED_LITERAL`. Time is preserved exactly:

```text
DATE   3
YEAR   1
NULL   1
```

The null predecessor date produces no `occurred_at` value.

### Nine v1.6 change Candidates

All nine stable predecessor candidate IDs materialize. Candidate class and status preserve predecessor change class/adjudication, while the complete predecessor record remains the Candidate payload. Free-text subjects are not promoted into Entity identity.

## Governed predecessor state

The first-v2 migration requirement permits a predecessor family to remain an explicitly retained legacy/governance payload when native conversion would invent identity, collapse semantics, or weaken claim boundaries.

### Organization and coverage history — 39 records

```text
organization_resolution   26
regional_expansion        13
```

Organization-resolution history checks exact predecessor organization identity, exact source references, effective date, and `verification_after` reconciliation with the resulting v1.4 organization record.

Regional-expansion history preserves its contemporaneous verification state. It is not overwritten from the final organization row; this matters where a later correction changed the organization record after the acquisition action.

### Transport-unresolved predecessor observation evidence — 12 records

The 12 v1.6 source checks preserve exact source ID, retrieval timestamp, predecessor outcome, baseline match, page-content-hash state, and metadata digest. They do not become ordinary v2 `Observation` objects because predecessor evidence did not govern exact `retrieval_method` and `requested_locator` semantics.

### v1.6 adjudication state — 17 records

```text
no_change_confirmations    2
reopening_decisions        6
withheld_claims             9
```

No-change confirmations remain scoped comparison evidence and explicitly do not claim global absence.

Reopening decisions preserve exact decision IDs, object labels, trigger/basis IDs, and required actions. Migration records that it performs no assessment mutation.

Withheld claims remain explicit non-claims. They are not transformed into negative Assertions.

### Residual v1.4 and DELTA16 families — 55 records

```text
V14 representative_model_records                 13
V14 model_and_dataset_registry                    5
V14 trial_site_relationships                      7
V14 participant_authority_relationships           6
V14 supplier_dependency_relationships             9
V14 data_quality                                  6
DELTA16 regulatory_and_market_events              2
DELTA16 capital_and_ownership_events              2
DELTA16 model_records                             2
DELTA16 supplier_dependency_relationships         1
DELTA16 governance_and_leadership_events          2
---------------------------------------------------
TOTAL                                             55
```

Each family retains its complete payload, payload digest, record count, explicit migration blocker reason, and recursively validated Source references.

The blocker reasons preserve the actual semantic boundary, including unresolved model family/checkpoint identity, unresolved relationship endpoints, unresolved system identity, release-level quality state, and native evidence/event semantics that cannot be inferred from predecessor fields.

### Release-level state

V14 `metadata`, `methodology`, and `coverage`, plus V16 `metadata`, `methodology`, and `baseline`, are preserved as release-level migration bundles. They are not graph claims.

### v1.7 and PRIMA successor lineage

The entire v1.7 successor snapshot and standalone PRIMA successor delta remain exact successor-state payloads.

Mechanical lineage checks establish:

- V16 `adjudicated_delta` exactly equals standalone DELTA16;
- V17 embedded `delta` exactly equals standalone DELTA16;
- V17 embedded `assessment_successor_delta` exactly equals standalone PRIMA17;
- baseline hash identity reconciles across V17 baseline/provenance state;
- predecessor archive hash reconciles across V17 and PRIMA predecessor references;
- `ROP-16-001` is the predecessor reopening decision and `ROP-17-001` its successor;
- predecessor and successor decision states match the explicit transition;
- the five unrelated V16 reopening decisions carry into V17 unchanged;
- successor basis retains predecessor trigger IDs and adds the executed PRIMA assessment ID;
- successor open actions equal the successor decision required actions;
- PRIMA prohibited inferences remain explicit and preserved.

Embedded duplicate containers are lineage evidence and are never double-materialized as new graph state.

## Corrected field-preservation accounting

Current frozen-corpus field accounting after ontology correction:

```text
physical predecessor record occurrences       842
leaf field occurrences                     11,664
reviewed native class+field destinations     2,117
preserved legacy field occurrences           9,399
preserved unresolved occurrences               148
unmapped required predecessor fields             0
invented values                                  0
claim-boundary losses                            0
source-reference losses                          0
history-lineage losses                           0
temporal-precision losses                        0
```

The earlier 2,340-native-field proof is superseded because predecessor `organization_type` is not a v2 `Entity.entity_type` mapping. The old proof digest is therefore also superseded until the updated field-proof implementation is executed against the exact frozen inputs.

## Representational completeness

At this checkpoint:

```text
representational_scope_complete = true
native_v2_materialization_complete = false
gate_a_complete = false
release_authorized = false
```

There are **no unaccounted predecessor record families** in the current frozen scope. A family is either:

- native v2 state;
- explicitly unresolved predecessor state;
- governed history/adjudication/successor state;
- explicitly retained residual legacy state with a documented native blocker;
- or a verified duplicate governing container.

This satisfies the architecture's first-v2 representation objective without weakening the identity or evidence model.

## Identity-bound package

`observatory_gate_a_package` writes a deterministic hierarchical checkpoint package.

The native 403-object candidate remains a manifest-bound subpackage. Root-level state binds:

- v1.6 adjudication state;
- v1.7/PRIMA successor lineage;
- residual predecessor state;
- duplicate-container proofs;
- all seven frozen input SHA-256 identities;
- Workbench compatibility version;
- exact producer Workbench commit;
- exact runtime execution pin;
- graph schema generation;
- exact S2 predecessor commit.

No one identity substitutes for another.

## Remaining Gate-A requirements

Representational completeness is not Gate-A completion. The remaining controlled requirements are:

```text
UPDATED_FIELD_PROOF_EXECUTION_AND_DIGEST
CANDIDATE_WIDE_TYPED_REFERENTIAL_AND_TEMPORAL_VALIDATION
IDENTITY_BOUND_DETERMINISTIC_FULL_PACKAGE
REPRESENTATIVE_HUMAN_DOMAIN_REVIEW
```

The deterministic full-package implementation now exists; its exact real-corpus package identity must still be generated and independently verified with the selected producer/runtime/S2 pins.

Candidate-wide typed referential and temporal validation must use the corrected validators from PRs #236 and #237 or equivalent merged logic. Cross-class ID collisions cannot satisfy references, and YEAR/DATE/TIMESTAMP precision cannot be normalized or ordered by precision labels.

Human domain review must sample every predecessor family, including native, unresolved, governance, residual, and successor surfaces. Mechanical equality establishes preservation, not substantive truth.

## Authority boundary

Nothing in this checkpoint sets or implies:

```text
release_authorized = true
gate_a_complete = true
canonical publication
assessment endorsement
clinical validity
regulatory authorization
system conformance
global completeness
```

Canonical publication remains a separate attestation and publication process after Gate A closes.
