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
6. Event history is edited or truncated.
7. Spreadsheet, JSON and human-readable outputs diverge.
8. A software validity result is misrepresented as substantive conformance.
9. A dependency or build artifact is compromised.
10. Backups, exports or logs leak protected information.

## Implemented controls

- Localhost binding by default.
- No remote JavaScript, CSS, fonts or analytics.
- Content Security Policy and defensive HTTP headers.
- Controlled path resolution and case identifiers.
- Atomic JSON writes.
- SHA-256 evidence registration and verification.
- Hash-chained event log.
- Schema and semantic validation.
- Decision-object separation and explicit result boundaries.
- Reproducible tests, checksum manifests and Git history.

## Residual risks

The application does not authenticate users, encrypt files, isolate tenants, scan uploads, verify signatures, establish source authenticity, or prevent a privileged local actor from replacing an entire workspace and its backups. Production deployment requires a separate architecture and review.
