# Review-state snapshot contract

## Purpose

The review-state snapshot is a deterministic, read-only interchange surface over the stored monitoring-review workflow. It gives a later deployment layer a stable machine-readable contract without requiring that layer to read workspace files directly or depend on browser-oriented API payloads.

Snapshot version `1` contains the stored reviewer profiles, queue-item projections, leases, lease-release records, and opinions, plus the review event-chain count and head hash. The snapshot is generated only after the underlying review queue passes integrity verification.

## Deterministic state identity

The contract deliberately represents stored facts, not clock-dependent convenience state. Records are ordered by their stable identifiers. Internal fields are excluded. No generation timestamp is present. Lease records retain their recorded claim and expiry timestamps, but the snapshot does not embed a derived `active` flag. A consumer that needs lease activity must evaluate the recorded lease and release facts against an explicit time supplied by that consumer.

The `snapshot_sha256` value is SHA-256 over the canonical JSON value of every snapshot field except `snapshot_sha256` itself. Identical stored review state therefore produces the same snapshot identity across repeated reads. The digest detects content drift; it is not a digital signature or an identity assertion.

## Integrity chain

Snapshot emission is fail closed.

1. The stored review queue must pass its existing integrity checks.
2. The review event chain must verify in full.
3. Every exported stored record is validated against its existing record schema.
4. The generated snapshot is validated against `REVIEW_STATE_SNAPSHOT.schema.json`.
5. The generated snapshot must pass the independent snapshot verifier before it is returned.

The event-chain `event_count` and `head_hash` bind the snapshot to the verified local review history. Queue-item projections retain their monitoring-record hashes. Profile, lease, lease-release, and opinion records retain their own content hashes.

## API surface

`GET /api/review/snapshot` returns snapshot version `1` from the local reference server. The route is read only. Existing review mutation routes are unchanged.

Consumers must reject unsupported snapshot versions. An incompatible field or semantic change requires a new snapshot version. A consumer must not infer compatibility solely from the presence of familiar fields.

## Data boundary

The snapshot excludes source-capture bodies, protected evidence bytes, credentials, and internal filesystem paths. It does contain claimed local profile metadata and review rationale. Those fields may be sensitive in a real deployment.

An institutional deployment remains responsible for identity, authorization, transport security, storage encryption, key management, network controls, logging, retention, privacy review, incident response, and other controls described by the institutional deployment profile. The reference server does not acquire those properties through this contract.

## Authority boundary

The snapshot establishes a deterministic read model and content-integrity check. It does not authenticate reviewers, prove institutional provenance, establish non-repudiation, authorize an adjudication, validate the substantive truth of evidence, establish regulatory or clinical conclusions, confer conformance, or authorize publication or release.

A later deployment layer may transport or persist this snapshot behind independently implemented security controls. It must preserve the snapshot version and digest semantics and must not reinterpret the digest as an authorization credential.
