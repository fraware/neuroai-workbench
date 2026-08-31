# S2/S3 evidence contract for Observatory v2

Status: **design contract; non-normative; non-canonical**

This document refines the existing five-store architecture for Observatory v2. It does not authorize transfer of protected evidence, change redistribution rights, or create an institutional custody model.

## Purpose

The observatory needs observation-level provenance without turning the public data repository into a repository of protected, licensed, copyrighted, or otherwise restricted evidence bytes.

The architectural rule is:

```text
S2 = public canonical evidence metadata and permitted public records
S3 = protected/restricted evidence bytes and sensitive operational evidence
```

A digest in S2 can bind an S3 object or an external public object. The digest proves byte identity under the declared representation only; it does not establish authenticity, lawful custody, completeness, relevance, or substantive truth.

## Source, observation, capture

These objects are distinct.

### Source

Logical identity of a publication, registry record, webpage, regulatory record, manual, announcement, legal text, dataset/model registry, or other controlled evidence resource.

### Observation

A time-specific record that the programme attempted or completed retrieval/inspection of a source.

### Capture

The actual retrieved bytes or controlled material, when preservation is authorized and technically possible.

A source may have many observations. An observation may have no stored capture, for example when retrieval failed, the research interface did not expose bytes, redistribution/custody was not authorized, or only metadata was permitted.

## S2 permitted content

Subject to programme publication review and redistribution rules, S2 may contain:

- source IDs and titles;
- publisher/issuer;
- public locator/URL;
- source class;
- jurisdiction and language metadata;
- source publication/effective dates when public;
- observation IDs and timestamps;
- retrieval method and outcome;
- HTTP/status metadata where public and non-sensitive;
- content type;
- representation/content digest where permitted;
- capture state and non-secret reference class;
- redistribution state;
- evidence/verification/review states;
- bounded support statements;
- claim boundaries and prohibited inferences;
- public excerpts only when redistribution is permitted and necessary;
- public disposition summaries;
- canonical assertions, relationships, events, dependencies, and reopening decisions approved for public release.

## S2 prohibited content

S2 must not contain, unless a separate reviewed public-release decision explicitly establishes otherwise:

- private neural data;
- participant records or participant identifiers;
- clinical records not already lawfully public and appropriate for republication;
- credentials, tokens, keys, cookies, or authenticated session material;
- private regulator, sponsor, or institutional files;
- protected security findings;
- licensed source captures lacking redistribution permission;
- copyrighted full-text captures where republication is not permitted;
- local protected filesystem paths;
- secret holder references;
- confidential legal or ethics analysis;
- model-assistance context containing protected evidence.

## S3 content

Depending on lawful authority and deployment controls, S3 may contain:

- authorized evidence captures;
- licensed documents;
- restricted regulator/sponsor materials;
- participant-related or clinical evidence;
- protected assessment evidence;
- controlled copies of public sources where redistribution is prohibited but local preservation is lawful;
- evidence transaction/quarantine material;
- sensitive evidence-exchange results.

S3 inherits the strongest applicable access, retention, backup, legal-hold, incident-response, and destruction requirements of its contents.

## Capture states

The v2 observation model should distinguish at least:

```text
NOT_ATTEMPTED
RETRIEVAL_FAILED
METADATA_ONLY
PUBLIC_EXTERNAL_REFERENCE_ONLY
CAPTURED_PUBLIC_REDISTRIBUTABLE
CAPTURED_PROTECTED_S3
CAPTURED_EXTERNAL_CUSTODIAN
INACCESSIBLE
WITHHELD_FROM_PUBLICATION
```

The exact controlled vocabulary belongs in schema resources. The important semantic rule is that `CAPTURED_PROTECTED_S3` does not mean the public repository contains or can retrieve the bytes.

## Capture reference boundary

S2 may record a non-secret, non-path-leaking reference sufficient to support controlled reconciliation, for example:

```text
capture_state: CAPTURED_PROTECTED_S3
content_sha256: ...
custody_reference_class: INSTITUTIONAL_EVIDENCE_OBJECT
```

S2 must not publish a local path, bucket secret, credentialed URL, access token, or identifier whose disclosure materially weakens protected access controls.

## Extraction boundary

An assertion may be supported by an extraction record that points to an observation and a source location.

For public redistributable text, a bounded excerpt may be retained where lawful and useful.

For copyrighted or protected text, use metadata such as:

```text
observation_id
source_location_type
page_or_section_reference
byte_or_character offsets where meaningful
excerpt_hash
```

without publishing the underlying protected excerpt.

The extraction contract must not overstate a digest of normalized or extracted text as a digest of the original file bytes.

## Collector boundary

Collectors can retrieve, quarantine, compare, and propose. They do not:

- decide source authenticity;
- decide scientific truth;
- accept evidence into an assessment automatically;
- publish a canonical assertion automatically;
- authorize redistribution;
- grant institutional custody authority.

Live capture bytes produced by public network monitoring remain outside the public Git working tree unless an explicit public-record publication path applies.

## Rights and redistribution

Every source/capture should carry an explicit redistribution state where material.

Examples:

```text
PUBLIC_REDISTRIBUTABLE
PUBLIC_REFERENCE_ONLY
NOT_PACKAGED_COPYRIGHTED_SOURCE
LICENSED_LOCAL_ONLY
PROTECTED_RESTRICTED
RIGHTS_UNRESOLVED
```

A public URL does not imply permission to redistribute a full capture.

## Evidence authenticity

Retrieval from an expected URL and a stable hash can establish that the programme observed specific bytes from a particular route. It does not by itself prove that:

- the publisher is who it claims to be;
- the source is legally authoritative;
- the content is scientifically correct;
- the record is complete;
- the record applies to the exact system/configuration under assessment.

Source authenticity and substantive weight require separate evidence and review.

## Institutional profile

An institutional S3 implementation must add controls outside the local reference profile, including authenticated identity, authorization, encryption, managed keys, audit, backup/recovery, retention/deletion/legal hold, incident response, and named evidence custodians.

The local Workbench metadata-only exchange and content-addressed evidence store remain reference mechanisms; they are not by themselves an institutional evidence service.

## Migration rule

Current public records that contain source metadata map to S2 source and observation objects. Current local digests or historical capture statements may map to S2 digest/capture-state metadata only. No migration step may copy protected or non-redistributable source bytes into S2 merely because a digest or local file once existed in the programme archive.
