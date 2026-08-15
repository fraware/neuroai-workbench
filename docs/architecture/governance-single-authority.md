# Single designated human governance authority

## Decision

Governance completion policy v2 uses one designated human authority for repository governance. The designated authority key is `fraware`.

The same designated human may record review opinions, owner dispositions, authorization, and publication decisions. These roles are consolidated at the human-authority layer but remain separate records and separate append-only events.

The authority model is a repository decision-right model. It does not authenticate an institution, convert workflow integrity into substantive validity, or collapse the release state machine into one approval event.

## State machine

```text
exact governed bytes
      |
      v
scope manifest
      |
      v
six track-specific reviewer opinions
      |
      +----> supersession when a judgment changes
      |
      v
owner dispositions when policy requires them
      |
      +----> condition lineage / closure evidence
      |
      v
completion evaluation
      |
      v
release-readiness package
      |
      +----> blocker => stop
      |
      v
authorization decision
      |
      v
publication decision, only if separately chosen
```

Each transition consumes exact identifiers and digests from the preceding state. A later record cannot rewrite an earlier record. A changed governed artifact changes the decision basis and requires a new scope instead of retrospective mutation.

## Invariants

Role consolidation does not collapse the governance state machine. Review, disposition, readiness evaluation, authorization, and publication remain distinct stages. Every stage binds exact scope and record digests, and no stage rewrites an earlier governance record.

All six governance review tracks remain mandatory:

- `SECURITY`;
- `METHODOLOGY`;
- `DATA_GOVERNANCE`;
- `ACCESSIBILITY`;
- `DOMAIN`;
- `AFFECTED_COMMUNITY`.

A supporting opinion from the designated authority is required on every track. Opinions from other identities remain attributable and visible, including objections, abstentions, and evidence requests, but they do not satisfy the designated-authority threshold and do not acquire repository decision or veto authority.

When an owner disposition is part of the active v2 decision path, its owner key must match the designated authority. A different owner identity fails readiness. Final authorization and publication actions likewise require the decision actor to match the designated authority and to be bound to the exact current v2 policy digest.

Conditions, supersession history, scope bindings, owner dispositions, and explicit release blockers remain visible. A blocking state asserted by the designated authority, a missing required disposition, a non-designated owner disposition, an unresolved explicit release blocker, a stale policy binding, or a non-designated final actor fails closed.

## Opinion semantics

The designated authority can record `SUPPORT`, `SUPPORT_WITH_CONDITIONS`, `OBJECT`, `ABSTAIN`, or `REQUEST_EVIDENCE`.

`OBJECT` and `REQUEST_EVIDENCE` are active blockers on the designated-authority decision path. An owner disposition can record the programme response to those opinions, but it does not erase the active blocker. If the judgment later changes, the designated authority must record a superseding opinion on the same scope and track.

`ABSTAIN` preserves the judgment but does not satisfy the support threshold.

`SUPPORT_WITH_CONDITIONS` satisfies the support threshold only with the required owner disposition. An unresolved condition explicitly marked `BLOCKS_RELEASE` still prevents readiness.

This distinction preserves disagreement and evidence requests as first-class history instead of treating disposition as retroactive consent.

## Derived readiness versus decision authority

`evaluate_governance_completion()` computes policy satisfaction over exact scope, opinion, disposition, and policy digests. It is deterministic readiness evidence and remains non-authorizing.

`build_release_readiness_package()` binds that evaluation to the exact candidate, predecessor, product digests, and withheld-claims digest. It also remains non-authorizing.

Only the release-decision functions can append canonical authorization/publication workflow records, and they re-evaluate the current inputs at decision time. Stale policy, stale scope, candidate drift, product drift, changed review records, unresolved blockers, or a wrong final actor therefore fail closed instead of inheriting an earlier readiness result.

## Protected authority evidence

The final authorization/publication path requires a real-execution authority claim with an opaque protected evidence reference and digest. The repository record binds that evidence identity without embedding the protected bytes or private path.

This protected evidence requirement is compatible with one designated human authority. It is an evidence-binding requirement, not a second-person requirement.

The software records the claimed authority basis but does not authenticate external delegation. `external_authority_authenticated` remains false in the release-decision record.

## Legacy candidate gate

The successor candidate retains a historical/local release-gate representation from earlier workflow mechanics. Under the current governance path, a candidate containing local `AUTHORIZED` or `PUBLISHED` gate state/history is treated as a legacy authority claim and blocks current readiness.

Canonical v2 authorization and publication are therefore represented by governance release-decision records, not by reinterpreting or advancing the candidate's legacy gate.

## Versioning

`GOVERNANCE_COMPLETION_POLICY.v1.json` remains the historical multi-person policy and retains its original semantics and digest behavior.

`GOVERNANCE_COMPLETION_POLICY.v2.json` is the active single-designated-authority policy. Historical evidence must be evaluated against the policy version it originally bound. Policy migration does not rewrite prior evaluations or records.

The active v2 policy requires one designated `CLAIMED_HUMAN_REVIEWER` on each of the six tracks and explicitly permits role consolidation. Its independence and no-conflict fields remain auditable record content but are not v2 completion thresholds.

## Operational references

- [Governance records and release-control semantics](../reference/governance-records.md)
- [Protected governance execution runbook](../operations/protected-governance-execution.md)
- [Governance transaction recovery](../operations/governance-transaction-recovery.md)
- [Deferred governance boundary](../operations/deferred-governance.md)
- [Observatory successor releases](../reference/successor-releases.md)

## Authority boundary

Single-human repository governance authority is a project decision right. It does not authenticate an external institution or establish scientific truth, clinical safety or effectiveness, regulatory or legal authorization, conformance, institutional endorsement, external adoption, or publication by an external body.

Software integrity checks establish record and workflow properties only. They do not authenticate the human claimant beyond the attribution recorded by the repository workflow.