# Governance transaction data boundary

## Purpose

This document defines what data the issue #127 crash-consistency layer is permitted to persist. It complements the transaction ADR, recovery runbook, and threat model.

## Data classes

### Immutable governance record

The record body remains in its record-type directory, for example governance scope manifests, reviewer opinions, owner dispositions, and future release-decision records. The transaction layer does not duplicate the record body into its journal.

The substantive record schema owns decisions about which public, generated, archival, or opaque protected references are permitted.

### Prepared transaction journal

A prepared journal is control-plane metadata. It can contain:

- transaction ID;
- prepared timestamp;
- normalized record path relative to the governance root;
- record ID;
- semantic record SHA-256;
- exact serialized record-byte SHA-256;
- secondary digest names and SHA-256 values;
- event action;
- complete event-payload SHA-256;
- persistence-only authority profile and boundary;
- journal SHA-256.

A prepared journal must not contain:

- governance record bodies;
- protected capture bytes;
- credentials, tokens, cookies, or authorization headers;
- private filesystem evidence paths;
- licensed evidence bytes;
- raw source documents copied solely for transaction recovery;
- new private human identity data that is absent from the intentional governance record/event metadata.

### Event commit witness

The event can carry the record type's intentionally public/local governance metadata plus the transaction envelope:

- transaction ID;
- transaction record ID;
- transaction record SHA-256;
- named secondary digest map.

The event remains subject to the existing event-log governance boundary. Transaction support is not permission to add protected evidence bodies to events.

### Locks

Lock files contain coordination metadata only. They are not governance evidence and must not contain substantive record bodies or protected evidence.

## Protected evidence

Protected captures remain outside Git. Governance records can refer to protected material through approved opaque references and digests. Transaction journals can bind the digest of the governance record or an intentionally supplied secondary digest; they do not materialize the protected object.

Recovery operates on governance record bytes and transaction metadata. It does not dereference protected evidence to decide whether a transaction committed.

## Historical records

Pre-transaction governance records are not rewritten to add transaction identifiers. Their existing exact record/event bindings are classified by the legacy diagnostic. An exact legacy binding can remain valid under the record-type verifier. Missing, duplicate, or divergent bindings remain explicit unresolved states.

No migration may manufacture historical actor identity, reviewer independence, owner authority, release authority, or protected evidence content.

## Retention and deletion semantics

For an interrupted pre-commit transaction, recovery can delete only:

- the exact newly created record whose serialized bytes match the prepared journal; and
- the corresponding prepared transaction journal.

Recovery does not delete a record with divergent bytes and does not alter previously committed governance records or historical events.

For a transaction with an exact durable commit-witness event, recovery retains the record and removes only the prepared journal.

A recovery-blocked state preserves all unresolved material for explicit investigation.

## Repository boundary

Transaction journals are runtime workspace state. They are not evidence artifacts for source control and should not be committed as ordinary repository data. Documentation, schemas, code, and synthetic fixtures can be version controlled; live prepared transaction residue cannot.

## Authority boundary

Data integrity is orthogonal to governance authority. A transaction can be internally valid even when the associated governance opinion is an abstention, objection, evidence request, local owner claim, synthetic rehearsal record, or other non-authorizing state.

The transaction layer never converts data availability into research reporting, regulatory status, clinical benefit, operational deployment, commercial availability, conformance, scientific approval, or release authorization.
