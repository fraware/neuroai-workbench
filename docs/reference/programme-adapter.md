# Programme completed-assessment adapter

The programme adapter converts the consolidated UNESCO NeuroAI completed-assessment JSON shape into the native v4.2 workbench object model.

```bash
neuroai-workbench programme-adapt \
  examples/programme/PRIMA_COMPLETED_ASSESSMENT_v4.2.1.programme.json \
  artifacts/PRIMA.native.json \
  --report artifacts/PRIMA.adapter-report.json
```

The adapter preserves claims, evidence objects, denominators, endpoints, all 78 requirement findings, gaps, decisions, prohibited inferences, and source-assessment provenance. Programme-only safety-event rows are retained as deterministic assessment notes because the native v4.2 schema has no standalone safety-event register.

The adapter is loss-aware. Its report states what was projected, what was consolidated, and which fields remain source-format specific. Adaptation does not re-appraise evidence, upgrade a finding, establish authorization, or create conformance.
