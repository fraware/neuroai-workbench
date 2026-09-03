# ADR 0019: PRE-G2 held-out benchmark implementation lineage

- Status: Accepted (implementation-lineage decision only)
- Date: 2026-09-03
- Base reviewed: `685f1597a2a63f2e2217f65f115a67ac3e35cc55` (post-transport main)
- Compared heads:
  - [#269](https://github.com/fraware/neuroai-workbench/pull/269) `ae9b9966d1017a9629c91c714246447b4388f015`
  - [#272](https://github.com/fraware/neuroai-workbench/pull/272) preferred foundation (rebased lineage)
  - [#275](https://github.com/fraware/neuroai-workbench/pull/275) stacked freeze/run manifests on #272

## Boundary

This ADR selects the public Workbench **software scaffold lineage** for D3/D4 PRE-G2 evaluation machinery. It does **not**:

- approve G0, G1, or G2;
- freeze real D3/D4 held-out sets;
- authorize publication, canonical S2 mutation, or v4.2 assessment effect;
- introduce real held-out labels, adjudication packets, licensed bytes, or commitment secrets into the public repository.

Authority fields on the selected lineage remain fail-closed (`g2_passed=false` and equivalent non-authority flags). Schema validity, commitment equality, and offline metric calculations do not establish scientific validity or governance approval.

## Decision

1. Treat #269 and #272 as **competing foundations**. Do not merge them as parallel commitment/evaluation stacks.
2. Select the preferred lineage **#272 then #275**.
3. Port one independent control from #269 into the selected lineage before merge: **ASCII domain separation inside keyed HMAC commitments**, plus a broadened prediction-row leakage denylist for source-text / licensed-byte / nonce field names.
4. Defer #269-only packaging patterns (JSON Schema resource package, checked-in empty public manifests, synthetic fixture package with explicit `UNTRUSTED_DRAFT_ONLY` fixture validator) as unresolved follow-on work. They are useful engineering packaging, not a second commitment foundation.
5. Close #269 as superseded after this ADR exists and the domain-separation port is present on the selected lineage branch set.

## Dimension comparison

| Dimension | #269 (unkeyed / nonce-salted) | #272 + #275 (keyed HMAC lineage) | Finding |
| --- | --- | --- | --- |
| Commitment threat model | `SHA256(scheme \|\| domain \|\| canonical \|\| nonce)`; nonce held in S3 until a governed reveal | `HMAC-SHA256(key, scheme \|\| domain \|\| canonical)`; key held in S3 and not designed for routine public opening | Prefer keyed HMAC for permanent held-out opacity; domain separator ported from #269 |
| Keyed vs unkeyed | Unkeyed digest with secret nonce | Keyed HMAC | Keyed preferred for small label domains |
| Key/nonce custody | `nonce_disposition=S3_CONTROLLED_NOT_PUBLIC`, min 32 bytes | Secret key min 32 bytes in S3; private membership/labels `S3_CONTROLLED` | Equivalent custody intent; selected lineage states S3 locations on the public contract |
| Canonical serialization | Sorted-key compact UTF-8 JSON; reject non-finite floats | Same canonical JSON contract (`allow_nan=False`, sorted keys) | Parity |
| Domain separation | Explicit ASCII domain separator in hash material | Originally absent; **ported** into `HMAC_SHA256_DOMAIN_CANONICAL_JSON_V1` | Selected lineage now includes domain separation |
| Dictionary-attack resistance on small label domains | Relies on nonce secrecy; mis-shared nonce enables enumeration | HMAC resists offline enumeration without the key | Prefer #272 |
| Public/private field boundary | Recursive denylist on public manifests | Exact allowlist of public contract fields; private payloads never accepted on the public contract | Allowlist on #272 is stronger for the public contract surface |
| Held-out identity protection | Opaque digests without nonce disclosure | Opaque membership/label commitments; freeze/run manifests bind digests only | Prefer #272/#275 |
| Leakage guards | Recursive denylist including source text, licensed bytes, nonces | Recursive prediction oracle denylist; **broadened** with #269 field names | Combined on selected lineage |
| G1 disposition binding | Boolean `g1_approved=false` only in PRE-G2 scaffold | Exact `g1_disposition_id` + `g1_disposition_sha256` required before freeze | Prefer #272/#275 |
| Freeze predecessor lineage | Not present | #275 `ROOT` / `SUCCESSOR` + predecessor digest | Prefer #275 |
| Contamination / abstention / missing prediction | Contractual metrics; no scoring engine | Fail-closed contamination on manifests; unresolved gold preserved; positive abstention/missing counted as effective FN | Prefer #272/#275 |
| Subgroup evaluation | Required subgroup dimensions in schema | Implemented offline subgroup metrics by stratum/language/jurisdiction/text availability | Prefer #272 |
| Aggregate-only public export | Implied by public/S3 split | #275 `export_policy=AGGREGATE_ONLY` | Prefer #275 |
| Deterministic offline evaluation | Commitment + validation only | Commitment + validation + deterministic scorer | Prefer #272 |
| Schema evolution | JSON Schema resources + package-data inclusion | Versioned Python allowlists/`schema_version=0.1` | #269 packaging deferred; not a merge blocker for lineage choice |
| CI / package integration | Adds `resources/benchmarks/*` package-data | Module + tests; no packaged real/empty freeze claims | Selected lineage kept code-first; package-data deferred |

## Controls ported from #269

- Domain-separated keyed commitment material (`scheme || domain_separator || canonical_json`) under scheme id `HMAC_SHA256_DOMAIN_CANONICAL_JSON_V1`.
- Broader prediction leakage denylist entries for abstract/source/licensed/nonce-style keys.
- Dedicated tests for domain separation and the broadened denylist.

## Controls deferred from #269

- Packaged JSON Schema files and empty PRE-G2 public manifests under `resources/benchmarks/`.
- Synthetic fixture package validator enforcing `synthetic=true` / `UNTRUSTED_DRAFT_ONLY` model outputs as repository resources.

Rationale for deferral: these are packaging and fixture-distribution patterns, not a second cryptographic foundation. Porting them wholesale would reintroduce a parallel manifest vocabulary beside #272/#275. They may be scheduled later as additive schema packaging on the selected lineage only.

## Merge posture

- Do **not** blind-merge #269 or the unrebased historical PR heads.
- Rebase/update #272 then #275 onto `685f159…` (or successor green main) and require hosted CI green on the exact heads before merge.
- Keep PRs open while CI is red or unverified.
- Never place real held-out labels or S3 secrets in the public repository.

## Consequences

- Future PRE-G2 benchmark work continues on the #272/#275 vocabulary and modules (`evaluation_benchmarks.py`, `benchmark_manifests.py`).
- #269 is architectural evidence and a control donor, not a merge target.
- Later G1 disposition binding, freeze, and held-out runs remain human-governed S3 operations; this ADR does not create those states.
