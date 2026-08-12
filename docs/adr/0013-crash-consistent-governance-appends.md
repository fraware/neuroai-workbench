# ADR 0013: Crash-consistent append-only governance writes

## Status

Proposed under issue #127. This ADR governs the local persistence mechanism for append-only governance records. It does not establish substantive governance authority.

## Context

Governance scope manifests and reviewer opinions were initially persisted as two independent operations: write the immutable JSON record, then append its event. Owner dispositions proposed the same pattern. A process failure between those operations can leave a durable record without its append-only event binding. Concurrent writers can also inspect the same active state and both pass semantic uniqueness or supersession checks before either record is visible.

The event chain already provides append-only integrity and a durable hash-linked witness. Governance persistence should use that witness as the transaction commit point and should serialize semantic validation with the write that depends on it.

## Decision

All new mutable governance entry points use one governance-wide write lock and one prepared transaction journal.

The write protocol is:

1. acquire the governance write lock;
2. recover any prepared governance transactions;
3. verify the current governance store and perform semantic precondition checks;
4. create a unique transaction identifier;
5. persist a prepared journal containing record identity, exact record-byte digest, semantic record digest, secondary digests, event action, and event-payload digest;
6. persist the immutable governance record;
7. append the event carrying the transaction identifier and exact record/digest bindings;
8. verify the returned event as the transaction commit witness;
9. remove the prepared journal;
10. release the governance write lock.

The event is the commit witness. A record without a matching transaction event is uncommitted. A matching durable event makes the transaction committed even if the caller receives an error after event persistence.

## Recovery

Recovery executes under the governance write lock.

| Prepared state | Matching record | Matching event | Outcome |
|---|---:|---:|---|
| journal only | no | no | remove journal |
| pre-commit record | yes, exact bytes | no | remove only the uncommitted record and journal |
| committed, cleanup incomplete | yes, exact bytes | exactly one | retain record; remove journal |
| event without record | no | yes | fail closed |
| record digest mismatch | yes, divergent | any | fail closed |
| duplicate commit witnesses | any | more than one | fail closed |
| corrupt or ambiguous journal/event state | any | any | fail closed |

Recovery never guesses which bytes were intended and never repairs a committed governance record by substitution.

## Concurrency

The governance lock spans recovery, current-state verification, semantic uniqueness/supersession checks, journal preparation, record persistence, event append, and commit verification. This scope is intentional. A lock limited to file creation would leave a time-of-check/time-of-use race in reviewer-opinion and owner-disposition semantics.

The event chain retains its own lock. Lock acquisition order is governance lock first, event-chain lock second. Governance transaction recovery follows the same order.

## Journal minimization

Prepared journals contain control-plane metadata only. They do not contain governance record bodies, protected capture bytes, credentials, licensed evidence bytes, private evidence paths, or reviewer material beyond identifiers already required for transaction binding.

Protected evidence continues to be represented through opaque references at the governance layer.

## Legacy records

Governance records created before this ADR can remain valid when their existing record/event binding verifies under the record-type verifier. They are classified as legacy non-transactional records. A legacy record with no valid event binding is diagnosed as an orphan and is never silently promoted to transaction-complete state.

No historical immutable governance record or historical event is rewritten solely to retrofit a transaction identifier.

## Authority boundary

The transaction mechanism establishes local persistence integrity and concurrency safety only. A successful transaction does not:

- authenticate a reviewer, owner, or release authority;
- establish reviewer independence;
- establish institutional mandate;
- establish scientific, clinical, regulatory, or legal validity;
- establish governance-policy sufficiency;
- authorize a successor;
- authorize publication.

Those states remain explicit higher-layer decisions.

## Verification requirements

The implementation must retain the repository's global coverage threshold and satisfy a permanent 95% module coverage floor. Tests must cover pre-journal, post-journal, post-record, pre-event, post-event, cleanup, corrupt-state, path-containment, secondary-digest, and concurrent-writer cases across the supported Python matrix.
