# Data governance

The workbench follows data-minimisation and federated-evidence principles.

## Default policy

- Keep raw neural and participant-protected data with the lawful custodian when possible.
- Register controlled metadata, access state, holder, authorization requirement, checksum and decision relevance.
- Import bytes only when the assessor is authorised to preserve them locally.
- Use participant-controlled records and confidentiality classifications explicitly.
- Exclude credentials, access tokens and decryption keys from case bundles.
- Treat exports and backups as protected copies with their own retention and destruction rules.
- Treat review rationales, disagreement records, proposed changes, application records, transaction journals, and model-assistance context as potentially sensitive assessment metadata.
- Keep registered evidence bytes out of model-assistance requests. Include only the minimum selected structured fields required for the declared task.
- Exclude credentials, private evidence excerpts, participant identifiers, protected security findings, and confidential legal analysis from review or model-assistance free-text fields.

## Local evidence store

Evidence bytes are content-addressed by SHA-256 and stored under the case directory. Newly registered local files receive `access_state: EVALUATION NOT EXECUTED` and `publication_or_record_state: LOCAL CONTROLLED RECORD`, preserving the distinction between local custody and public evidence. The workbench provides byte-integrity checks. It provides no encryption, source authentication, lawful-custody proof, or substantive appraisal.

### Evidence-registration transaction journal

Local evidence registration uses a case-scoped write-ahead journal under `evidence/transactions/`. During an active transaction, the transaction directory temporarily contains:

- one staged copy of the evidence bytes;
- predecessor and desired copies of the evidence index;
- predecessor and desired assessment and persistence records for linked registration;
- a self-hashed transaction record containing state hashes, evidence metadata, assessment-event metadata, object-preexistence state, timestamps, and the byte-identity boundary.

Every staged predecessor and desired image is hash-verified before application or rollback. Parent-directory metadata is flushed after atomic replacement, transaction-directory creation, quarantine rename, and controlled removal on POSIX.

After `COMMITTED` or `ROLLED_BACK`, the workbench removes staged evidence and predecessor/successor snapshot copies. The terminal journal retains transaction identity, hashes, timestamps, evidence identifiers, state, recovery outcome, and the byte-identity boundary.

A transaction directory lacking a durable journal moves into `evidence/transaction-orphans/`. Its bytes remain protected for controlled inspection. The event record uses `UNKNOWN_FAIL_CLOSED`; software makes no claim that external case state remained unchanged.

Transaction directories and orphan quarantines inherit the strongest protection, retention, backup, access-control, legal-hold, incident-response, and destruction requirements of the evidence and assessment content they contain. They remain outside public exports and Git repositories.

Recovery follows three controlled outcomes:

- **forward completion** after every durable surface matches the recorded desired hashes;
- **exact rollback** after every durable surface matches either the recorded predecessor or successor hash;
- **recovery blocking or orphan quarantine** after corruption, third-state divergence, unexpected object bytes, or missing transaction identity.

Linked registration preserves transaction-keyed `ASSESSMENT_SAVED` and `EVIDENCE_ADDED` events. Rollback preserves an `EVIDENCE_REGISTRATION_ROLLED_BACK` marker and performs no selective historical-finding edits.

SHA-256 equality establishes byte identity only. It carries no source-authenticity, lawful-custody, relevance, completeness, disclosure-authorization, or substantive-status claim.

## Assessment-save transaction journal

Ordinary `Workspace.save_case` mutations use a separate case-scoped transaction journal under `transactions/assessment-saves/<transaction_id>/`. Proposal application relies on this path; it does not introduce an independent assessment writer.

A prepared assessment-save transaction contains a self-hashed `transaction.json` and temporary predecessor snapshots needed for exact rollback. The journal binds:

- transaction ID and actor;
- predecessor and planned successor assessment digests;
- predecessor and successor persistence digests;
- the content-addressed assessment-history path;
- whether that history object was newly created;
- every exclusive case-contained application-record path and digest;
- the local filesystem transaction boundary.

The transaction state machine is `PREPARED` to either `COMMITTED` or `ROLLED_BACK`. Before durable event commit, failure restores the predecessor assessment and persistence state, removes newly created exclusive application records, and removes a newly created history object after hash verification. After durable event commit, recovery requires the transaction-keyed `ASSESSMENT_SAVED` event and the recorded successor/application digests to match before marking the transaction `COMMITTED`.

A later save recovers any remaining `PREPARED` transaction before beginning a new mutation. If the matching durable event is absent, exact rollback is attempted. If the event chain is invalid, the journal hash is invalid, a predecessor snapshot is missing or corrupt, an exclusive record has diverged, or committed state no longer matches the journal, automatic recovery stops. Operators must preserve the workspace for controlled inspection; recovery must not overwrite an unrecorded third state.

