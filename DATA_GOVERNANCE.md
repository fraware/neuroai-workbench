# Data governance

The workbench follows data minimisation and federated-evidence principles.

## Default policy

- Keep raw neural and participant-protected data with the lawful custodian when possible.
- Register controlled metadata, access state, holder, authorization requirement, checksum and decision relevance.
- Import bytes only when the assessor is authorised to preserve them locally.
- Use participant-controlled records and confidentiality classifications explicitly.
- Exclude credentials, access tokens and decryption keys from case bundles.
- Treat exports and backups as protected copies with their own retention and destruction rules.

## Local evidence store

Evidence bytes are content-addressed by SHA-256 and stored under the case directory. The workbench provides integrity checks, not encryption or authenticity verification.

## Deletion and retention

Deletion is an administrative filesystem operation. Secure erasure depends on the storage medium, filesystem, backup system and hosting environment. Institutional deployments must adopt a retention schedule, legal-hold process, backup policy, participant-withdrawal process and destruction verification procedure.
