# Threat model

## Protected assets

- Neural, clinical, participant, caregiver, site and regulatory evidence.
- Exact system and configuration records.
- Assessment findings, dissent records and decision objects.
- Evidence custody, hashes, snapshots and event history.
- Review/model proposals, dispositions, application records, assessment history, and transaction journals.

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
17. A stale, malformed, expired, or replaced event lock is treated as valid ownership, or one writer deletes another writer's successor lock.
18. A trailer sidecar is trusted after historical log replacement or tampering.
19. A writer crashes after persisting event bytes and before persisting the corresponding trailer.
20. Evidence registration crashes between object, index, assessment, persistence, and event writes, leaving partial or divergent state.
21. Recovery overwrites an external change outside the recorded predecessor/successor transaction states.
22. A transaction journal or predecessor/successor snapshot is altered before recovery.
23. A transaction directory loses its journal and is incorrectly treated as harmless cleanup.
24. A review assignment is silently overwritten, branches into multiple successors, or remains effective after revocation.
25. An appeal or minority dissent is erased, overwritten, or omitted after a later statement or appeal disposition.
26. An accepted assistance or review proposal is treated as path authorization, allowing text different from the accepted proposal to enter the assessment.
27. A user without an active covering decision role applies an accepted proposal, or authority is revoked/superseded between the initial check and persistence.
28. A concurrent writer changes the target field after application planning but before persistence.
29. Assessment, persistence, history, or application-record files become durable even though the corresponding assessment-save event does not commit.
30. A forged or corrupt content-addressed assessment-history object is trusted because its filename matches the expected digest.
31. An application record path escapes the controlled case tree, or recovery deletes/overwrites a record outside the transaction boundary.
32. A crash leaves an assessment-save transaction `PREPARED` and later recovery incorrectly assumes commit or rollback despite a corrupt event chain, journal, snapshot, or divergent third state.

## Implemented controls

- Localhost binding by default in the CLI, Dockerfile `CMD`, and `compose.yaml`; non-loopback binding requires both `--allow-network` and `NEUROAI_ALLOW_NETWORK=1` (see `compose.network.yaml`). The network overlay is not an authenticated or TLS-terminated deployment.
- No remote JavaScript, CSS, fonts or analytics.
- Content Security Policy and defensive HTTP headers.
- Controlled path resolution and case identifiers, including observatory release versions and evidence object basenames via `ensure_identifier` / `safe_join`.
- Atomic JSON and evidence-object replacement with file `fsync` and POSIX parent-directory `fsync` after replacement.
- SHA-256 evidence registration and verification that refuses path-escaping index entries, unsafe basenames, digest/suffix mismatches, and escaping symlinks.
- Hash-chained event logs with durable filesystem coordination:
  - structured ownership records with unique lock identity, host, PID, process-start token, lease expiry, and explicit coordination-only authority;
  - immediate dead-owner recovery on the same host;
  - retention of a live same-host local owner after lease expiry;
  - fail-closed treatment of a foreign local-profile lock;
  - lease-expiry recovery for cooperative shared-filesystem writers;
  - ownership checks that refuse to delete or continue under a replacement lock;
  - append-only event persistence with complete-write handling and `fsync`;
  - content-addressed trailer indexes binding event count, head hash, log extent, final-event position, and file identity;
  - O(1) indexed-head verification and append preparation when the trailer is current;
  - full-chain fallback and trailer rebuild on missing, stale, malformed, tampered, or identity-mismatched indexes;
  - verified-prefix recovery of complete unindexed events and digest-recorded truncation of incomplete or invalid crash tails.
