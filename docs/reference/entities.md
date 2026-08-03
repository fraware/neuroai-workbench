# Entity registry and resolver

The entity subsystem stores canonical organizations, systems, models, products, trials, regulatory records, and source entities, and produces layered resolution proposals for monitored mentions.

## Boundary

Entity resolution identifies likely record correspondence. It does **not** establish technical capability, ownership beyond cited evidence, regulatory authorization, clinical benefit, or system conformance.

Canonical entity records are never silently merged or deleted. Alias and identifier registrations are append-only; in-place overwrites are refused. Resolution proposals never mutate the canonical registry automatically. Disposition records capture human decisions only; registry registration remains a separate controlled workflow.

## Exact-ID registry

`resolve_exact` accepts exactly one selector: `entity_id`, `alias_id`, or `identifier_scheme` + `identifier_value`.

Refused inputs include normalized-name matching, similarity thresholds, fuzzy match modes, and multiple simultaneous selectors.

## Layered resolver

The layered resolver extends exact-ID lookup with deterministic matching layers and human disposition records:

1. **EXACT_ENTITY_ID** — auto-confirms when the entity exists.
2. **EXACT_ALIAS_ID** — proposal only; requires human disposition.
3. **EXACT_IDENTIFIER** — proposal only; requires human disposition.
4. **NORMALIZED_NAME** — deterministic normalized-string scan; emits `DUPLICATE_CANDIDATE` or `AMBIGUOUS`; never auto-merges.
5. **NO_MATCH** — emits `NEW_ENTITY` when no layer matches.

Refused inputs include normalized-name overrides, similarity thresholds, unsupported fuzzy match modes, and simultaneous selectors.

### Proposal states

| State | Meaning |
| --- | --- |
| `EXISTING_ENTITY` | One or more candidates map to a registry entity |
| `NEW_ENTITY` | No acceptable match; may warrant registration |
| `DUPLICATE_CANDIDATE` | Single normalized-name match; human must confirm or reject merge |
| `AMBIGUOUS` | Multiple candidates; human must select or defer |

Only exact `entity_id` matches set `auto_confirmed: true`. All other proposals remain `PENDING_HUMAN_DISPOSITION` until `record_resolution_disposition` runs.

## Evaluation

Blinded stub (5), public annotated subset (≥20), and public/synthetic scale corpus (≥200 with frozen train/dev/test partitions) live under entity benchmark resources. Measured precision, recall, false-merge, false-split, and abstention counts are engineering behavioral metrics against annotated synthetic or public cases; they do not establish substantive entity identity. Ops ≥60 remains ops-gated. See [entity-resolution-report.md](../evaluation/entity-resolution-report.md).

Ops-gated full ≥60 annotated runs require `NEUROAI_OPS_WORKSPACE` and do not commit protected annotations to the software repository. Issue #37 layers 5–6 remain deferred.

## Schemas and fixtures

See `src/neuroai_workbench/resources/entities/` for JSON schemas and `tests/fixtures/entities/` for synthetic fixtures.
