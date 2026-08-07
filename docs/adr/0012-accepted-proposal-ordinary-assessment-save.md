# ADR 0012 — Accepted proposals use the ordinary assessment-save path

## Status

Accepted for the local reference profile.

## Context

Model-assistance responses and review statements may contain candidate wording. Their human dispositions deliberately perform zero assessment mutation. Issue #22 delivered a controlled bridge from an accepted proposal to an ordinary assessment edit without granting authority to the proposal, disposition, or model output and without rewriting historical finding state in place.

The initial bridge correctly separated disposition from mutation, but later adversarial testing exposed three integrity gaps: application authority was not enforced consistently across assistance and review; accepted proposal paths were not sufficient to bind the exact successor text; and `Workspace.save_case` could leave assessment-side files changed if event persistence failed after earlier file writes.

A direct write from an assistance or review module would create a second mutation path, obscure the predecessor assessment, weaken concurrency controls, and blur the distinction between proposal acceptance and assessment authority.

## Decision

### Separate acceptance from application

A human disposition records workflow treatment of a proposal. A later `assist-apply` or `review-apply` operation performs the assessment edit. Application requires exact proposal/disposition linkage, an explicit actor, the current assessment digest, a closed field plan, active covering local decision-role assignments, a valid event chain, and a valid successor assessment.

### Bind exact accepted content

Application is content-bound, not path-authorized.

For assistance, every patch must match exactly one recorded `(target_path, proposed_text)` suggestion. `ACCEPTED_AS_DRAFT` applies every recorded suggestion exactly. `PARTIALLY_USED` applies a non-empty proper subset exactly.

For review, an `ACCEPTED` statement applies one exact `proposed_change` through one explicit field patch inside the statement target. `PARTIALLY_ACCEPTED` remains ambiguous under the current one-text proposal record and is refused until a successor statement records the exact accepted wording.

The application record binds normalized target paths, exact predecessor values, exact successor values, and before/after field digests. Structural edits and unrestricted generic JSON Patch remain outside this proposal-oriented path.

### Require and revalidate local assessment-edit authority

Application requires an active local `DECISION_AUTHORITY` or `LEAD_ASSESSOR` assignment covering every target. Assignment hashes, lineage, corresponding assignment events, event-chain validity, and trailer validity are checked before the authority set is accepted.

The same authority assignment digests are revalidated inside the case mutation lock immediately before persistence. Each target field's predecessor value is also rechecked under that lock. Revocation, supersession, event-history failure, or concurrent field mutation therefore causes a fail-closed refusal instead of a time-of-check/time-of-use authorization gap.

These assignment records authorize a local workflow operation only. They do not authenticate a person, prove institutional delegation, establish scientific correctness, or grant clinical, regulatory, legal, UNESCO, canonical-release, or publication authority.

### Use one recoverable assessment-save transaction

`Workspace.save_case` remains the assessment mutation path. It now uses a self-hashed transaction journal under `transactions/assessment-saves/<transaction_id>/` with terminal states `COMMITTED` or `ROLLED_BACK` from an initial `PREPARED` state.

Before mutation, the transaction records the predecessor and planned successor assessment digests, predecessor/successor persistence digests, content-addressed history path, whether the history object is newly created, and every exclusive application-record path and digest. Exclusive records must resolve inside the controlled case directory.

Before replacement, the exact predecessor assessment is preserved at `history/assessments/<sha256>.json`. Existing history is re-hashed before trust or reuse.

The save then writes the successor assessment, persistence record, and application record and appends one physical transaction-keyed `ASSESSMENT_SAVED` event. Proposal-specific logical actions (`ASSISTANCE_PROPOSAL_APPLIED` or `REVIEW_PROPOSAL_APPLIED`) are embedded in that event under `related_events`, with apply provenance in the same payload. They are not committed as a second independent event.

If failure occurs before the save event is durable, rollback restores the predecessor assessment and persistence state, removes newly created application records, and removes a newly created history object after digest verification. If the event was already durably appended and a later exception is observed, the transaction is considered committed only after the transaction ID and successor digest match the durable event.

A later save recovers any remaining `PREPARED` transaction before starting a new mutation. A matching durable event completes commit; absence of that event triggers exact rollback. Invalid event history, corrupt transaction metadata, missing/corrupt predecessor snapshots, duplicate transaction events, or divergent controlled records block automatic recovery.

### Preserve proposal source bytes

Assistance request, response, and disposition files and review statement/disposition files remain byte-identical during application. Post-save checks verify that invariant. No model invocation occurs during application.

## Consequences

- Proposal acceptance and assessment authority remain separate.
- Accepted text is bound exactly, not inferred from an authorized path.
- Local decision-role authority is checked against integrity-linked assignment history and rechecked at persistence time.
- Field-level predecessor checks close cooperative concurrent-edit races.
- Prior assessment state is content-addressed, recoverable, and hash-verified.
- Assessment state, application record, persistence state, and proposal-apply provenance share one recoverable save boundary.
- Duplicate, stale, ambiguous, unauthorized, and divergent applications fail closed.
- Historical proposal, review, and disposition bytes remain available for audit.
- The reference profile still does not authenticate real-world identities or create release authority.

## Rejected alternatives

### Mutate the assessment inside `assist-dispose` or `review-dispose`

Rejected because a disposition alone does not establish assessment-edit authority and because implicit mutation hides the exact edit plan.

### Write assessment JSON directly from a proposal module

Rejected because a parallel writer would bypass ordinary validation, history, persistence, transaction recovery, event, and concurrency controls.

### Treat an accepted target path as permission to supply arbitrary successor text

Rejected because acceptance concerns the recorded proposal content. Path-only authorization permits text that was never reviewed or accepted.

### Apply a generic JSON Patch

Rejected for the local reference profile because unrestricted structural edits could alter identifiers, status, evidence relationships, or historical fields under a proposal-oriented command.

### Treat partial review acceptance as an exact edit

Rejected because the current review statement carries one free-text proposal and a partial disposition does not identify the exact accepted substring or successor wording.

### Commit proposal-apply as a second physical event

Rejected because two independent event appends would create a partial-commit window for one filesystem mutation. One `ASSESSMENT_SAVED` commit event with embedded logical actions gives recovery a single durable witness.

## Validation

Adversarial tests cover assistance and review application, exact source binding, full/partial assistance selection semantics, ambiguous partial review acceptance, stale assessment and field state, invalid lineage, missing or insufficient authority, authority changes during persistence, event correspondence, source tampering, duplicate application, path containment, history corruption, rollback before event commit, durable-event completion after a caller-visible exception, recovery of a remaining prepared transaction, source-record immutability, predecessor recoverability, CLI dispatch, and module coverage.
