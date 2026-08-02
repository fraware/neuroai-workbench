# Entity registry

The entity registry stores canonical organizations, systems, models, products, trials, regulatory records, and source entities. It supports **exact-ID resolution only** and refuses similarity-based merging.

## Boundary

Entity resolution identifies likely record correspondence. It does **not** establish technical capability, ownership beyond cited evidence, regulatory authorization, clinical benefit, or system conformance.

Canonical entity records are never silently merged or deleted. Alias and identifier registrations are append-only; in-place overwrites are refused.

## Exact resolution

`resolve_exact` accepts exactly one selector: `entity_id`, `alias_id`, or `identifier_scheme` + `identifier_value`.

Refused inputs include normalized-name matching, similarity thresholds, fuzzy match modes, and multiple simultaneous selectors.

For layered resolution proposals, see [entity-resolver.md](entity-resolver.md).

## Related issues

- #37 — controlled entity resolution and duplicate detection
- #34 — observatory operationalization epic

See `src/neuroai_workbench/resources/entities/` for JSON schemas and `tests/fixtures/entities/` for synthetic fixtures.
