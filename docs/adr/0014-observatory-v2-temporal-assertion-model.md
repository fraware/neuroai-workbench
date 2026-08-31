# ADR 0014: Observatory v2 temporal assertion model

## Status

Accepted as the Workbench temporal implementation ADR (handoff ADR-TEMPORAL-001; issues #225/#226). It governs Workbench `TimeValue` types and the target observatory representation. It does not change the v4.2 normative assessment kernel, authorize a v2 public data release, set `release_authorized=true`, or establish institutional deployment readiness.

Implementation: `neuroai_workbench.temporal` persists `{value, precision}` with `YEAR`, `DATE`, `TIMESTAMP`, and `UNKNOWN`. Date-only predecessors round-trip as `YYYY-MM-DD` and must not be stored as fabricated `T00:00:00Z` timestamps.

## Context

The current public observatory successfully preserves bounded evidence records, source provenance, monitoring, adjudicated deltas, reopening decisions, and immutable successor history. Its principal canonical records are nevertheless large record-centric JSON documents whose fields combine stable identity, current descriptive state, source metadata, and time-dependent claims.

That representation is sufficient for the current controlled corpus but is difficult to scale into a continuously maintained global observatory. Different facts about one entity change independently; one logical source may be observed repeatedly; discovery and extraction need a proposal boundary; historical and current state must coexist; and a later observation must not silently overwrite a predecessor assertion or assessment.

## Decision

Observatory v2 will model the public evidence graph using separate first-class object families:

- stable entities;
- logical sources;
- time-specific source observations;
- bounded assertions;
- typed relationships;
- typed events;
- optional extraction-support records;
- assessment dependencies; and
- reopening decisions.

A bounded assertion becomes the principal unit of substantive state. Each consequential assertion identifies its subject, predicate, object/value, applicable scope and jurisdiction, temporal semantics, source/observation provenance, evidence and verification state, review state, claim boundary, prohibited inferences where useful, and predecessor/supersession lineage.

The model uses separate valid time and knowledge time. A current-state view is a deterministic projection over canonical assertions and lineage; it is not a mutable source-of-truth row.

## Canonical storage decision

Immutable versioned S2 release artifacts remain the canonical public authority.

Operational relational databases, graph databases, search indexes, analytical tables, APIs, and websites are deterministic or explicitly noncanonical projections derived from S2 releases. They must not become the only representation of canonical state.

## Discovery and extraction authority

Automated discovery, retrieval, extraction, entity matching, and materiality analysis may create candidates and evidence-support records. They do not publish canonical assertions or mutate assessments automatically.

Human or otherwise explicitly governed programme disposition remains required wherever current policy requires substantive adjudication.

## Evidence decision

A logical source is distinct from an observation of that source. Repeated observations are append-only. Captured bytes may remain in S3 or with an external custodian while S2 records permitted metadata and digests.

## Identity decision

Canonical entity IDs remain stable and are not derived from display names. Exact controlled IDs or equally deterministic reviewed identifiers may auto-resolve. Fuzzy or ambiguous matches produce proposals. Acquisition, succession, renaming, programme transfer, and entity equivalence remain distinct dispositions.

## Migration decision

The v1.4/v1.6/v1.7 public governing corpus remains immutable. The first v2 migration is a noncanonical projection until deterministic reconciliation accounts for all current meaningful record families and fields without invented values, weakened claim boundaries, lost source references, or lost historical/reopening semantics.

## Consequences

Positive consequences:

- facts about one entity can change independently without rewriting the entity;
- historical and current states coexist naturally;
- repeated source observations have explicit identity;
- evidence lineage becomes queryable;
- cross-domain graph queries become possible;
- monitoring can reason about changed assertions and dependent assessments;
- public website/API indexes can be rebuilt from immutable releases;
- provenance and claim boundaries scale with the data model.

Costs and risks:

- more object types and referential-integrity rules;
- a nontrivial migration/reconciliation programme;
- entity resolution becomes infrastructure rather than incidental curation;
- temporal queries require carefully tested semantics;
- scale can increase reviewer/adjudication burden unless discovery precision and materiality filtering are measured;
- a graph representation can create false confidence if source class and claim boundary are hidden in presentation.

## Rejected alternatives

### Continue adding fields to large entity/current-state records

Rejected as the target architecture because independently changing facts, source observations, and historical state become increasingly difficult to represent without overwrite or duplication.

### Make an operational graph database canonical

Rejected because canonical state would depend on mutable infrastructure and database-specific semantics. Immutable release artifacts remain easier to verify, archive, reproduce, and independently consume.

### Let automated extraction directly write canonical graph edges

Rejected because extraction quality, entity ambiguity, source authority, and substantive interpretation remain separate evidence questions.

### Encode all history only as release diffs

Rejected because users and assessment-dependency logic need first-class temporal assertions and events, not only file-level predecessor differences.

## Verification requirements

Before a v2 canonical successor can be proposed, implementation evidence must demonstrate:

1. lossless migration accounting for the current canonical record families;
2. referential integrity across entities, sources, observations, assertions, relationships, events, dependencies, and reopening decisions;
3. preservation of exact source references and claim boundaries;
4. explicit handling of incomplete date precision;
5. no protected evidence bytes in public release paths;
6. deterministic projection/rebuild behavior;
7. tests for ambiguous identity, supersession, corrections, temporal queries, missing evidence, and assessment reopening boundaries.

Passing these checks does not establish scientific truth, global completeness, institutional adoption, or assessment validity.
