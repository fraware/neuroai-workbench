# Governance rehearsal and protected handoff

This reference defines the engineering-only portion of issue #114. It covers a synthetic end-to-end rehearsal of the governance stack and a safe handoff template for later protected real-human execution.

## Status boundary

The rehearsal is deliberately non-authoritative. Its fixed execution mode is:

`SYNTHETIC_REHEARSAL`

Every repository-controlled rehearsal certificate and handoff template is explicitly typed as:

`NON_AUTHORITATIVE_GOVERNANCE_REHEARSAL`

Synthetic reviewer and owner records are test/workflow fixtures. They do not represent real people, organizations, independence claims, institutional delegation, scientific approval, regulatory authority, release authority, publication authority, or UNESCO endorsement.

A successful rehearsal therefore proves that the machinery works **and** that synthetic execution cannot cross the release-authority boundary.

## Rehearsal coverage

`run_synthetic_governance_rehearsal` exercises:

- an exact hash-bound governance scope;
- all six governance tracks: security, methodology, data governance, accessibility, domain, and affected community;
- support;
- objection;
- evidence request;
- abstention;
- support with conditions;
- reviewer-opinion supersession;
- owner dispositions;
- an unresolved `BLOCKS_RELEASE` condition;
- six-track policy evaluation;
- release-readiness evaluation;
- a synthetic attempt to cross the reserved release-authority boundary.

The fixture intentionally remains structurally insufficient for real governance. Synthetic accountability states do not satisfy the policy's claimed-human reviewer threshold. Objection, evidence request, abstention, blocking owner dispositions, and the unresolved release-blocking condition remain visible.

Expected outcome:

- policy readiness: `UNSATISFIED`;
- release readiness: `NOT_READY`;
- synthetic authority probe: blocked;
- release authorization performed: `false`;
- canonical successor authorized: `false`;
- publication authorized: `false`;
- real-human governance completed: `false`.

## Rehearsal certificate

The rehearsal emits a local certificate under the workspace governance area. The certificate records:

- exact scope ID and SHA-256;
- synthetic opinion IDs and SHA-256 digests;
- synthetic disposition IDs, disposition digests, and condition-register digests;
- six-track evaluation ID, evaluation digest, and input-binding digest;
- release-readiness package ID, digest, state, and blockers;
- the result of the synthetic authority-boundary probe;
- explicit false authority/publication flags;
- the list of real-human actions still pending;
- a digest of the associated handoff template.

The certificate is evidence of a rehearsal only. It must not be presented as a reviewer approval, owner approval, release decision, or publication decision.

## Protected handoff template

`build_handoff_template` produces a safe template for later protected execution. The template contains:

- exact governance-scope ID and SHA-256;
- exact successor-candidate references supplied by the release-readiness package;
- exact policy-evaluation references;
- exact release-readiness package references;
- two review questions for each of the six tracks;
- required record schemas;
- verification commands;
- return instructions;
- placeholders for future real reviewer identities;
- explicit flags confirming that no protected evidence, real reviewer records, real owner dispositions, release-authority decision, or canonical publication authorization is included.

The template itself can be repository-controlled. The later completed handoff package can contain protected references and real reviewer information only inside the protected governance workflow. Protected evidence bytes and private identity material must not be committed to the public repository.

## Track questions

### Security

1. Are security assumptions, attack surfaces, privileged transitions, and unresolved security conditions explicit?
2. Do release controls fail closed under tampering, concurrency, interruption, and stale-input substitution?

### Methodology

1. Are assessment methods, evidence dependencies, uncertainty states, and reopening semantics inspectable?
2. Do reported conclusions remain within the evidential scope of the reviewed artifacts?

### Data governance

1. Are provenance, licensing, protected/public boundaries, retention, and disclosure constraints explicit?
2. Can every release input be traced to an exact digest without exposing protected evidence?

### Accessibility

1. Are public products usable and interpretable across the programme's intended accessibility requirements?
2. Are known accessibility gaps recorded as explicit conditions instead of being silently omitted?

### Domain

1. Do domain-specific interpretations preserve distinctions among research, regulatory, clinical, and deployment states?
2. Are unresolved domain questions and evidence gaps visible to the release decision?

### Affected community

1. Are affected-community perspectives represented as an explicit governance track with visible gaps and dissent?
2. Can abstention, objection, requested evidence, and minority positions remain visible without being converted to support?

## Schemas for the later protected execution

The handoff points real reviewers and owners to the repository-controlled schemas:

- `GOVERNANCE_REVIEWER_OPINION.schema.json`;
- `GOVERNANCE_OWNER_DISPOSITION.schema.json`;
- `GOVERNANCE_RELEASE_DECISION.schema.json`.

Returned records must bind the exact scope and input digests. They must preserve append-only supersession semantics. Reviewer disagreement must remain visible. Owner disposition must not rewrite reviewer records or assessment findings.

## Verification

The handoff template carries targeted verification commands for scope/opinion integrity, dispositions/policy integrity, and release-gate integrity. Full CI remains authoritative for repository integration.

The later real-human execution must additionally verify the protected authority evidence outside the public repository. Software record integrity alone does not authenticate a reviewer, owner, organization, or release authority.

## Deferred completion criteria

The following #114 criteria remain intentionally incomplete after the engineering rehearsal lands:

- actual reviewer assignment and returned real reviewer records;
- at least two genuinely independent human reviewer claims where policy requires them;
- actual owner dispositions over real reviewer opinions and conditions;
- actual release-authority decision backed by protected external authority evidence;
- canonical publication.

Issue #114 must remain open until those human-only criteria are completed. No synthetic fixture can satisfy them.
