# ADR 0007 — Transactional evidence registration journal

## Status

Accepted and implemented for the local and cooperative filesystem engineering profiles.

## Context

Evidence registration spans five durable surfaces:

1. content-addressed evidence bytes;
2. `evidence/index.json`;
3. the assessment evidence register;
4. the assessment persistence sidecar;
5. the case event chain.

Atomic replacement protects an individual file. It does not make this sequence atomic. A crash may leave an orphan object, an index row without its assessment link, a linked assessment without its event records, or fully written state whose journal still appears pending. Concurrent registrations also need one case-level serialization boundary for recovery and evidence-ID allocation.

Issue #24 established durable cooperative lock ownership, ownership-safe release, append-only event persistence, trailer indexing, and event-tail recovery. Evidence registration builds on that substrate without changing the normative assessment schema.

## Decision

### Durable metadata writes

`atomic_write_bytes` flushes file data, performs atomic replacement, and flushes the parent directory on POSIX. Transaction-directory creation, rename, cleanup, and rollback object removal also flush the affected directories. These controls reduce the gap between process-visible completion and crash-durable metadata.

### Case-level registration lock

Every registration and recovery pass acquires `evidence/registration.lock` through the durable local-filesystem lock protocol. Recovery, ID allocation, transaction preparation, case-state writes, event completion, and terminal journal updates occur under this lock.

A live same-host local owner retains its lock after the recorded lease timestamp. Immediate recovery applies to a dead same-host owner. Lease-expiry takeover applies only to the cooperative shared-filesystem profile. A foreign local-profile lock fails closed.

The lock coordinates cooperative filesystem writers. It carries no identity, custody, or institutional authority.

### Write-ahead transaction directory

Each registration creates:

```text
evidence/transactions/EVTX-<uuid>/
```

Before any case state changes, the directory receives:

- staged evidence bytes;
- exact predecessor snapshots of the index, assessment, and persistence state;
- exact desired successor snapshots;
- a versioned `journal.json` containing the transaction identity, evidence record, predecessor hashes, successor hashes, object-preexistence state, assessment-event metadata, and the byte-identity boundary.

The journal contains a hash over its complete content excluding the hash field. Every staged predecessor and successor image is verified against its journal hash before application or rollback.

A directory lacking a durable journal enters `evidence/transaction-orphans/`. The workbench preserves its bytes for inspection, records `UNKNOWN_FAIL_CLOSED`, and avoids claims about external state mutation.

### Commit sequence

After durable preparation, the implementation:

1. writes or verifies the content-addressed object;
2. verifies the predecessor index hash and writes the desired index;
3. for linked evidence, verifies predecessor assessment and persistence hashes and writes their desired successors;
4. appends an idempotent `ASSESSMENT_SAVED` event for linked evidence;
5. appends an idempotent `EVIDENCE_ADDED` event;
6. marks the journal `COMMITTED`;
7. removes staged bytes and predecessor/successor snapshot copies.

Both event records carry the transaction ID. Recovery checks the event chain before each append, which permits completion after a crash between the two event writes without duplication.

The terminal journal retains metadata, hashes, state, timestamps, and recovery outcome. It holds no duplicate evidence object or assessment snapshot.

### Recovery decision

The next registration or an explicit recovery call evaluates every non-terminal journal under the registration lock.

**Forward completion** applies only after the object, index, assessment, and persistence files match the desired hashes for the transaction. Recovery then completes any missing transaction events and seals the journal as `COMMITTED`.

**Rollback** applies only after every current durable file matches either the recorded predecessor or recorded successor for that transaction. Recovery restores the exact predecessor bytes. An object created solely by the incomplete transaction is removed only after the restored index confirms that no record references it. The event chain receives `EVIDENCE_REGISTRATION_ROLLED_BACK` with predecessor/successor hashes and `historical_finding_mutation_performed=false`.

**Recovery blocking** applies after journal corruption, staged-image corruption, an unexpected content-addressed object digest, or any case-state hash outside the recorded predecessor/successor set. The journal records `RECOVERY_BLOCKED` where its own integrity permits an update, and software refuses to overwrite the divergent state.

### Historical findings

Rollback restores the complete predecessor assessment bytes captured before registration. It performs no selective deletion, reconstruction, or reinterpretation of historical findings. Forward completion applies the exact desired assessment snapshot prepared for the transaction.

### Digest boundary

SHA-256 verifies byte identity. Digest agreement carries no source-authenticity, evidence-quality, relevance, completeness, lawful-custody, disclosure-authorization, or substantive-validity claim.

## Consequences

- Successful registration returns after object, index, linked assessment/persistence, both transaction events, and terminal journal state are durable.
- Incomplete state recovers through exact predecessor rollback.
- Fully written state recovers through idempotent forward completion.
- A crash between transaction events completes the missing event without duplicating the first.
- Concurrent cooperative registrations allocate unique evidence IDs under one lock.
- Journal and snapshot tampering fail closed.
- Terminal journals retain transaction provenance without duplicate protected content.
- The normative assessment schema and evidence vocabulary remain unchanged.

## Residual risks

- A privileged actor may replace a complete case and its transaction history.
- A writer that ignores the lock protocol may corrupt state.
- Filesystem, kernel, storage-controller, or hardware behavior outside atomic-rename and `fsync` assumptions may still cause loss.
- The shared-filesystem profile depends on coherent exclusive-create and rename semantics plus bounded clock skew.
- Registration provides no evidence authentication, custody proof, legal authorization, or substantive appraisal.
- Backup, retention, legal hold, secure erasure, and disaster recovery remain deployment responsibilities.
- Cross-case, distributed, and database-backed transactions remain outside this architecture.

## Validation

Adversarial tests inject failures after preparation, object write, index write, case write, the first transaction event, and both transaction events. They verify exact rollback, forward completion, event idempotency, journal-hash enforcement, snapshot-hash enforcement, orphan quarantine, divergence blocking, unlinked registration, terminal recovery idempotency, live-local-lock retention, and concurrent evidence-ID allocation.

Issue #23 records implementation and verification evidence.
