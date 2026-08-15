# High-assurance governance records

## Purpose

This reference describes the repository's multi-record governance machinery. It remains supported for historical verification and for programmes that intentionally choose the optional high-assurance profile. It is no longer the default canonical release path.

The default path is the proportional [release attestation](../architecture/release-attestation.md): one designated-maintainer record containing six domain judgments and an explicit `AUTHORIZE` or `WITHHOLD` decision, followed by a separate publication record when publication is chosen.

## High-assurance record graph

```text
exact release inputs
    -> GOVERNANCE_SCOPE_MANIFEST
    -> GOVERNANCE_REVIEWER_OPINION records
    -> GOVERNANCE_OWNER_DISPOSITION records when required
    -> evaluate_governance_completion()
    -> build_release_readiness_package()
    -> GOVERNANCE_RELEASE_DECISION / AUTHORIZATION
    -> GOVERNANCE_RELEASE_DECISION / PUBLICATION, if chosen
```

Every persisted record is append-only and has a matching event-chain witness. Explicit supersession preserves prior judgments. The governance transaction journal protects record/event consistency across interrupted writes.

## Active v2 semantics inside this profile

`GOVPOLICY-2.0.0` uses `SINGLE_DESIGNATED_HUMAN_AUTHORITY` with `fraware` as the designated repository authority. Historical policy v1 remains verifiable under its original semantics.

The six review tracks are `SECURITY`, `METHODOLOGY`, `DATA_GOVERNANCE`, `ACCESSIBILITY`, `DOMAIN`, and `AFFECTED_COMMUNITY`. An active designated `OBJECT` or `REQUEST_EVIDENCE` blocks high-assurance readiness until explicitly superseded. `SUPPORT_WITH_CONDITIONS` requires the corresponding disposition, and an unresolved condition marked `BLOCKS_RELEASE` remains blocking.

Role consolidation is permitted under v2. Separate opinion and disposition records therefore express stronger audit granularity; they do not create additional independent decision makers when one designated person occupies the roles.

## Release-decision semantics

The high-assurance `GOVERNANCE_RELEASE_DECISION` store remains positive-only. It records `AUTHORIZATION` / `AUTHORIZED` and `PUBLICATION` / `PUBLISHED`. This limitation applies only to this optional profile.

The default release-attestation profile has first-class typed `AUTHORIZE` and `WITHHOLD` outcomes and does not require protected external-authority evidence from the designated repository maintainer.

High-assurance authorization still uses the current protected-evidence admission rules implemented by `governance_release.py`. Choosing this profile is therefore an explicit programme decision to require the additional evidence and record choreography.

## When to use this profile

Use the high-assurance path when the programme needs one or more of the following:

- separately attributable review records for audit or delegation;
- explicit owner-disposition and condition lineage;
- protected authority-evidence binding;
- historical compatibility with v1/v2 governance records;
- a programme-specific control framework that requires the additional record surfaces.

Those properties are optional repository controls. They are not prerequisites for a default release attestation.

## Verification

The existing verifiers remain authoritative for this profile:

- `verify_governance_scope_records()`;
- `verify_governance_reviewer_opinions()`;
- `verify_governance_owner_dispositions()`;
- `evaluate_governance_completion()`;
- `build_release_readiness_package()`;
- `verify_governance_release_decisions()`;
- `verify_release_decision_binding()`.

See [governance transaction recovery](../operations/governance-transaction-recovery.md) for persistence failures and [protected governance execution](../operations/protected-governance-execution.md) for the optional operator procedure.

## Authority boundary

These records establish repository workflow state only. They do not authenticate institutional delegation or establish scientific validity, clinical safety or effectiveness, regulatory or legal authorization, conformance, external endorsement, or publication by an external body.
