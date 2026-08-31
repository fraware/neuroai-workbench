# Extending Observatory programmes and graph vocabulary

This guide covers contributor extension points for source universes, collector adapters, assertion predicates, entity kinds, and typed delta operations. It does not authorize releases, institutional deployment, or substantive truth claims.

## Offline reference flow

One-command offline path (no network):

```bash
python scripts/offline_reference_flow.py --output-dir .tmp/offline-flow
```

The script runs SU-PUBS fixture discovery, human-gated proposal adjudication, and a mechanical release candidate. `release_authorized` remains false.

## Add a source universe programme

1. Author `src/neuroai_workbench/resources/discovery/SU_*.programme.json` against `SOURCE_UNIVERSE_PROGRAMME.schema.json`.
2. Keep a stable `universe_id`. Documentation aliases must not silently rename the stable id (`SU-TRIAL` stays `SU-TRIAL`; `SU-TRIALS` is alias-only).
3. Register the resource in `discovery/programme.py` (`PROGRAMME_RESOURCES`).
4. For offline fixture/replay maturity, add projection metadata in `discovery/universe_projection.py` and fixtures under tests.
5. Coverage reports must retain denominators, duplicates, conflicts, pagination state, and an explicit failure taxonomy. Cursor completion is not recall.
6. Programme execution emits candidates only. No S2 or monitor-registry mutation.

## Add a collector adapter

1. Implement under `collector/adapters/` with an explicit adapter id and boundary string.
2. Add/extend adapter contract JSON under `resources/collector/`.
3. Keep capture quarantine-only. Successful retrieval remains `RETRIEVED_BYTES_NOT_SUBSTANTIVELY_ADJUDICATED`.
4. Adapter presence is not programme maturity. Wire a programme projection before claiming offline executability.
5. Live network requires authorization-packet collection and the live collection gate. Default stays offline-first.

## Add an assertion predicate

1. Prefer schema-validated observatory-graph `Assertion` objects (`resources/observatory_graph/ASSERTION.schema.json`).
2. Record `evidence_state`, `verification_state`, `review_state`, `claim_boundary`, and `prohibited_inferences`.
3. Subject references that require resolved entity ids must reject unresolved literals.
4. Predicates do not grant assessment mutation or release authority.

## Add an entity kind

1. Extend entity-type vocabulary only with schema + registry updates and migration notes.
2. Exact-identifier matches may auto-confirm. Fuzzy/name matches remain proposals.
3. Disposition vocabulary: `SAME_ENTITY`, `NOT_SAME_ENTITY`, `SUCCESSOR_OF`, `SUBSIDIARY_OF`, `ACQUIRED_BY`, `ALIAS_OF`, `UNRESOLVED`.
4. Directed relations require `related_entity_id`. Predecessors are never deleted. No fuzzy auto-merge.

## Add a typed delta operation

1. Extend `resources/delta/DELTA_OPERATION.schema.json` and `delta/schemas.py` / `delta/apply.py` together.
2. Keep typed ops only. Do not introduce unrestricted RFC-6902 patch application to canonical state.
3. Add adversarial tests: duplicate ids, dangling refs, predecessor digest mismatch, idempotent apply refusal.
4. `RECORD_NO_CHANGE_COMPARISON` requires an explicit `comparison_scope`.

## Verification expectations

- Behavioral change: focused tests.
- Integrity/security boundary: adversarial tests.
- Local: `make quality` and `make test` (or the focused pytest subset on Windows PowerShell with `;`).
- Hosted jobs with `steps: []` are `INFRASTRUCTURE_FAILURE`, not test results. Do not loosen required checks.
