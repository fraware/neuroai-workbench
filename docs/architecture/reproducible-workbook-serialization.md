# Reproducible workbook serialization

## Scope

The analytical workbook is a deterministic projection of canonical release data. Its package bytes participate in hashes, publication manifests, comparison workflows, and release verification. Identical input must therefore produce identical bytes independently of render time across the supported Python runtime matrix.

This contract applies to both the native XLSX package and the CSV-in-ZIP fallback. It does not change workbook field meanings, canonical data, assessment state, evidence, governance, review records, or publication authority.

## Canonical package contract

The serializer removes wall-clock and archive-writer metadata from the byte representation.

For native XLSX:

- workbook `created` and `modified` core properties are fixed to `2000-01-01T00:00:00`;
- ZIP members are rewritten in lexicographic filename order;
- every ZIP member uses the DOS epoch timestamp `1980-01-01T00:00:00`;
- member comments and extra fields are empty;
- archive comments are empty;
- creator system and external attributes are fixed;
- members use `ZIP_STORED`, avoiding compressor-version variability.

The CSV-in-ZIP fallback uses the same canonical metadata writer while retaining its established public member sequence: `README.txt`, `workbook.manifest.json`, then sheet CSVs sorted by sheet name. Preserving that stable sequence avoids an unnecessary format-contract change; determinism does not require the fallback package to adopt the native package's lexicographic ordering rule.

Duplicate member names are rejected instead of being normalized ambiguously.

## Verification

Unit tests manufacture source archives with deliberately different timestamps, member order, comments, extra fields, and file attributes, then require native-package canonicalization to converge to identical bytes. Native workbook tests also verify core document properties, package readability, release identity, and canonical ZIP metadata. Fallback tests verify both the established member sequence and the same timestamp, attribute, comment, extra-field, and storage-method normalization.

The supported Python 3.10–3.14 CI lanes execute a deterministic-workbook fingerprint check over the same synthetic serializer fixture. The fingerprint is intended to be pinned after cross-version calibration. Once pinned, a byte-level drift on any supported runtime fails that lane even when workbook semantics still parse successfully.

`neuroai_workbench/products/excel.py` has a permanent module coverage floor to keep the serialization contract exercised as it evolves.

## Change protocol

A deliberate change to the canonical serializer may change the expected fingerprint. Such a change should include:

1. a reviewed explanation of the byte-contract change;
2. updated adversarial tests;
3. a regenerated cross-version fingerprint that is identical on every supported Python lane;
4. exact-head CI and security verification.

A fingerprint update alone is insufficient evidence for accepting serializer drift.

## Boundaries

Byte determinism applies to bytes emitted by this renderer. Re-saving a workbook in another spreadsheet application creates a new package outside this contract. The guarantee also does not extend automatically to DOCX, PDF, third-party conversions, or future spreadsheet-writer versions unless their own deterministic contracts are established.
