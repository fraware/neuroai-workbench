# ADR 0006 — Single-writer event chain and concurrency

## Status

Accepted for the local offline profile. Full multi-writer concurrency remains deferred.

## Context

Case `events.jsonl` files are hash-chained append logs. Concurrent writers can interleave reads of the previous head, compute colliding sequence numbers, and corrupt the chain. The default workbench profile is a single local operator on one workstation.

## Decision

1. Document the local profile as **single-writer**. Shared networked filesystems and multi-process writers are out of scope for the reference application.
2. Provide a best-effort exclusive lockfile around `append_event` (`events.jsonl.lock`) to reduce accidental local races. Lock acquisition is not a distributed consensus protocol; a crashed holder can leave a stale lock until timeout.
3. Future institutional deployments that require multi-writer access must introduce an O(1) trailer index, durable lock ownership, and a reviewed concurrency architecture before claiming multi-user integrity.

## Consequences

- Local accidental double-clicks and overlapping CLI/server writes are less likely to corrupt the chain.
- Stale lockfiles can briefly block appends after a crash.
- Concurrent multi-host writers remain unsupported; THREAT_MODEL residual risk records this boundary.
- No institutional authentication or server-side tenancy is implied by the lock.

## Follow-on

Track implementation of durable multi-writer event indexing under GitHub issue #24. Do not claim production multi-user integrity until that work lands with adversarial tests.
