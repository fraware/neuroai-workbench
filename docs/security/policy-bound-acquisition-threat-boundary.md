# Policy-bound acquisition threat boundary

This document covers the Phase 2A policy-bound live acquisition path only. It does not authorize a production/default-mode transition and does not replace the collector threat model.

## Protected assets and invariants

The protected assets are acquisition-policy integrity, least-privilege source eligibility, deterministic run lineage, request-target authorization, and truthful acquisition provenance.

The central invariant is that no DNS resolution or HTTP send in a policy-bound target may occur unless the actual URL is authorized for every logical source represented by that retrieval target. Acquisition permission remains distinct from source truth, evidence adjudication, assessment mutation, release authority, and publication authority.

## Threats and controls

**Policy substitution or tampering.** The policy is validated on construction and its digest, identity, programme, and execution mode are included in the deterministic scheduler configuration/run binding. Substitution therefore cannot silently resume a prior policy lineage.

**Privilege inheritance through target coalescing.** Individual sources are policy-checked before grouping. Unauthorized sources are removed from retrieval groups and receive explicit `POLICY_BLOCK` outcomes. Authorized coalesced sources share a fetch only when the actual request URL is permitted for all bound source IDs.

**Adapter origin expansion.** The adapter-resolved request URL is policy-checked before collection. Existing public-URL, DNS, and pinned-peer controls remain in force.

**Redirect origin expansion.** The request-scoped logical-source set is retained across redirects. Policy is checked before DNS resolution of a redirect destination and again immediately before its transport send. A forbidden redirect does not resolve or send to the forbidden host.

**Cross-worker source-scope corruption.** Request scope uses `ContextVar`, is reset after use, and is not shared through mutable process-global state.

**Misclassification of policy refusal as network failure.** `POLICY_BLOCK` is non-retryable acquisition refusal. It does not create a durable collector failure record or enter ordinary network retry accounting.

**Incomplete authoritative summary after interruption.** Policy acquisition metadata is composed before the policy-bound run summary's single authoritative write. Tests pin both base-accounting equivalence and one-write behavior.

## Residual risk and excluded scope

Phase 2A does not implement prior-capture fallback, replay, capture-age validation, fallback interruption/recovery, or an operational default switch. Those mechanisms create additional stale-data, provenance, rollback, and availability threats and belong to Phase 2B or a later reviewed transition.

Policy authorization also does not certify content safety, rights, provenance quality, source authenticity, evidentiary sufficiency, or release fitness. Those remain governed by their existing independent controls.
