# ADR 0007 — Transactional evidence registration journal

## Status

Accepted and implemented for the local/cooperative filesystem engineering profile.

## Context

Evidence registration spans five durable surfaces:

1. content-addressed evidence bytes;
2. `evidence/index.json`;
3. the assessment evidence register;
4. the assessment persistence sidecar;
5. the case event chain.

Atomic writes protect individual files, but they do not make this sequence atomic. A crash could leave an orphan object, an index row without an assessment link, an assessment link without its event marker, or a completed state whose journal still appeared pending. Concurrent registrations could also allocate the same evidence ID without one case-level serialization boundary.

The event substrate implemented under issue #24 now provides durable cooperative locking, ownership-safe release, append-only persistence, and crash-tail recovery. Evidence registration can therefore build a recoverable transaction protocol without changing the normative assessment schema.

## Decision

### Case-level registration lock

Every registration and recovery pass acquires `evidence/registration.lock` through the durable local-filesystem lock protocol. ID allocation, transaction recovery, preparation, state writes, and the commit event occur inside this lock.

The lock is a coordination mechanism. It does not authenticate a person or institution and does not provide hostile-writer fencing or distributed consensus.

### Write-ahead transaction directory

Each registration creates:

```text
evidence/transactions/EVTX-<uuid>/
```

Before any case state is changed, the directory receives:

- staged evidence bytes;
- exact predecessor snapshots of index, assessment, and persistence state;
- exact desired successor snapshots;
- a versioned `journal.json` containing transaction ID, record metadata, predecessor hashes, successor hashes, object-preexistence state, and the byte-identity boundary.

The journal is written last during preparation. A directory lacking a durable journal cannot have changed external case state and is removed as an orphan preparation with an event marker.

### Commit sequence

After durable preparation, the implementation:

1. writes or verifies the content-addressed object;
2. verifies the predecessor index hash and writes the desired index;
3. when linked, verifies predecessor assessment and persistence hashes and writes their desired successors;
4. appends one idempotent `EVIDENCE_ADDED` event carrying the transaction ID;
5. marks the journal `COMMITTED`;
6. removes staged bytes and before/desired snapshot copies.

The terminal journal retains metadata, hashes, state, timestamps, and recovery outcome. It does not retain a duplicate evidence object or assessment snapshot.

### Recovery decision

On the next registration or explicit recovery call, each non-terminal journal is evaluated under the registration lock.

**Forward completion** is permitted only when:

- the object digest matches;
- the index matches its desired hash;
- the assessment and persistence records match their desired hashes when linked.

The commit event is appended only when the transaction ID is absent from the event chain. The journal then becomes `COMMITTED` with a recovery marker.

**Rollback** is permitted only when every current durable file matches either the recorded predecessor or the recorded successor for that transaction. Recovery restores the exact predecessor index, assessment, and persistence bytes. An object created solely by the incomplete transaction is removed only when the restored index contains no reference to it. The event chain receives `EVIDENCE_REGISTRATION_ROLLED_BACK` with hashes and `historical_finding_mutation_performed=false`.

**Recovery blocking** occurs when any state has a hash outside the recorded predecessor/successor set, or a content-addressed object has an unexpected digest. The journal becomes `RECOVERY_BLOCKED`, and software refuses to overwrite the divergent state.

### Historical findings

Rollback restores the complete predecessor assessment bytes captured before registration. It never synthesizes or selectively edits historical findings. Forward completion applies only the desired assessment snapshot prepared for the registration.

### Digest boundary

SHA-256 verifies byte identity. A matching digest does not establish source authenticity, evidence quality, relevance, completeness, lawful custody, disclosure authorization, or substantive validity.

## Consequences

- Successful registration returns only after object, index, assessment/persistence when applicable, event marker, and terminal journal are durable.
- Crashes before complete state produce exact rollback on recovery.
- Crashes after all desired state writes produce idempotent forward completion.
- A crash after event append cannot create a duplicate commit event.
- Concurrent cooperative registrations allocate unique evidence IDs under one lock.
- Unknown external divergence fails closed.
- Terminal journals provide transaction provenance without retaining duplicate evidence or assessment content.
- The normative assessment schema and evidence record vocabulary remain unchanged.

## Residual risks

- A privileged actor can replace a complete case and its transaction history.
- A writer that ignores the lock protocol can corrupt state.
- Filesystem or hardware behavior outside the guarantees assumed by atomic rename and `fsync` may still cause loss.
- Registration does not authenticate evidence or custody.
- Backup, retention, secure erasure, and legal-hold behavior remain deployment responsibilities.
- Cross-case and distributed transactions remain outside this architecture.

## Validation

Adversarial tests inject crashes after preparation, object write, index write, case write, and event append. They verify exact rollback, forward completion, event idempotency, orphan cleanup, divergence blocking, unlinked registration, terminal recovery idempotency, and concurrent unique-ID allocation.

Issue #23 records implementation and verification evidence.