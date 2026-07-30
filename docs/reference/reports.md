# Deterministic assessment reports

The `report` command renders a human-readable Markdown projection of a native v4.2 assessment.

```bash
neuroai-workbench report \
  --assessment examples/assessments/PRIMA_Controlled_Assessment_v4.2.1.native.json \
  --output artifacts/PRIMA.md
```

The report contains controlled identity, typed decisions, counts, system boundaries, claims, evidence, endpoints, every requirement finding, evidence gaps, validation state, and the canonical assessment digest.

Report generation is deterministic for identical assessment bytes. It introduces no new finding, evidence weight, authorization, or decision authority.
