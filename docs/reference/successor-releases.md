# Observatory successor releases

The successor generator builds a reviewable candidate from an immutable predecessor and adjudicated delta. Candidate generation, candidate-local gate history, canonical release attestation, and publication are distinct states.

## Default canonical path

```text
successor candidate + exact products
        |
        v
release attestation
        |
        +----> WITHHOLD
        |
        +----> AUTHORIZE
                  |
                  v
          publication, if separately chosen
                  |
                  v
        published attestation frozen
```

The release attestation binds:

- candidate ID and canonical digest;
- serialization contract `JSON_UTF8_INDENT2_LF` and SHA-256 of that deterministic serialized representation;
- predecessor version and digest;
- exact product IDs and digests;
- withheld-claims digest;
- all six required domain judgments;
- conditions;
- decision and rationale;
- exact attestation-policy digest.

The serialized-representation digest binds the complete candidate object under the declared deterministic serialization contract. It does not claim identity with arbitrary source-file bytes that use different formatting or encoding.

The required domains are `SECURITY`, `METHODOLOGY`, `DATA_GOVERNANCE`, `ACCESSIBILITY`, `DOMAIN`, and `AFFECTED_COMMUNITY`.

`AUTHORIZE` requires every domain to be `PASS` and no unresolved `BLOCKS_RELEASE` condition. `WITHHOLD` is a first-class typed decision.

A corrected judgment may explicitly supersede one active unpublished attestation only for the same deterministic candidate representation. History remains append-only. A published attestation is frozen; a correction after publication uses a new successor candidate.

## Publication

Publication is a separate record. It requires one active `AUTHORIZE` attestation, exact attestation digest binding, publication evidence, and the designated actor.

One attestation may have at most one publication record. Recording publication does not perform external publication automatically. Once publication is recorded, the referenced authorization cannot be superseded.

## Candidate-local gate

The candidate retains a historical/local `release_gate` for compatibility. Its `AUTHORIZED` or `PUBLISHED` values are not canonical release-attestation records and must not be interpreted as the default current release decision.

## Optional high-assurance path

The existing v2 governance pipeline remains available as a stronger process profile:

```text
scope
 -> six separate opinions
 -> dispositions / condition closure
 -> policy evaluation
 -> readiness package
 -> governance authorization
 -> governance publication
```

That profile remains useful when the deployment context genuinely requires separately attributable review records or protected authority-evidence binding. It is not needed for the default single-maintainer release path.

See [default release attestation](../architecture/release-attestation.md) and [high-assurance governance records](governance-records.md).

## Generated candidate objects

A successor candidate includes predecessor reference, adjudicated delta state, reopening recommendations, changed and unresolved inventories, data-quality checks, withheld claims, and historical/local gate state.

## Boundary

Canonical repository release state does not make underlying source claims true or establish scientific validity, clinical safety or effectiveness, regulatory or legal authorization, conformance, institutional delegation, external endorsement, or publication by an external body.
