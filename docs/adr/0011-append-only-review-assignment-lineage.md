# ADR 0011 — Append-only review-assignment lineage

## Status

Accepted for the local reference profile.

## Context

Review assignments were immutable files with one supported state, `ACTIVE`. Ending or transferring an assignment would have required editing the original file or adding an informal convention outside the verifier. In-place state edits would erase historical authority context, invalidate hashes, create races with statement submission, and make later disagreement records harder to interpret.

The local reference profile also lacks authenticated institutional identity. Any assignment mechanism must preserve this authority boundary while still supporting controlled engineering workflows.

## Decision

### Immutable successor records

Assignment changes append a new assignment-lineage record in the existing `reviews/assignments/` store.

- `CREATED` starts a lineage with an active assignment.
- `SUPERSEDES` appends a new active assignment and binds the predecessor ID and digest.
- `REVOKES` appends a terminal revoked record that copies the predecessor reviewer, role, and scope.

The predecessor file is never edited. Each successor records its actor, timestamp, rationale, predecessor digest, current assessment digest, local-authority boundary, and zero-assessment-mutation statement.

### Effective state

A lineage may have one successor per record. The effective assignment is the unique active tip. A predecessor is reported as `SUPERSEDED` or `REVOKED` according to its successor transition. Revocation records cannot gain review authority.

Verification rejects branching, cycles, unresolved predecessors, predecessor-hash substitution, temporal inversion, transitions from a non-active predecessor, and revocation records that alter reviewer, role, or scope.

### Transition authority

The original assigning actor or a covering active decision-role assignment may supersede or revoke an assignment. An assigned reviewer may relinquish their own assignment through revocation. A reviewer cannot appoint a successor solely by holding the assignment. Decision-role self-assignment remains refused.

These are local workflow checks. They do not authenticate the actor or establish institutional delegation.

### Historical validity

Statements and dispositions retain the assignment IDs that authorized them. Verification evaluates whether the linked assignment was active at the statement or disposition timestamp. A later transition does not erase valid historical attribution, and a revoked or superseded assignment cannot authorize new records.

### Concurrency

Assignment creation and transitions, statement submission, and disposition use the case mutation lock. Cooperative writers cannot create two successor records or interleave a statement after a revocation decision but before its persistence.

## Consequences

- Historical assignment bytes remain recoverable and verifiable.
- Transfers and revocations are explicit, attributable, and event-linked.
- Review reports show recorded and effective assignment state separately.
- Existing version-1 assignment records without transition fields remain readable as legacy `CREATED` records.
- The local profile still provides no identity proof, institutional authorization, distributed consensus, or hostile-writer fencing.

## Rejected alternatives

### Edit `state` in place

Rejected because it destroys the original hash-bound assignment state and creates silent historical overwrite.

### Maintain a mutable current-assignment table only

Rejected because current state alone cannot explain which assignment authorized a historical statement.

### Permit the assigned reviewer to name a successor

Rejected because relinquishment and appointment are distinct actions. The local assignment holder may revoke their own assignment but may not create authority for another reviewer without the original assigner or a covering decision-role record.

## Validation

Adversarial tests cover append-only revocation, transfer of effective authority, self-relinquishment, appointment refusal, covering decision-role control, predecessor-hash tampering, concurrent successor attempts, assessment immutability, event linkage, and CLI exposure.
