# Observatory v2 temporal model

Status: **design contract; non-normative; non-canonical**

The observatory must distinguish time in the world from time in the evidence system. This document defines the minimum temporal semantics for Observatory v2.

## Why one timestamp is insufficient

A single `last_verified` or `retrieved` field cannot answer both:

1. When was the represented fact or state valid in the world?
2. When did the observatory observe, adjudicate, or publish that representation?

These can differ substantially. A financing event may occur in March and be discovered in July. A product page may disappear in August even though the historical event described on it remains valid. A regulatory state may become effective before the observatory retrieves the controlling record.

The v2 model therefore uses two temporal axes.

## Valid time

Valid time describes when the represented state or relationship applies in the world, to the extent supported by evidence.

Fields:

```text
valid_from
valid_until
```

Rules:

- Either boundary may be unknown.
- Unknown is represented as missing or an explicit unresolved state, never guessed.
- An event may use an exact occurrence timestamp/date, a bounded period, or an unresolved occurrence period.
- `valid_until = null` must not automatically mean "still true". Currentness requires an appropriate assertion/review state and evidence context.
- A later successor assertion may close the predecessor validity interval when evidence supports a transition.
- Historical assertions remain preserved after their validity interval closes.

## Knowledge time

Knowledge time describes the observatory's handling of evidence and claims.

Core fields:

```text
observed_at
adjudicated_at
published_at
release_id
```

Definitions:

- `observed_at`: when a source was retrieved or a controlled inspection was recorded.
- `adjudicated_at`: when a candidate assertion/change received the relevant human or controlled programme disposition.
- `published_at`: when the assertion entered an authorized public release, if it did.
- `release_id`: immutable release identity that first or currently carries the canonical assertion representation.

Knowledge-time fields describe programme history. They do not backdate substantive truth.

## Source publication/record time

Sources may also carry their own date fields:

```text
source_published_at
source_updated_at
source_effective_at
```

These are source metadata and must remain distinguishable from both valid time and observatory knowledge time.

A source's stated publication date is not the same as the date on which every claim within it became valid.

## Observation succession

A logical source can have many observations:

```text
SRC-001
  -> OBS-2026-07-29-A
  -> OBS-2026-08-29-B
  -> OBS-2026-09-29-C
```

Observations are append-only identities. A later observation does not overwrite an earlier observation.

Comparison may classify the transition between two observations, for example:

```text
NO_CHANGE
COSMETIC_CHANGE
SOURCE_MOVED
SOURCE_REMOVED
METADATA_CHANGE
MATERIAL_FACT_CHANGE
RETRIEVAL_FAILURE
ACCESS_RESTRICTED
```

A comparison classification is operational evidence. It is not by itself a canonical substantive assertion.

## Assertion succession

Assertions are also append-only identities.

If the represented state changes, create a successor assertion and preserve the predecessor.

Example:

```text
AST-A
subject: SYSTEM-X
predicate: TRIAL_STATUS
value: RECRUITING
valid_from: 2026-01-10
observed_at: 2026-01-12

AST-B
subject: SYSTEM-X
predicate: TRIAL_STATUS
value: ACTIVE_NOT_RECRUITING
valid_from: 2026-06-03
observed_at: 2026-06-05
supersedes: [AST-A]
```

If the transition date cannot be established, the programme must not invent `valid_until` for `AST-A`. It may instead preserve an explicit uncertainty interval or unresolved transition boundary.

## Correction versus world change

The model must distinguish:

### World change

The prior assertion was supported for an earlier period and a later state became true.

Example: trial recruitment status changes.

### Observatory correction

The prior canonical representation was found to be incorrect, overbroad, or misclassified.

The correction must preserve the erroneous predecessor in release history and create a successor with correction provenance. The programme must not rewrite the historical release to make it appear that the error never existed.

### Source correction

The publisher corrects or retracts a source. The observatory records the source-level event and separately decides what dependent assertions or assessments require review.

## Current state queries

"Current" is a derived projection, not a primitive truth field.

A current-state projection should consider at least:

- assertion valid-time information;
- successor/supersession lineage;
- canonical publication state;
- explicit lifecycle resolution;
- unresolved conflicts;
- the query's jurisdiction, system configuration, and evidence cutoff.

A projection must not select the record with the greatest timestamp and assume it is substantively current.

## As-of queries

The architecture must support two independent query modes.

### World-time as-of

> What state does the current canonical evidence represent for date T?

Uses valid-time semantics.

### Knowledge-time as-of

> What had the observatory canonically represented by date T?

Uses publication/release history and observation/adjudication time.

This distinction is required for reproducibility and historical accountability.

## Assessment evidence freeze

An assessment evidence freeze remains independent of the current observatory state.

If an assessment was executed with evidence cutoff `T0`, later observations do not silently enter the assessment. They can create a dependency impact and reopening proposal.

The reopened assessment or successor assessment must record its own new evidence freeze.

## Dates with incomplete precision

Current records contain dates with different precision, including exact dates, years, and null values. Migration must preserve that precision.

Do not convert:

```text
"2026"
```

into an invented date such as:

```text
"2026-01-01"
```

The v2 representation should support date precision explicitly where needed:

```text
temporal_value: "2026"
temporal_precision: YEAR
```

or retain an equivalent lossless source value until normalized semantics are governed.

## Clock and timezone requirements

- Machine event timestamps should use RFC 3339/ISO 8601 with explicit offset or `Z` when an actual timestamp is known.
- Source-reported local dates may remain dates without timezone when the source does not support finer precision.
- Collector receipt time and source publication time must never be conflated.

## Migration rule

The v1-to-v2 migration must preserve existing dates exactly unless a deterministic normalization is lossless and reversible. Where current records do not establish valid time, the migration must leave valid time unresolved and carry existing retrieval/effective-date semantics into the appropriate knowledge/source-time fields.
