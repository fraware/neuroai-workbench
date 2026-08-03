# ADR 0006 — Durable event-chain coordination and trailer indexing

## Status

Accepted for the local and cooperative shared-filesystem engineering profiles.

The implementation provides durable filesystem coordination, indexed append preparation, and bounded crash recovery. It does not provide distributed consensus, authenticated identity, hostile-writer fencing, or multi-tenant production integrity.

## Context

Case `events.jsonl` files are hash-chained append logs. Every event commits to its sequence number, predecessor hash, actor, action, payload, and timestamp. The earlier implementation verified the entire chain and rewrote the entire file for every append. It used a best-effort exclusive lockfile containing only the process identifier.

That design had four material limitations:

1. every append required an O(n) full-chain scan and an O(n) file rewrite;
2. a crashed process could leave a stale lock that blocked subsequent writers until manual removal;
3. a process identifier alone could not distinguish a dead process from PID reuse;
4. a crash between event persistence and any future index update had no explicit recovery protocol.

The workbench needs stronger local durability before transactional evidence registration under issue #23. It also needs a cooperative shared-filesystem profile for engineering workflows without implying institutional authentication or distributed consensus.

## Decision

### Structured lock ownership

Each event chain uses a sibling `events.jsonl.lock` ownership record created with exclusive filesystem creation. The record contains:

- a unique lock identifier;
- coordination profile;
- hostname;
- process identifier;
- Linux process-start token when available;
- acquisition time;
- lease-expiration time;
- the explicit authority boundary `FILESYSTEM_COORDINATION_ONLY`.

The local profile recovers a same-host lock immediately when the PID and process-start token identify a dead owner. Both supported profiles recover an expired lease. A malformed lock is recovered only after its lease-age threshold. Recovered lock bytes are preserved in a sibling recovery directory with digest-only metadata.

Lock release checks the unique lock identifier. A process never deletes a lock that has been replaced by another owner. Append operations re-check ownership before the log write, before the trailer write, and before returning.

### Append-only persistence

Events are appended with `O_APPEND`, complete-write handling, and `fsync`. The implementation no longer rewrites the complete event file for an ordinary append.

### Trailer index

Each chain has a content-addressed sibling `events.jsonl.trailer.json` containing:

- trailer format version;
- event count;
- head event hash;
- indexed log size;
- final-event byte offset and length;
- file identity metadata;
- index timestamp;
- trailer hash.

When the trailer and final event validate against the current file identity, append preparation and indexed-head verification are O(1). Full chain verification remains O(n) and remains the authoritative method for detecting arbitrary historical alteration.

A missing, malformed, stale, or identity-mismatched trailer triggers a full-chain verification and deterministic trailer rebuild. A trailer is never trusted solely because its self-hash is valid.

### Crash-tail recovery

A crash after appending event bytes and before persisting the trailer may leave an unindexed suffix. Under the exclusive lock, the implementation:

1. verifies the complete indexed prefix against the trailer;
2. parses the unindexed suffix in order;
3. adopts complete, correctly linked events;
4. truncates incomplete, malformed, or unlinked tail bytes to the last verified boundary;
5. records the discarded byte count and SHA-256 in `events.jsonl.recoveries.jsonl` without duplicating event content;
6. writes a successor trailer.

Recovery is refused when the indexed prefix fails verification.

## Verification modes

`verify_chain(path)` performs full-chain verification and separately reports trailer validity.

`verify_chain(path, mode="head")` validates the trailer and indexed final event in O(1). Its result carries the explicit boundary that indexed-head verification does not detect arbitrary historical alteration.

## Security and authority boundary

The lock and trailer are filesystem coordination and integrity aids. They do not:

- authenticate a person, organization, or institutional role;
- establish source truth or event completeness;
- provide Byzantine fault tolerance or distributed consensus;
- fence a hostile writer that ignores the protocol;
- prevent a privileged actor from replacing an entire workspace and its backups;
- make the local reference server production-ready.

Cooperative writers must use the same append protocol. Shared-filesystem lease recovery assumes sufficiently coherent filesystem semantics and reasonably bounded clock skew. Institutional multi-user deployment remains a separate architecture under issue #9.

## Consequences

- Ordinary append preparation is O(1) when the trailer is current.
- Full historical integrity verification remains available and authoritative.
- Dead local owners and expired leases recover without manual lock deletion.
- Complete events persisted before a trailer-write crash remain recoverable.
- Incomplete tail bytes are removed only after verified-prefix analysis and leave a digest-only recovery record.
- Issue #23 may build transactional evidence registration on a stronger event substrate.
- The remaining concurrency risk concerns hostile or non-cooperating writers, weak remote-filesystem semantics, clock skew, and privileged workspace replacement.

## Validation

The implementation includes adversarial tests for:

- concurrent writers and monotonic sequence allocation;
- active-lock timeout;
- dead-owner, expired-lease, malformed-lock, and PID-reuse recovery;
- ownership-safe lock release;
- trailer tampering and file-identity drift;
- O(1) append preparation;
- complete unindexed-event adoption;
- malformed, incomplete, and unlinked tail recovery;
- refusal to recover over an invalid indexed prefix.

Issue #24 records the implementation and verification evidence.