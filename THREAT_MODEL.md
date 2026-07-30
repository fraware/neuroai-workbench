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
11. A local actor impersonates a reviewer or overstates a recorded role as authenticated institutional authority.
12. Review disagreement is deleted, rewritten or hidden after disposition.
13. Sensitive context or credentials are included in a model request, or a provider response attempts prompt injection or unsupported evidence attribution.
14. A model response or human disposition is applied automatically and silently changes the assessment.

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
- Integrity-addressed review assignments, statements and dispositions linked to the case event chain.
- Review-role scope checks and explicit local-identity and authority boundaries.
- Provider-neutral model-assistance records with selected context, credential-pattern guards, evidence-reference checks, hashes and mandatory human disposition.
- No automatic assessment mutation from review or model-assistance records.

## Residual risks

The application does not authenticate users or reviewers, verify institutional roles, encrypt files, isolate tenants, scan uploads, verify signatures, establish source authenticity, or prevent a privileged local actor from replacing an entire workspace and its backups. The model-assistance guard is a bounded structural control, not a complete secret detector, redaction system, prompt-injection defence or provider-security assessment. Production deployment and direct provider integration require separate architectures and independent review.
