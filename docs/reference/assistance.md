# Controlled model assistance

The workbench supports a provider-neutral, offline exchange protocol for language-model assistance. It does not call a model API, transmit evidence, or modify an assessment automatically.

## Lifecycle

1. `assist-request` creates a bounded JSON request containing selected public or synthetic structured context, explicit prohibited inferences, and an output contract.
2. An operator submits that request to an approved model outside the workbench.
3. `assist-record` validates and stores the structured response with provider, model, request hash, and output hash.
4. `assist-dispose` records a human disposition without changing the assessment.
5. `assist-verify` verifies request, response, and disposition linkage.

```bash
neuroai-workbench assist-request ./workspace CASE-001 DRAFT_FINDING \
  --prompt "Draft bounded wording for NK-01-R01." \
  --evidence-id EV-001 \
  --requirement-id NK-01-R01 \
  --out request.json

neuroai-workbench assist-record ./workspace CASE-001 AI-REQUEST-ID response.json \
  --provider approved-provider \
  --model exact-model-id

neuroai-workbench assist-dispose ./workspace CASE-001 AI-REQUEST-ID REJECTED \
  --notes "Rejected after domain review; no assessment change."

neuroai-workbench assist-verify ./workspace CASE-001 AI-REQUEST-ID
```

## Authority boundary

A model response is a candidate suggestion. It cannot assign applicability, change a finding, close a gap, issue a conformance decision, determine legal or clinical status, alter historical records, or authorize a release. Human reviewers must make any subsequent assessment edit through the ordinary controlled workflow.

## Data boundary

The request generator includes selected structured summaries only. It does not include registered evidence bytes. Obvious credential and secret patterns are scanned across the prompt and the full exported context JSON. The request records `disclosure_policy: ATTESTATION_PLUS_SECRET_SCAN_ONLY`; this is not field-level classification or proof that context is public or synthetic. Protected neural, clinical, participant, regulator-held, security-sensitive, or private evidence remains outside this workflow unless a separately approved institutional deployment profile supplies lawful and technically enforced controls.

Recording a response requires the request `assessment_sha256` to match the current assessment. After an assessment edit, create a new assistance request before importing a model response.
