# Online-first Phase 2B: prior-capture fallback and replay

Status: bounded migration architecture. This document does not change the Workbench default scheduler or production execution mode.

Phase 2B extends the opt-in Phase 2A policy-bound acquisition path with explicit continuity modes while preserving the acquisition/evidence authority boundary.

## Execution semantics

`ONLINE_REQUIRED` remains live-only. A source or network failure remains a source or network failure and stored evidence is never substituted.

`ONLINE_PREFERRED` executes the live path first. A prior capture is eligible only after the configured live attempt sequence reaches a terminal retryable failure, and only when every logical source represented by the retrieval target explicitly permits `EXPLICIT_PRIOR_CAPTURE_ALLOWED` under the exact acquisition policy. Policy, origin, rights, security, and other non-retryable blocks are ineligible for fallback.

`REPLAY_ONLY` is implemented by a separate executor. It does not construct the HTTP adapter, DNS guard, or transport path and records zero network attempts.

## Immutable capture binding

Prior captures are derived from existing collector result records and their quarantined bytes. Eligibility requires the result record to identify an HTTP(S) requested URL, original `result_id`, `retrieved_at`, content SHA-256, byte size, media type, filename, and quarantine path. The referenced bytes must exist and match both the recorded size and SHA-256.

Selection is deterministic per normalized retrieval URL. The selected capture is the latest eligible capture at or before the run `as_of` cutoff, with `result_id` as the tie-breaker for equal timestamps. A date-only `as_of` is interpreted as 23:59:59 UTC for this bounded executor. The selected capture binding and a deterministic selection digest are included in the target/run binding before target execution.

A later capture therefore changes the binding of a new run; it cannot silently replace the capture already bound to an existing run or checkpoint lineage.

## Provenance

Fallback and replay reuse the original result identity. They do not mint a new collector result, rewrite `retrieved_at`, or present stored bytes as a current observation. Run outcomes record the acquisition route (`LIVE`, `PRIOR_CAPTURE_FALLBACK`, or `REPLAY`), original result identity, original capture timestamp, content SHA-256, and capture age relative to the run cutoff.

For `ONLINE_PREFERRED`, a successful live result always wins over an available prior capture. Fallback is an explicit continuity state, not an implicit cache hit.

## Interruption and resume

When live execution has reached a terminal retryable failure and a pre-bound fallback is available, the scheduler writes a durable nonterminal checkpoint before applying fallback. The checkpoint uses the existing run-ledger `INTERNAL_ERROR` state with a `fallback_pending` marker; this avoids expanding the run-ledger state schema during Phase 2B while preserving restartability. A resumed target with that marker applies the exact bound capture before any new live attempt.

Terminal fallback or replay checkpoints remain idempotent under normal run-ledger resume semantics.

## Authority boundary

Prior-capture continuity does not establish source truth, evidence validity, canonical S2 admission, assessment mutation, release authority, or publication authority. The legacy scheduler and Phase 2A scheduler remain separately available and unchanged. Phase 3 must still prove controlled live/replay equivalence, interruption behavior, and operational accounting before any later change to the production default is considered.
