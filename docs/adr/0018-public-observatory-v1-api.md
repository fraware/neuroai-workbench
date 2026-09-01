# ADR 0018: Public observatory /v1 API is published-release-scoped and read-only

- Status: Accepted
- Date: 2026-08-31
- Updated: 2026-09-01
- Related: handoff ADR-API-009; issue #238

## Context

The local case `ThreadingHTTPServer` is an unauthenticated reference UI. The living observatory needs a versioned public read API over immutable S2 release artifacts. These must not be collapsed.

A second distinction is equally important: a mechanically valid Observatory candidate is not canonical merely because a release directory exists. Candidate compilation, explicit authorization, and publication are separate states.

The Observatory launch path currently uses a lightweight designated-operator release decision rather than the Workbench's six-domain institutional review profile. This changes the review mechanism, not the authority invariant.

## Decision

1. `neuroai_workbench.api.v1` serves `/v1/*` only from an S2 Observatory-v2 release directory whose candidate bytes verify and whose governance directory contains:
   - exactly one active explicit `AUTHORIZE` record bound to the exact candidate reference; and
   - one matching publication record bound to that authorization and candidate.
2. The candidate descriptor remains permanently non-authoritative:
   - `release_authorized = false`;
   - `published = false`;
   - `canonical_publication_state = NOT_AUTHORIZED`.
   Authority is never created by mutating the candidate.
3. Candidate preview is separate and explicitly noncanonical through `load_candidate_preview`. The public HTTP server never uses the preview loader.
4. Every public response exposes candidate manifest identity plus authorization/publication record identities.
5. `/v1/diff` is canonical-to-canonical only. An unpublished predecessor is refused in public mode.
6. Write methods are refused. No endpoint mutates canonical state.
7. ETag/cache keys bind to the immutable candidate manifest digest.
8. The public API consumes only S2 public release artifacts. Protected S3 evidence is excluded.
9. This package is not an extension of the local case server and is not institutional SSO.

## S2 release shape

The stable graph-native public record surface is:

```text
records/entities.jsonl
records/sources.jsonl
records/observations.jsonl
records/assertions.jsonl
records/events.jsonl
records/relationships.jsonl
records/candidates.jsonl
records/reopening-decisions.jsonl
```

Classes with no native records in a release use empty files. Governed migration/predecessor lineage lives under `migration/`; release authority records live under `governance/`.

## Consequences

- A compiler-only or Gate-A/S2 candidate cannot become public merely because its schema and manifest pass.
- Manually setting an authorization-looking boolean does not confer authority and invalidates the candidate descriptor binding.
- `WITHHOLD`, superseded authorization, missing publication, digest substitution, and wrong-candidate publication all fail closed.
- Published authorization is immutable in place; corrections require a successor release.
- Local case API docs remain distinct.
- Institutional OIDC/RBAC, if later required, lives in separate adapters rather than changing release identity semantics.

## Boundary

Publication lineage does not establish scientific truth, clinical or regulatory authorization, conformance, institutional endorsement, or global completeness.
