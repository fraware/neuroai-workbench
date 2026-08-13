# Six-track governance completion policy

## Purpose

The governance completion evaluator converts verified governance records into a deterministic **workflow-readiness** result. It evaluates whether the structurally recorded review package satisfies a versioned policy. It does not perform review, authenticate people, confer institutional authority, or authorize a release.

Policy v1 is stored as `GOVERNANCE_COMPLETION_POLICY.v1.json` and is content-addressed at evaluation time. A policy change produces a new policy digest and a new evaluation. Historical evaluations are not retroactively reinterpreted under a later policy.

## Tracks

Policy v1 treats six tracks as applicable:

- `SECURITY`
- `METHODOLOGY`
- `DATA_GOVERNANCE`
- `ACCESSIBILITY`
- `DOMAIN`
- `AFFECTED_COMMUNITY`

An absent affected-community review is therefore an explicit coverage gap, not an implicit pass.

## Reviewer-claim threshold

For each track, v1 requires at least:

- two active records carrying the accountability state `CLAIMED_HUMAN_REVIEWER`;
- two of those claimed-human records in a supporting state (`SUPPORT` or `SUPPORT_WITH_CONDITIONS`);
- two distinct claimed organizations;
- a non-empty claimed-independence statement for each counted reviewer;
- a machine-readable no-conflict declaration for each counted reviewer.

These fields are **claims recorded by the workflow**. They are not proof of identity, independence, institutional affiliation, delegation, expertise, or authorization. A future real-governance process is responsible for authenticating those properties outside this evaluator.

Synthetic rehearsal/test records can exercise the schema and evaluator but are never evidence that real-human review occurred.

## Opinion semantics

`SUPPORT` and `SUPPORT_WITH_CONDITIONS` contribute to the support threshold.

`ABSTAIN` contributes zero support. It remains visible in the track result.

`OBJECT` remains a blocking opinion state and remains visible even if a claimed owner records a disposition over it.

`REQUEST_EVIDENCE` remains a blocking opinion state and remains visible even if a claimed owner records a disposition over it.

This preserves the distinction between recording how an owner handled an opinion and resolving the substantive concern expressed by the reviewer.

## Owner dispositions and conditions

Policy v1 expects an owner disposition for active opinions in these states:

- `SUPPORT_WITH_CONDITIONS`
- `OBJECT`
- `REQUEST_EVIDENCE`

The owner-disposition states `REJECT`, `DEFER`, and `REQUEST_FURTHER_REVIEW` are workflow blockers under v1.

Unresolved conditions with `release_effect = BLOCKS_RELEASE` block workflow release readiness. Unresolved `NON_BLOCKING` conditions remain visible without independently failing the readiness gate.

Owner records remain claimed workflow attribution. Owner disposition does not erase an objection, satisfy an evidence request, authenticate delegation, or establish scientific validity.

## Conflict and structural-independence fields

Policy v1 uses explicit machine-readable prefixes:

- `NO_CONFLICT_DECLARED`
- `CONFLICT_DECLARED`

A free-form disclosure without one of the policy markers does not satisfy the no-conflict rule. A declared conflict fails structural independence for that track. Two records claiming the same organization fail the two-organization threshold.

These checks establish only **structural sufficiency of the stored claims**. They do not independently investigate or authenticate conflicts, organizations, or reviewer independence.

## Deterministic input binding

Every evaluation binds:

- exact governance scope ID and SHA-256;
- policy ID, version, and SHA-256;
- the complete same-scope opinion history by opinion ID and SHA-256, including superseded records;
- the complete same-scope owner-disposition history by disposition ID and SHA-256;
- each disposition's condition-register SHA-256.

The evaluator hashes this input binding, then hashes the evaluation itself. Superseded history remains evidentially bound even though only active records determine current policy state.

## Output dimensions

The evaluator keeps separate:

- input integrity;
- scope binding;
- track coverage;
- consensus state;
- claimed structural independence;
- abstention;
- disagreement/objection;
- evidence requests;
- missing required owner dispositions;
- unresolved conditions;
- explicit release-blocking conditions;
- affected-community coverage;
- workflow release readiness.

This separation prevents one aggregate status from concealing a missing track, minority objection, evidence request, conflict, or unresolved release blocker.

## Readiness versus authority

`release_readiness = SATISFIED` means only that the exact hash-bound governance records satisfy the selected workflow policy. Every evaluation also reports:

- `release_authorization_performed = false`
- `canonical_successor_authorized = false`
- `publication_authorized = false`

The evaluator has no code path that converts structural readiness into release authority.

In particular, a readiness result does not establish reviewer identity, institutional delegation, scientific or clinical validity, regulatory designation, marketing authorization, system conformance, UNESCO endorsement, canonical successor authority, or publication authority.

## Policy evolution

A policy revision receives a distinct policy ID/version and content digest. Existing evaluations retain the policy digest used to produce them. New policy thresholds do not retroactively alter an older evaluation object.

A future governance process can explicitly choose the policy version applicable to a release decision and bind that exact policy/evaluation digest in the release-authority layer.