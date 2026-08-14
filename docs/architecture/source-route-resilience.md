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

## Evidence-bound lifecycle resolution

Availability and lifecycle are separate questions. A previously registered source can stop being an active publisher surface without losing its historical evidentiary identity.

`NO_LONGER_LISTED` is the narrow lifecycle state for that case. It resolves only when all of the following are true:

1. an explicit source-bound lifecycle assertion exists;
2. the registered primary route is observed as HTTP 404 or 410;
3. a pre-registered current official publisher listing is successfully retrieved;
4. that listing is a `LIVENESS_CORROBORATION` route;
5. the exact historical source identity is confirmed absent from that listing;
6. no registered route has successfully resolved the source.

HTTP 404 or 410 alone never establishes `NO_LONGER_LISTED`. A failed publisher-listing retrieval also leaves the lifecycle unresolved.

A resolved `NO_LONGER_LISTED` state means only that the historical source is no longer present on the publisher surfaces checked under the declared policy. It does not establish why it disappeared, that a role was filled, that a programme ended, commercial withdrawal, regulatory status, clinical status, or any assessment conclusion. The historical source record remains intact, and lifecycle resolution never authorizes evidence substitution.

## Health axes

Operational reporting keeps these concepts separate:

1. engineering health;
2. source resolution;
3. active-source availability;
4. active evidence-payload availability;
5. primary-route health;
6. lifecycle transition state.

A degraded primary route can coexist with `AVAILABLE_FALLBACK` source availability and `READY` engineering health. A lifecycle-resolved historical source is excluded from active-source availability calculations but remains explicitly visible as a lifecycle transition. Liveness-only fallback remains visibly non-substitutable for the evidence payload.

## Determinism and auditability

Route policies and observations are included in a deterministic hash-bound availability report. Route identifiers, priorities, official hosts, official basis, identity/corroboration checks, and selected route are explicit. Missing earlier route observations block silent fallback.

Lifecycle reports are independently hash-bound to the exact source ID, registered route IDs, official-listing evidence reference, observation time, route report digest, and lifecycle assertion. Recomputing with substituted or tampered inputs fails verification.
