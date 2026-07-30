# Programme completed-assessment adapter

The programme adapter converts the consolidated UNESCO NeuroAI completed-assessment JSON shape into the native v4.2 workbench object model.

```bash
neuroai-workbench programme-adapt \
  examples/programme/PRIMA_COMPLETED_ASSESSMENT_v4.2.1.programme.json \
  artifacts/PRIMA.native.json \
  --report artifacts/PRIMA.adapter-report.json
```

## Preservation and no-reappraisal boundary

The adapter preserves claims, evidence objects, denominators, endpoints, all 78 requirement findings, gaps, decisions, prohibited inferences, and source-assessment provenance. Programme-only safety-event rows are retained as deterministic assessment notes because the native v4.2 schema has no standalone safety-event register.

`migration_provenance.preservation_verified` is **computed** from independent mechanical checks (identifier completeness/uniqueness, finding-status equality, count reconciliation, and no missing-evidence-to-FAIL conversion). A true flag means those checks passed. It does **not** mean scientific truth, authorization, conformance, or independent re-appraisal.

Expected PRIMA controlled counts:

| Object | Count |
| --- | ---: |
| Claims | 14 |
| Evidence objects | 15 |
| Endpoints | 11 |
| Denominators | 8 |
| Requirement findings | 78 |
| Gaps | 22 |
| Decisions | 4 |
| Safety-event notes | 11 |

Status counts: PASS 15 / PARTIAL 42 / NOT ASSESSED 21 / FAIL 0.

## Explicit loss boundaries

The adapter report lists loss boundaries, including:

- source-register consolidation into native evidence records;
- safety-event rows retained only as assessment notes;
- native `gap_register.linked_requirement_ids` left empty because programme `gaps_and_requests` do not carry requirement links;
- classification `sc_01`–`sc_12` values as **provisional** hardcoded projections pending human domain confirmation;
- unmatched programme `claim_state` strings mapped to `NOT REVIEWABLE` (not silently treated as supported-within-scope);
- no model-generated content.

Adaptation does not re-appraise evidence, upgrade a finding, establish authorization, or create conformance.
