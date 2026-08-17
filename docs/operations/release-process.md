# Release process

## Scope

Software release integrity and canonical observatory release control are separate state machines.

A package tag, build artifact, checksum, SBOM, or passing release verification does not authorize or publish an observatory successor.

## Software release integrity

1. Freeze resource inputs and record checksums.
2. Run compilation, unit, CLI, API, migration, reference-case, and release-verification checks.
3. Generate dependency and software-bill-of-materials records.
4. Identify the exact release commit.
5. Build wheel and source distribution.
6. Generate checksum manifests.
7. Preserve failed checks and remediation history.
8. Create a software tag or release only through the repository's explicit release action.

These steps establish software artifact identity and repository-controlled build properties only.

## Canonical observatory release

The default canonical path is:

```text
exact successor candidate + exact products
        |
        v
one six-domain release attestation
        |
        +----> WITHHOLD: stop
        |
        +----> AUTHORIZE
                  |
                  v
          separate publication, if chosen
```

The attestation covers `SECURITY`, `METHODOLOGY`, `DATA_GOVERNANCE`, `ACCESSIBILITY`, `DOMAIN`, and `AFFECTED_COMMUNITY`.

`AUTHORIZE` is rejected if any domain is `BLOCK` or an unresolved condition is release-blocking. `WITHHOLD` is a typed terminal decision for that attestation.

Publication requires an active exact `AUTHORIZE` attestation and its own publication-evidence reference and digest. Recording publication does not publish artifacts automatically.

See [default release attestation](../architecture/release-attestation.md).

## Optional high-assurance governance

The existing v2 scope/opinion/disposition/readiness/release-decision pipeline remains supported as an optional high-assurance profile. It is appropriate when separate review records, stronger condition lineage, or protected authority-evidence binding add real assurance.

See [high-assurance governance records](../reference/governance-records.md) and [protected governance execution](protected-governance-execution.md).

## Current v0.3 boundary

`0.3.0.dev0` remains a development-line package identity. Implementing the default attestation path does not create a `v0.3.0` software release, a canonical authorization, or a publication record.

## Interpretation rule

When a release statement is ambiguous, identify the state being claimed:

- package development identity;
- software release/tag;
- canonical observatory authorization;
- canonical observatory publication;
- institutional deployment readiness.

Do not infer a stronger state from evidence belonging to a narrower one.
