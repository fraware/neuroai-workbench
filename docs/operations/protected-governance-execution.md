# Protected governance execution

## Status

This runbook describes the optional high-assurance governance profile.

It is retained for deployments that genuinely require separate scope manifests, reviewer opinions, owner dispositions, condition lineage, deterministic readiness, and protected authority-evidence binding. It is no longer a prerequisite for the default single-maintainer release path.

For the default path, use [default release attestation](../architecture/release-attestation.md).

## High-assurance sequence

```text
exact governed bytes
    -> governance scope
    -> six separate designated-authority opinions
    -> required owner dispositions / condition closure
    -> governance completion evaluation
    -> release-readiness package
    -> authorization decision
    -> publication decision, if separately chosen
```

The designated repository authority is `fraware`. Historical v1 and v2 records remain verifiable under the policy version they originally bound.

## When to use this profile

Use the high-assurance profile only when its additional records provide a concrete assurance benefit, for example:

- multiple independently produced review inputs;
- institutionally required review traceability;
- protected evidence that must be hash-bound without entering public Git;
- formal condition ownership and closure lineage;
- a programme requirement for a distinct readiness package.

Role consolidation under v2 remains allowed. Where the same maintainer would create every intermediate record without an external process requirement, the default release-attestation profile is preferred.

## Protected-data boundary

Protected evidence bytes, credentials, licensed material, private paths, and non-public authority evidence remain outside public Git. Opaque `protected-ref:` identifiers and SHA-256 digests may be stored only where the relevant schema permits them.

## Fail-closed rules

The high-assurance workflow stops on invalid record stores, invalid event-chain or transaction state, changed governed inputs, stale policy binding, missing required opinions, active designated blockers, missing required dispositions, unresolved `BLOCKS_RELEASE` conditions, candidate/scope mismatch, wrong final actor, or publication inputs that differ from the prior authorization.

Do not edit append-only history to clear a blocker. Record new evidence, dispositions, conditions, or explicit superseding records as appropriate.

## Boundary

This profile records repository workflow evidence. It does not establish scientific truth, clinical safety or effectiveness, regulatory or legal authorization, conformance, institutional delegation, external endorsement, or external publication.
