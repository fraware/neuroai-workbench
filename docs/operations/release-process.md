# Release process

## Scope

This page defines **software release integrity** for the `neuroai-workbench` package. It does not define canonical observatory authorization or publication.

A software release and a canonical observatory release are separate state machines with separate evidence. A package tag, build artifact, checksum, SBOM, or passing release verification must not be used as evidence that a successor observatory release has been authorized or published.

## Software release integrity procedure

1. Freeze the v4.2 resource inputs and record checksums.
2. Run compilation, unit, CLI, API, migration, reference-case, and release verification tests.
3. Generate the software bill of materials and dependency record.
4. Create the example workspace and controlled release report.
5. Identify the exact release commit and release-candidate state.
6. Build wheel and source distribution.
7. Generate checksum manifests and archive integrity records.
8. Preserve all failed checks and remediation history in the release verification record.
9. Create a tag or published software release only through the repository's explicit release action.

Release integrity confirms software artifact identity and repository-controlled build properties. It does not establish production security, institutional adoption, scientific validity, clinical safety or effectiveness, regulatory or legal authorization, system conformance, or external endorsement.

## Canonical observatory release is separate

Canonical observatory `AUTHORIZED` / `PUBLISHED` state is governed by the protected governance path tracked in #114, not by the software packaging procedure above.

The active canonical sequence is:

```text
exact successor candidate and products
    -> governance scope
    -> six mandatory review tracks
    -> required owner dispositions / condition closure
    -> governance completion evaluation
    -> release-readiness package
    -> authorization decision
    -> publication decision, if separately chosen
```

See:

- [protected governance execution](protected-governance-execution.md) for the operator procedure;
- [governance records and release-control semantics](../reference/governance-records.md) for record semantics;
- [single designated human authority](../architecture/governance-single-authority.md) for the active v2 authority model;
- [observatory successor releases](../reference/successor-releases.md) for the candidate/canonical-state distinction;
- [v0.3 foundation boundary](../releases/v0.3-foundation-boundary.md) for current release-state interpretation.

## Current v0.3 boundary

`0.3.0.dev0` is a development-line package identity. Foundation completion does not create a `v0.3.0` software tag or release.

Likewise, completion of software release integrity would not by itself create a canonical observatory authorization or publication. Each stronger state requires its own explicit governing record.

## Interpretation rule

When a release statement is ambiguous, identify the state being claimed:

- package development identity;
- software release/tag;
- canonical observatory authorization;
- canonical observatory publication;
- institutional deployment readiness.

Do not infer a stronger state from evidence belonging to a narrower one.