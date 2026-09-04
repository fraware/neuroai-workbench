# Prior-capture fallback and replay provenance

Status: Phase 2B data-governance boundary. This document does not change canonical S2 authority or publication authority.

Phase 2B distinguishes acquisition route from evidentiary content identity. The same immutable captured bytes may participate in a later continuity or replay execution while retaining the original capture identity and timestamp.

## Required provenance

A prior-capture reference records the original collector `result_id`, logical source and monitor IDs, requested and normalized URL, original `retrieved_at`, content SHA-256, quarantine path, byte size, media type, and original filename. The referenced bytes are revalidated against size and SHA-256 before use.

The run binding records the selected capture for each retrieval target before target execution. Selection is deterministic at the run cutoff. A new capture changes the binding of a new execution; it does not rewrite the lineage of an existing run.

A fallback/replay outcome records its route and the original result identity, capture timestamp, content SHA-256, capture age, and original source identity. It does not mint a replacement collector result or alter the original `retrieved_at`.

## Route semantics

`LIVE` means the target was satisfied by the live acquisition path in that execution.

`PRIOR_CAPTURE_FALLBACK` means an `ONLINE_PREFERRED` execution exhausted an eligible retryable live failure path and then reused the exact policy-authorized bound capture.

`REPLAY` means the replay-only executor reused an exact bound capture with zero network attempts.

These route labels are operational provenance. They are not evidence grades, source-truth dispositions, or canonical-admission decisions.

## Coalesced sources

When multiple logical sources share a retrieval target, fallback is permitted only when every represented source independently permits prior-capture fallback under the exact policy. A coalesced source cannot inherit continuity permission from another logical source.

## Failure accounting

Missing, malformed, substituted, or byte-inconsistent captures are ineligible. Missing replay capture is recorded as an explicit replay failure. Policy/security failure is recorded separately and cannot be converted into fallback success. Interruption before fallback terminalization remains an incomplete operational state until the exact pending binding is resumed or fails closed.

## Canonical boundary

Fallback and replay outputs remain acquisition/run records. They do not directly mutate canonical S2, assessments, release state, or publication products. Any downstream candidate derived from a prior capture retains the capture's original temporal identity and remains subject to the same adjudication and publication authority boundaries as live-derived candidates.
