# ADR 0016: Identifier versus unresolved literal versus resolved entity reference

## Status

Accepted as the Workbench identity-reference implementation ADR (handoff ADR-IDENTITY-003, scoped to typed references). Entity-resolution disposition vocabulary expansion (`SAME_ENTITY`, `ACQUIRED_BY`, and related states) remains an E5/M2 concern and is not authorized by this ADR.

## Context

A display name, an NCT ID string, and a registry `entity_id` are different kinds of reference. APIs that need a resolved entity must not silently accept a literal.

## Decision

Workbench graph objects use three reference kinds:

- `IDENTIFIER` — a scheme-scoped identifier that has not been resolved to a registry entity.
- `UNRESOLVED_LITERAL` — a human or source string that is not an identifier scheme value and is not a resolved entity.
- `RESOLVED_ENTITY_REFERENCE` — an `entity_id` that already exists in the controlled registry (or an explicitly migrated resolved predecessor).

APIs that require a resolved entity id (`Assertion.subject`, `Relationship` endpoints, `Event.subject`, `ReopeningDecision.subject`) reject `IDENTIFIER` and `UNRESOLVED_LITERAL`. Exact-ID auto-confirm remains the only automatic resolution path already implemented in `entities/resolver.py`. Fuzzy matches remain proposals.

## Consequences

Callers must construct a `RESOLVED_ENTITY_REFERENCE` after human-gated resolution. Graph builders fail closed rather than promoting a literal into a canonical edge. This ADR does not merge entities, invent ids from display names, or expand the disposition vocabulary.
