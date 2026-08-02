# Independent review acceptance

This document defines the human acceptance scaffolding for named independent reviews required before the workbench or an observatory successor release is presented as suitable for institutional pilots.

Software can record review dispositions. It cannot commission reviewers, authenticate identities, or authorize release.

## Boundary

Independent review acceptance records attribute a claimed local review outcome under `authority_profile: LOCAL_UNAUTHENTICATED_ATTRIBUTION`. Automated tests, repository-author review, Cursor agents, and model-generated critiques may support preparation but do not substitute for independent expert review or affected-user testing.

Passing schema validation, hash verification, or disposition completeness does not establish institutional-pilot readiness, security acceptance, methodological correctness, or release authorization.

## Required review tracks

Each track requires a named reviewer, documented scope, conflict-of-interest disclosure, findings register reference where applicable, and an append-only disposition record.

| Track | Primary focus |
|---|---|
| Security | Local-server boundary, path handling, evidence integrity, event-chain tampering, dependency risk, release provenance |
| Methodology | Requirement interpretation, evidence-state distinctions, prohibited-inference enforcement, migration preservation, reviewer-authority model |
| Data governance | Protected-evidence exchange metadata, retention, disclosure, participant-data boundaries, federated evidence handling |
| Accessibility | Keyboard operation, screen-reader semantics, focus order, contrast, error recovery, report accessibility, representative-user testing |
| Domain | Independent domain expert review of substantive claim boundaries, system identity, and assessment conclusions |
| Affected community | Participant or community representative review of burden, consent language, remedy routes, and public-facing information |

## Pre-review preparation

Before commissioning reviewers:

1. Freeze the review scope artifact and record its SHA-256 digest.
2. Publish reviewer scope, independence criteria, and conflict-of-interest template.
3. Confirm no readiness claim will be issued solely from internal or automated review.
4. Identify residual human blockers that software cannot complete.

## Security checklist

- [ ] Review scope approved before testing begins.
- [ ] Local-server binding, network exposure, and container defaults reviewed.
- [ ] Path traversal, archive handling, and safe-join boundaries reviewed.
- [ ] Evidence-byte integrity and replacement detection reviewed.
- [ ] Event-chain tampering and append-only record semantics reviewed.
- [ ] Dependency, supply-chain, and release-provenance controls reviewed.
- [ ] Future authenticated deployment design reviewed separately from local reference server.
- [ ] Every finding has an owner, priority, evidence, and closure condition.
- [ ] Unresolved risks remain public or explicitly access-controlled with rationale.

## Methodology checklist

- [ ] Requirement interpretation and v4.2 kernel boundaries reviewed by an independent domain expert.
- [ ] PASS, PARTIAL, FAIL, and NOT ASSESSED use reviewed for semantic drift.
- [ ] Unavailable, inaccessible, and unresolved evidence remain distinct states.
- [ ] Prohibited-inference enforcement reviewed.
- [ ] Migration preservation and successor-record semantics reviewed.
- [ ] Conformance-level calculation and reviewer-authority model reviewed.
- [ ] Disagreement and abstention records preserved without erasure.
- [ ] No readiness claim issued solely from schema validity or test success.

## Data governance checklist

- [ ] Protected-evidence exchange remains metadata-only.
- [ ] No protected neural, participant, clinical, regulatory, or credential material in public storage.
- [ ] Retention, disclosure, and destruction rules named for every exported copy.
- [ ] Federated evidence handling preserves custody and access-state boundaries.
- [ ] Data-governance controls updated when exchange or workspace boundaries change.
- [ ] Withheld claims appendix reviewed for outward-facing language.

## Accessibility checklist

- [ ] Keyboard-only operation verified for primary workflows.
- [ ] Screen-reader semantics and focus order verified.
- [ ] Contrast and non-color status communication verified.
- [ ] Error recovery and form comprehension verified.
- [ ] Report and export accessibility verified.
- [ ] Testing includes representative users, not only automated checks.
- [ ] Accessibility findings tracked to owner and closure condition.

## Domain checklist

- [ ] Independent domain expert identified and scope signed.
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

Use the append-only independent review disposition schema and module:

```python
from neuroai_workbench.independent_review import record_independent_review_disposition, scope_sha256_for_path

record_independent_review_disposition(
    workspace,
    "SECURITY",
    scope_label="v0.3.0.dev0 release candidate",
    scope_sha256=scope_sha256_for_path(scope_artifact_path),
    disposition="ACCEPTED_WITH_CONDITIONS",
    reviewer_claim={
        "name_or_role": "Named security reviewer",
        "organization": "Independent reviewer organization",
        "accountability_state": "CLAIMED_LOCAL_IDENTITY",
        "independence_statement": "No material conflict with the assessed release scope.",
        "conflict_of_interest_disclosure": "None declared.",
    },
    rationale="Scope reviewed; residual items tracked in findings register.",
    conditions=["Close path-handling finding SEC-014 before institutional pilot."],
    findings_register_ref="FINDINGS-SECURITY-2026-001",
)
```

Disposition records must keep `release_authorization_performed: false`. Release authorization remains a separate human decision outside this scaffold.

## Acceptance gate

Independent review acceptance is complete only when:

1. All six review tracks have a valid, append-only disposition record for the frozen scope.
2. Integrity verification passes without hash or schema errors.
3. No track disposition is `REJECTED`, `DEFERRED`, or `INCOMPLETE`.
4. Unresolved risks and conditions are tracked with owners and closure criteria.
5. A separate authorized release decision is recorded through the ordinary release process.

Software summary helpers may report track completeness. They must never set `release_authorization_performed` or `institutional_pilot_readiness_established` to true.

## Residual human blockers

The repository cannot complete the following without named human reviewers:

- Commission and execute independent security testing beyond automated gates.
- Conduct representative-user accessibility testing.
- Obtain independent domain expert sign-off on substantive claim boundaries.
- Obtain affected-community representative review where applicable.
- Issue an authorized release or institutional-pilot readiness decision.

See issue #10 for the commissioning workflow and issue #34 for programme context.

## Appendix E — Withheld claims

The following claims are withheld unless separately established by named competent authority and controlled evidence:

1. Global completeness of the NeuroAI observatory or assessment corpus.
2. Scientific validity or evidence authenticity of substantive findings.
3. Legal or regulatory authorization for any assessed system.
4. Clinical safety or effectiveness.
5. Production-grade cybersecurity or security acceptance of any deployment.
6. System conformance to any external standard beyond recorded assessor entries.
7. UNESCO endorsement, official-methodology status, or institutional authority.
8. Institutional-pilot readiness based solely on repository tests, hashes, or disposition records.
9. Independent review completion based solely on software-generated disposition placeholders.
10. Release authorization implied by disposition recording or track-completeness summaries.

Any change affecting outward-facing language must update this appendix and the controlled status record.
