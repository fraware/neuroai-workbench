# ADR 0012 — Accepted proposals use the ordinary assessment-save path

## Status

Accepted for the local reference profile.

## Context

Model-assistance responses and review statements may contain candidate wording. Their human dispositions deliberately perform zero assessment mutation. Issue #22 delivered a controlled bridge from an accepted proposal to an ordinary assessment edit without granting authority to the proposal, disposition, or model output and without rewriting historical finding state in place.

A direct write from an assistance or review module would create a second mutation path, obscure the predecessor assessment, weaken optimistic concurrency, and blur the distinction between proposal acceptance and assessment authority.

## Decision

### Separate acceptance from application

A human disposition records workflow treatment of a proposal. A later `proposal-apply` operation performs the assessment edit. Application requires the exact proposal and disposition digests, an explicit actor, the current assessment digest, a closed application plan, active covering decision-role assignments, a valid event chain, and a fully valid successor assessment.

### Closed field-level plan

The plan binds each target path, exact predecessor text, and exact successor text. Assistance patches also bind the source suggestion index. The first implementation supports narrative string fields on requirement findings only. Finding status, applicability, identifiers, evidence references, requirement identity, and historical flags remain outside the application allowlist.

`ACCEPTED_AS_DRAFT` assistance applies every recorded suggestion exactly. `PARTIALLY_USED` applies a non-empty proper subset. An accepted review statement applies one exact `proposed_change`. `PARTIALLY_ACCEPTED` review text remains ambiguous under the current single-text record model and is refused until a successor statement records the exact accepted wording.

### Ordinary save and recoverable predecessor

`Workspace.save_case` remains the only assessment mutation path. It now accepts an optional expected predecessor digest and operation metadata. Before replacement, it stores the exact predecessor assessment bytes at `history/assessments/<sha256>.json`. The normal validation, persistence, atomic replacement, and `ASSESSMENT_SAVED` event path then records the successor.

The event includes predecessor, successor, history, proposal, disposition, application-plan, patch, and local authority-assignment hashes. The proposal and disposition files remain unchanged. A failed save restores the prior assessment and persistence records and removes a newly created history object.

### Authority boundary

Application requires an active local `DECISION_AUTHORITY` or `LEAD_ASSESSOR` assignment covering every target. These records authorize a local workflow operation only. They do not authenticate a person, prove institutional delegation, establish scientific correctness, or grant clinical, regulatory, legal, UNESCO, canonical-release, or publication authority.

No external model invocation occurs during application.

## Consequences

- Proposal acceptance and assessment authority remain separate.
- Prior assessment state is content-addressed and recoverable.
- Duplicate and stale applications fail closed.
- Every applied change follows one canonical save and event route.
- Historical proposal, review, and disposition bytes remain available for audit.
- The first implementation deliberately excludes structural edits and status changes.

## Rejected alternatives

### Mutate the assessment inside `assist-dispose` or `review-dispose`

Rejected because a disposition alone does not establish assessment-edit authority and because implicit mutation hides the exact edit plan.

### Write assessment JSON directly from a proposal module

Rejected because a parallel writer would bypass ordinary validation, history, persistence, event, and concurrency controls.

### Apply a generic JSON Patch

Rejected for the local reference profile because unrestricted structural edits could alter identifiers, status, evidence relationships, or historical fields under a proposal-oriented command.

### Treat partial review acceptance as an exact edit

Rejected because the current review statement carries one free-text proposal and a partial disposition does not identify the exact accepted substring or successor wording.

## Validation

Adversarial tests cover assistance and review application, exact source binding, partial-selection semantics, stale assessment and field state, invalid lineage, missing or insufficient authority, forbidden fields, source tampering, rejected and ambiguous dispositions, duplicate and concurrent application, rollback after event failure, source-record immutability, predecessor recoverability, ordinary event creation, and real CLI dispatch.
