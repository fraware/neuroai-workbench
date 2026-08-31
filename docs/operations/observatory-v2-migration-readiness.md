# Observatory v2 predecessor family readiness ledger

Status: **noncanonical migration planning evidence**. This ledger prevents field-preservation PASS from being confused with complete native-object readiness.

## Readiness states

- `NATIVE_COMPLETE` — the complete predecessor family is materialized with exact trace verification.
- `PARTIAL_NATIVE_WITH_EXPLICIT_PRESERVATION` — some records are native and every excluded record has an explicit governed migration classification.
- `PRESERVED_REQUIRED_NATIVE_FIELDS_ABSENT` — predecessor evidence is preserved, but one or more native-required fields were never governed and cannot be invented.
- `BLOCKED_IDENTITY_RESOLUTION` — native representation requires controlled subject/object identity that predecessor literals do not establish.
- `BLOCKED_ONTOLOGY_MAPPING` — the predecessor record does not yet have a sufficiently exact v2 object/identity distinction.
- `BLOCKED_TEMPORAL_OR_TRIGGER_TYPING` — target identity, trigger type, or decision time is insufficient for the intended native object.
- `PRESERVED_RELEASE_LEVEL_STATE` — release/methodology/quality/provenance state remains exact predecessor metadata rather than a graph object.
- `DUPLICATE_CONTAINER_PRESERVED` — a governing successor embeds a predecessor delta for traceability; it is preserved but must not be double-materialized.

## Current frozen-corpus readiness

| Role/family | Records | State | Controlling reason |
| --- | ---: | --- | --- |
| V14 `organizations` | 223 | `PARTIAL_NATIVE_WITH_EXPLICIT_PRESERVATION` | 153 exact current organization identities become `ORGANIZATION` Entities; 63 legacy endpoints, 6 provenance nodes, 1 historical/current-identity-unresolved record remain preserved. |
| V14 `sources` | 224 | `NATIVE_COMPLETE` | Exact source identity fields available; all records materialized with trace sidecars. |
| V16 `new_sources` | 12 | `NATIVE_COMPLETE` | Exact source identity fields available; publication precision preserved. |
| V16 `source_checks` | 12 | `PRESERVED_REQUIRED_NATIVE_FIELDS_ABSENT` | `retrieval_method` and `requested_locator` were not governed by predecessor; no native Observation is fabricated. |
| V14 `capital_and_ownership_events` | 5 | `NATIVE_COMPLETE` | Exact unique organization subject identity and source bindings; counterparties remain unresolved literals; DATE/YEAR/null event time preserved. |
| V16 `change_candidates` | 9 | `NATIVE_COMPLETE` | Stable candidate IDs/classes/adjudications; exact predecessor payload retained; all source references resolve. |
| V14 `organization_resolution` | 26 | `BLOCKED_ONTOLOGY_MAPPING` | Identity-history semantics need a governed event/assertion representation; rationale/before/after state must not be flattened. |
| V14 `regional_expansion` | 13 | `BLOCKED_ONTOLOGY_MAPPING` | Coverage-acquisition action is not organization identity and needs a bounded coverage assertion/provenance representation. |
| V14 `representative_model_records` | 13 | `BLOCKED_ONTOLOGY_MAPPING` | Model family/checkpoint/record identity must be distinguished before Entity materialization. |
| V14 `model_and_dataset_registry` | 5 | `BLOCKED_ONTOLOGY_MAPPING` | Aggregate registry state spans model/dataset/benchmark semantics and cannot be coerced into one object type. |
| V14 `trial_site_relationships` | 7 | `BLOCKED_IDENTITY_RESOLUTION` | Study/system and site literals require controlled entities on both endpoints. |
| V14 `participant_authority_relationships` | 6 | `BLOCKED_IDENTITY_RESOLUTION` | Case and participant/holder literals require controlled identities and privacy-safe representation. |
| V14 `supplier_dependency_relationships` | 9 | `BLOCKED_IDENTITY_RESOLUTION` | System/provider/origin endpoints are not uniformly controlled entity IDs. |
| V14 `data_quality` | 6 | `PRESERVED_RELEASE_LEVEL_STATE` | Programme quality findings require explicit scope/subject mapping before graph assertions. |
| V16 `adjudicated_delta` | 1 container | `DUPLICATE_CONTAINER_PRESERVED` | Child delta families are separately governed in DELTA16 and must not be double-materialized. |
| V16 `reopening_decisions` | 6 | `BLOCKED_TEMPORAL_OR_TRIGGER_TYPING` | Free-text target objects and basis identifiers require exact subject plus typed assertion/event triggers; native decision time is not uniformly governed. |
| V16 `no_change_confirmations` | 2 | `BLOCKED_ONTOLOGY_MAPPING` | Scoped comparison evidence must not be translated into “nothing changed” or a substantive PASS assertion. |
| V16 `withheld_claims` | 9 | `PRESERVED_RELEASE_LEVEL_STATE` | Withholding boundaries remain explicit release/adjudication state. |
| DELTA16 `regulatory_and_market_events` | 2 | `BLOCKED_IDENTITY_RESOLUTION` | System subjects require exact controlled System identity before native Event/Assertion mapping. |
| DELTA16 `capital_and_ownership_events` | 2 | `BLOCKED_ONTOLOGY_MAPPING` | Subjects may resolve, but predecessor does not carry a native-equivalent evidence-state contract; do not synthesize it from source class. |
| DELTA16 `model_records` | 2 | `BLOCKED_ONTOLOGY_MAPPING` | Roadmap/preprint model identity and checkpoint semantics must remain distinct. |
| DELTA16 `supplier_dependency_relationships` | 1 | `BLOCKED_IDENTITY_RESOLUTION` | Subject/provider endpoints require controlled identities. |
| DELTA16 `governance_and_leadership_events` | 2 | `BLOCKED_ONTOLOGY_MAPPING` | Event type/evidence semantics require an explicit governed mapping; organization name alone is insufficient. |
| V17 `delta` | 1 container | `DUPLICATE_CONTAINER_PRESERVED` | Carries predecessor delta state for successor traceability. |
| V17 `reopening_decisions` | 6 | `BLOCKED_TEMPORAL_OR_TRIGGER_TYPING` | Target/basis/time typing remains incomplete for native ReopeningDecision. |
| V17 `assessment_successor_delta` | 1 container | `DUPLICATE_CONTAINER_PRESERVED` | Embedded PRIMA successor state remains governed successor provenance; standalone audit must not double-count it. |
| V17 metadata/count/provenance/predecessor fields | release-level | `PRESERVED_RELEASE_LEVEL_STATE` | Release identity, arithmetic and provenance are not silently converted into graph claims. |

## Current materialized candidate checkpoint

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

Separate preserved migration state includes 70 v1.4 organization records and 12 v1.6 transport-unresolved source-check records, plus all other blocked/release-level predecessor families through the field-preservation ledger.

## Gate rule

A family may move to `NATIVE_COMPLETE` only when:

1. every predecessor record in that family is accounted;
2. every native-required semantic field is either exact predecessor state or explicitly bounded migration metadata that does not manufacture a predecessor fact;
3. every referenced controlled object resolves by exact identity, not fuzzy/display-name matching;
4. all predecessor fields without native slots remain traceable and content-addressed;
5. temporal precision/absence round-trips without normalization invention;
6. candidate-wide referential validation succeeds;
7. the family verifier independently compares native mapped fields to predecessor state rather than trusting generator output alone.

A new predecessor family or field shape is a fail-closed review event. This ledger itself does not authorize schema evolution or publication.
