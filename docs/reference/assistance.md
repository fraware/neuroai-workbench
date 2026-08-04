# Controlled model assistance

The workbench supports a provider-neutral, offline exchange protocol for language-model assistance. It does not call a model API, transmit evidence, or modify an assessment automatically.

## Lifecycle

1. `assist-request` creates a bounded JSON request with a UUID-based `request_id`, selected public or synthetic structured context, explicit prohibited inferences, and an output contract. Creating a request refuses to overwrite an existing request file.
2. An operator submits that request to an approved model outside the workbench.
3. `assist-record` validates the structured response, scans model output for blocked secret patterns, and stores it with provider, model, request hash, and output hash. Response `disposition_state` remains `PENDING_REVIEW` until a disposition file exists.
4. `assist-dispose` records a final human disposition (`ACCEPTED_AS_DRAFT`, `PARTIALLY_USED`, or `REJECTED`) without changing the assessment. Dispose and verify both reject assessment hash drift against the request (`ASSESSMENT_DRIFT`). `ACCEPTED_AS_DRAFT` and `PARTIALLY_USED` remain draft dispositions; acceptance is not application.
5. `assist-apply` applies an accepted draft only through ordinary `Workspace.save_case`, with optimistic `expected_assessment_sha256`, explicit field patches limited to proposal paths, recoverable prior assessment history, and an `ASSISTANCE_PROPOSAL_APPLIED` event. Proposal and disposition bytes stay unchanged. No model is invoked.
6. `assist-verify` verifies request, response, and disposition linkage, including assessment hash currency.

```bash
neuroai-workbench assist-request ./workspace CASE-001 DRAFT_FINDING \
  --prompt "Draft bounded wording for NK-01-R01." \
  --evidence-id EV-001 \
  --requirement-id NK-01-R01 \
  --out request.json

neuroai-workbench assist-record ./workspace CASE-001 AI-REQUEST-ID response.json \
  --provider approved-provider \
  --model exact-model-id

neuroai-workbench assist-dispose ./workspace CASE-001 AI-REQUEST-ID ACCEPTED_AS_DRAFT \
  --notes "Accepted as draft wording only; apply separately."

neuroai-workbench assist-apply ./workspace CASE-001 AI-REQUEST-ID \
  --expected-assessment-sha256 CURRENT_SHA256 \
  --patches-file patches.json \
  --actor domain-reviewer

neuroai-workbench assist-verify ./workspace CASE-001 AI-REQUEST-ID
```

## Authority boundary

A model response is a candidate suggestion. It cannot assign applicability, change a finding, close a gap, issue a conformance decision, determine legal or clinical status, alter historical records, or authorize a release. Human reviewers must make any subsequent assessment edit through the ordinary controlled workflow. Disposition and application are separate: disposing `ACCEPTED_AS_DRAFT` or `PARTIALLY_USED` does not mutate the assessment.

## Data boundary

The request generator includes selected structured summaries only. It does not include registered evidence bytes. Obvious credential and secret patterns are scanned across the prompt and the full exported context JSON. The request records `disclosure_policy: ATTESTATION_PLUS_SECRET_SCAN_ONLY`; this is not field-level classification or proof that context is public or synthetic. Protected neural, clinical, participant, regulator-held, security-sensitive, or private evidence remains outside this workflow unless a separately approved institutional deployment profile supplies lawful and technically enforced controls.

Recording a response, disposing a response, and verifying an assistance record all require the request `assessment_sha256` to match the current assessment. After an assessment edit, create a new assistance request before importing or disposing a model response. Model output is scanned with the same sensitive-text guard used for prompts and context; findings reject persistence.
