# Governance transaction recovery

## Purpose

This runbook covers local diagnosis and recovery of interrupted append-only governance writes introduced under issue #127. It covers persistence integrity only. It does not authorize governance or release decisions.

## Controlled storage

Governance records remain below `governance/`. Prepared transaction journals are stored below `governance/transactions/`. The governance-wide coordination lock is `governance/.append.lock`. The durable commit witness is the matching transaction-bound event in the workspace event chain.

A prepared journal binds the transaction ID, target record path, record ID, semantic record digest, exact on-disk record-byte digest, secondary digests, event action, and event-payload digest. It does not contain the governance record body or protected capture bytes.

## Normal recovery

Recovery runs automatically under the governance write lock before a new transaction. The explicit recovery API performs the same operation.

Recovery first validates the event chain and its trailer. An invalid event chain blocks governance recovery. It then validates each prepared journal before inspecting its record/event state.

For each journal:

- no event and no record: remove the prepared journal;
- no event and exact prepared record: remove that uncommitted record and the journal;
- exactly one matching event and exact prepared record: retain the committed record and remove the journal;
- matching event with missing record: stop and report an ambiguous/corrupt committed state;
- divergent record bytes: stop and preserve evidence for investigation;
- duplicate matching events: stop and preserve evidence for investigation;
- corrupt journal or invalid path: stop and preserve evidence for investigation.

A failure after the event is durably appended is treated as a committed transaction. Caller success is not the commit criterion.

## Operator response to a blocked recovery

1. Do not delete or edit governance records, journals, or event-chain files by hand.
2. Preserve the workspace directory as evidence.
3. Run the non-mutating transaction diagnostic and the existing record-type verifiers.
4. Record the exact transaction ID, target record ID, record digest, journal digest, and event-chain verification result.
5. Determine whether the state is a legacy orphan, corruption, unexpected duplicate witness, or an implementation defect.
6. Repair through a reviewed code/data migration with explicit before/after hashes. Do not synthesize a missing historical event or transaction identity.

## Legacy orphan policy

Pre-#127 governance records are expected to lack transaction IDs. They are accepted as legacy records only when their record-type verifier confirms both their immutable record hash and their existing event binding. A record with no valid event binding is a legacy orphan and remains unresolved until explicitly adjudicated through a migration or archival decision.

Transaction recovery must not infer that a legacy record was committed solely from the presence of its JSON file.

## Concurrency

Governance recorders must hold the governance lock across semantic preconditions and commit. Do not implement a separate per-record lock that releases between active-state inspection and record creation. That pattern permits conflicting writers to pass the same semantic check.

Lock order is governance lock, then event-chain lock. New code must preserve that order.

## Protected-data boundary

Transaction journals and events may contain opaque protected references and cryptographic digests. They must not contain protected capture bodies, credentials, private evidence paths, or licensed evidence bytes. Protected evidence remains outside Git and outside transaction-control records.

## Release boundary

A successful transaction means only that one governance record was persisted crash-consistently. It does not authenticate the actor, establish substantive review, satisfy six-track governance policy, authorize a canonical successor, or authorize publication.
