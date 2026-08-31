# NeuroAI Observatory v2 target architecture

Status: **design contract; non-normative; non-canonical**

This document defines the target programme architecture for the next observatory generation. It does not change the v4.2 assessment instrument, authorize a public data successor, establish institutional readiness, or supersede any current canonical release.

## Mission

The programme target is a global, temporally explicit, evidence-backed intelligence infrastructure for NeuroAI. The observatory maps the ecosystem and preserves attributable evidence over time. The Workbench evaluates exact systems and configurations against a controlled assessment instrument. The two functions are coupled by explicit dependencies and reopening proposals, but remain separate authorities.

The mature system must let a user start from an exact NeuroAI system and trace, where evidence exists, its developer, configuration, technical dependencies, models, datasets, publications, clinical studies, sites, regulatory states, capital and ownership events, suppliers, participant or affected-community powers, deployment state, standards and policy context, historical changes, supporting evidence, unresolved evidence, and bounded assessments.

## Architectural invariants

1. Exact system, configuration, population, task, endpoint, context, jurisdiction, evidence freeze, and observation period remain attached to every conclusion.
2. Capability, authorization, deployment, commercial availability, and conformance remain separate typed states.
3. Missing, inaccessible, conflicting, or unresolved evidence never becomes automatic substantive failure.
4. Source retrieval, hashes, schemas, tests, and software-generated counts establish integrity or internal consistency only; they do not establish substantive truth.
5. Historical findings and predecessor releases remain immutable. Change is represented by successor records, observations, assertions, events, and deltas.
6. Automated discovery, collection, extraction, matching, or materiality analysis may generate proposals. It may not silently write canonical substantive truth or mutate an assessment.
7. A canonical observatory change may recommend assessment reopening. It may not automatically change an assessment finding.
8. Public canonical metadata and protected evidence bytes remain separated under the S2/S3 boundary.
9. Generated databases, indexes, dashboards, APIs, Office files, and websites are projections. They are never the canonical authority.
10. The v4.2 assessment semantics and the prohibition on an aggregate conformance score remain unchanged unless separately governed.

## Seven-layer target architecture

### Layer 1 — Discovery

Purpose: identify potentially relevant new sources, entities, events, relationships, and changes within explicitly governed source universes.

Inputs include controlled search programmes, structured registries, official institutional surfaces, approved APIs, and bounded network discovery. Outputs are candidate source, entity, event, relationship, or assertion proposals. Discovery output carries no publication or assessment authority.

The mature discovery layer must expose source-universe scope, inclusion and exclusion criteria, coverage methodology, known blind spots, retrieval strategy, language and jurisdiction coverage, and measurable precision/recall proxies.

### Layer 2 — Evidence

Purpose: preserve attributable evidence identity and observations without conflating retrieval with truth.

A logical `source` identifies a resource or record. An `observation` identifies what was observed from that source at a particular time. Where permitted and necessary, captured bytes are stored in S3; public observation metadata and permitted public evidence references are stored in S2.

Every high-materiality canonical assertion should eventually be traceable through:

```text
assertion -> extraction/disposition -> observation -> capture/reference -> source
```

### Layer 3 — Canonical temporal graph

Purpose: represent the public observatory as typed entities, relationships, events, assertions, sources, observations, and lineage.

The canonical authority remains immutable versioned S2 release artifacts. Operational databases, graph stores, search indexes, and analytical tables are derived projections.

The graph uses separate valid-time and knowledge-time semantics so that the programme can answer both:

- what was represented as valid at a given world time; and
- what the observatory knew or had adjudicated at a given knowledge time.

The principal unit of substantive state is a bounded assertion rather than an unconstrained mutable entity row.

### Layer 4 — Exact-system assessment

Purpose: evaluate an exact system/configuration under the controlled v4.2 instrument.

Assessments consume evidence and observatory dependencies but remain independent controlled records. New observatory evidence can identify potentially affected findings and create reopening recommendations. Reopening and finding mutation remain explicit human-governed operations.

### Layer 5 — Monitoring and controlled change

Purpose: keep the observatory current without silent overwrite.

The standard lifecycle is:

