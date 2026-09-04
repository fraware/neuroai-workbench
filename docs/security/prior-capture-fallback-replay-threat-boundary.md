# Prior-capture fallback and replay threat boundary

Status: Phase 2B security boundary. This document does not authorize an operational-default transition.

Prior-capture fallback changes availability semantics without relaxing the collector's trust model. Stored external content remains untrusted input. Reuse is permitted only when the original collector result record and the exact referenced bytes remain available and the bytes match the recorded SHA-256 and byte count.

## Threat model

A stale, substituted, truncated, deleted, or modified capture must never be accepted as equivalent to the capture originally recorded. Phase 2B therefore binds the original `result_id`, requested URL, `retrieved_at`, SHA-256, byte size, quarantine path, media type, and filename into the selected capture reference and revalidates the result record and bytes before fallback or replay use.

A newly arrived capture must not silently alter a run already in progress. Selection is deterministic before target execution, and the selected capture is part of the run target binding. Resume verifies that exact binding instead of rescanning and selecting a newer object for the existing run lineage.

Authorization failure must not be converted into availability success. `POLICY_BLOCK`, origin mismatch, and other non-retryable policy/security failures remain failures. `ONLINE_PREFERRED` fallback is considered only after terminal retryable live failure, and every logical source represented by a coalesced retrieval target must independently permit prior-capture fallback under the exact acquisition policy.

`REPLAY_ONLY` is isolated from the network path by construction. The replay executor does not construct an HTTP adapter, DNS guard, or transport and records zero live attempts.

## Currentness and provenance

Stored evidence must not be laundered into a claim of current observation. Fallback and replay retain the original result identity, original capture timestamp, original content hash, and an explicit capture age relative to the run cutoff. Their routes are recorded as `PRIOR_CAPTURE_FALLBACK` or `REPLAY`; neither is reported as `LIVE`.

## Interruption boundary

The live-first executor persists a durable fallback-pending marker before applying the pre-bound capture. Restart consumes that exact pending binding before another live attempt. A successfully terminalized fallback remains subject to ordinary run-ledger idempotence.

## Authority boundary

These controls govern acquisition continuity only. They do not adjudicate source truth, validate substantive evidence, mutate assessments or canonical S2, or authorize release or publication. Browser/open-world execution remains outside this Phase 2B boundary.
