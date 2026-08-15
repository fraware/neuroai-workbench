# Single designated human governance authority

## Decision

Governance completion policy v2 uses one designated human authority for repository governance. The designated authority key is `fraware`.

The same designated human may record review opinions, owner dispositions, authorization, and publication decisions. These roles are consolidated at the human-authority layer but remain separate records and separate append-only events.

## Invariants

Role consolidation does not collapse the governance state machine. Review, disposition, readiness evaluation, authorization, and publication remain distinct stages. Every stage binds exact scope and record digests, and no stage rewrites an earlier governance record.

All six governance review tracks remain mandatory. A supporting opinion from the designated authority is required on every track. Opinions from other identities remain attributable and visible, including objections, abstentions, and evidence requests, but they do not satisfy the designated-authority threshold and do not acquire decision or veto authority.

When an owner disposition is part of the active v2 decision path, its owner key must match the designated authority. A different owner identity fails readiness. Final authorization and publication actions likewise require the decision actor to match the designated authority and to be bound to the exact current v2 policy digest.

Conditions, supersession history, scope bindings, owner dispositions, and explicit release blockers remain visible. A blocking state asserted by the designated authority, a missing required disposition, a non-designated owner disposition, an unresolved explicit release blocker, a stale policy binding, or a non-designated final actor fails closed.

## Versioning

`GOVERNANCE_COMPLETION_POLICY.v1.json` remains the historical multi-person policy and retains its original semantics and digest behavior.

`GOVERNANCE_COMPLETION_POLICY.v2.json` is the active single-designated-authority policy. Historical evidence must be evaluated against the policy version it originally bound. Policy migration does not rewrite prior evaluations or records.

## Authority boundary

Single-human repository governance authority is a project decision right. It does not authenticate an external institution or establish scientific truth, clinical safety or effectiveness, regulatory or legal authorization, conformance, institutional endorsement, external adoption, or publication by an external body.

Software integrity checks establish record and workflow properties only. They do not authenticate the human claimant beyond the attribution recorded by the repository workflow.