```text
due source
  -> retrieve
  -> create observation
  -> compare predecessor observation
  -> classify change
  -> extract candidate changes
  -> materiality analysis
  -> adjudication
  -> typed delta
  -> dependency impact analysis
  -> reopening proposal where applicable
  -> successor candidate
  -> release decision
```

Monitoring cadences are risk- and source-class-based. Static publications may be archival while living trial registries, regulatory records, product pages, and operational sources may require recurring retrieval.

### Layer 6 — Public observatory

Purpose: make the canonical graph usable to researchers, policymakers, clinicians, technical developers, affected communities, and other legitimate public users.

The public product is generated from tagged S2 releases and should support global search, entity and system pages, timelines, evidence provenance, historical comparisons, unresolved-evidence views, bulk downloads, and a stable read-only API.

A consequential assertion should expose a clear answer to: "Why does the observatory say this?"

### Layer 7 — Institutional infrastructure

Purpose: operate the system under real institutional controls when protected evidence, authenticated roles, multi-user workflows, or institutional decision processes are involved.

This layer is separate from the local reference profile and requires, at minimum, institutional identity, RBAC, TLS, encrypted storage and managed keys, segmentation, signed releases, backup/recovery, retention/deletion/legal-hold controls, malware/document controls, audit logging, incident response, privacy/legal/participant-governance review, independent security testing, named service ownership, and continuity planning.

## Store mapping

The existing five-store model remains authoritative:

| Store | Role in v2 |
| --- | --- |
| S1 | reusable Workbench software, schemas, normative assessment resources, architecture, adapters, validation and release tooling |
| S2 | public canonical observatory releases, public evidence metadata, public assertions/events/relationships, release manifests and approved public dispositions |
| S3 | protected or restricted evidence captures, licensed material, participant-related evidence, credentials outside record content, private institutional evidence |
| S4 | generated website indexes, databases, dashboards, Office/PDF products, analytical tables and release packages |
| S5 | immutable predecessor programme archives and historical packages |

Monitoring workspace state remains derived operational state, not a new canonical store.

## Canonical authority

A database is not canonical because it is queryable. A website is not canonical because it is public. A graph store is not canonical because it contains normalized relationships.

Canonical observatory state is the set of immutable, versioned, manifest-bound S2 release artifacts authorized through the programme release process. Any operational representation must be rebuildable from those artifacts or clearly declared noncanonical.

## Immediate transition objective

The first v2 milestone is not large-scale data expansion. It is a lossless representation contract for the current canonical corpus.

Before any v2 canonical successor is proposed, the programme must demonstrate that the current v1.4/v1.6/v1.7 public governing state can be mapped into v2 without:

- inventing values;
- dropping source references;
- weakening claim boundaries;
- losing predecessor/history semantics;
- collapsing source observations into unsupported truth claims;
- losing reopening decisions or assessment dependencies; or
- rewriting the current canonical releases.

## Programme gates

### Gate A — Observatory foundation

Required evidence:

- v2 ontology and assertion contract;
- observation/evidence contract;
- explicit temporal model;
- entity identity and resolution model;
- lossless current-corpus migration proof;
- stable S1/S2 compatibility contract;
- at least several evaluated production source universes.

### Gate B — Living observatory

Required evidence:

- multi-domain evidence graph at materially larger scale;
- systematic discovery and monitoring;
- controlled adjudication and successor publication;
- explicit assessment dependency and reopening propagation;
- empirical validation across materially different exact systems;
- public evidence explorer and documented API;
- historical state reproducibility.

### Gate C — Institutional infrastructure

Required evidence:

- authenticated deployment profile;
- protected evidence controls;
- independent security review;
- multi-institution and multi-country pilot evidence;
- participant/affected-community review;
- stable API and migration policy;
- operational continuity, maintenance, incident-response, and service ownership.

## Non-goals of this architecture tranche

This design does not:

- claim global ecosystem completeness;
- establish scientific validity of the current corpus;
- alter the 78 v4.2 requirements;
- create a new regulatory or conformance authority;
- make model-generated extraction authoritative;
- authorize a v2 public release;
- define an aggregate NeuroAI score; or
- declare the current local server institutionally deployable.
