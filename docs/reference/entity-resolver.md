# Entity resolver

The layered entity resolver produces **resolution proposals** for monitored mentions. It extends the exact-ID registry from PR-10 with deterministic matching layers and human disposition records.

## Boundary

Resolution proposals identify likely record correspondence. They do **not** establish technical capability, ownership beyond cited evidence, regulatory authorization, clinical benefit, or system conformance.

Proposals never mutate the canonical registry automatically. Disposition records capture human decisions only; registry registration remains a separate controlled workflow.

## Matching layers

1. **EXACT_ENTITY_ID** — auto-confirms when the entity exists.
2. **EXACT_ALIAS_ID** — proposal only; requires human disposition.
3. **EXACT_IDENTIFIER** — proposal only; requires human disposition.
4. **NORMALIZED_NAME** — deterministic normalized-string scan; emits `DUPLICATE_CANDIDATE` or `AMBIGUOUS`; never auto-merges.
5. **NO_MATCH** — emits `NEW_ENTITY` when no layer matches.

Refused inputs include normalized-name overrides, similarity thresholds, unsupported fuzzy match modes, and simultaneous selectors.

## Proposal states

| State | Meaning |
| --- | --- |
| `EXISTING_ENTITY` | One or more candidates map to a registry entity |
| `NEW_ENTITY` | No acceptable match; may warrant registration |
| `DUPLICATE_CANDIDATE` | Single normalized-name match; human must confirm or reject merge |
| `AMBIGUOUS` | Multiple candidates; human must select or defer |

Only exact `entity_id` matches set `auto_confirmed: true`. All other proposals remain `PENDING_HUMAN_DISPOSITION` until `record_resolution_disposition` runs.

## Blinded benchmark stub

`run_blinded_benchmark` executes synthetic pseudonymized cases from `RESOLUTION_BENCHMARK_BLINDED.json`. The stub reports case pass rate only; precision and recall require a fully annotated blinded sample outside this PR.

## Related issues

- #37 — controlled entity resolution and duplicate detection
- #34 — observatory operationalization epic

See `src/neuroai_workbench/resources/entities/` for JSON schemas and `tests/fixtures/entities/` for synthetic fixtures.
