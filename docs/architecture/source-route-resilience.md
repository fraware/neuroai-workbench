# Source-route resilience

Operational source availability is evaluated separately from individual retrieval-route health.

A source can remain available when its primary route is degraded if a pre-registered official route resolves the same source identity under an explicit equivalence contract. Route failover never changes assessment meaning, source truth, regulatory or clinical interpretation, governance authority, or release authority.

## Availability states

- `AVAILABLE_PRIMARY`: the preferred route succeeded.
- `AVAILABLE_FALLBACK`: the preferred route failed and a registered fallback succeeded under its declared verification contract.
- `UNRESOLVED`: no registered route established availability.
- `RETIRED`: reserved for an explicit lifecycle assertion with attributable evidence; HTTP 404 or 410 alone never proves retirement.

## Route classes

- `PRIMARY`: the registered preferred source route.
- `IDENTITY_EQUIVALENT`: an alternate official representation of the same source identity. It can support evidence substitution only after its explicit identity check passes. Example: two official ClinicalTrials.gov API representations resolving the same NCT identifier.
- `LIVENESS_CORROBORATION`: an official publisher surface that can establish continued listing or reference, but cannot replace the primary evidence payload. Example: an official careers index corroborating a deep job page.

## Failover boundary

Only pre-registered official routes are considered. There is no arbitrary web search, host substitution, credential injection, browser impersonation, or anti-bot circumvention.

The current failoverable route conditions are deliberately narrow:

- timeout;
- network error;
- HTTP 403, 404, 408, 410, 425, 429, 500, 502, 503, or 504.

Policy/security failures do not authorize fallback. A successful identity-equivalent route is rejected if its identity check fails. A successful liveness route is rejected if its corroboration check fails.

## Health axes

Operational reporting keeps four concepts separate:

1. engineering health;
2. source availability;
3. primary-route health;
4. evidence freshness/substitutability.

A degraded primary route can coexist with `AVAILABLE_FALLBACK` source availability and `READY` engineering health. Liveness-only fallback must remain visibly non-substitutable for the evidence payload.

## Determinism and auditability

Route policies and observations are included in a deterministic hash-bound availability report. Route identifiers, priorities, official hosts, official basis, identity/corroboration checks, and selected route are explicit. Missing earlier route observations block silent fallback.
