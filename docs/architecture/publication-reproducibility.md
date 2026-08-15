# Reproducible narrative publication artifacts

## Scope

DOCX and PDF reports are deterministic projections of canonical release data. Their SHA-256 identities participate in publication metadata and release reconciliation, so identical canonical input must emit identical bytes across the supported Python 3.10-3.14 runtime matrix.

This contract extends the analytical-workbook byte-integrity boundary without changing report content, canonical records, assessment state, evidence state, governance state, review records, or publication authority.

## Shared OPC archive contract

ZIP-based publication packages use one deterministic archive primitive. It fixes member timestamps to the DOS epoch, clears archive/member comments and extra fields, fixes creator system and external attributes, uses `ZIP_STORED`, and rejects duplicate member names. Native OPC packages are normalized in lexicographic member-name order. Callers with an established public sequence can explicitly preserve that sequence.

The analytical workbook uses this shared implementation with its established serialization parameters. Its pinned SHA-256 remains a compatibility oracle during this refactor; a change to the shared primitive is unacceptable if the workbook fingerprint changes without a separately reviewed workbook byte-contract change.

## DOCX

The native DOCX renderer fixes `created` and `modified` core properties to `2000-01-01T00:00:00`, saves through the document library, then canonicalizes the OPC ZIP container. Member payloads are preserved during container normalization.

Verification covers repeated byte identity, fixed core properties, canonical ZIP metadata, package readability, release identity, substantive appendix tables, duplicate-member rejection, and the dependency-unavailable fallback path.

## PDF

The native PDF renderer enables the document template's instance-level invariant mode. The setting is passed into the PDF canvas/document layer, fixing renderer-controlled timestamps and document identifiers without process-global configuration. Existing page-stream compression remains disabled, avoiding compressor-version variability in the report byte contract.

Verification covers repeated byte identity, fixed invariant creation/modification metadata, PDF structure, release identity, substantive multi-page output, and the dependency-unavailable fallback path.

## Cross-version fingerprint protocol

Every supported Python lane runs the existing pinned XLSX fingerprint gate plus a publication fingerprint gate. The first exact-head matrix for this slice is calibration-only for DOCX and PDF: repeated byte identity and structure remain mandatory, the XLSX golden digest remains enforced, and DOCX/PDF digests are observed independently on Python 3.10, 3.11, 3.12, 3.13, and 3.14.

DOCX/PDF digests are pinned only after all five runtimes converge. A second exact-head matrix with those values enforced is required for merge evidence. Post-merge `main` must then pass the same enforced matrix.

## Change protocol

A deliberate change to a pinned publication byte contract requires an explanation of the serialization change, adversarial tests, fresh five-runtime calibration, exact-head CI and security verification, and an explicit compatibility assessment. Updating a fingerprint alone is insufficient evidence.

## Boundary

These guarantees apply to bytes emitted by this repository's renderers under the pinned product dependencies. Third-party re-saves, conversions, or edits create new artifacts outside this contract. Byte reproducibility does not confer scientific, regulatory, governance, or institutional authority on report contents.
