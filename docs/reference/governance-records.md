# Governance records and release-control semantics

## Purpose

This reference describes the implemented governance record model used by the canonical observatory release-control path. It defines structural workflow semantics only. It does not authenticate a person or institution, establish substantive validity, or create release authority by itself.

The active completion policy is `GOVPOLICY-2.0.0`. Its authority model is `SINGLE_DESIGNATED_HUMAN_AUTHORITY`, with `fraware` as the designated repository authority. Historical policy v1 remains verifiable under its original semantics and is not retroactively reinterpreted.

## Record graph

```text
exact release inputs
        |
        v
GOVERNANCE_SCOPE_MANIFEST
        |
        v
GOVERNANCE_REVIEWER_OPINION  x 6 mandatory tracks
        |
        +----> superseding opinions when a judgment changes
        |
        v
GOVERNANCE_OWNER_DISPOSITION  when required by policy
        |
        +----> condition register / closure evidence
        |
        v
evaluate_governance_completion()
        |
        v
build_release_readiness_package()
        |
        +----> NOT_READY: stop; preserve blockers
        |
        v
READY_FOR_REAL_AUTHORITY_REVIEW
        |
        v
GOVERNANCE_RELEASE_DECISION / AUTHORIZATION
        |
        v
GOVERNANCE_RELEASE_DECISION / PUBLICATION
```

Every persisted governance record is append-only and is bound to a matching event-chain witness. Later records may supersede earlier records through explicit digest-bound references; they do not rewrite history.

## Record surfaces

| Surface | Storage | Primary schema / implementation | Authority effect |
| --- | --- | --- | --- |
| Governance scope | `governance/scopes/` | `GOVERNANCE_SCOPE_MANIFEST.schema.json`; `governance_scope.py` | Binds exact governed bytes and storage boundaries only |
| Reviewer opinions | `governance/opinions/` | `GOVERNANCE_REVIEWER_OPINION.schema.json`; `governance_opinions.py` | Records claimed review attribution and judgment only |
| Owner dispositions | `governance/owner-dispositions/` | `GOVERNANCE_OWNER_DISPOSITION.schema.json`; `governance_dispositions.py` | Records owner response and condition lineage only |
| Policy evaluation | Deterministic derived object | `evaluate_governance_completion()` | Computes workflow readiness only |
| Readiness package | Deterministic derived object | `build_release_readiness_package()` | Binds candidate, scope, policy, products, withheld claims, and blockers only |
| Release decisions | `governance/release-decisions/` | `GOVERNANCE_RELEASE_DECISION.schema.json`; `governance_release.py` | Records authorization or publication workflow decisions when all admission checks pass |

The event chain and governance transaction journal provide durability and tamper evidence. See [governance transaction recovery](../operations/governance-transaction-recovery.md).

## Governance scope

A scope manifest binds the exact objects reviewed for one release decision. Six logical roles are mandatory:

- `PREDECESSOR_RELEASE`;
- `SUCCESSOR_CANDIDATE`;
- `DELTA`;
- `REOPENING_REGISTER`;
- `PRODUCT_MANIFEST`;
- `WITHHELD_CLAIMS`.

`CORE_CYCLE_EXECUTION` is an optional additional role. Logical roles are unique and canonically ordered. Duplicate object digests, missing required roles, invalid locators, stale digests, or missing referenced bytes fail verification.

Storage boundaries are `PUBLIC_GIT`, `GENERATED_OUTPUT`, `PROTECTED_WORKSPACE`, and `ARCHIVE`. Protected objects use opaque `protected-ref:<identifier>` locators. Public governance records must not contain protected local paths or protected evidence bodies.

A recorded scope is deliberately non-authorizing: `release_authorization_performed` remains `false`.

## Mandatory review tracks

The active v2 policy requires one designated-authority review on each track:

1. `SECURITY`
2. `METHODOLOGY`
3. `DATA_GOVERNANCE`
4. `ACCESSIBILITY`
5. `DOMAIN`
6. `AFFECTED_COMMUNITY`

The designated reviewer key is `fraware`, and the human accountability state admitted by the active policy is `CLAIMED_HUMAN_REVIEWER`.

A reviewer claim also records `name_or_role`, `independence_statement`, and `conflict_of_interest_disclosure`, with `organization` optional at the schema layer. These fields remain auditable record content. Under v2, claimed independence and a no-conflict marker are not threshold requirements because explicit role consolidation is allowed.

Other identities may record opinions. Their opinions remain visible in the evidence record but do not satisfy the designated-authority threshold and do not acquire repository decision or veto authority.

## Opinion states under v2

| State | Counts as designated support | Owner disposition required | Active release effect |
| --- | --- | --- | --- |
| `SUPPORT` | Yes | No | Satisfies the track if the designated-authority claim is valid |
| `SUPPORT_WITH_CONDITIONS` | Yes | Yes | Can satisfy support; unresolved `BLOCKS_RELEASE` conditions still block release |
| `OBJECT` | No | Yes | Active designated-authority objection blocks release |
| `REQUEST_EVIDENCE` | No | Yes | Active designated-authority evidence request blocks release |
| `ABSTAIN` | No | No | Preserved, but does not satisfy the support threshold |

