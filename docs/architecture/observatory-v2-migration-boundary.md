# Observatory v2 predecessor-migration boundary

Status: **design contract; non-normative; non-canonical**

This document defines the narrow exception required to migrate historical public governing records into the Observatory v2 evidence graph without fabricating provenance that the predecessor did not record. It does not weaken the evidence requirements for newly discovered or newly adjudicated claims.

## Governing rule

For ordinary v2 operation, a consequential accepted assertion is expected to carry explicit source provenance and, where available, observation-level provenance.

Migration is different. A predecessor release may contain a historically governed record whose source linkage or knowledge time was not encoded at record level. Lossless migration must preserve that state instead of either:

- inventing a source, observation, timestamp, or verification event;
- silently deleting the predecessor field;
- converting missing provenance into substantive `FAIL`; or
- silently upgrading the record to ordinary source-backed v2 evidence.

Accordingly, a migrated predecessor assertion may carry:

```text
review_state = MIGRATED_PREDECESSOR_STATE
record_state = NONCANONICAL_CANDIDATE
source_linkage_state = PREDECESSOR_SOURCE_LINKAGE_UNRESOLVED
source_ids = []
```

when and only when the predecessor record itself lacks source linkage.

Likewise, when the predecessor lacks a record-level knowledge time:

```text
knowledge_time_state = PREDECESSOR_TIME_UNRESOLVED
observed_at = null
```

No default date or midnight timestamp may be manufactured from a release date, evidence cutoff, file modification time, or migration execution time and presented as predecessor observation time.

## Source-linked predecessor state

When predecessor source IDs exist, migration must preserve them exactly:

```text
source_linkage_state = SOURCE_LINKED
source_ids = exact predecessor source_ids
```

When predecessor knowledge time exists, its literal value and precision must be preserved. A date-only value remains date precision; it must not be converted to an invented timestamp.

## Current v1.4 organization-array case

The immutable v1.4 `organizations` array contains 223 entries:

- 217 organization records;
- 6 entries explicitly reclassified as `NON_ORGANIZATION_PROVENANCE_NODE`;
- 154 source-linked entries with record-level `last_verified = 2026-07-29`;
- 69 entries without source IDs or record-level verification time, comprising 63 `LEGACY_ONLY` stubs and the 6 provenance nodes.

The six provenance nodes must remain provenance nodes. They must not be silently counted or promoted back into organizations.

The 69 source-unresolved entries remain historical migration state until separate evidence work establishes a source-backed successor assertion. Migration itself must not perform that evidence work implicitly.

## Promotion boundary

A migrated source-unresolved assertion cannot become canonical merely because it is schema-valid or because its predecessor payload is hash-preserved.

Any later source-backed successor requires the ordinary observatory path:

```text
source discovery or explicit evidence registration
  -> observation/evidence support
  -> entity resolution where needed
  -> candidate assertion
  -> substantive adjudication
  -> authorized successor release
```

The predecessor assertion remains in lineage and is superseded; it is not rewritten in place.

## Authority boundary

This exception preserves historical fidelity only. It does not establish that a predecessor assertion was true, sufficiently evidenced, current, institutionally endorsed, or appropriate for a new decision. Hash equality proves predecessor representation identity, not substantive correctness.
