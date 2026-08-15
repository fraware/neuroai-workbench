# Default release attestation

## Decision

The default canonical observatory release path uses one attributable release attestation by the designated repository authority, `fraware`.

The attestation binds the exact successor candidate bytes, predecessor digest, product digests, withheld-claims digest, six domain judgments, conditions, and an explicit `AUTHORIZE` or `WITHHOLD` decision. Publication remains a separate explicit record.

This is the proportional default for a single-maintainer authority model. The existing scope/opinion/disposition/readiness/release-decision pipeline remains available as an optional high-assurance profile.

## Default state machine

```text
exact successor candidate + products
        |
        v
six-domain release attestation
        |
        +----> WITHHOLD: stop
        |
        +----> AUTHORIZE
                  |
                  v
          explicit publication
```

The six required domains are:

- `SECURITY`;
- `METHODOLOGY`;
- `DATA_GOVERNANCE`;
- `ACCESSIBILITY`;
- `DOMAIN`;
- `AFFECTED_COMMUNITY`.

Each domain is recorded once as `PASS` or `BLOCK` with a rationale.

## Fail-closed rules

`AUTHORIZE` is rejected when:

- any required domain is missing or duplicated;
- any domain is `BLOCK`;
- an unresolved condition has `release_effect = BLOCKS_RELEASE`;
- the actor is not the designated authority;
- candidate or product digests are malformed;
- the attestation store or append-only event chain is invalid;
- the same exact candidate already has an active attestation unless the new record explicitly supersedes it.

`WITHHOLD` is a first-class typed decision. It does not require a separate protected programme note.

A correction may supersede one active attestation only for the same exact candidate artifact. The earlier record remains append-only history.

## Exact binding

A release attestation records:

- candidate ID;
- candidate canonical SHA-256;
- exact serialized candidate-artifact SHA-256;
- predecessor release version and SHA-256;
- sorted product IDs and SHA-256 digests;
- SHA-256 of the candidate's withheld-claims set;
- exact attestation-policy ID, version, and SHA-256;
- six domain assessments;
- explicit conditions;
- decision and rationale.

Passing tests do not create an attestation. Creating an attestation does not publish content.

## Publication

`record_attested_publication()` accepts only an active `AUTHORIZE` attestation and records a separate publication-evidence reference and digest. One attestation can have at most one publication record.

`automatic_publication_performed` remains `false`. The record witnesses the repository workflow decision; it does not perform external publication.

## High-assurance profile

The existing v2 governance machinery remains supported for deployments that genuinely need separate scope manifests, reviewer-opinion records, owner dispositions, condition lineage, readiness evaluation, protected authority evidence, and separate governance release decisions.

That profile is additive assurance. It is no longer required for the default single-maintainer release path.

See [single designated human governance authority](governance-single-authority.md) and [high-assurance governance records](../reference/governance-records.md).

## Authority boundary

Repository release authority is a project decision right. Neither the default attestation nor the high-assurance profile establishes scientific truth, clinical safety or effectiveness, regulatory or legal authorization, conformance, institutional delegation, external endorsement, or publication by an external body.
