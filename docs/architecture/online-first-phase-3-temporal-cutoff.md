# Online-first Phase 3 temporal cutoff contract

**Status:** bounded Phase 3 proof-harness clarification for #299  
**Scope:** live observation time versus historical replay cutoff  
**General collector/replay semantics:** unchanged

## Temporal distinction

A live collection result has an immutable `retrieved_at` generated at the acquisition boundary. A replay plan has an `as_of` cutoff that determines which already captured observations existed for that replay. These are different temporal facts.

For an exact Phase 3 live/replay equivalence proof, the capture used by replay must satisfy:

```text
exact_live_capture.retrieved_at <= replay_as_of
```

Date-only `as_of` values retain the existing replay convention and resolve to end-of-day UTC. An exact timestamp requires an explicit timezone.

A capture newer than the replay cutoff is not eligible. The proof harness must not move the capture timestamp backward, move the historical cutoff forward implicitly, or treat an older eligible capture as equivalent to the requested live result.

## Exact-result replay binding

The Phase 3 `replay` command now requires `--result-id`. Before replay execution, the runner loads that exact collector result, validates the stored capture reference and bytes, verifies the source binding, and checks temporal eligibility at the requested cutoff. After replay execution, the returned `record_id` must equal the requested `--result-id`.

This second check matters when several captures exist for the same normalized retrieval URL. The general replay scheduler correctly selects the latest eligible capture at the declared cutoff. If that selection differs from the live result named by the Phase 3 operator, the bounded equivalence run fails closed instead of silently comparing different observations.

The live command also validates its completed capture against the declared `as_of` before emitting a Phase 3 live-run reference. A stale cutoff can therefore leave a durable live acquisition record, but it cannot be represented by the proof runner as temporally coherent Phase 3 equivalence evidence.

## Deterministic CI seam

Synthetic Phase 3 tests previously used a fixed `as_of` date while collector result timestamps came from wall clock. The fixture was green only while the wall clock had not advanced past that cutoff. The Phase 3 unit-test seam now fixes the synthetic collector capture time explicitly inside the declared cutoff. The patch is restricted to the Phase 3 runtime-proof test module and does not change production collector clocks, acquisition policy clocks, ordinary replay selection, or historical fallback semantics.

An adversarial temporal test separately proves that a capture with `retrieved_at > as_of` remains ineligible. Exact replay identity assertions remain unchanged.

## Authority boundary

Temporal compatibility establishes only that the exact captured observation existed by the declared replay cutoff and that the proof harness selected the intended result. It does not establish source truth, source completeness, clinical/scientific validity, evidence adjudication, G0/G1/G2 passage, legal authority, canonical S2 admission, release authorization, publication authority, or production readiness.

The external ClinicalTrials.gov execution required by #287 remains a separate controlled operation. This clarification does not execute or satisfy it.
