# Release A completion status

**Plan binding:** [Product Population → Industrial Observatory deployment plan](product-population-industrial-observatory-deployment-plan.md) Release A / `A-G`  
**Status:** `A-G PASSED` (controlled research packet; repository-safe)  
**Does not authorize:** Release B, Release C, Release D, S2 publication authority, or v4.2 assessment effect

This document is the durable programme pointer to the immutable Release A gate artifacts. Mutable issue/PR chatter is not the gate record. Stronger claims than the frozen packages are prohibited.

## Gate disposition

| Field | Value |
| --- | --- |
| Gate | `A-G` |
| Outcome | `PASSED` |
| Next required state | `RELEASE_A_COMPLETE_AG_PASSED_NO_BCD_AUTHORIZATION` |
| A8 package | `src/neuroai_workbench/resources/discovery/RELEASE_A_A8_PRODUCT_POPULATION_RELEASE_PACKAGE.v1.0.json` |
| A8 package SHA-256 | `71ff7a917e9104ca279352643afbaebabc19c362527d36bcbfab1311aef73190` |
| A-G packet | `src/neuroai_workbench/resources/discovery/RELEASE_A_AG_RECONSTRUCTION_PACKET.v1.0.json` |
| A-G packet SHA-256 | `33dc577617518df8f88a6faf38ef0b6b6b0c06ec91e004776cf74d64d9f69c92` |
| A-G protocol SHA-256 | `5fba335b37459d0b474f9b868d14275f8bf62372332aba2d6cb1a9b565aebb76` |
| A2 bounded-frame checkpoint SHA-256 | `452c8c504990c05edd6ac7c29b542a49ffa4fd81ccdece2bd7ca8e9e0921ca32` |
| Tip SHA at A-G merge | `abf53c8882eef1c4501a2a14f16ead37ad5bd7ca` (`#408`) |

Reconstruction checks walk the A8 package to upstream digests and source packets for each required headline. Outcome is `PASSED` only when every required field resolves from immutable artifacts.

## Headline counts (denominators required)

All headline values below are taken from the frozen A8 package / A-G packet under population view `A-P1` unless noted. Do not restate them without the denominator.

| Headline | Value | Denominator / view |
| --- | --- | --- |
| `N_observed` | `6` | Distinct resolved in-scope canonical `PRODUCT`/`OFFERING` identities under `A-P1` |
| `N_estimated` | `null` | Same `A-P1` target population; A7 fail-closed — no headline unseen-population estimate admitted |
| `delta_n_capability` | `0` | Exact offering IDs in the capability-expanded arm absent from the conventional arm under `A-P1` |
| `delta_n_multilingual` | `0` | Exact offering IDs in the English+native arm absent from the English arm under `A-P1` |
| D4 working `INCLUDE` | `49` / `60` | D4 working-reference boundary cases (`TOTAL=60`) |
| Unresolved candidates retained | `416` | A2 checkpoint unresolved candidates (candidates, not products) |

A7 estimation outcome: `FAIL_CLOSED` — `NO_DEFENSIBLE_UNSEEN_POPULATION_ESTIMATE_UNDER_PREREGISTERED_ACCEPTANCE_CRITERIA`. `N_observed` is reported separately from any estimate.

## Work packages A2–A8

A2 through A8 execution artifacts are frozen under `src/neuroai_workbench/resources/discovery/`. The A8 package binds exact A1–A7 upstream digests, the Product Registry, D4 working-summary binding, Frame Register, A3/A4/A6/A7 reports, analytical figure tables, source/coverage/uncertainty register, and the unresolved-candidate register.

A2 multi-frame discovery is recorded in the bounded-frame checkpoint (`RELEASE_A_A2_BOUNDED_FRAME_CHECKPOINT.v1.0.json`). That checkpoint covers bounded-frame exhaustion under frozen protocols; it is not a claim that every relevant product worldwide was found.

## Frame semantics preserved

- **F9 / F2 / F3:** bounded exhaustion under frozen actor/provider/query universes. Exhaustion of a declared bounded input set is not global completeness.
- **F1 / F4 / F5 / F6 / F8 / F11 (open-world):** protocol saturation under declared round protocols and stop rules. Open-world saturation is not a census.
- **Estimator exclusions:** F7, F9, and F11 remain excluded from the primary v1.0 capture estimator. They may still contribute observed identities and coverage diagnostics.

## Authority boundary

From the A-G packet `authority_controls` and `boundary`:

- A-G does **not** authorize Release B/C/D.
- A-G does **not** establish S2 publication authority.
- A-G does **not** create a v4.2 assessment effect.
- A7 fail-closed (`N_observed=6`, `N_estimated=null`) is preserved.
- F9 exhaustion is not global completeness; open-world saturation is not a census.
- The A8 package status remains `CONTROLLED_RESEARCH_PACKET_REPOSITORY_SAFE`.

Related contracts: [Release-A Product Discovery Frame Contract](release-a-product-discovery-frame-contract.md), [Release A Analysis Preregistration](release-a-analysis-preregistration.md).
