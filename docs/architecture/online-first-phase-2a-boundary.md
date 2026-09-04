# Online-first Phase 2A execution boundary

Phase 2A adds an explicit, opt-in policy-bound due-cycle execution path. It does **not** change the default `CollectionScheduler`, scheduled operating mode, evidence authority, assessment state, release authority, or publication authority.

## Execution contract

`PolicyBoundCollectionScheduler` is constructed with one validated acquisition policy, one `programme_id`, and one explicit live execution mode. The exact `policy_id`, `policy_sha256`, `programme_id`, and execution mode are included in the deterministic scheduler configuration and therefore in the run binding and run identity. A policy substitution creates a different run lineage.

Before retrieval-target grouping, each due or included-manual HTTP source is checked against the policy. An unauthorized source becomes an explicit `POLICY_BLOCK` pre-outcome and cannot inherit a result fetched for an authorized source that shares the same normalized target.

For grouped targets, request-scoped logical source IDs are isolated with `ContextVar`. Policy is checked before DNS resolution and again immediately before every transport send. Adapter-resolved URLs and redirect hops therefore require authorization for every logical source represented by the retrieval target.

`POLICY_BLOCK` is an acquisition-permission refusal, not a retryable network or collector failure. It is recorded in run/checkpoint provenance without creating a durable collector failure record.

Policy metadata and the `LIVE` acquisition route are inserted before the policy-bound run summary's single authoritative write. This avoids a crash window in which a valid run summary could omit the acquisition binding.

## Compatibility decision

Issue #283 originally proposed optional all-or-none policy inputs on `CollectionScheduler.run_plan(...)`. Phase 2A instead uses a separate scheduler class. This keeps legacy construction and run binding untouched and makes policy-bound execution structurally opt-in. A later reviewed transition may choose a unified API or make policy binding mandatory; Phase 2A does neither.

## Phase boundaries

Phase 2A covers live policy binding, least-privilege coalescing, resolved-target and redirect enforcement, deterministic policy lineage, and live-route provenance.

Phase 2B remains responsible for prior-capture selection, capture identity and age, fallback accounting, replay execution, and interruption/recovery semantics for fallback. `ONLINE_PREFERRED` in Phase 2A executes only its live path and records `fallback_used=false`. `REPLAY_ONLY` is refused by the HTTP executor.

A later default-transition phase must separately decide whether scheduled operation requires the policy-bound path. Such a transition requires its own compatibility, operational, security, and governance review.

## Authority boundary

Acquisition permission does not establish source truth, evidence sufficiency, adjudication, assessment mutation, release authorization, publication authorization, or governance disposition. Existing public-URL validation, DNS controls, pinned-peer transport, redirect controls, quarantine, scanning, rights/retention controls, and independent live-authorization controls remain additive and authoritative within their own boundaries.
