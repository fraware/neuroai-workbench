# Single designated human governance authority

## Decision

The designated repository authority is `fraware`.

One human may make the repository release decision. Governance proportionality is explicit: the default path records one six-domain release attestation, and the existing multi-record governance pipeline is retained as an optional high-assurance profile.

## Default profile

The default profile is `DEFAULT_RELEASE_ATTESTATION`.

```text
exact candidate + products
        |
        v
one six-domain attestation
        |
        +----> WITHHOLD
        |
        +----> AUTHORIZE
                  |
                  v
          separate publication
```

The attestation preserves the properties that matter for a single-maintainer project:

- exact-object binding;
- explicit human judgment across all six required domains;
- visible conditions and blockers;
- typed authorization or withholding;
- append-only correction history;
- a separate publication action.

The default profile does not require six separate reviewer records, owner dispositions for the maintainer's own judgments, a derived readiness package, or protected external-authority evidence from the same maintainer.

See [default release attestation](release-attestation.md).

## High-assurance profile

`GOVERNANCE_COMPLETION_POLICY.v2.json` and the scope/opinion/disposition/readiness/release-decision modules remain supported as a higher-assurance workflow.

Use that profile when the deployment context genuinely benefits from separately attributable review records, condition lineage, external evidence bindings, or stronger institutional process controls.

Historical v1 records remain verifiable under their original multi-person semantics. Existing v2 records remain verifiable under v2. The default attestation profile does not rewrite or reinterpret either history.

## Common invariants

Both profiles preserve:

- designated-authority admission;
- append-only persisted records and event witnesses;
- exact SHA-256 binding to release objects;
- fail-closed blocker semantics;
- explicit authorization;
- publication as a separate action;
- bounded repository authority.

Passing CI, generating products, or advancing a candidate-local gate never creates canonical authorization by itself.

## Authority boundary

The designated authority is a repository decision right. It does not authenticate an external institution or establish scientific truth, clinical safety or effectiveness, regulatory or legal authorization, conformance, institutional endorsement, external adoption, or publication by an external body.
