# Policy-bound acquisition provenance

Phase 2A records acquisition authorization as operational provenance. It does not convert authorization metadata into evidence, adjudication, assessment, release, or publication authority.

## Required provenance

A policy-bound run binds the exact `policy_id`, `policy_sha256`, `programme_id`, and execution mode into the deterministic scheduler configuration and run manifest. Run summaries record the same acquisition binding together with `route=LIVE`, `fallback_used=false`, and the Phase 2A authority boundary. Retrieval targets and attempts record the live acquisition route; attempts also record the policy digest and execution mode.

Policy-blocked sources are accountable outcomes. Pre-group policy refusals are recorded as explicit source outcomes. Runtime policy refusals are recorded in target/checkpoint provenance as `POLICY_BLOCK` without manufacturing a collector/network failure record.

## Integrity and interruption semantics

The run manifest remains the immutable binding witness for plan, registry, configuration, target, and policy identity. Policy substitution changes deterministic run identity and cannot reuse the prior checkpoint lineage.

The policy-complete run summary is assembled before its single authoritative write. There is no valid intermediate run-summary state that omits the acquisition binding. Summary hashes cover the acquisition metadata included in semantic summary content.

## Retention and access

Phase 2A does not change existing quarantine, rights, retention, or access-control rules. Policy provenance is retained with the run ledger and acquisition records to the extent required by those existing controls. Acquisition authorization should be interpreted only within the policy's programme, execution mode, origin scope, and validity interval.

## Phase 2B and later transitions

Phase 2B must add explicit provenance for prior captures and replay: original capture identity, capture time and age, selection rule, fallback reason, replay route, and interruption/recovery state. Phase 2A records no such fallback and must not imply that one occurred.

Any later default transition must separately define migration and rollback provenance, operational policy ownership, policy-rotation procedures, and compatibility treatment for legacy unbound run histories.
