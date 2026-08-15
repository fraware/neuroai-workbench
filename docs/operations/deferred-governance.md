# Release governance status

## Current status

The repository no longer requires the protected multi-record choreography formerly tracked by #114 as the default release path.

The proportional default is the release-attestation profile implemented by #184:

```text
exact candidate + products
    -> one six-domain human attestation
    -> AUTHORIZE or WITHHOLD
    -> separate publication if chosen
```

The designated repository authority remains `fraware`.

No real authorization, withholding, or publication is inferred from implementation, tests, documentation, issue ownership, or prior synthetic governance records. A real release state exists only after the corresponding runtime record is explicitly created.

## What remains for a real release

For the default profile, the designated authority must:

1. select the exact successor candidate and exact product digests;
2. assess all six required domains;
3. record one `AUTHORIZE` or `WITHHOLD` attestation with rationale and any conditions;
4. if authorized and publication is chosen, record publication separately against that exact active attestation.

An `AUTHORIZE` attestation fails closed if any domain is `BLOCK` or any unresolved condition is marked `BLOCKS_RELEASE`.

A `WITHHOLD` attestation is a first-class typed record.

## Optional high-assurance profile

The existing v2 governance workflow remains available for contexts that justify additional process:

- exact governance scope;
- separate reviewer opinions;
- owner dispositions and condition lineage;
- deterministic policy evaluation and readiness;
- protected authority-evidence binding;
- separate governance authorization and publication records.

The protected-governance runbook documents that optional profile. It is not a prerequisite for the default release-attestation path.

## Boundaries retained

- predecessor and historical objects remain immutable;
- protected evidence remains outside public Git;
- retrieval failures do not become substantive findings automatically;
- shadow evaluation does not mutate assessments;
- tests do not authorize a release;
- authorization does not perform publication automatically;
- repository workflow state does not establish scientific, clinical, regulatory, legal, conformance, institutional, or external authority.