- Transactional local evidence registration:
  - one durable case-level registration lock covering recovery, ID allocation, preparation, durable writes, event completion, and terminal journal state;
  - write-ahead journals with self-hashes, exact predecessor hashes, exact desired hashes, and object-preexistence state;
  - hash verification of every staged evidence, predecessor, and desired snapshot before application or rollback;
  - idempotent forward completion only after object, index, assessment, and persistence match the complete desired state;
  - exact predecessor rollback only after every current file matches a recorded predecessor or successor state;
  - recovery blocking on journal corruption, snapshot corruption, third-state divergence, or object digest mismatch;
  - object removal only when the incomplete transaction created the object and the restored index contains no reference;
  - transaction-ID-keyed `ASSESSMENT_SAVED`, `EVIDENCE_ADDED`, and rollback events;
  - fail-closed quarantine of journal-less transaction directories with preserved bytes and `UNKNOWN_FAIL_CLOSED` status;
  - terminal compaction removing staged evidence and predecessor/successor snapshot copies.
- Schema and semantic validation with explicit `DRAFT_INVALID` / `VALID` persistence labeling.
- Decision-object separation and explicit result boundaries.
- Programme-adapter fail-closed mappings for unknown evidence, access, and decision states.
- Reproducible tests, checksum manifests and Git history.
- Integrity-addressed review assignments, statements, dispositions, appeals, and appeal dispositions linked to the case event chain.
- Review-role scope checks, refusal of decision-role self-assignment, and explicit local-identity and authority boundaries (`LOCAL_UNAUTHENTICATED_ATTRIBUTION`).
- Append-only review-assignment lineage with predecessor ID/digest binding, unique-successor and cycle checks, case-lock serialization, effective-state derivation, timestamp-scoped historical authorization, and event-linked supersession/revocation records.
- Append-only appeal and dissent records that bind source-statement digests, refuse silent erasure after later dispositions, require decision-role authority at disposition time, and verify event correspondence without mutating assessments.
- Provider-neutral model-assistance records with selected context, credential-pattern guards over prompt and context, evidence-reference checks, stale-request rejection, hashes and mandatory human disposition.
- Accepted-proposal application hardening:
  - application is a separate explicit operation; disposition alone never mutates the assessment;
  - assistance patches must match exact `(target_path, proposed_text)` suggestions; `ACCEPTED_AS_DRAFT` applies the complete set and `PARTIALLY_USED` a non-empty proper subset;
  - review application accepts one exact `proposed_change`; `PARTIALLY_ACCEPTED` is refused until a successor statement records exact accepted wording;
  - the actor must hold an active `LEAD_ASSESSOR` or `DECISION_AUTHORITY` assignment covering every target;
  - assignment hashes, lineage, event correspondence, event-chain validity, and trailer validity are checked before authority is accepted;
  - authority and field predecessor values are rechecked inside the case mutation lock immediately before persistence;
  - application records bind before/after field values and hashes, assessment digests, proposal/disposition digests, and authority-assignment digests;
  - proposal, response, statement, and disposition source bytes are checked unchanged after application;
  - application-record paths are resolved inside the controlled case tree and path escape is refused.
- Transactional ordinary assessment saves:
  - `transactions/assessment-saves/<transaction_id>/transaction.json` is self-hashed and uses `PREPARED`, `COMMITTED`, and `ROLLED_BACK` states;
  - predecessor assessment and persistence snapshots are retained only as needed for recovery;
  - assessment history under `history/assessments/<sha256>.json` is re-hashed before trust or reuse;
  - a pre-event failure rolls back assessment, persistence, new application records, and newly created history;
  - a durable transaction-keyed `ASSESSMENT_SAVED` event is the commit witness;
  - logical `ASSISTANCE_PROPOSAL_APPLIED` and `REVIEW_PROPOSAL_APPLIED` actions are embedded in the single physical save event under `related_events`;
  - recovery of a remaining `PREPARED` journal either verifies durable commit or performs exact rollback;
  - invalid event chains, corrupt journals/snapshots, duplicate transaction events, or divergent committed state block automatic recovery.
