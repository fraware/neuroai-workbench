# Observatory v2 ontology

Status: **design contract; non-normative; non-canonical**

This ontology defines the minimum typed object model needed to evolve the public NeuroAI observatory from large record-centric JSON documents into a temporal evidence graph while preserving current claim boundaries, provenance, and predecessor history.

## Design principles

1. Stable identity and mutable descriptive state are separate.
2. A source and an observation of that source are separate objects.
3. A bounded assertion is the primary unit of substantive state.
4. Events represent occurrences; relationships represent durable or scoped links; assertions may describe either.
5. Every consequential assertion carries provenance and a claim boundary.
6. Unknown, inaccessible, disputed, and unresolved values are represented explicitly rather than inferred.
7. Temporal validity and observatory knowledge time are separate.
8. Canonical IDs never depend on display names alone.
9. Entity resolution and canonical publication are separate operations.
10. Existing v1.4/v1.6/v1.7 semantics must be representable losslessly.

## Core object families

### Entity

An entity is a persistently identified object that can participate in assertions, relationships, and events.

Minimum fields:

```text
entity_id
entity_type
canonical_label
aliases[]
identifiers[]
status
lineage
```

Initial controlled entity types:

- `ORGANIZATION`
- `SYSTEM`
- `PRODUCT`
- `MODEL`
- `MODEL_CHECKPOINT`
- `DATASET`
- `BENCHMARK`
- `PUBLICATION`
- `STUDY`
- `TRIAL`
- `SITE`
- `REGULATOR`
- `JURISDICTION`
- `GRANT`
- `PATENT`
- `INVESTOR`
- `SUPPLIER`
- `STANDARD`
- `POLICY_INSTRUMENT`
- `PARTICIPANT_OR_AFFECTED_COMMUNITY_BODY`
- `PERSON_ROLE_RECORD` where public and materially necessary
- `PROVENANCE_NODE` for non-organization collectives retained only for lineage

This initial list is extensible through reviewed schema evolution. New types must not be created merely to encode a one-off display category that is better represented as an assertion.

### Source

A source is a logical public or controlled resource identity.

Minimum fields:

```text
source_id
source_class
title
publisher
canonical_url_or_reference
jurisdiction
language
publication_or_record_date
access_class
redistribution_state
```

A source identity may persist while its live representation changes over time.

### Observation

An observation records a retrieval or controlled inspection of a source at a particular knowledge time.

Minimum fields:

```text
observation_id
source_id
observed_at
retrieval_method
retrieval_outcome
requested_locator
resolved_locator
content_type
content_sha256
normalized_content_sha256
capture_state
capture_reference
collector_or_operator_version
```

Hashes are byte or representation identity statements only. They do not establish source authenticity or substantive truth.

### Assertion

An assertion is a bounded claim about a subject.

Minimum fields:

```text
assertion_id
subject_id
predicate
object_id OR value
scope
jurisdiction
valid_from
valid_until
observed_at
source_ids[]
observation_ids[]
evidence_state
verification_state
review_state
claim_boundary
prohibited_inferences[]
supersedes_assertion_ids[]
```

Examples:

```text
PRIMA --DEVELOPED_BY--> Science Corporation
PRIMA --REGULATORY_STATE[EU/EEA]--> COMPANY_ANNOUNCED_CE_MARKED
Neuralink --FINANCING_EVENT--> CAP-...
BrainGate2 T15 --PARTICIPANT_AUTHORITY--> OUTPUT_CORRECTION
CLEF --PUBLICATION_STATE--> PREPRINT
```

Assertions may be current, historical, superseded, unresolved, or disputed. A superseded assertion remains part of canonical history.

### Relationship

A relationship is a typed link whose identity or lifecycle is useful independently of any single textual claim.

Examples:

- `DEVELOPS`
- `OWNS`
- `ACQUIRED_BY`
- `FUNDED_BY`
- `SUPPLIES`
- `DEPENDS_ON`
- `STUDIED_IN`
- `TRIAL_AT`
- `USES_MODEL`
- `TRAINED_ON`
- `EVALUATED_ON`
- `AUTHORIZED_IN`
- `DEPLOYED_AT`
- `GOVERNED_BY`
- `PARTICIPATES_IN`
- `SUCCESSOR_OF`

Minimum fields:

```text
relationship_id
relationship_type
subject_id
object_id
valid_from
valid_until
source_ids[]
observation_ids[]
evidence_state
claim_boundary
```

