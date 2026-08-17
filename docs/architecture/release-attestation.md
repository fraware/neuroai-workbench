# Default release attestation

## Decision

The default canonical observatory release path uses one attributable release attestation by the designated repository authority, `fraware`.

The attestation binds the successor candidate's canonical digest, a deterministic serialized representation of the complete candidate object, predecessor digest, exact product digests, withheld-claims digest, six domain judgments, conditions, and an explicit `AUTHORIZE` or `WITHHOLD` decision. Publication remains a separate explicit record.

This is the proportional default for a single-maintainer authority model. The existing scope/opinion/disposition/readiness/release-decision pipeline remains available as an optional high-assurance profile.

## Default state machine

```text
candidate representation + products
        |
        v
six-domain release attestation
        |
        +----> WITHHOLD: stop or supersede before publication
        |
        +----> AUTHORIZE
                  |
                  v
          explicit publication
                  |
                  v
        published attestation frozen
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
- the attestation or publication store is invalid;
- the append-only event chain is invalid;
- the same candidate representation already has an active attestation unless the new record explicitly supersedes it;
- a supersession attempts to replace an attestation that already has a publication record.

`WITHHOLD` is a first-class typed decision. It does not need a separate protected programme note.

A correction may supersede one active unpublished attestation only for the same candidate representation. The earlier record remains append-only history. Once an attestation has a publication record, it is immutable for release-control purposes. A correction after publication uses a new successor candidate.

## Candidate binding

A release attestation records:

- candidate ID;
- candidate canonical SHA-256;
- serialization contract `JSON_UTF8_INDENT2_LF`;
- SHA-256 of that deterministic serialized candidate representation;
- predecessor release version and SHA-256;
- sorted product IDs and SHA-256 digests;
- SHA-256 of the candidate's withheld-claims set;
- exact attestation-policy ID, version, and SHA-256;
- six domain assessments;
- explicit conditions;
- decision and rationale.

The serialization digest is computed from the in-memory candidate object using UTF-8 JSON, two-space indentation, and one trailing line feed. It binds the deterministic representation used by this profile. It is not a claim about arbitrary source-file bytes supplied in another encoding or formatting.

The verifier independently rechecks schema, record hash, authority and policy binding, event correspondence, product and assessment canonicalization, six-domain completeness, `AUTHORIZE` blocker semantics, serialization contract, supersession integrity, and publication freeze semantics. Recorder admission and later verification therefore enforce the same substantive release-control invariants.

Passing tests do not create an attestation. Creating an attestation does not publish content.

## Publication

`record_attested_publication()` accepts only an active `AUTHORIZE` attestation and records a separate publication-evidence reference and digest. One attestation may have at most one publication record.

After publication, the referenced authorization cannot be superseded. This preserves the historical validity of the publication binding. A later correction creates a new successor candidate and a new release decision.

`automatic_publication_performed` remains `false`. The record witnesses the repository workflow decision; it does not perform external publication.

## High-assurance profile

The existing v2 governance machinery remains supported for deployments that genuinely need separate scope manifests, reviewer-opinion records, owner dispositions, condition lineage, readiness evaluation, protected authority evidence, and separate governance release decisions.

That profile is additive assurance. It is no longer needed for the default single-maintainer release path.

See [single designated human governance authority](governance-single-authority.md) and [high-assurance governance records](../reference/governance-records.md).

## Authority boundary

Repository release authority is a project decision right. Neither the default attestation nor the high-assurance profile establishes scientific truth, clinical safety or effectiveness, regulatory or legal authorization, conformance, institutional delegation, external endorsement, or publication by an external body.