- Metadata-only evidence requests, public-URL filtering, local-path rejection, credential-pattern guards, explicit no-byte flags, and out-of-band `NOT_VERIFIED_BY_WORKBENCH` material states.
- Discovery query execution is offline-first; opt-in network mode requires `NEUROAI_LIVE_DISCOVERY=1`, reuses collector public-URL SSRF checks, emits candidate source proposals only, and refuses silent registry overwrite in favour of append-only successor drafts (ADR 0010).
- Shadow-refresh evaluation handoff samples only quarantine records already `APPROVED_FOR_HANDOFF`; `approve_handoff` / `--approve-handoff` consents to that handoff and does not auto-approve pending captures.
- The #43 core shadow-refresh cycle is complete. Small-team dual review records claimed local opinions and a formal `NO_GO`; typed URL residual remains `KEEP_AS_TYPED_FAILURE` with `finding_effect = NONE`. Canonical `AUTHORIZED` / `PUBLISHED` gates remain deferred to issue #101.

## Residual risks

The application does not authenticate users or reviewers, verify institutional roles, encrypt files, isolate tenants, scan uploads comprehensively, verify signatures, establish source authenticity, or prevent a privileged local actor from replacing an entire workspace and its backups.

Event-chain locking coordinates cooperative writers through filesystem primitives. It is not distributed consensus, Byzantine fault tolerance, or hostile-writer fencing. A writer that ignores the protocol can still corrupt the log or sidecars. The shared-filesystem profile depends on filesystem coherence and bounded clock skew. O(1) indexed-head verification detects current trailer/final-event inconsistency but does not replace periodic full-chain verification for arbitrary historical tampering. Recovery records preserve discarded-byte digests, not discarded event bytes.

Evidence journaling coordinates one case on a cooperative filesystem. It does not provide cross-case transactions, remote database isolation, hostile-writer fencing, evidence authentication, legal custody, or disclosure authorization. Active transaction directories and journal-less quarantines may contain duplicate evidence and assessment state; they inherit the case's strongest protection, backup, retention, access-control, and incident-response requirements. A `RECOVERY_BLOCKED` journal or `UNKNOWN_FAIL_CLOSED` orphan requires controlled intervention. The software preserves divergent state instead of overwriting it.

Assessment-save journaling likewise coordinates cooperative local filesystem mutation only. It does not provide hostile-writer fencing, remote database isolation, hardware-level atomicity, or institutional authorization. A privileged actor can replace the case tree, event log, journals, and backups together. Recovery depends on integrity of the recorded event chain and predecessor snapshots; if those are corrupt or inconsistent, automatic recovery intentionally stops instead of inferring a safe state.

File and directory `fsync` reduce crash windows under the operating-system and filesystem guarantees available to the process. Storage-controller caches, hardware faults, network-filesystem semantics, privileged tampering, and incomplete backup sets remain outside those guarantees.

Review-assignment lineage coordinates cooperative local writers and preserves claimed attribution. It does not authenticate actors, prove institutional delegation, prevent a privileged writer from replacing the complete case tree, or establish that a transition rationale is truthful. Timestamp-scoped authorization depends on the recorded UTC order and event-chain integrity.

Appeal and dissent records preserve attributable disagreement under the same local-claim profile. Digests and event correspondence detect alteration of stored bytes; they do not prove that an appeal outcome is substantively correct or institutionally authorized.

Exact proposal binding proves that the applied text matches recorded accepted wording; it does not prove that the wording is correct, safe, clinically appropriate, legally valid, or authorized for publication. Local decision-role checks prove consistency with the reference workflow's stored assignment graph, not real-world identity or mandate.

The model-assistance guard is a bounded structural control (`ATTESTATION_PLUS_SECRET_SCAN_ONLY`), not a complete secret detector, redaction system, field-level classification, prompt-injection defence or provider-security assessment. Discovery result counts do not prove registry completeness or evidence authenticity. Quarantine `APPROVED_FOR_HANDOFF` and `--approve-handoff` remain local workflow gates, not authenticated institutional authority. Production deployment, institutional identity, canonical release governance, and direct provider integration require separate architectures and independent review.