Temporary predecessor assessment and persistence snapshots are removed after a terminal transaction state. The terminal `transaction.json` remains audit metadata and follows the case retention schedule. `PREPARED` or recovery-blocked transaction directories may contain prior assessment state and therefore inherit the case's strongest classification, backup, legal-hold, access-control, incident-response, and destruction requirements.

Assessment history under `history/assessments/<sha256>.json` is content-addressed and re-hashed on load and reuse. A matching filename is not sufficient evidence of integrity.

Proposal application commits one physical `ASSESSMENT_SAVED` event. Logical `ASSISTANCE_PROPOSAL_APPLIED` or `REVIEW_PROPOSAL_APPLIED` actions are retained under that event's `related_events` payload so assessment state, application record, and provenance share one recoverable commit boundary.

## Deletion and retention

Deletion is an administrative filesystem operation. Secure erasure depends on the storage medium, filesystem, backup system and hosting environment. Institutional deployments must adopt a retention schedule, legal-hold process, backup policy, participant-withdrawal process and destruction-verification procedure.

Terminal transaction metadata follows the case audit-retention schedule. Non-terminal, recovery-blocked, and journal-less quarantined transactions remain protected until controlled resolution, as they may contain the only predecessor, successor, or staged bytes needed to interpret the case accurately.

## Collaborative review records

Review assignments, assignment-transition rationales, statements, disagreements, dispositions, appeals, appeal dispositions, and proposal-application records are stored as integrity-addressed local records. Assignment changes append predecessor-bound `SUPERSEDES` or `REVOKES` records; predecessor files remain immutable, and effective authority is derived from the unique lineage tip. Appeals bind source-statement digests and remain visible after later dispositions; appeal outcomes do not erase prior positions. Reviewer identifiers and roles are claimed workflow metadata; the reference implementation does not authenticate a person, institution, licence, mandate or delegated authority. Review, transition, appeal, and application text may contain sensitive interpretations, personnel information, availability information, or conflict context even in the absence of evidence bytes, so institutions must classify, retain, disclose and redact these records deliberately.

A disposition records how a local workflow handled a statement or appeal. It does not edit the assessment and does not itself establish scientific, legal, clinical or institutional authority. Accepted changes enter the assessment through a separate controlled change with ordinary provenance (`assist-apply` / `review-apply`), exact proposal binding, covering local decision-role checks, recoverable prior assessment history, and an explicit application record.

## Model-assistance records

The default workflow exports selected structured context and imports a candidate response. Requests, responses and human dispositions are hashed and attributable to the recorded provider and model identifiers. The workbench does not contact a provider by default. Applying an accepted draft requires a separate human command with exact proposal-bound field patches and active covering local decision-role assignments; disposition alone never mutates the assessment. Any provider integration must define lawful basis, user opt-in, data classification, redaction, provider retention, provider training use, geographic processing, incident response and deletion requirements.

## Protected-evidence metadata exchange

The exchange workflow records the minimum structured metadata required to request controlled evidence from a lawful custodian. It excludes evidence bytes, local paths, credentials and access tokens. Public URLs may be retained; non-public access locations remain outside the workbench request.

A holder response may record access conditions, a non-secret holder reference and an optional supplied digest. The workbench marks every out-of-band material `NOT_VERIFIED_BY_WORKBENCH`. Receipt, transfer, authentication and substantive appraisal require a separate authorized evidence workflow.

## Discovery query records

Discovery runs and candidate source proposals are workflow metadata stored under an operations discovery workspace. Default execution is offline through fixtures or replay. Opt-in network discovery requires an explicit environment gate and public-URL SSRF checks. Public synthetic fixtures may enter the software repository; live result bodies and protected captures remain outside public Git. Discovery acceptance creates append-only registry successor drafts and carries no canonical publication authority.

The ClinicalTrials.gov reference programme identity is `SU-TRIAL`. `SU-TRIALS` is a documentation alias only. Programme execution emits candidates and coverage reports. It does not mutate S2 or a live monitor registry.

## Collector quarantine custody

Quarantine records may carry optional rights/redistribution, retention-policy, and content-safety scan hooks. The default scanner is fail-closed and never reports CLEAN. Scanning is not substantive adjudication. Approval and rejection append successor records; pending capture records remain immutable. Successful retrieval remains `RETRIEVED_BYTES_NOT_SUBSTANTIVELY_ADJUDICATED` and does not write canonical S2.

## Candidate graph releases

The candidate release compiler writes descriptor, manifest, SHA256SUMS, JSONL object classes, verification report, and PENDING six-domain attestation stubs bound to the manifest digest. Mechanical PASS does not authorize publication. Attestation recording remains `release_attestation.py`.

