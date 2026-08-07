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
