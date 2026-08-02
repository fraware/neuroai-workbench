# Observatory operations verification

This checklist applies to the controlled monitoring and refresh-candidate pipeline.

## Software gates

- Source-registry schema and semantic validation pass.
- Capture identifiers remain distinct from content hashes.
- Repeated unchanged retrievals preserve both capture events and deduplicate bytes.
- Snapshot manifests and content digests verify.
- Change candidates never mutate canonical observatory or assessment state.
- Accepted candidates require explicit human change class, materiality, reopening effect, and rationale.
- Adjudications and refresh packages are immutable and content-addressed.
- The monitoring core satisfies its dedicated module coverage floor.
- Ruff, mypy, Python 3.10–3.14 tests, package verification, release verification, container checks, CodeQL, and dependency controls pass.

## Substantive gates

Software verification does not establish source authenticity, claim truth, scientific validity, regulatory status, clinical safety, conformance, or UNESCO endorsement. A canonical observatory successor still requires reconciliation against the predecessor release and an authorized release decision with named release-authority approval. Issue #10 independent-review tracks remain optional recommended follow-up and do not block AUTHORIZED or PUBLISHED.

## Deferred architecture

The approved external collector, DNS and redirect controls, robots and terms-of-use policy, entity resolution, bounded model-assisted extraction, canonical delta application, generated Excel/Word/PDF products, and institutional review interface remain separate bounded increments.
