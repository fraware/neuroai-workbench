# Observatory v2 Gate-A migration checkpoint

Status: **mechanical Gate-A PASS over the exact frozen predecessor corpus; publication remains unauthorized**.

Gate A is an engineering and representational-integrity gate. Human domain review and GitHub Actions status are not mandatory closure conditions at this stage. Canonical publication remains a separate authority boundary.

## Claims kept separate

1. **Representational completeness** — every in-scope predecessor family has an exact native or governed-preserved destination. This is established.
2. **Native graph completeness** — every predecessor semantic has become a first-class v2 graph object. This is not claimed and is not required for Gate A.
3. **Mechanical Gate-A completion** — exact input binding, corrected field proof, typed/temporal validation, deterministic package verification, and an explicit Gate-A decision artifact have all executed from the bound Workbench runtime. This is established.
4. **Canonical publication** — a separately authorized S2 release. Gate A never implies this and publication remains unauthorized.

## Frozen inputs

The seven bound governing inputs are:

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

All seven archive bytes were independently extracted from the preserved programme archive and re-hashed before operator execution. Every observed SHA-256 matched the frozen identity exactly.

The Source Register is exactly the 224-record V14 `sources` array and is not double-materialized. The monitor registry contains exactly 224 unique monitor records mapped one-to-one to V14 Source identities with matching governed baseline fields.

## Bound execution identity

The exact mechanical run was bound to:

```text
producer_workbench_commit = 719170f2fd3556f4b9710f2b14ba96e8e34a8855
runtime_execution_pin      = 719170f2fd3556f4b9710f2b14ba96e8e34a8855
s2_predecessor_commit      = 3a94d7c1277988f342cad184d3a6f866653f42d2
observatory_graph_schema   = 1
```

The runtime was reconstructed from the successfully built `30df6fbee5bd78a84c7150c888efe147952b0379` source-distribution artifact plus every production-code delta between that commit and the bound producer commit. The three changed production-module Git blob identities and both operator-script Git blob identities were checked against GitHub before execution.

## Native v2 checkpoint

```text
Entity              153
Source              236
Event                 5
Candidate              9
Observation            0
Relationship           0
Assertion              0
ReopeningDecision      0
------------------------
TOTAL                403
```

The 223 predecessor organization-array entries partition into 153 identity-safe current organizations, 63 unresolved legacy endpoints, six provenance-only nodes, and one historical/current-identity-unresolved record. Native organization entities use `entity_type=ORGANIZATION`; predecessor subtype such as `COMPANY` remains predecessor descriptive state.

All 224 V14 Sources and 12 V16 new Sources materialize. Retrieval knowledge time is not promoted to publication time. Explicit publication dates preserve their original precision and null publication values remain absent.

All five V14 capital/ownership events materialize with exact subject identity and Source binding. Counterparties without controlled IDs remain unresolved literals. Temporal precision is exactly three DATE values, one YEAR value, and one absent date.

All nine V16 change Candidates materialize with exact predecessor payloads. Free-text subjects are not promoted into controlled identity.

## Governed predecessor state

Representational completeness does not require invented native objects. Exact content-addressed preservation covers:

- 70 non-native organization records;
- 12 transport-unresolved V16 source-check records;
- 26 organization-resolution history records;
- 13 regional-expansion history records;
- 2 scoped no-change confirmations;
- 6 reopening decisions with no assessment mutation;
- 9 withheld non-claims;
- 55 residual V14/DELTA16 model, registry, relationship, quality, regulatory, dependency, and governance records;
- V14/V16 release-level metadata/methodology/coverage/baseline state;
- the full V17 and PRIMA17 successor lineage;
- the duplicate Source Register and operational monitor projection.

Every residual family carries an explicit reason why native projection would currently invent identity, evidence semantics, temporal semantics, or claim scope.

## Successor and duplicate-container integrity

The migration implementation verifies:

- V16 embedded `adjudicated_delta` equals standalone DELTA16;
- V17 embedded `delta` equals standalone DELTA16;
- V17 embedded PRIMA successor payload equals standalone PRIMA17;
- baseline and predecessor archive identities reconcile;
- `ROP-16-001` transitions to `ROP-17-001`;
- the other five reopening decisions carry forward unchanged;
- successor basis preserves predecessor trigger identity and adds the executed PRIMA assessment identity;
- prohibited inferences remain explicit;
- duplicate containers are not double-materialized.

## Executed corrected field proof

The corrected canonical proof over V14, V16, DELTA16, V17, and MONITOR15 executed against the exact frozen bytes:

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

Proof SHA-256:

```text
0e69937b898eb09697ee57ce9e1f4e055162f1e158807a0932b606b17d391df9
```

The earlier 2,340-native-field proof and its digest are superseded.

## Candidate-wide native validation

The exact run validated the complete 403-object native candidate:

```text
object_count               = 403
typed_reference_checks     = 36
temporal_values_checked    = 14
cross_class_id_collisions  = {}
validation                 = PASS
```

Class counts were 153 Entity, 236 Source, 5 Event, and 9 Candidate objects. No Observation, Relationship, Assertion, or ReopeningDecision object was invented merely to satisfy native schema expectations.

## Consolidated integrity implementation

Former PR #236 and PR #237 were absorbed into the consolidated implementation. The authoritative code therefore includes:

- class-qualified release referential integrity;
- Event object and Entity lineage validation;
- typed Source/Observation/Assertion/Event/Entity references;
- conservative mixed YEAR/DATE/TIMESTAMP temporal comparison;
- interval failure only when the end definitely precedes the start;
- class-qualified graph diff identities;
- non-authoritative candidate projections.

The standalone fix PRs were closed as superseded rather than merged separately.

## Mechanical Gate-A operator

`scripts/observatory_v2_gate_a_run.py` is the controlling operator path. It:

1. verifies all seven frozen input hashes;
2. canonicalizes proof filenames and executes the corrected field proof;
3. builds the representationally complete checkpoint;
4. validates the native candidate with typed references and precision-safe temporal semantics;
5. writes the deterministic identity-bound hierarchical package;
6. independently verifies the package;
7. writes a separate content-addressed mechanical Gate-A decision.

The exact run recorded:

```text
decision = PASS_REPRESENTATIONAL_MIGRATION_MECHANICALLY_COMPLETE
gate_a_complete = true
representational_scope_complete = true
native_v2_materialization_complete = false
release_authorized = false
remaining_gate_requirements = []
```

No human-review packet was generated or required by the controlling operator path.

## Identity-bound package and decision

The exact runtime-dependent identities are:

```text
field_proof_sha256                 = 0e69937b898eb09697ee57ce9e1f4e055162f1e158807a0932b606b17d391df9
gate_a_package_manifest_sha256     = 4006f1d95b40b8d7f093d236dca54f90a898a835845bdc16dd492322e1a8c539
gate_a_package_descriptor_sha256   = fb7089e3127f200342fcfc0b4bb8c1835f0ae0a86850a9f06005abbb593e9827
gate_a_decision_sha256             = 5d3b1aa02d44dfe4391cad32a51846586ee30868ebdb4a1864e5e44f91356bc2
```

The package verifier returned no errors before the decision artifact was written.

## Authority boundary

Mechanical Gate-A PASS does not imply:

```text
release_authorized = true
canonical publication
substantive truth
clinical validity
regulatory authorization
system conformance
global completeness
```

Canonical Observatory-v2 publication remains a separate S2 candidate, authorization, and publication operation. Public `/v1` must be bound only to a genuinely published S2 release.
