# Governance append transactions: threat model

## Scope

This threat model covers the local append-only governance persistence mechanism introduced under issue #127. The protected assets are immutable governance records, their exact content digests, secondary digests such as condition-register hashes, prepared transaction journals, and the append-only event-chain commit witness.

The mechanism establishes persistence integrity and recoverability only. Reviewer identity, owner identity, independence, institutional delegation, scientific validity, release readiness, canonical authority, and publication authority remain outside this mechanism.

## Security objectives

The transaction layer must ensure that:

- an uncommitted governance record cannot be mistaken for committed state;
- a durably committed record is not deleted after a caller-side failure;
- transaction identity, record identity, record digest, secondary digests, and event payload remain bound exactly;
- concurrent writers cannot both pass a semantic uniqueness or supersession check against the same prior state;
- corrupt or ambiguous recovery state fails closed;
- historical committed governance records and events are never rewritten to manufacture transaction completeness;
- transaction-control files cannot escape the workspace governance root;
- protected evidence bodies, credentials, private evidence paths, and licensed evidence bytes do not enter transaction journals.

## Trust boundaries

### Workspace filesystem

The implementation assumes ordinary filesystem primitives can fail at any operation boundary. Atomic file replacement and directory fsync are used for individual journal and record persistence. The design does not assume a multi-file filesystem transaction.

### Event chain

The event chain is the commit-witness boundary. Recovery accepts a transaction as committed only when the event chain and trailer verify and exactly one event carries the expected transaction ID, record ID, record digest, secondary digest map, action, and event-payload digest.

### Governance lock

The governance-wide lock serializes recovery, semantic precondition evaluation, immutable record persistence, event append, and commit verification. The event chain retains its own lock. The acquisition order is governance lock first, event-chain lock second.

### Human and institutional authority

Actor strings and reviewer/owner keys are workflow attribution. They are not authentication of human identity or evidence of delegated authority. This transaction layer must never promote those strings into release authority.

## Threats and controls

### T1 — process loss after record persistence and before event append

**Risk:** an orphan JSON record appears durable even though the logical operation never committed.

**Control:** the prepared journal binds the intended record bytes. On recovery, exact record + no matching event is classified as uncommitted and only that new record plus transaction residue are removed.

### T2 — caller receives an error after durable event append

**Risk:** retry logic deletes or duplicates an operation that actually committed.

**Control:** the event is the commit witness. Exact record + exactly one matching event is committed even if the initiating call returned an exception. Recovery retains the record and removes only transaction residue.

### T3 — record substitution or post-write tampering

**Risk:** a different record is accepted under the prepared transaction.

**Control:** the journal binds both the governance record's semantic SHA-256 and the exact serialized record-byte SHA-256. Divergence blocks recovery.

### T4 — transaction/event substitution

**Risk:** an unrelated event is used to commit a prepared record.

**Control:** the event binds transaction ID, record ID, semantic record digest, secondary digest map, and the complete event payload digest. Any mismatch blocks recovery.

### T5 — duplicate commit witnesses

**Risk:** replay or duplication leaves ambiguous transaction cardinality.

**Control:** more than one event carrying the transaction ID is an ambiguous commit state and fails closed.

### T6 — check/write race

**Risk:** two writers both inspect the same active governance state and create conflicting active opinions, dispositions, or supersessions.

**Control:** semantic verification and persistence execute under the same governance-wide lock. Concurrency tests must demonstrate one deterministic commit and one deterministic refusal for conflicting writers.

### T7 — path traversal or transaction-control overwrite

**Risk:** a governance write targets files outside the declared governance root or overwrites lock/journal control state.

**Control:** record targets are resolved below the workspace governance root, normalized, and rejected if they target `transactions/` or `.append.lock`.

### T8 — corrupt journal or event chain

**Risk:** recovery guesses intent and silently destroys evidence.

**Control:** invalid journal schema/control fields, journal hashes, digest encodings, event-chain integrity, or trailer integrity block recovery. Operator intervention is explicit and preserves the unresolved state.

### T9 — protected-data leakage into transaction control records

**Risk:** recovery metadata creates a second copy of sensitive evidence.

**Control:** journals store identifiers, paths relative to the governance root, digests, event action, and event-payload digest. They do not store the governance record body. Protected evidence remains represented by opaque references at the governance layer.

### T10 — authority escalation through successful persistence

**Risk:** a technically committed reviewer or owner record is interpreted as substantive or institutional approval.

**Control:** transaction records carry an explicit persistence-only authority profile and boundary. APIs and diagnostics keep release authorization false. Higher-level policy and release gates remain separate.

## Recovery-blocked state

Recovery stops without destructive repair when it encounters any ambiguous or corrupt state, including record-byte divergence, event without record, duplicate transaction witnesses, invalid event chain, invalid journal hash, conflicting transaction identity, or unsafe path.

Operators preserve the workspace, run non-mutating diagnostics and record-type verifiers, and repair only through an explicit reviewed migration with exact before/after hashes. A missing historical event is never synthesized.

## Residual risks

This design does not defend against a fully compromised host that can coherently rewrite the record, journal, event chain, trailer, code, and verification environment. External repository protections, release attestations, backups, reproducible verification, and later human governance provide additional layers.

It also does not authenticate local actor claims. That limitation is intentional and remains visible in every transaction boundary.
