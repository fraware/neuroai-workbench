# Online-first acquisition architecture

**Status:** Phase 1 additive architecture for issue #279  
**Baseline:** Workbench `336da167700a7ce2894c27826f8a1c999e1ee844`  
**Scope:** operational acquisition permission semantics only  
**Runtime default:** unchanged; local/offline-first  

## Objective

The long-run Observatory needs current external observations as a normal operational input while preserving deterministic replay, explicit coverage accounting, quarantine custody, and independent publication authority. The migration therefore makes acquisition online-first at the operational edge without making network state authoritative inside the evidence or release layers.

Phase 1 introduces a digest-bound `AcquisitionPolicy` contract. It does not bind that policy into the scheduler or collector, perform network I/O, replace current live authorization, mutate S2, or change the default application mode.

The governing separation is:

```text
acquisition permission
    != source truth
    != evidence adjudication
    != assessment mutation
    != release authorization
    != publication
```

## Existing operational foundation

The existing due-cycle executor already supplies the mechanics needed for a later runtime binding: deterministic run identity, bounded global and per-host concurrency, typed retry policy, independently durable collector outcomes, per-target checkpoints, exact resume without duplicate committed retrieval work, and explicit source-accountability / target-execution coverage.

The collector already ends network retrieval at quarantine records whose successful evidence state is `RETRIEVED_BYTES_NOT_SUBSTANTIVELY_ADJUDICATED`. The online-first migration preserves that boundary. A successful request is an observation/capture event, not a scientific or governance decision.

## Phase 1 policy contract

A policy is one canonical JSON-compatible object:

```text
policy_schema_version
policy_id
programme_id
approved_by
approved_at
expires_at
source_rules[]
  source_id
  execution_modes[]
  allowed_origins[]
  fallback_policy
boundary
policy_sha256
```

`policy_sha256` binds the deterministic canonical JSON representation of every field except the digest itself. Unknown top-level or source-rule fields fail closed. Source rules are canonicalized by source ID; execution modes and origins are canonical sorted lists.

The policy carries a claimed local `approved_by` identity. It is not authenticated institutional identity, delegated legal authority, source authorization, or release authority.

### Per-source least privilege

Origins are bound inside each source rule instead of being placed in one programme-wide set. This prevents a policy containing sources A and B and origins X and Y from implicitly granting the Cartesian product `{A,B} × {X,Y}`.

At request time the policy check requires an exact match across:

- programme ID;
- source ID;
- execution mode;
- approval / expiry window;
- requested origin for network modes;
- fallback state when prior-capture fallback is requested.

A source cannot use an origin listed only for another source in the same policy.

## Execution modes

`ONLINE_REQUIRED` means the operation is intended to observe current external state. Prior-capture fallback is forbidden. A retrieval failure must remain a current-run operational failure or coverage gap; a historical capture cannot be silently substituted and represented as a fresh observation.

`ONLINE_PREFERRED` means the operation is intended to obtain a fresh observation, with prior-capture fallback available only when the source rule explicitly sets `EXPLICIT_PRIOR_CAPTURE_ALLOWED`. Phase 1 validates permission only. A later runtime binding must record whether the actual path was live retrieval or fallback, including the original capture identity and age.

`REPLAY_ONLY` means the operation performs no network request. Supplying a requested URL is rejected. Replay is an explicit execution mode, not a disguised live-fallback outcome.

These modes are operational semantics. They do not change assessment or release states.

## Exact origin model

Policy origins use exact `http` or `https` scheme/host/optional-port identity. Canonicalization:

- converts DNS names to lowercase IDNA ASCII form;
- validates bounded DNS labels;
- normalizes IP literals;
- removes default ports (`80` for HTTP, `443` for HTTPS);
- preserves non-default ports;
- refuses user-info, wildcards, trailing-dot hosts, IPv6 zone identifiers / percent escapes, queries, fragments, and non-root policy paths.

Requested URLs may contain application paths and queries, but their canonical origin must exactly match the origin authorized for that source. Requested URLs containing user-info or fragments are refused.

Origin policy is not an SSRF or DNS-rebinding replacement. The existing public-address / DnsGuard checks and pinned transport remain independently mandatory. When Phase 2 binds policy into live execution, every redirect hop must remain subject to both the existing network safety controls and acquisition-policy origin scope before connection.

## Authorization layering

Phase 1 intentionally leaves the existing live gate unchanged:

```text
AcquisitionPolicy permits exact operational scope
        AND
existing digest-bound live authorization permits network collection
        AND
NEUROAI_LIVE_COLLECTION=1
        -> live collector may execute
```

A valid acquisition policy by itself cannot make `EvidenceCollectionService` perform network I/O. The current authorization packet and environment gate remain required. This additive ordering allows the policy semantics to be reviewed and adversarially tested before any production default changes.

The future migration may replace per-run/operator mechanics with a reviewed standing acquisition-policy workflow, but that is a separate authority change and requires its own issue, tests, threat analysis, and transition evidence.

## Determinism and replay

The policy object is designed to become part of the deterministic operational run binding already used by the due-cycle executor. Phase 2 should bind at least the policy ID and digest into the run manifest so resume cannot silently substitute a different network scope.

Network I/O must end at a durable immutable capture/result boundary before deterministic projection. Downstream extractors and candidate compilers should consume captured observation objects, whether they originated from a fresh live attempt or an explicit replay. Live retrieval and replay must never be conflated in coverage accounting.

## Phase boundaries

### Phase 1 — policy semantics (this issue)

- add canonical, digest-bound acquisition policy objects;
- add per-source exact-origin / mode / fallback checks;
- preserve the existing live authorization and environment gate;
- keep CI and default execution offline;
- document security and data-governance boundaries.

### Phase 2 — executor binding

A separate issue should:

- bind the exact policy digest into deterministic run identity and durable manifests;
- enforce policy before initial requests and each redirect hop;
- record live-vs-fallback route and capture age explicitly;
- preserve deterministic request IDs and exact resume;
- fail closed on policy substitution, expiry, corruption, or source/origin mismatch;
- prove that policy checks do not weaken DnsGuard, pinned-peer verification, quarantine, scanning, or authorization controls.

### Phase 3 — controlled runtime proof

Before changing an operational default, execute a structured reference source under a controlled runtime and prove:

- live acquisition produces a durable capture before projection;
- replay of that exact capture reproduces deterministic downstream projection under the same code/configuration;
- interruption after durable capture and before checkpoint resumes without duplicate network retrieval;
- source failure remains explicit and does not mutate canonical S2;
- `ONLINE_PREFERRED` fallback is visibly distinct from a fresh observation;
- normal scheduled recurrence preserves full source-accountability coverage.

### Phase 4 — operational default transition

Only reviewed programmes with active policy and completed Phase 3 evidence should become online-first in scheduled operation. Unit tests, PR CI, benchmark evaluation, historical reconstruction, and release verification remain replay/offline-capable by design.

Open-world/browser acquisition is a later, higher-risk expansion and requires a separate content-adversary and rights architecture.

## Non-claims

Phase 1 does not establish G0, G1, or G2 passage; production deployment; institutional authentication; legal authorization; source authenticity; scientific validity; evidence completeness; canonical S2 admission; release authorization; publication; or global source-universe completeness.
