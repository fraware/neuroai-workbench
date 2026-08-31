# Institutional deployment profile

The reference implementation can support an institutional pilot only after additional controls are assigned outside the package.

Workbench provides **profile adapters** under `neuroai_workbench.institutional` (OIDC/SAML stubs, RBAC role records, append-only audit sink, S3 tenant boundary, break-glass hook). Deployment modes are explicit:

| Mode | Meaning |
| --- | --- |
| `LOCAL` | Unauthenticated local development. Never reports institutional authentication. |
| `INSTITUTIONAL` | Profile adapters for a separately hosted identity plane. Fail-closed until a reviewed verifier is supplied. |

Local development mode must not be confused with authenticated mode. Role assignment alone cannot grant release authority. Do not add authentication to the local `ThreadingHTTPServer` and call it institutional.

## Fail-closed defaults

- OIDC/SAML adapters refuse empty tokens/assertions.
- Default OIDC verification state is `FAIL_CLOSED_UNVERIFIED` with `authenticated=false`.
- SAML ACS URLs must not target localhost / `127.0.0.1` (local case server).
- Cross-tenant S3 keys that escape the tenant prefix fail closed.
- Audit events are append-only (in-memory list or JSON array file sink).
- Break-glass records require rationale and never grant release authority.

## Required controls

- Identity provider and role-based access.
- TLS and authenticated reverse proxy.
- Encrypted storage and managed keys.
- Network segmentation and host hardening.
- Signed releases and provenance verification.
- Backup, recovery and secure destruction.
- Malware and document-content controls.
- Security logging and incident response.
- Privacy, clinical, legal and participant-governance review.
- Independent penetration testing.
- Named service owner and continuity plan.

The institutional profile must preserve the canonical v4.2 semantics and must not convert system status into a composite score.

## Related runbooks

Operations hooks under `neuroai_workbench.operations` record runbook invocations and synthetic canaries. They do not claim DR readiness or institutional pilot clearance. See also [hosted-ci-empty-steps.md](../operations/hosted-ci-empty-steps.md) for CI triage that must not be confused with security acceptance.