A relationship record does not remove the need for assertions when the relationship has qualifiers or disputed semantics.

### Event

An event represents an occurrence with temporal identity.

Initial event classes include:

- financing;
- grant award;
- acquisition/ownership transition;
- regulatory designation, authorization, filing, withdrawal, recall, or enforcement action;
- trial status transition;
- publication/preprint/model/dataset release;
- leadership/governance change;
- deployment or site activation;
- safety/post-market event where publishable and appropriately evidenced;
- standard or policy revision.

Minimum fields:

```text
event_id
event_type
occurred_at_or_period
subjects[]
objects[]
jurisdiction
source_ids[]
observation_ids[]
evidence_state
verification_state
claim_boundary
```

### Extraction / evidence support

Where an assertion is derived from text or structured fields, the programme may retain a separate extraction-support object.

Minimum fields:

```text
extraction_id
observation_id
assertion_candidate_id
method
extractor_version
source_location
excerpt_or_field_reference
excerpt_hash
human_disposition
```

This object must not expose protected or copyrighted text in S2 when redistribution is not permitted.

### Assessment dependency

Assessment dependencies connect observatory state to exact assessment findings without granting automatic mutation authority.

Minimum fields:

```text
dependency_id
assessment_id
finding_or_requirement_id
assertion_ids[]
source_ids[]
dependency_scope
materiality
```

A changed assertion can make a dependency potentially stale and generate a reopening recommendation. It cannot directly change the assessment finding.

### Reopening decision

The existing reopening semantics remain first-class.

Minimum fields:

```text
reopening_decision_id
target_assessment_or_object
trigger_assertion_ids[]
trigger_event_ids[]
decision
required_actions[]
decided_at
provenance
```

## Domain representation

### Organizations

Stable organization identity belongs in `Entity`. Headquarters, jurisdiction, role, current representation, and verification are bounded assertions unless they are immutable identifiers.

This avoids making an organization row a silently mutable container for many facts that can change independently.

### Systems and products

A `SYSTEM` identifies an exact or bounded technical system where the programme can establish stable identity. `PRODUCT` may represent a commercial or formally named product family. Exact configuration, intended use, jurisdictional authorization, deployment, and commercial status are assertions scoped to the relevant configuration and time.

### Models and datasets

Models, checkpoints, datasets, and benchmarks are separate entities. Publication state, license state, checkpoint availability, benchmark scope, dataset lineage, and assurance state are assertions. A model-family identity must not imply that all checkpoints have identical performance, data lineage, or licensing.

### Clinical studies and trial sites

Trials and studies are entities. Site relationships require explicit evidence. The existence of a hospital or research institution is never sufficient to infer trial participation.

### Participant and affected-community powers

Participant authority is represented as a typed relationship or assertion with explicit holder, scope, valid time, evidence, and boundary. Consent, operational control, registry interest, co-design, correction, voting, veto, and institutional governance authority remain distinct.

### Technical dependencies

System-specific dependencies require system-specific evidence. Supplier capability can be represented separately and must not be promoted to a named-system dependency without evidence.

### Regulatory state

Regulatory records are always jurisdiction- and configuration-scoped. Filing, designation, authorization, clearance, approval, conformity marking, reimbursement, deployment, and commercial availability are distinct predicates.

### Capital and ownership

Financing and grants are events. Ownership/control is a separate relationship/assertion. A financing amount must not be interpreted as valuation, cash availability, control, or technological quality unless separately supported.

## Verification and evidence semantics

The ontology deliberately separates:

- `evidence_state`: what kind of evidence is present;
- `verification_state`: what the programme has verified about the record;
- `review_state`: whether a substantive human disposition exists;
- `claim_boundary`: the maximum supported interpretation;
- `prohibited_inferences`: common unsupported conclusions that must remain excluded.

A schema-valid record can still be substantively wrong. A current source can still contain a false claim. A company statement remains a company statement even when its retrieval is perfectly verified.

## Extensibility rules

Schema evolution may add optional fields, controlled vocabulary values, or new object classes when there is a repeated programme need. It must not:

- collapse authorization and deployment states;
- convert absence into failure;
- silently merge entities;
- erase predecessor assertions;
- weaken source-class boundaries;
- turn model output into canonical authority;
- alter v4.2 assessment semantics as an incidental observatory change.

## Migration requirement

Every current canonical record family must map to one or more of these object families or to an explicitly retained legacy payload with a documented reason. A migration is incomplete if a meaningful current field has no accounted destination.
