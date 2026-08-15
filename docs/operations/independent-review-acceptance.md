# Independent review acceptance

## Purpose

This document defines an **optional external-review evidence scaffold** for issue #10 and stronger institutional-readiness claims. It is distinct from the active v2 governance-completion policy used for canonical observatory release control.

The two layers intentionally share domain labels such as security, methodology, accessibility, and affected-community review, but they use different record types, authority semantics, and completion criteria.

## Critical distinction

### Mandatory v2 governance review

Canonical governance completion under `GOVPOLICY-2.0.0` requires six separate designated-authority reviewer opinions:

- `SECURITY`;
- `METHODOLOGY`;
- `DATA_GOVERNANCE`;
- `ACCESSIBILITY`;
- `DOMAIN`;
- `AFFECTED_COMMUNITY`.

Those opinions are recorded through the governance opinion store and are evaluated by `evaluate_governance_completion()`. The designated repository authority is `fraware`.

Mandatory v2 governance review is documented in [governance records and release-control semantics](../reference/governance-records.md) and the [protected governance execution runbook](protected-governance-execution.md).

### Optional external independent review

The scaffold on this page records additional claimed independent-review evidence through `independent_review.py`. It is useful for stronger statements about institutional readiness, external security assessment, independent methodological review, representative-user accessibility evidence, domain review, or affected-community engagement.

These optional independent-review records:

- do not satisfy the six mandatory v2 designated-authority opinion requirements by themselves;
- do not authorize a canonical successor;
- do not publish a successor;
- do not authenticate institutional delegation;
- do not establish scientific, clinical, regulatory, legal, conformance, or deployment claims.

The designated authority may cite valid external-review artifacts as evidence in a separate v2 governance opinion. The external-review disposition itself does not become a v2 opinion automatically.

## Relationship to canonical release control

Optional external review is **not a universal prerequisite** for repository canonical authorization under active v2. Its absence can still matter substantively: the designated authority may record an objection, evidence request, condition, or withholding decision when external review is needed for the actual release basis.

Conversely, completion of every optional external-review track does not create canonical authorization. The active canonical sequence remains:

```text
exact governance scope
    -> six mandatory v2 reviewer opinions
    -> required v2 owner dispositions / condition closure
    -> governance completion evaluation
    -> release-readiness package
    -> authorization decision
    -> publication decision, if separately chosen
```

Do not use the successor candidate's historical/local release-gate state as a substitute for this sequence. See [observatory successor releases](../reference/successor-releases.md).

## External-review boundary

Independent-review acceptance records use claimed local attribution. Software can preserve scope, claimed reviewer identity, disposition, conditions, findings references, and integrity; it cannot commission reviewers, authenticate identities, determine independence as a real-world fact, or confer authority.

Automated checks and internal preparation can support an external review but do not substitute for the named independent expert, representative user, or affected-community participant when such evidence is claimed.

Passing schema validation, hash verification, or disposition completeness does not establish institutional-pilot readiness, security acceptance, methodological correctness, accessibility conformance, or release authorization.

## Recommended external-review tracks

Each track, when commissioned, should have a named reviewer, documented scope, conflict-of-interest disclosure, findings-register reference where applicable, and an append-only disposition record.

| Track | Primary focus |
|---|---|
| Security | Local-server boundary, path handling, evidence integrity, event-chain tampering, dependency risk, release provenance |
| Methodology | Requirement interpretation, evidence-state distinctions, prohibited-inference enforcement, migration preservation, reviewer-authority model |
| Data governance | Protected-evidence exchange metadata, retention, disclosure, participant-data boundaries, federated evidence handling |
| Accessibility | Keyboard operation, screen-reader semantics, focus order, contrast, error recovery, report accessibility, representative-user testing |
| Domain | Independent domain expert review of substantive claim boundaries, system identity, and assessment conclusions |
| Affected community | Participant or community representative review of burden, consent language, remedy routes, and public-facing information |

## Pre-review preparation

Before commissioning an external review:

1. Freeze the external-review scope artifact and record its SHA-256 digest.
2. Publish or privately agree the reviewer scope, independence criteria, and conflict-of-interest template as appropriate.
3. Identify the stronger claim for which the external evidence is relevant.
4. Confirm that no canonical release or institutional-readiness claim will be inferred solely from the external-review disposition.
5. Identify any protected evidence and custody constraints before access is granted.

## Security checklist

- [ ] Review scope fixed before testing.
- [ ] Local-server binding, network exposure, and container defaults reviewed.
- [ ] Path traversal, archive handling, and safe-join boundaries reviewed.
- [ ] Evidence-byte integrity and replacement detection reviewed.
- [ ] Event-chain tampering and append-only record semantics reviewed.
- [ ] Dependency, supply-chain, and release-provenance controls reviewed.
- [ ] Future authenticated deployment design reviewed separately from the local reference server.
- [ ] Every finding has an owner, priority, evidence, and closure condition.
- [ ] Unresolved risks remain visible or explicitly access-controlled with rationale.

## Methodology checklist

