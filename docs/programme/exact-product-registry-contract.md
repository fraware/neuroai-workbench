# Exact-product registry projection contract v1.0

**Plan binding:** `P0.3`  
**Tracking issue:** #324  
**Depends on:** Product Measurement Contract `FROZEN_v1.0`; D4 Product Reference Standard v1.0 working set  
**Status:** implementation candidate

## Purpose

P0.3 turns the frozen Product Measurement Contract into a deterministic machine-readable projection without creating a second canonical ontology.

The registry is an **analytical projection over existing canonical `PRODUCT` and `SYSTEM` identities**. A registry row is never a new product identity. Its row count is never a product-population denominator by itself.

## Identity model

The projection preserves three non-interchangeable levels:

- `FAMILY` → canonical `PRODUCT` aggregation identity;
- `OFFERING` → canonical `PRODUCT` offering identity and the default Release-A product/service unit;
- `CONFIGURATION` → canonical `SYSTEM` with role `PRODUCT_CONFIGURATION`.

`FAMILY` rows cannot silently enter offering denominators. `CONFIGURATION` rows require a parent offering. A research system lacking a qualifying external offering identity remains outside offering-level product counts.

## Deterministic row identity

`registry_row_id` is a SHA-256 analytical key over:

```text
canonical_entity_id
product_offering_id
configuration_system_id OR explicit configuration-coverage marker
jurisdiction_scope
world_time_cutoff
knowledge_time_cutoff
registry_projection_version
```

Changing scope, cutoffs, configuration binding, or projection version creates a new row key without creating a new canonical entity.

## State axes

The v1.0 projection preserves separate controlled fields for:

- identity state;
- boundary disposition;
- lifecycle state;
- access/commercial state;
- regulatory state;
- deployment state;
- currentness state;
- evidence state.

This prevents product existence, currentness, commercial access, authorization, deployment, and effectiveness from collapsing into one status field.

## Enumeration roles

Every countable offering carries one primary role:

```text
INTEGRATED_SYSTEM
COMPONENT_OR_SUBSYSTEM
STANDALONE_SOFTWARE_OR_SERVICE
UNRESOLVED
OTHER_REVIEW_REQUIRED
```

This allows the programme to report broad offering inventories and complete end-user systems separately.

## Population-view policy v1.0

The implementation exposes deterministic predicates for the frozen P0.1 views:

- `A-P1` current identifiable offering inventory;
- `A-P2` current commercially accessible;
- `A-P3` current research or investigational access;
- `A-P4` current integrated end-user systems;
- `A-P5` historical cumulative offerings;
- `A-P6` current released or externally accessible;
- `A-P7` current deployed legacy;
- `A-P8` current distinct technical implementations.

A-P8 is evaluated with registry context because a configuration must be associated with a qualifying current offering at the same projection scope and cutoff pair.

## Reference-standard edge cases

The unit tests bind representative cases from the resolved D4 working reference set:

- Enobio family → in-scope family aggregation, excluded from offering denominator;
- BrainGate2 → formal investigational offering, eligible for A-P1/A-P3/A-P6 but not commercial access;
- Layer 7-T → in-scope component, excluded from A-P4 integrated systems;
- iMotions EEG Module → separately represented software/service layer;
- Empatica Embrace2 → discontinued offering with continuing deployment, represented by A-P7;
- Mudra Band → `EXCLUDE`, never entering primary product views;
- Percept RC adaptive configuration → configuration `SYSTEM` eligible for A-P8 only with qualifying parent offering.

## Boundary

The registry provides identity, state, and population-view mechanics. It does not establish product effectiveness, commercial success, market share, global completeness, or publication authority. Those remain separate downstream evidence and measurement tasks.
