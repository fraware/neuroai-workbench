# Threat model

## Protected assets

- Neural, clinical, participant, caregiver, site, and regulatory evidence.
- Exact system and configuration records.
- Assessment findings, dissent records, and decision objects.
- Evidence custody, hashes, snapshots, and event history.
- Review and assistance proposals, dispositions, application records, assessment history, and transaction journals.
- Successor candidates, release attestations, publication records, and their exact digest bindings.

## Adversaries and failure modes

1. An unauthorised local user reads or changes workspace files.
2. A malicious document exploits a viewer opened outside the workbench.
3. A network client reaches a server bound beyond localhost.
4. A user imports a structurally valid assessment containing false or misleading claims.
5. Evidence bytes are replaced after registration.
6. Event history is edited, truncated, concurrently corrupted, or left with an incomplete crash tail.
7. Spreadsheet, JSON, and human-readable outputs diverge.
8. A software validity result is misrepresented as substantive conformance.
9. A dependency or build artifact is compromised.
10. Backups, exports, or logs leak protected information.
11. A local actor impersonates a reviewer or overstates a recorded role as authenticated institutional authority.
12. Review disagreement is deleted, rewritten, or hidden after disposition.
13. Sensitive context or credentials enter an assistance request, or a provider response attempts prompt injection or unsupported evidence attribution.
14. A provider response or human disposition is applied automatically and silently changes the assessment.
15. A metadata exchange leaks a local path, credential, participant detail, or protected evidence excerpt, or overstates an out-of-band reference as verified receipt.
16. A discovery query or opt-in network result is treated as an authorized registry source, or silent in-place registry overwrite bypasses human acceptance and append-only succession.
17. A stale, malformed, expired, or replaced event lock is treated as valid ownership, or one writer deletes another writer's successor lock. On Windows, lock liveness checks must not use `os.kill(pid, 0)` (CTRL_C_EVENT); owner unlock and contended reads must tolerate brief sharing violations without leaving an unrecoverable live-PID lock.
18. A trailer sidecar is trusted after historical log replacement or tampering.
19. A writer crashes after persisting event bytes and before persisting the corresponding trailer.
20. Evidence registration crashes between object, index, assessment, persistence, and event writes, leaving partial or divergent state.
21. Recovery overwrites an external change outside the recorded predecessor/successor transaction states.
22. A transaction journal or predecessor/successor snapshot is altered before recovery.
23. A transaction directory loses its journal and is incorrectly treated as harmless cleanup.
24. A review assignment is silently overwritten, branches into multiple successors, or remains effective after revocation.
25. An appeal or minority dissent is erased, overwritten, or omitted after a later statement or appeal disposition.
26. An accepted assistance or review proposal is treated as path authorization, allowing text different from the accepted proposal to enter the assessment.
27. A user without an active covering decision role applies an accepted proposal, or authority is revoked or superseded between initial check and persistence.
28. A concurrent writer changes the target field after application planning but before persistence.
29. Assessment, persistence, history, or application-record files become durable even though the corresponding assessment-save event does not commit.
30. A forged or corrupt content-addressed assessment-history object is trusted because its filename matches the expected digest.
31. An application record path escapes the controlled case tree, or recovery deletes or overwrites a record outside the transaction boundary.
32. A crash leaves an assessment-save transaction `PREPARED` and later recovery incorrectly assumes commit or rollback despite a corrupt event chain, journal, snapshot, or divergent third state.
33. A release attestation is persisted with a semantically impossible `AUTHORIZE` state even though one required domain blocks release or an unresolved `BLOCKS_RELEASE` condition exists.
34. A published authorization is superseded later, invalidating the publication's active-authorization binding after the publication record was validly created.
35. Concurrent path containment checks treat Windows extended (`\\?\`) and ordinary path forms as different roots and refuse legitimate writes inside a controlled quarantine tree.
36. A collector transport reconnects by hostname after DNS validation, allowing DNS rebinding between check and connect.
37. Network capture proceeds because `NEUROAI_LIVE_COLLECTION=1` is set, without an attributable authorization packet.
38. Quarantine approval overwrites the pending capture record, erasing the pending state.
39. A candidate compiler mechanical PASS is treated as `release_authorized=true` or as six-domain attestation PASS.
40. An institutional OIDC/SAML adapter stub is treated as verified authentication, or auth is bound to the local `ThreadingHTTPServer` and called production.
41. Empty-basis `NO_REOPENING` / `NO_EFFECT` recommendations are misread as “nothing changed,” or non-deterministic recommendation ids prevent reproducible review.
42. Fuzzy name similarity auto-merges entities, or directed identity relations delete predecessor ids.

## Implemented controls

### Local service and content boundary

- Localhost binding by default in the CLI, Dockerfile `CMD`, and `compose.yaml`; non-loopback binding needs both `--allow-network` and `NEUROAI_ALLOW_NETWORK=1` through the documented network overlay.
- No remote JavaScript, CSS, fonts, or analytics.
- Content Security Policy and defensive HTTP headers.
- Controlled path resolution and identifiers via `ensure_identifier` / `safe_join`.
- `safe_join` compares extended and ordinary Windows path forms so concurrent resolve results inside a controlled root are not rejected as escapes.

The network overlay is not an authenticated or TLS-terminated institutional deployment.

### Evidence integrity and event history

- Atomic JSON and evidence-object replacement with file `fsync` and POSIX parent-directory `fsync` after replacement.
- SHA-256 evidence registration and verification that refuses path escape, unsafe basenames, digest/suffix mismatches, and escaping symlinks.
- Hash-chained event logs with durable filesystem coordination, structured lock ownership, dead-owner recovery, replacement-lock checks, append-only persistence, content-addressed trailer indexes, full-chain fallback, and verified-prefix crash-tail recovery.
- Trailer indexes bind event count, head hash, log extent, final-event position, and file identity.

### Transactional evidence and assessment mutation

- Case-level evidence-registration serialization covers recovery, ID allocation, preparation, durable writes, event completion, and journal cleanup.
- Write-ahead journals bind exact predecessor and desired hashes, staged evidence, and object-preexistence state.
- Automatic recovery proceeds only when current state matches recorded predecessor/successor states; third-state divergence, corrupt journals, corrupt snapshots, and object digest mismatch fail closed.
- Journal-less transaction directories are quarantined as `UNKNOWN_FAIL_CLOSED`.
- Ordinary assessment saves use self-hashed `PREPARED`, `COMMITTED`, and `ROLLED_BACK` journals.
- A durable transaction-keyed `ASSESSMENT_SAVED` event is the commit witness.
- Content-addressed assessment history is re-hashed before trust or reuse.
- Interrupted saves either verify durable commit or perform exact rollback; ambiguous or corrupt state blocks recovery.

### Assessment, review, and proposal controls

- Schema and semantic validation with explicit `DRAFT_INVALID` / `VALID` persistence labels.
- Decision-object separation and explicit result boundaries.
- Programme-adapter fail-closed mappings for unknown evidence, access, and decision states.
- Integrity-addressed review assignments, statements, dispositions, appeals, and appeal dispositions linked to the case event chain.
- Append-only review-assignment lineage with predecessor ID/digest binding, unique-successor and cycle checks, revocation, and event correspondence.
- Appeal and dissent records preserve attributable disagreement and refuse silent erasure after later dispositions.
- Provider-neutral assistance records use selected context, credential-pattern guards, evidence-reference checks, stale-request rejection, hashes, and mandatory human disposition.
- Applying an accepted proposal is a separate explicit operation. The applied target path and text must match the recorded accepted proposal exactly.
- Active role authority, assignment digests, event correspondence, predecessor field values, and source records are rechecked immediately before persistence.
- Application records bind before/after values and hashes, assessment digests, proposal/disposition digests, and authority-assignment digests.

### Protected evidence and discovery

- Metadata-only evidence requests, public-URL filtering, local-path rejection, credential-pattern guards, explicit no-byte flags, and out-of-band `NOT_VERIFIED_BY_WORKBENCH` material states.
- Discovery is offline-first. Opt-in network discovery reuses public-URL SSRF controls, emits candidate source proposals only, and refuses silent registry overwrite in favour of append-only successor drafts.
- Shadow-refresh handoff samples only quarantine records already `APPROVED_FOR_HANDOFF`; approval does not convert pending captures into accepted evidence automatically.
- Production HTTP collection uses `PinnedSocketHttpTransport`, which connects only to DnsGuard-approved IP literals, preserves Host/SNI, does not self-follow redirects, and records the connected address per response without mutable `last_connected_address` state.
- `EvidenceCollectionService` requires an authorization packet; `NEUROAI_LIVE_COLLECTION=1` is an additional gate, not a sufficient gate. Default CLI and data builds remain offline.
- Quarantine approval and rejection write immutable successor records. Scanning, rights, and retention hooks are custody metadata and are not substantive adjudication.
- The candidate release compiler binds attestation stubs to the candidate manifest digest, starts six domains at PENDING, and never sets `release_authorized=true`.

### Release attestation and publication

- The default canonical release path uses one append-only six-domain attestation by the designated repository authority.
- Every attestation contains exactly one judgment for `SECURITY`, `METHODOLOGY`, `DATA_GOVERNANCE`, `ACCESSIBILITY`, `DOMAIN`, and `AFFECTED_COMMUNITY`.
- `AUTHORIZE` fails closed if any domain is `BLOCK` or any unresolved condition has `release_effect = BLOCKS_RELEASE`.
- `WITHHOLD` is a first-class typed decision.
- Candidate binding includes the candidate's canonical digest plus SHA-256 of the declared deterministic `JSON_UTF8_INDENT2_LF` serialized representation. This is an explicit representation contract, not a claim about arbitrary differently formatted source bytes.
- Product identifiers and SHA-256 digests are canonicalized and bound into the attestation.
- The attestation verifier independently recomputes schema validity, record hash, policy/authority binding, event correspondence, canonical product/track/condition structure, six-domain completeness, authorization blocker semantics, serialization contract, and supersession integrity.
- An unpublished attestation may be superseded only by a new attestation over the same deterministic candidate representation.
- A published attestation is frozen. Corrections after publication use a new successor candidate and a new release decision.
- Publication is a separate append-only record that needs one active `AUTHORIZE` attestation plus publication evidence. Recording publication does not perform external publication automatically.
- The existing v1/v2 multi-record governance machinery remains available as an optional higher-assurance workflow where separate scope, opinion, disposition, readiness, or protected authority-evidence records provide concrete value.

The non-canonical shadow-refresh cycle and synthetic governance fixtures do not create a canonical release attestation, authorization, or publication decision.

## Residual risks

The application does not authenticate users or reviewers, verify institutional roles, encrypt files, isolate tenants, scan uploads comprehensively, verify signatures, establish source authenticity, or prevent a privileged local actor from replacing an entire workspace and its backups.

Event-chain locking coordinates cooperative writers through filesystem primitives. It is not distributed consensus, Byzantine fault tolerance, or hostile-writer fencing. A writer that ignores the protocol can corrupt logs or sidecars. Shared-filesystem operation depends on filesystem coherence and bounded clock skew. Indexed-head verification does not replace periodic full-chain verification for arbitrary historical tampering.

Evidence journaling coordinates one case on a cooperative filesystem. It does not provide cross-case transactions, remote database isolation, hostile-writer fencing, evidence authentication, legal custody, or disclosure authorization. Active transaction directories and quarantined orphans may contain duplicate protected state and inherit the case's strongest protection, backup, retention, access-control, and incident-response requirements.

Assessment-save journaling likewise does not provide hostile-writer fencing, remote database isolation, hardware-level atomicity, or institutional authorization. A privileged actor can replace the case tree, event log, journals, and backups together. Ambiguous recovery state intentionally stops instead of inferring a safe result.

File and directory `fsync` reduce crash windows under operating-system and filesystem guarantees available to the process. Storage-controller caches, hardware faults, network-filesystem semantics, privileged tampering, and incomplete backup sets remain outside those guarantees.

Review-assignment lineage and release-attestation records preserve claimed attribution. They do not authenticate actors, prove institutional delegation, or establish that a rationale is truthful or substantively correct. Digests and event correspondence detect stored-state alteration under the cooperative trust model; they do not create legal non-repudiation.

Exact proposal binding proves that applied text matches recorded accepted wording. It does not prove correctness, safety, clinical appropriateness, legal validity, or publication authority.

The assistance guard is a bounded structural control, not a complete secret detector, redaction system, field-level classification system, prompt-injection defence, or provider-security assessment. Discovery result counts do not prove registry completeness or evidence authenticity.

Passing software tests, module coverage gates, accessibility structure checks, deterministic product generation, or a release attestation do not establish scientific truth, clinical safety or effectiveness, regulatory or legal authorization, conformance, institutional readiness, external adoption, representative-user accessibility validation, or endorsement by an external institution. Production deployment, institutional identity, and external validation remain separate architectures and evidence programmes.
