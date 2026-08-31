# Compatibility identity

Status: implementation contract. These identities remain distinct. Equality of one never establishes another, and none of them grants canonical, public, or institutional authority.

## Why the identities must stay separate

Workbench software, a particular process that ran, S2 data-store metadata, a data-release producer, and a schema generation can share a similar-looking version string. Collapsing them hides whether a record was produced by the code that a reviewer thinks ran, whether a data repository is merely *compatible* with a Workbench line, or whether a schema generation changed.

## Five identities

### 1. Package version

Python distribution identity from `neuroai_workbench.__version__` (currently `0.3.0.dev0`).

This is the installable software line. It is not a git tag, not a data-release authorization, and not proof that a particular commit executed.

### 2. Runtime execution pin

The exact Workbench git commit (and, when recorded, Python version, platform, and dependency lock) that executed a workflow.

A package version can be built from many commits. An execution pin names one. CI logs, collector configuration hashes, and discovery run provenance should bind this pin when they claim reproducibility.

### 3. S2 `WORKBENCH_VERSION`

The string stored in the observatory-data template at `templates/neuroai-observatory-data/WORKBENCH_VERSION`.

This is a **compatibility declaration** for the public data store: which Workbench package line the data repository currently documents as compatible. S2 may continue to record `0.3.0.dev0` until a data release independently pins a producer commit. It is not the commit that produced a given release candidate.

### 4. Data-release producer commit

The exact Workbench commit that produced or verified a particular observatory release candidate (descriptor / manifest / JSONL set).

A candidate compiler must record this separately from package version and from S2 `WORKBENCH_VERSION`. Changing the producer commit without changing the package version is a real identity change.

### 5. Schema version

The generation of a JSON Schema or object family (for example observatory-graph object schemas, collector contracts, v4.2 assessment kernel).

Schema validity is mechanical. It does not establish substantive truth, release authorization, or compatibility of a runtime pin with a producer commit. The v4.2 requirement identifiers remain a separate normative kernel and are not an observatory-graph schema version.

## Recording rule

When a candidate descriptor or run record mentions Workbench identity, it must name which of the five it is using. Forbidden collapses:

- treating `0.3.0.dev0` as a `v0.3.0` tag;
- treating S2 `WORKBENCH_VERSION` as the producer commit;
- treating schema validation as execution-pin evidence;
- treating mechanical compiler PASS as `release_authorized=true`.

## Related documents

- [release-model-v2.md](release-model-v2.md)
- [v0.3-foundation-boundary.md](../releases/v0.3-foundation-boundary.md)
- [release-attestation.md](release-attestation.md)