- [ ] Requirement interpretation and v4.2 kernel boundaries reviewed by an appropriate independent expert.
- [ ] `PASS`, `PARTIAL`, `FAIL`, and `NOT ASSESSED` use reviewed for semantic drift.
- [ ] Unavailable, inaccessible, and unresolved evidence remain distinct states.
- [ ] Prohibited-inference enforcement reviewed.
- [ ] Migration preservation and successor-record semantics reviewed.
- [ ] Conformance-level calculation and authority boundaries reviewed.
- [ ] Disagreement and abstention records preserved without erasure.
- [ ] No stronger claim inferred solely from schema validity or test success.

## Data-governance checklist

- [ ] Protected-evidence exchange remains metadata-only where required.
- [ ] No protected neural, participant, clinical, regulatory, or credential material is placed in public storage.
- [ ] Retention, disclosure, and destruction rules are named for exported copies.
- [ ] Federated evidence handling preserves custody and access-state boundaries.
- [ ] Data-governance controls are updated when exchange or workspace boundaries change.
- [ ] Withheld claims are reviewed for outward-facing language.

## Accessibility checklist

- [ ] Keyboard-only operation verified for primary workflows.
- [ ] Screen-reader semantics and focus order verified.
- [ ] Contrast and non-color status communication verified.
- [ ] Error recovery and form comprehension verified.
- [ ] Report and export accessibility verified.
- [ ] Claimed representative-user validation actually includes representative users.
- [ ] Accessibility findings are tracked to owner and closure condition.

## Domain checklist

- [ ] Independent domain expert identified and scope fixed.
- [ ] Exact system, configuration, population, endpoint, context, and jurisdiction preserved.
- [ ] Strongest supported claim boundaries reviewed against controlled evidence.
- [ ] Capability, authorization, deployment, commercial availability, and conformance remain separate typed states.
- [ ] Historical findings preserved; successor records used instead of silent overwrite.

## Affected-community checklist

- [ ] Participant or community representative identified where applicable.
- [ ] Burden, consent language, and remedy routes reviewed.
- [ ] Public-facing information bounded and free of unsupported institutional claims.
- [ ] Dissent and abstention from community representatives preserved.
- [ ] Community-raised risks tracked to owner and closure condition.

## Disposition recording

Use the append-only independent-review disposition schema and module:

```python
from neuroai_workbench.independent_review import (
    record_independent_review_disposition,
    scope_sha256_for_path,
)

record_independent_review_disposition(
    workspace,
    "SECURITY",
    scope_label="frozen external-review scope",
    scope_sha256=scope_sha256_for_path(scope_artifact_path),
    disposition="ACCEPTED_WITH_CONDITIONS",
    reviewer_claim={
        "name_or_role": "Named security reviewer",
        "organization": "Independent reviewer organization",
        "accountability_state": "CLAIMED_LOCAL_IDENTITY",
        "independence_statement": "Reviewer-supplied independence statement.",
        "conflict_of_interest_disclosure": "Reviewer-supplied disclosure.",
    },
    rationale="Reviewer-supplied rationale for the frozen scope.",
    conditions=["Example condition text to be replaced by the real reviewer condition."],
    findings_register_ref="EXTERNAL-FINDINGS-REFERENCE",
)
```

Example values above are placeholders only. Real external-review records must contain the actual reviewer-supplied statements and exact frozen scope digest.

Disposition records keep `release_authorization_performed: false`. They do not enter the v2 governance opinion store automatically.

## Optional completeness

For a deliberately commissioned external-review programme, local completeness can be summarized when:

1. every commissioned track has a valid append-only disposition for the frozen external-review scope;
2. integrity verification passes;
3. unresolved negative dispositions and conditions remain visible;
4. findings are tracked to owners and closure criteria.

This completeness state describes the optional external-review programme only. It must not be called v2 governance completion, canonical authorization, publication, or institutional readiness.

## Residual human follow-ups

The repository cannot itself:

- commission or perform independent security testing;
- conduct representative-user accessibility testing;
- obtain independent domain-expert judgment;
- obtain affected-community participation;
- determine whether a reviewer is genuinely independent;
- issue an institutional-pilot readiness decision.

When any of those forms of evidence are material to the real #114 decision, the designated authority should reference the evidence or record the appropriate v2 blocker instead of inferring completion from this scaffold.

## Withheld claims

Unless separately established by named competent authority and controlled evidence, withhold claims of:

1. global completeness of the NeuroAI observatory or assessment corpus;
2. scientific validity or evidence authenticity of substantive findings;
3. legal or regulatory authorization for an assessed system;
4. clinical safety or effectiveness;
5. production-grade cybersecurity or security acceptance of a deployment;
6. system conformance to an external standard beyond recorded assessor entries;
7. endorsement, official-methodology status, or institutional authority from an external body;
8. institutional-pilot readiness based solely on repository tests, hashes, or disposition records;
9. independent-review completion based solely on placeholders or automated preparation;
10. canonical authorization implied by external-review disposition or track-completeness summaries.