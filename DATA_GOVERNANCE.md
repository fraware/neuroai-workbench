# Data governance

The workbench follows data minimisation and federated-evidence principles.

## Default policy

- Keep raw neural and participant-protected data with the lawful custodian when possible.
- Register controlled metadata, access state, holder, authorization requirement, checksum and decision relevance.
- Import bytes only when the assessor is authorised to preserve them locally.
- Use participant-controlled records and confidentiality classifications explicitly.
- Exclude credentials, access tokens and decryption keys from case bundles.
- Treat exports and backups as protected copies with their own retention and destruction rules.
- Treat review rationales, disagreement records, proposed changes, and model-assistance context as potentially sensitive assessment metadata.
- Keep registered evidence bytes out of model-assistance requests. Include only the minimum selected structured fields required for the declared task.
- Do not place credentials, private evidence excerpts, participant identifiers, protected security findings, or confidential legal analysis in review or model-assistance free-text fields.

## Local evidence store

Evidence bytes are content-addressed by SHA-256 and stored under the case directory. The workbench provides integrity checks, not encryption or authenticity verification.

## Deletion and retention

Deletion is an administrative filesystem operation. Secure erasure depends on the storage medium, filesystem, backup system and hosting environment. Institutional deployments must adopt a retention schedule, legal-hold process, backup policy, participant-withdrawal process and destruction verification procedure.

## Collaborative review records

Review assignments, statements, disagreements and dispositions are stored as integrity-addressed local records. Reviewer identifiers and roles are claimed workflow metadata; the reference implementation does not authenticate a person, institution, licence, mandate or delegated authority. Review text can contain sensitive interpretations even when no evidence bytes are attached, so institutions must classify, retain, disclose and redact these records deliberately.

A disposition records how a local workflow handled a statement. It does not edit the assessment and does not itself establish scientific, legal, clinical or institutional authority. Accepted changes must be applied through a separate human-controlled assessment change with ordinary provenance.

## Model-assistance records

The default workflow exports selected structured context and imports a candidate response. Requests, responses and human dispositions are hashed and attributable to the recorded provider and model identifiers. The workbench does not contact a provider by default. Any provider integration must define lawful basis, user opt-in, data classification, redaction, provider retention, provider training use, geographic processing, incident response and deletion requirements.
