# Observatory successor releases

The successor package generator builds a reviewable candidate from an immutable predecessor and adjudicated delta. Candidate generation and candidate-local gate history are distinct from the active canonical governance authorization path.

## Candidate state and canonical release control

A successor candidate contains a historical/local `release_gate` object retained for compatibility with earlier workflow mechanics. That object can describe candidate progression, but it is **not** the active canonical authorization mechanism under governance policy v2.

The active canonical path is:

```text
successor candidate
    -> exact governance scope
    -> six mandatory designated-authority reviews
    -> required owner dispositions / condition closure
    -> governance completion evaluation
    -> deterministic release-readiness package
    -> governance AUTHORIZATION decision
    -> governance PUBLICATION decision, if separately chosen
```

Canonical authorization and publication are persisted as `GOVERNANCE_RELEASE_DECISION` records under `governance/release-decisions/`. See [governance records and release-control semantics](governance-records.md) and the [protected governance execution runbook](../operations/protected-governance-execution.md).

## Legacy candidate gate

The candidate-local gate order historically includes:

1. `CANDIDATE`;
2. `REVIEWED`;
3. `AUTHORIZED`;
4. `PUBLISHED`.

Under the current release-readiness builder, a candidate whose current local gate or gate history contains `AUTHORIZED` or `PUBLISHED` is classified as `LEGACY_LOCAL_AUTHORITY_CLAIM_NOT_GOVERNANCE_COMPLETE`. The readiness package adds blocker `LEGACY_LOCAL_AUTHORITY_GATE_PRESENT`.

This is deliberate. A local gate claim cannot be upgraded into current canonical authority by interpretation. The candidate must enter the active governance path without a conflicting legacy authorizing gate history.

Candidate-local gate records remain useful historical workflow evidence. They do not authenticate institutional delegation and do not substitute for current governance release-decision records.

## Active v2 governance requirements

The active policy is `GOVPOLICY-2.0.0`, authority model `SINGLE_DESIGNATED_HUMAN_AUTHORITY`, with `fraware` as the designated repository authority.

All six review tracks are mandatory:

- `SECURITY`;
- `METHODOLOGY`;
- `DATA_GOVERNANCE`;
- `ACCESSIBILITY`;
- `DOMAIN`;
- `AFFECTED_COMMUNITY`.

Each designated review is a separate opinion record bound to the exact governance scope. Required owner dispositions are separate records. Conditions, supersession, objections, abstentions, evidence requests, and non-designated opinions remain visible in the audit history.

An active designated-authority `OBJECT` or `REQUEST_EVIDENCE` blocks readiness until explicitly superseded. `SUPPORT_WITH_CONDITIONS` can satisfy the support threshold only with the required owner disposition, and unresolved conditions marked `BLOCKS_RELEASE` still prevent readiness.

Historical policy v1 remains verifiable under its original semantics. Its multi-person independence requirements do not define active v2 completion.

## Readiness package

`build_release_readiness_package()` validates and binds the exact release basis, including:

- candidate validity and canonical digest;
- exact candidate artifact digest;
- exact candidate artifact digest bound in the governance scope;
- predecessor digest;
- governance scope ID and digest;
- current policy ID/version/digest;
- opinion and owner-disposition references;
- product IDs and digests;
- withheld-claims digest;
- unresolved release-blocking condition IDs;
- blocker codes.

The package is ready only when `readiness_state = READY_FOR_REAL_AUTHORITY_REVIEW` and both blocker collections are empty.

Readiness is deterministic workflow evidence. It does not authorize the candidate.

## Authorization

`record_release_authorization()` records the canonical authorization workflow decision only after the readiness package passes all admission checks.

The current policy requires:

- final actor `fraware`;
- current v2 policy binding;
- real execution mode `PROTECTED_REAL_GOVERNANCE`;
- authority accountability state `CLAIMED_EXTERNAL_RELEASE_AUTHORITY`;
- a non-empty opaque `protected-ref:` authority-evidence reference;
- the SHA-256 digest of that protected authority evidence.

The software records claimed authority evidence but does not authenticate external institutional or legal delegation.

Only one authorization decision is allowed per candidate.

## Publication

`record_release_publication()` is a separate subsequent action. It requires exactly one prior stored authorization and recomputes the same readiness package.

Publication fails if the candidate or readiness package differs from the prior authorization. It also requires publication evidence represented by a `public-ref:` or `protected-ref:` plus digest and final actor `fraware`.

Only one publication decision is allowed per authorization.

The publication record sets governance workflow state to `PUBLISHED`; it does not publish artifacts automatically. `automatic_publication_performed` remains `false`. The real publication mechanism and publication evidence remain a separate operational action.

## Generated candidate objects

A successor candidate includes, among other fields:

- predecessor reference and SHA-256;
- adjudicated delta counts and operation inventory;
- reopening recommendation register;
- changed, unchanged, superseded, and unresolved inventories;
- data-quality report checklist;
- withheld-claims statements;
- historical/local release-gate state and history.

The candidate's own gate history must not be interpreted as the current governance release-decision store.

## Verification

Core successor verification:

```bash
python -m pytest tests/unit/test_successor.py -q
```

Governance release verification is additionally covered by the governance policy, release, authority-guard, adversarial, and transaction test suites.

Relevant schemas include:

- `src/neuroai_workbench/resources/operations/SUCCESSOR_CANDIDATE.schema.json`;
- `src/neuroai_workbench/resources/operations/SUCCESSOR_RELEASE_GATE.schema.json`;
- `src/neuroai_workbench/resources/operations/GOVERNANCE_SCOPE_MANIFEST.schema.json`;
- `src/neuroai_workbench/resources/operations/GOVERNANCE_REVIEWER_OPINION.schema.json`;
- `src/neuroai_workbench/resources/operations/GOVERNANCE_OWNER_DISPOSITION.schema.json`;
- `src/neuroai_workbench/resources/operations/GOVERNANCE_RELEASE_DECISION.schema.json`.

## Boundary

Canonical governance workflow state is a repository release-control state. It does not make underlying source claims true or establish scientific validity, clinical safety or effectiveness, regulatory or legal authorization, system conformance, institutional delegation, external endorsement, or publication by an external body.