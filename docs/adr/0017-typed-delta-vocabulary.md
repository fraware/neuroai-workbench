# ADR 0017: Typed delta vocabulary expansion (no RFC-6902 patch)

- Status: Accepted
- Date: 2026-08-31
- Related: ADR 0014 (temporal assertion), handoff ADR-DELTA-004

## Context

Observatory v1.6 deltas used eight typed operations. The living observatory needs graph-native operations for Entity, Source, Observation, Assertion, successor routes, reopening decisions, and explicit no-change comparisons. Unrestricted RFC-6902 JSON Patch must remain forbidden.

## Decision

1. Expand `DELTA_OPERATION.schema.json` to schema generation 1.1 by **adding** operation types:
   - `ADD_ENTITY`, `ADD_SOURCE`, `ADD_OBSERVATION`, `ADD_ASSERTION`
   - `SUPERSEDE_ASSERTION`, `SUPERSEDE_ENTITY`
   - `RECORD_SOURCE_SUCCESSOR_ROUTE`, `RECORD_REOPENING_DECISION`, `RECORD_NO_CHANGE_COMPARISON`
2. Keep `ADD_RECORD` and `SUPERSEDE_RECORD`. Migration is an explicit mapping, not a silent rename.
3. Supersession never deletes predecessor identifiers; predecessors remain addressable via tombstone metadata.
4. Delta application still produces a candidate successor only. It does not authorize a canonical release.

## Consequences

- Existing adjudicated deltas remain valid.
- Tests must cover schema acceptance of new ops and predecessor preservation on supersession.
- Website/database derived loaders remain non-authoritative relative to release artifacts.