An owner disposition does **not** erase an active `OBJECT` or `REQUEST_EVIDENCE`. If the designated authority's judgment changes after review, evidence, or remediation, the earlier opinion must be explicitly superseded by a new opinion on the same scope and track. The supersession record binds the predecessor opinion ID and digest.

Only one active opinion is allowed per reviewer, track, and scope. Recording a replacement without explicit supersession fails closed.

## Owner dispositions and conditions

Disposition states are:

- `ACCEPT`;
- `ACCEPT_WITH_ACTION`;
- `REJECT`;
- `DEFER`;
- `REQUEST_FURTHER_REVIEW`.

Under active v2, a disposition on the decision path must use owner key `fraware`. A disposition from another owner identity remains auditable but fails the owner-authority threshold.

`REJECT`, `DEFER`, and `REQUEST_FURTHER_REVIEW` are blocking owner states. `ACCEPT_WITH_ACTION` requires at least one condition.

Condition records preserve:

- immutable condition identity and description;
- owner;
- priority: `CRITICAL`, `HIGH`, `MEDIUM`, or `LOW`;
- status: `OPEN`, `IN_PROGRESS`, or `RESOLVED`;
- release effect: `BLOCKS_RELEASE` or `NON_BLOCKING`;
- closure evidence for a resolved condition.

A `RESOLVED` condition requires a closure-evidence reference. An unresolved condition with `release_effect = BLOCKS_RELEASE` prevents readiness. A superseding disposition must preserve the exact predecessor opinion set and immutable condition fields.

## Completion evaluation

`evaluate_governance_completion()` is deterministic and non-authorizing. It binds:

- scope ID and scope digest;
- current policy ID, version, and digest;
- every opinion ID and digest in scope;
- every owner-disposition ID, digest, and condition-register digest in scope.

The evaluation reports both visible consensus and designated-authority decision consensus. It also reports missing track coverage, missing owner dispositions, active blocking opinions, non-designated blocking opinions, blocking owner dispositions, unresolved conditions, and release-blocking conditions.

`release_readiness = SATISFIED` requires all six tracks to satisfy their active v2 requirements and all structural integrity checks to pass. The evaluation itself sets `release_authorization_performed`, `canonical_successor_authorized`, and `publication_authorized` to `false`.

## Readiness package

`build_release_readiness_package()` recomputes the current governance evaluation and binds it to the exact successor candidate and release products. The package validates, among other things:

- successor-candidate validity;
- exact predecessor digest;
- exact candidate artifact digest;
- equality between the candidate artifact and the `SUCCESSOR_CANDIDATE` artifact bound in the governance scope;
- current governance policy identity and digest;
- reviewer-opinion and owner-disposition references;
- product IDs and digests;
- withheld-claims digest;
- absence of unresolved release-blocking conditions.

Only a package with `readiness_state = READY_FOR_REAL_AUTHORITY_REVIEW`, an empty `blocker_codes` list, and no release-blocking conditions can enter the final decision functions.

The package remains non-authorizing and is recomputed at final decision time. A stale scope, stale policy, changed candidate, changed product set, changed opinions, changed dispositions, or changed withheld claims therefore changes the binding and fails the intended exact-input path.

## Authorization and publication

Canonical release-control decisions are persisted through `record_release_authorization()` and `record_release_publication()`.

For both decision types:

- the decision actor must be exactly `fraware` under the current policy;
- the readiness package must be bound to the current v2 policy ID, version, and digest;
- the authority claim must use accountability state `CLAIMED_EXTERNAL_RELEASE_AUTHORITY`;
- execution mode must be `PROTECTED_REAL_GOVERNANCE`;
- authority evidence must be represented by an opaque `protected-ref:` plus a SHA-256 digest;
- the software records claimed authority evidence but does not authenticate external delegation.

Publication additionally requires exactly one prior stored authorization for the same candidate and exact readiness package. It records publication evidence using a `public-ref:` or `protected-ref:` plus digest. The publication record does not perform publication automatically; `automatic_publication_performed` remains `false`.

A candidate can have at most one authorization record, and an authorization can have at most one publication record.

## Legacy successor gate

The successor candidate contains a historical/local `release_gate` state for compatibility with earlier workflow mechanics. It is not the active canonical authorization mechanism.

The current readiness builder classifies a candidate whose current gate or gate history contains `AUTHORIZED` or `PUBLISHED` as `LEGACY_LOCAL_AUTHORITY_CLAIM_NOT_GOVERNANCE_COMPLETE` and adds blocker `LEGACY_LOCAL_AUTHORITY_GATE_PRESENT`.

Canonical v2 authorization and publication therefore come from governance release-decision records, not from mutating the candidate's legacy gate.

## Verification surfaces

The principal non-mutating verification functions are:

- `verify_governance_scope_records()`;
- `verify_governance_reviewer_opinions()`;
- `verify_governance_owner_dispositions()`;
- `evaluate_governance_completion()`;
- `build_release_readiness_package()`;
- `verify_governance_release_decisions()`;
- `verify_release_decision_binding()`.

A failed verifier is a stop condition. Do not repair governance history by hand. Use the transaction-recovery procedure and, where necessary, a reviewed migration with explicit before/after hashes.

## Authority boundary

These records establish repository workflow state and cryptographic binding. They do not establish scientific truth, clinical safety or effectiveness, regulatory or legal authorization, system conformance, institutional delegation, external endorsement, or publication by an external body.