## Acquisition policy records — online-first phase 1

Issue #279 introduces acquisition policies as operational metadata. A policy contains a policy/programme identifier, a claimed local approver identity, an approval window, per-source execution modes, per-source exact public-network origins, explicit fallback semantics, the fixed authority boundary, and a SHA-256 digest over its canonical representation. It contains no evidence bytes, credentials, access tokens, decryption keys, benchmark secrets, release authorization, or publication record.

Per-source origin binding is a data-minimisation and least-privilege control: one source receives only the origins explicitly assigned to that source. A policy with multiple sources does not imply that each source may contact every origin listed elsewhere in the policy. Replay-only rules carry no network origins. Prior-capture fallback is explicit and is available only to `ONLINE_PREFERRED` rules that opt into `EXPLICIT_PRIOR_CAPTURE_ALLOWED`.

Policy success does not confer live execution permission. During Phase 1 the existing digest-bound live authorization packet and `NEUROAI_LIVE_COLLECTION=1` remain independently required, and the default workflow remains offline. The policy module is not yet bound into scheduler or collector execution. Production policy records, when introduced later, should be treated as operational control records: operator identifiers and source-origin topology may be sensitive even when all source URLs are public, and retention/access rules should reflect that operational sensitivity.

The policy digest establishes stored-object integrity under the local cooperative trust model only. It does not authenticate the approver, prove institutional delegation, establish lawful collection rights, establish source authenticity, adjudicate retrieved content, admit records to canonical S2, or authorize release/publication. Existing DnsGuard/public-address checks, pinned-peer verification, quarantine custody, content scanning, rights/redistribution metadata, and retention controls remain separate requirements.

A later executor-binding phase must record the exact policy ID/digest in deterministic run provenance, distinguish fresh live captures from prior-capture fallback, retain capture age/original identity when fallback occurs, and keep protected/live capture bodies outside public Git. Those runtime and retention transitions are outside Phase 1 and require separate review before any online-first default is enabled.

## Phase 3 runtime-proof records

Issue #287 introduces two additional operational record classes: controlled Phase 3 run references and a deterministic runtime-proof bundle. They are audit metadata over the collector quarantine/run-ledger state; they are not canonical S2 objects, assessment records, release attestations, or publication records.

A Phase 3 proof may contain the exact programme/source/policy identifiers, collector `result_id`, original `retrieved_at`, capture SHA-256 and byte size, normalized ClinicalTrials.gov projection, projection digest, live/replay run IDs, run-summary/manifest/binding/checkpoint digests, route labels, attempt/retry/recovery counts, and source/target coverage. `created_at` and output filesystem location are excluded from the semantic digest so recurrence over the same durable semantic state can be checked independently of file-emission time and path.

Live response bodies remain only under the controlled collector quarantine root. They must not be copied into the public repository or embedded in the proof bundle. The proof verifier reads and re-hashes those bytes in place, projects the structured JSON, and records hashes/provenance. Replay reuses the exact stored result identity and does not mint a fresh capture or rewrite the original timestamp.

The normalized projection is derived from public source fields but still inherits the operator's applicable source-rights, retention, classification, and redistribution analysis. Inclusion of a structured projection in a proof bundle does not authorize redistribution of the underlying captured response body and does not convert the source into accepted canonical evidence.

The opt-in proof runner requires an explicit operator-controlled proof-output directory and `--confirm-noncanonical-output`. That confirmation is a local workflow assertion that the destination is outside canonical S2; it is not an authenticated deployment policy or a substitute for filesystem/tenant isolation. Institutions that deploy the proof runner must enforce an actual storage boundary preventing proof output and quarantine material from being written into canonical/public release locations accidentally.

Live mode additionally requires the existing digest-bound live authorization packet, `NEUROAI_LIVE_COLLECTION=1`, and the exact acquisition policy before network transport is constructed. Authorization packets and acquisition policies should be retained according to operational audit needs, but credentials, tokens, decryption keys, and confidential authorization evidence must remain outside proof bundles and public Git. The proof run reference records authorization IDs/digests only; these establish local recorded provenance, not institutional delegation or lawful collection rights.

CI proof fixtures use synthetic/public ClinicalTrials.gov-shaped JSON and injected transport/DNS. CI output is test evidence only. An actual external live proof is separately executed and reviewed; until that evidence exists, a merged harness must not be described as completed Phase 3 proof or as justification for an online-first production default.

Runtime-proof hashes establish integrity and deterministic recomputation under the cooperative local trust model. They do not establish source authenticity, scientific or clinical truth, registry completeness, evidence adjudication, G0/G1/G2 passage, legal authority, canonical S2 admission, release authorization, or publication.
