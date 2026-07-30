
# ADR 0004 — Normative kernel change control

## Status

Accepted for repository stabilization.

## Decision

Files under `src/neuroai_workbench/resources/v4_2/`, together with validation and migration behavior that determines their interpretation, are controlled normative assets. A change to requirement meaning, identifier, applicability, finding semantics, prohibited inference, or conformance interpretation requires a dedicated ADR, migration analysis, domain review, and explicit instrument-version decision.

Ordinary refactoring may improve implementation structure only when tests demonstrate semantic preservation.

## Consequences

- CODEOWNERS review is required for controlled paths.
- Pull requests must state semantic impact explicitly.
- Historical findings remain immutable.
- Compatible additions require additive migration and regression fixtures.
