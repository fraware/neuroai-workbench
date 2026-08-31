# Observatory v2 entity identity model

Status: **design contract; non-normative; non-canonical**

The observatory needs persistent identities that remain stable across naming changes, source changes, acquisitions, reclassifications, and repository releases. This document defines the identity boundary for Observatory v2.

## Identity principles

1. Canonical identity must never be derived from display name alone.
2. Aliases, identifiers, domains, and source references are evidence for resolution, not unconditional proof of sameness.
3. Ambiguous matches create proposals and remain unresolved until an applicable disposition exists.
4. Historical identifiers and names remain preserved after canonical naming changes.
5. Legal succession, acquisition, renaming, subsidiary relationships, programme transfer, and simple aliasing are different relationship types.
6. A model family and a model checkpoint are not automatically the same entity.
7. A company, product, system configuration, research programme, and trial are not interchangeable entities even when one organization controls all of them.
8. Entity resolution establishes graph identity only. It does not establish substantive claims about performance, ownership, authorization, or conformance.

## Canonical IDs

Canonical IDs are opaque stable identifiers with a controlled type prefix, for example:

```text
ORG-...
SYS-...
PRD-...
MDL-...
CKPT-...
DS-...
PUB-...
STUDY-...
TRIAL-...
SITE-...
REGULATOR-...
JUR-...
GRANT-...
PAT-...
STD-...
POL-...
```

Existing stable IDs may be preserved during migration. New IDs must be allocated deterministically within the controlled programme process or through an append-only registry that prevents reuse.

IDs are never recycled after retirement.

## Identity evidence

Resolution may use evidence including:

- exact canonical IDs already present in controlled records;
- public persistent identifiers such as DOI, NCT, patent, grant, registry, legal-entity, or other authoritative IDs;
- official domains and canonical URLs;
- source-backed aliases and former names;
- organization/jurisdiction context;
- explicit acquisition, rename, successor, or transfer records;
- publication author/developer provenance;
- system/model identifiers from primary sources.

Fuzzy string similarity alone is insufficient for automatic canonical merge.

## Resolution dispositions

Resolution proposals use explicit dispositions:

```text
SAME_ENTITY
NOT_SAME_ENTITY
SUCCESSOR_OF
PREDECESSOR_OF
ACQUIRED_BY
SUBSIDIARY_OF
PROGRAMME_TRANSFERRED_TO
RENAMED_TO
ALIAS_OF
PROVENANCE_ONLY_NODE
UNRESOLVED
```

The disposition vocabulary may evolve through reviewed schema changes, but it must preserve the difference between identity equivalence and a relationship between distinct entities.

## Automatic confirmation boundary

Automatic confirmation is limited to cases where the candidate carries an already-controlled exact canonical entity ID or another reviewed deterministic mapping rule with no ambiguity.

Examples that can be safely automatic after validation:

- an existing `ORG-0001` reference resolves to that exact organization;
- an exact DOI resolves to the controlled publication entity already registered under the same DOI, subject to collision checks;
- an exact trial registration identifier resolves to the controlled trial entity already registered under that identifier.

Examples that remain proposals:

- same normalized organization name;
- same website domain without a controlled identifier;
- a company and its acquired predecessor;
- a model paper and a model implementation with similar names;
- an author collective and an incorporated organization;
- a hospital system and one of its named trial sites.

## Merge prohibition

The observatory does not physically merge historical records in place.

When two legacy records are adjudicated as the same entity, both predecessor identities remain in migration/provenance history while the canonical graph points them to the resolved entity. This preserves reproducibility of predecessor releases.

## Naming model

An entity may have:

```text
canonical_label
aliases[]
former_labels[]
source_specific_labels[]
```

The canonical label is a presentation choice for the current release. A label change does not create a new entity unless the underlying identity actually changes.

The source supporting a rename or former-name relationship should be retained where material.

## Organizations and acquisitions

Acquisition does not usually imply entity equivalence.

Example:

```text
Pixium Vision --PROGRAMME_TRANSFERRED_TO--> Science Corporation
```

or, if supported:

```text
Pixium Vision --ACQUIRED_BY--> Science Corporation
```

The predecessor organization remains a distinct historical entity unless legal identity evidence establishes something stronger.

System or programme continuity must be represented separately from corporate identity continuity.

## Systems, products, and configurations

The architecture must avoid collapsing:

```text
organization
product family
system
exact configuration
software/model version
trial configuration
commercial configuration
```

into one identifier.

A named product family may contain multiple exact configurations. Assessment IDs and assertions must bind to the exact supported level.

## Model identity

At minimum distinguish:

```text
model family
specific release/checkpoint
fine-tuned derivative
benchmark study about the model
roadmap/announced model with no released checkpoint
```

A company announcement of a future model does not create evidence that a runnable checkpoint exists.

## Dataset identity

Dataset registries and dataset entities are separate.

A registry that reports 827 eligible datasets does not automatically create 827 canonical dataset entities. Individual dataset entities are created when the programme has a justified discovery or assessment need and enough evidence to establish identity.

## Site identity

A site entity should represent the exact institution/site scope supported by source evidence. Trial-site relationships are never inferred from institutional existence or geographic proximity.

## Identity history

Entity identity records are append-only with lineage. A current canonical entity may reference:

```text
legacy_entity_ids[]
predecessor_entity_ids[]
resolution_decision_ids[]
```

Historical releases continue to use their original IDs. Migration adapters provide deterministic crosswalks.

## Collision and ambiguity controls

Resolution must fail closed on:

- duplicate supposedly unique external identifiers;
- one legacy ID mapping to multiple canonical IDs without an explicit split decision;
- circular successor/acquisition lineage;
- conflicting exact identifiers;
- unresolved many-to-one or one-to-many migration mappings;
- silent reassignment of an existing canonical ID.

## Evaluation

Entity resolution quality should be measured on adjudicated benchmark corpora with at least:

- precision for automatic confirmations;
- proposal precision;
- false-merge rate;
- false-split rate;
- unresolved rate;
- reviewer disagreement;
- time to adjudication.

The system should optimize against false merges more strongly than against temporary unresolved states because a false merge can contaminate many downstream assertions and assessments.
