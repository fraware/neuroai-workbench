# Threat model

## Protected assets

- Neural, clinical, participant, caregiver, site and regulatory evidence.
- Exact system and configuration records.
- Assessment findings, dissent records and decision objects.
- Evidence custody, hashes, snapshots and event history.

## Adversaries and failure modes

1. An unauthorised local user reads or changes workspace files.
2. A malicious document exploits a viewer opened outside the workbench.
3. A network client reaches a server bound beyond localhost.
4. A user imports a structurally valid assessment containing false or misleading claims.
5. Evidence bytes are replaced after registration.
6. Event history is edited, truncated, concurrently corrupted, or left with an incomplete crash tail.
7. Spreadsheet, JSON and human-readable outputs diverge.
8. A software validity result is misrepresented as substantive conformance.
9. A dependency or build artifact is compromised.
10. Backups, exports or logs leak protected information.
11. A local actor impersonates a reviewer or overstates a recorded role as authenticated institutional authority.
12. Review disagreement is deleted, rewritten or hidden after disposition.
13. Sensitive context or credentials are included in a model request, or a provider response attempts prompt injection or unsupported evidence attribution.
14. A model response or human disposition is applied automatically and silently changes the assessment.
15. A metadata exchange leaks a local path, credential, participant detail, or protected evidence excerpt, or overstates an out-of-band reference as verified receipt.
16. A discovery query or opt-in network search result is treated as an authorized registry source, or silent in-place registry overwrite bypasses human acceptance and append-only succession.
17. A stale, malformed, or replaced event lock is treated as valid ownership, or one writer deletes another writer's successor lock.
18. A trailer sidecar is trusted after historical log replacement or tampering.
19. A writer crashes after persisting event bytes and before persisting the corresponding trailer.

## Implemented controls

- Localhost binding by default in the CLI, Dockerfile `CMD`, and `compose.yaml`; non-loopback binding requires both `--allow-network` and `NEUROAI_ALLOW_NETWORK=1` (see `compose.network.yaml`). The network overlay is not an authenticated or TLS-terminated deployment.
- No remote JavaScript, CSS, fonts or analytics.
- Content Security Policy and defensive HTTP headers.
- Controlled path resolution and case identifiers, including observatory release versions and evidence object basenames via `ensure_identifier` / `safe_join`.
- Atomic JSON and evidence-object writes.
- SHA-256 evidence registration and verification that refuses path-escaping index entries and escaping symlinks.
- Hash-chained event logs with durable filesystem coordination:
  - structured ownership records with unique lock identity, host, PID, process-start token, lease expiry, and explicit coordination-only authority;
  - immediate dead-owner recovery on the same host and lease-expiry recovery for cooperative shared-filesystem writers;
  - ownership checks that refuse to delete or continue under a replacement lock;
  - append-only event persistence with complete-write handling and `fsync`;
  - content-addressed trailer indexes binding event count, head hash, log extent, final-event position, and file identity;
  - O(1) indexed-head verification and append preparation when the trailer is current;
  - full-chain fallback and trailer rebuild on missing, stale, malformed, tampered, or identity-mismatched indexes;
  - verified-prefix recovery of complete unindexed events and digest-recorded truncation of incomplete or invalid crash tails.
- Schema and semantic validation with explicit `DRAFT_INVALID` / `VALID` persistence labeling.
- Decision-object separation and explicit result boundaries.
- Programme-adapter fail-closed mappings for unknown evidence, access, and decision states.
- Reproducible tests, checksum manifests and Git history.
- Integrity-addressed review assignments, statements and dispositions linked to the case event chain.
- Review-role scope checks, refusal of decision-role self-assignment, and explicit local-identity and authority boundaries (`LOCAL_UNAUTHENTICATED_ATTRIBUTION`).
- Provider-neutral model-assistance records with selected context, credential-pattern guards over prompt and context, evidence-reference checks, stale-request rejection, hashes and mandatory human disposition.
- No automatic assessment mutation from review or model-assistance records.
- Metadata-only evidence requests, public-URL filtering, local-path rejection, credential-pattern guards, explicit no-byte flags, and out-of-band `NOT_VERIFIED_BY_WORKBENCH` material states.
- Discovery query execution is offline-first; opt-in network mode requires `NEUROAI_LIVE_DISCOVERY=1`, reuses collector public-URL SSRF checks, emits candidate source proposals only, and refuses silent registry overwrite in favour of append-only successor drafts (ADR 0010).
- Shadow-refresh evaluation handoff samples only quarantine records already `APPROVED_FOR_HANDOFF`; `approve_handoff` / `--approve-handoff` consents to that handoff and does not auto-approve pending captures.
- The active core shadow-refresh cycle uses development-only dispositions and creates no reviewer-governance or release-authority state. Human governance is deferred to issue #101.

## Residual risks

The application does not authenticate users or reviewers, verify institutional roles, encrypt files, isolate tenants, scan uploads comprehensively, verify signatures, establish source authenticity, or prevent a privileged local actor from replacing an entire workspace and its backups.

Event-chain locking coordinates cooperative writers through filesystem primitives. It is not distributed consensus, Byzantine fault tolerance, or hostile-writer fencing. A writer that ignores the protocol can still corrupt the log or sidecars. Shared-filesystem lease recovery depends on filesystem coherence and bounded clock skew. O(1) indexed-head verification detects current trailer/final-event inconsistency but does not replace periodic full-chain verification for arbitrary historical tampering. Recovery records preserve discarded-byte digests, not the discarded event bytes themselves.

Transactional multi-step evidence registration remains incomplete until issue #23 lands. A crash between evidence bytes, index updates, assessment updates, and event records may still leave partial state even though the event substrate itself has durable append and recovery controls.

The model-assistance guard is a bounded structural control (`ATTESTATION_PLUS_SECRET_SCAN_ONLY`), not a complete secret detector, redaction system, field-level classification, prompt-injection defence or provider-security assessment. Discovery result counts do not prove registry completeness or evidence authenticity. Quarantine `APPROVED_FOR_HANDOFF` and `--approve-handoff` remain local workflow gates, not authenticated institutional authority. Production deployment, institutional identity, canonical release governance, and direct provider integration require separate architectures and independent review.