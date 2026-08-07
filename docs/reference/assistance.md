# Controlled model assistance

The workbench supports a provider-neutral, offline exchange protocol for language-model assistance. It does not call a model API, transmit registered evidence bytes, or modify an assessment automatically.

## Lifecycle

1. `assist-request` creates a bounded JSON request with a UUID-based `request_id`, selected public or synthetic structured context, explicit prohibited inferences, and an output contract. Creating a request refuses to overwrite an existing request file.
2. An operator submits that request to an approved model outside the workbench.
3. `assist-record` validates the structured response, scans model output for blocked secret patterns, and stores it with provider, model, request hash, and output hash. Response `disposition_state` remains `PENDING_REVIEW` until a disposition file exists.
4. `assist-dispose` records a final human disposition (`ACCEPTED_AS_DRAFT`, `PARTIALLY_USED`, or `REJECTED`) without changing the assessment. Dispose and verify both reject assessment hash drift against the request (`ASSESSMENT_DRIFT`). Acceptance is not application.
5. `assist-apply` performs a separate, explicit assessment edit through transactional `Workspace.save_case`. It requires the current assessment digest, exact proposal/disposition/response linkage, exact proposal text, active covering local decision-role assignments, and explicit field patches.
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
  --actor lead-assessor

neuroai-workbench assist-verify ./workspace CASE-001 AI-REQUEST-ID
```

## Exact application semantics

Application is content-bound, not path-authorized. Every patch must match exactly one recorded response suggestion as the pair `(target_path, proposed_text)`. A path appearing in the model response does not authorize arbitrary replacement text.

Disposition semantics are closed:

- `ACCEPTED_AS_DRAFT` applies every recorded suggestion exactly.
- `PARTIALLY_USED` applies a non-empty proper subset of the recorded suggestions exactly.
- `REJECTED` cannot be applied.

Duplicate patch paths, duplicate path/text suggestions, stale request state, stale assessment state, malformed suggestions, and unmatched patch text fail closed.

For each applied field, the application record stores the normalized target path, exact predecessor value, successor value, and SHA-256 digests of both values. The application also records the exact request, response, disposition, before-assessment, after-assessment, application, and authority-assignment digests.

## Assessment-edit authority

The actor must hold an active local `LEAD_ASSESSOR` or `DECISION_AUTHORITY` assignment covering every assessment target derived from the applied paths. Assignment records must have valid hashes, valid lineage, and exactly matching assignment events on a valid event chain.

Authority is evaluated once when the application plan is built and revalidated inside the case mutation lock immediately before persistence. The workbench also rechecks each predecessor field value under that lock. Revocation, supersession, event-chain corruption, or concurrent field mutation causes the apply operation to fail closed.

These records authorize a local workflow edit only. `LOCAL_UNAUTHENTICATED_ATTRIBUTION` does not authenticate a person, establish institutional delegation, prove scientific correctness, or grant clinical, regulatory, legal, UNESCO, canonical-release, or publication authority.

## Transaction and event semantics

`assist-apply` uses the ordinary `Workspace.save_case` path. The save creates a self-hashed assessment-save transaction journal, preserves the predecessor assessment under `history/assessments/<sha256>.json`, writes the successor assessment and persistence record, writes the application record as an exclusive case-contained record, and commits one physical `ASSESSMENT_SAVED` event.

The logical `ASSISTANCE_PROPOSAL_APPLIED` action is embedded in the `ASSESSMENT_SAVED` payload under `related_events`. It is not a second independently committed event. This keeps assessment state, application record, provenance, and event history on one recoverable transaction boundary.

A failure before durable event commit rolls back the assessment, persistence record, application record, and newly created history object. If the event was durably committed but the caller observed a later exception, recovery verifies the transaction identity and successor digest and completes the journal as `COMMITTED`. A `PREPARED` transaction found on a later save is either completed from the matching durable event or rolled back exactly. Corrupt transaction metadata, snapshots, or event-chain state block automatic recovery.

The request, response, and disposition files remain byte-identical during application. No model is invoked.

## Authority boundary

A model response is a candidate suggestion. It cannot assign applicability, change a finding by itself, close a gap, issue a conformance decision, determine legal or clinical status, alter historical records, or authorize a release. Human disposition and assessment-edit authority remain separate operations.

## Data boundary

The request generator includes selected structured summaries only. It does not include registered evidence bytes. Obvious credential and secret patterns are scanned across the prompt and the full exported context JSON. The request records `disclosure_policy: ATTESTATION_PLUS_SECRET_SCAN_ONLY`; this is not field-level classification or proof that context is public or synthetic. Protected neural, clinical, participant, regulator-held, security-sensitive, or private evidence remains outside this workflow unless a separately approved institutional deployment profile supplies lawful and technically enforced controls.

Recording a response, disposing a response, and verifying an assistance record all require the request `assessment_sha256` to match the current assessment. After an assessment edit, create a new assistance request before importing or disposing a model response. Model output is scanned with the same sensitive-text guard used for prompts and context; findings reject persistence.
