# ADR 0007 — Transactional evidence registration

## Status

Accepted as deferred architecture with a partial local mitigation.

## Context

Evidence registration currently sequences object bytes, index update, optional assessment link, and event append as separate filesystem steps. A crash or concurrent writer can leave orphaned objects, index rows without bytes, or assessment links without index rows.

## Decision

1. Use `atomic_write_bytes` for evidence object bytes and keep content-addressed filenames (`sha256` + permitted suffix) as the Wave 2 partial mitigation.
2. Refuse path-escaping `stored_filename` values during verification; do not follow escaping symlinks.
3. Defer a full registration journal (bytes → index → assessment → events with rollback markers) until a dedicated implementation issue. The journal must preserve historical findings and never imply authenticity from digest match alone.
4. Allocate evidence IDs from the union of assessment register and index object IDs to avoid collisions when `link_to_assessment=False`.

## Consequences

- Object writes are less likely to leave half-written blobs.
- Multi-step registration is still not transactional; residual risk remains in THREAT_MODEL.
- Provider adapters and institutional custody workflows must not treat local registration as proof of authenticity, completeness, or disclosure authorization.

## Follow-on

Implement the evidence registration journal behind an explicit design review and adversarial crash/fault tests (GitHub issue #23). Keep package versioning and normative assessment schemas unchanged unless a separate major-version ADR is approved.
