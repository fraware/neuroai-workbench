# ADR 0015: Source versus Observation versus capture custody

## Status

Accepted as the Workbench provenance implementation ADR (handoff ADR-PROVENANCE-002). This ADR does not restate the Observatory v2 architecture essays. It binds Workbench code and schemas.

## Context

Collector capture, logical sources, and time-specific observations are easy to collapse. A successful HTTP retrieval can be misread as a Source, as a canonical Observation, or as S2 publication.

## Decision

1. A **Source** is a logical resource identity. It may persist while live bytes change.
2. An **Observation** is a time-specific retrieval or controlled inspection of a Source. Observations are append-only.
3. **Capture custody** is the quarantine/S3 holding of response bytes plus retrieval provenance. Successful retrieval remains `RETRIEVED_BYTES_NOT_SUBSTANTIVELY_ADJUDICATED`.
4. Capture must not write canonical S2 Source or Observation records.
5. Migration-origin records that lack a discovery-origin Source remain explicitly `migrated source-unresolved predecessor state` rather than invented Sources.
6. Connected-IP provenance, when a production transport is used, is part of retrieval provenance and is recorded per response without mutable `last_connected_address` state.

## Consequences

Collector, discovery, and the candidate release compiler may emit candidates and quarantined bytes. Canonical graph publication remains a separate attested release. Scanning, rights, and retention hooks on quarantine records are custody metadata, not adjudication.
