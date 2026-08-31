# Observatory v2 release model

Status: **design contract; non-normative; non-canonical**

This document defines the target public-release packaging and authority boundary for Observatory v2. It preserves the existing rule that canonical observatory state is established by an authorized immutable S2 release, not by a database, workflow run, test result, or generated product.

## Canonical unit

A v2 public release is an immutable set of machine-readable records plus a manifest and release descriptor.

A target release may contain logically separated tables such as:

```text
records/
  entities.jsonl
  sources.jsonl
  observations.jsonl
  assertions.jsonl
  relationships.jsonl
  events.jsonl
  assessment-dependencies.jsonl
  reopening-decisions.jsonl
  dispositions.jsonl
```

The exact physical partitioning can evolve, but all canonical records must be manifest-bound and reconstructable from the release without requiring an operational database.

## Authority boundary

The following can establish artifact integrity or internal consistency but cannot authorize a canonical release by themselves:

- JSON Schema validation;
- SHA-256 verification;
- test success;
- successful collector execution;
- successful extraction;
- successful entity matching;
- complete monitoring coverage;
- generated analytical counts;
- an LLM/model response;
- a website deployment;
- a graph database transaction.

Canonical publication requires the programme's explicit release-attestation/publication process.

## Predecessor binding

Every canonical v2 successor release identifies its canonical predecessor and binds the predecessor release identity and digest set.

A successor release must not rewrite predecessor artifacts.

Corrections are successor records with explicit correction provenance.

## Record lineage

Where a record replaces or changes earlier canonical state, lineage should be explicit through fields such as:

```text
supersedes_record_ids[]
supersedes_assertion_ids[]
predecessor_release_id
```

The absence of a predecessor reference must not be used to hide a correction or historical state change.

## Compatible Workbench identity

The data repository must distinguish three concepts that are currently easy to conflate:

1. **Compatibility package line** — the Workbench package version declared compatible with the data model.
2. **Execution pin** — the exact Workbench commit/runtime used for a particular deterministic workflow.
3. **Producer identity** — the exact Workbench commit/version that produced or verified a particular release candidate.

A v2 release descriptor should record these separately when applicable.

Example:

```text
workbench_compatibility_version
producer_workbench_commit
producer_workbench_version
```

Operational workflow files may separately pin an execution commit.

## Release states

At minimum distinguish:

```text
DEVELOPMENT
CANDIDATE
AUTHORIZED
PUBLISHED
WITHDRAWN_OR_SUPERSEDED
```

A candidate is not canonical merely because it is committed to `main` or available as a CI artifact.

`AUTHORIZED` and external/public `PUBLISHED` remain separate states where the existing release machinery requires that distinction.

## Deterministic projections

Operational products are regenerated from canonical releases:

```text
S2 release
  -> analytical tables
  -> SQL/graph/search indexes
  -> public API
  -> website
  -> XLSX/DOCX/PDF/dashboard products
```

Projection builders must expose the input release identity. Generated products must never become the only surviving representation of a canonical record.

## Release verification

A v2 verification routine should confirm at least:

- release descriptor schema validity;
- manifest integrity;
- expected record files and counts;
- canonical ID uniqueness;
- source/observation/assertion referential integrity;
- no dangling predecessor/supersession links within the declared release universe;
- no impossible temporal ordering introduced by deterministic transformation;
- no protected capture material in public release paths;
- compatibility/producer identity consistency;
- authority-state consistency.

These checks establish release integrity and internal consistency only.

## Current-to-v2 migration release

The first v2 migration output must remain explicitly noncanonical until a migration reconciliation demonstrates complete accounting for the current public governing corpus.

The reconciliation must report, by predecessor record family:

```text
input_record_count
input_field_count
mapped_record_count
mapped_field_count
preserved_legacy_field_count
unmapped_required_field_count
invented_value_count
claim_boundary_loss_count
source_reference_loss_count
```

Required exit conditions are:

```text
unmapped_required_field_count = 0
invented_value_count = 0
claim_boundary_loss_count = 0
source_reference_loss_count = 0
```

Counts alone do not prove semantic correctness; domain review remains required before authorization.

## Public release cadence

The architecture supports continuous monitoring and candidate generation without requiring a canonical Git release for every source observation.

A programme policy may later define routine release cadence and exceptional material-event releases. The release cadence must not weaken predecessor immutability or authority review.

## Withdrawal and correction

A published release is not edited in place.

If a release contains a material error:

1. preserve the published release and its manifest;
2. record withdrawal/correction status through the controlled publication mechanism;
3. create a successor candidate with explicit correction lineage;
4. re-run release review and authorization;
5. update public projections to the new authorized successor while retaining historical access where policy permits.

## Non-goals

This release model does not define a blockchain, distributed consensus system, legal non-repudiation scheme, regulatory certification mechanism, or substantive scientific validation process.
