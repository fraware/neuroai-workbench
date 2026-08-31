# ADR 0018: Public observatory /v1 API is release-scoped and read-only

- Status: Accepted
- Date: 2026-08-31
- Related: handoff ADR-API-009

## Context

The local case `ThreadingHTTPServer` is an unauthenticated reference UI. The living observatory needs a versioned public read API over immutable S2 release artifacts. These must not be collapsed.

## Decision

1. Add `neuroai_workbench.api` with `/v1/*` read handlers bound to a release directory.
2. Every response exposes release/version context (candidate id, manifest digest, authorization flag as recorded).
3. Write methods are refused. No endpoint mutates canonical state.
4. ETag/cache keys bind to immutable manifest digests.
5. This package is not an extension of the local case server and is not institutional SSO.

## Consequences

- Local case API docs remain distinct.
- Institutional OIDC/RBAC live in `institutional` profile adapters, not on ThreadingHTTPServer.
