# Release A status

**Plan binding:** [Product Population → Industrial Observatory deployment plan](product-population-industrial-observatory-deployment-plan.md) Release A / `A-G`  
**Current programme status:** `CORRECTIVE_REVIEW_R1_OPEN`  
**Historical reconstruction gate:** `A-G PASSED` in immutable packet `33dc577617518df8f88a6faf38ef0b6b6b0c06ec91e004776cf74d64d9f69c92`  
**Corrective tracker:** #410  
**Does not authorize:** Release B, Release C, Release D, S2 publication authority, or v4.2 assessment effect

This file is the mutable programme-status pointer. The historical A8 and A-G packet bytes remain immutable. A post-completion adversarial review found scientific-integrity gaps that were outside the reconstruction gate, so the historical `PASSED` outcome is retained as a reconstruction result while the scientific Release-A disposition is under successor review.

## Corrective-review notice

Release-A/R1 is required before the current A8 package is consumed as a final denominator by downstream Release B/C/D work.

The post-completion audit found:

- issues #342, #343, and #344 are **closed** following merged PR #415, which implements the authoritative A2 validation controls for estimator eligibility, round-start identity binding, and stopping-rule evidence. This does not retroactively make historical packets scientifically sufficient;
- the frozen A1 seed Product Registry yields **4**, not 6, identities under the existing A-P1 machine predicate: Flow FL-100 and Modius Spero have `UNRESOLVED` currentness/lifecycle and do not qualify; historical A7/A8 nevertheless hardcode `N_observed=6`;
- the historical A1 seed Product Registry knowledge cutoff (`2026-09-24T21:00:00Z`) differs from the frozen A2 analysis-universe cutoff (`2026-10-24T23:59:59Z`). R1.2 has since materialized an exact-A2 successor Product Registry and candidate-resolution checkpoint; this checkpoint remains non-final until the frozen knowledge-time window is dispositioned;
- the executed open-world/local-language/patent/snowball packets contain 240 `UNRESOLVED_IDENTITY` capture rows after the bounded-frame checkpoint, representing 168 globally distinct `candidate_key` values before governed identity deduplication;
- the historical A8 unresolved register contains the 416 checkpoint candidates from F3/F9 only and is therefore not the complete unresolved register for the full Release-A execution;
- `delta_n_capability=0` and `delta_n_multilingual=0` are counts of additional **resolved canonical offering IDs** under the executed pipeline; their substantive recall interpretation remains under corrective review because material unresolved/abstain mass remains in F6/F8;
- A7 correctly failed closed with `N_estimated=null`; a successor A7 compile is required after authoritative eligibility, candidate-resolution and stop-state corrections.

See [Release A corrective review R1](release-a-corrective-review-r1.md) and issue #410.

## Current corrective execution checkpoint (20 October 2026)

This is a dated engineering snapshot. The [corrective tracker](https://github.com/fraware/neuroai-workbench/issues/410), [R1.7 execution tracker](https://github.com/fraware/neuroai-workbench/issues/424), and S2 `curation/CURRENT_EXECUTION_CONTROL.json` must be rechecked for mutable operational and programme status.

- **R1.1:** PR #415 merged and closed #342/#343/#344 with authoritative A2 validation controls.
- **R1.2/R1.3:** Exact-universe Product Registry, cross-frame resolution ledger, and a resolution-completeness checkpoint exist. A-P1 `N_observed=4` and historical capability/multilingual zero increments are **checkpoint interpretations**, not final product-population findings. The latter remain resolution-censored.
- **R1.4–R1.6.1:** Frozen worklist and empirical-unit routing refinements have been implemented. R1.6.1 routes 171 source/query items, 21 actual literature-record items, 76 empirical-candidate adjudications, and two A-P1 temporal reviews. Routing is not evidence of substantive execution.
- **R1.7:** The 192 source/record work items (247 capture rows) still require evidence-bound execution. PR #436 was merged on 20 October 2026 as the **R1.7a pre-execution ledger contract** (Workbench `main` commit `8a04c8ebbf457fc5465640460622727ad9426ed4`). This establishes the ledger implementation boundary, **not execution of the 192 source/record routes**; [issue #424](https://github.com/fraware/neuroai-workbench/issues/424) governs substantive execution. The merged PR's exact-head `pip-audit` job failed on the then-pinned dependency lock, so its merge must not be described as an entirely green security gate.
- **Temporal gate:** The frozen A2 knowledge-time close is `2026-10-24T23:59:59Z`. Issue #413's administrative closure does not supply a final denominator before prescribed evidence-window disposition; issue #414's scientific saturation review remains open.
- **Authority:** Historical A-G remains reconstruction-pass evidence only. These documentation updates do not advance the Release-A scientific gate, Observatory G0/G2/G3/G5, S2 publication, or B/C/D denominator authority.

## Historical reconstruction gate disposition

| Field | Value |
| --- | --- |
| Historical gate | `A-G` |
| Historical packet outcome | `PASSED` |
| Current scientific disposition | `CORRECTIVE_REVIEW_R1_OPEN` |
| Next required state | `RELEASE_A_R1_SUCCESSOR_AG_DISPOSITION` |
| A8 package | `src/neuroai_workbench/resources/discovery/RELEASE_A_A8_PRODUCT_POPULATION_RELEASE_PACKAGE.v1.0.json` |
| A8 package SHA-256 | `71ff7a917e9104ca279352643afbaebabc19c362527d36bcbfab1311aef73190` |
| A-G packet | `src/neuroai_workbench/resources/discovery/RELEASE_A_AG_RECONSTRUCTION_PACKET.v1.0.json` |
| A-G packet SHA-256 | `33dc577617518df8f88a6faf38ef0b6b6b0c06ec91e004776cf74d64d9f69c92` |
| A-G protocol SHA-256 | `5fba335b37459d0b474f9b868d14275f8bf62372332aba2d6cb1a9b565aebb76` |
| A2 bounded-frame checkpoint SHA-256 | `452c8c504990c05edd6ac7c29b542a49ffa4fd81ccdece2bd7ca8e9e0921ca32` |
| Tip SHA at historical A-G merge | `abf53c8882eef1c4501a2a14f16ead37ad5bd7ca` (`#408`) |

The historical reconstruction checks walk A8 to upstream digests and source packets for each required headline. That result remains reproducible. It does not independently establish the scientific sufficiency of candidate-resolution coverage, estimator eligibility derivation, round-start identity accounting, or stop-state justification.

## Historical headline values under review

These values are preserved exactly as reported by the immutable A8/A-G artifacts. They must be described as historical Release-A v1.0 outputs until the R1 successor disposition completes.

| Headline | Historical value | Current interpretation |
| --- | --- | --- |
| `N_observed` | `6` | Historical A7/A8 value. The frozen A1 seed registry machine predicate currently yields 4 A-P1 identities; successor registry/eligibility derivation is required before a corrected observed count is stated |
| `N_estimated` | `null` | A7 fail-closed; no defensible unseen-population estimate admitted |
| `delta_n_capability` | `0` | Zero additional resolved canonical IDs; substantive recall increment under corrective review |
| `delta_n_multilingual` | `0` | Zero additional resolved canonical IDs; substantive multilingual increment under corrective review |
| D4 working `INCLUDE` | `49 / 60` | Working-reference boundary cases, not the separate PRE-G2/G2 held-out human benchmark |
| A8 unresolved register | `416` | Bounded-checkpoint F3/F9 unresolved candidates only; not the complete Release-A unresolved set |

A7's fail-closed outcome remains an important conservative result:
`NO_DEFENSIBLE_UNSEEN_POPULATION_ESTIMATE_UNDER_PREREGISTERED_ACCEPTANCE_CRITERIA`.

## Immutable historical artifacts

Do not rewrite:

- `RELEASE_A_A8_PRODUCT_POPULATION_RELEASE_PACKAGE.v1.0.json`;
- `RELEASE_A_AG_RECONSTRUCTION_PACKET.v1.0.json`;
- prior A1–A7 source packets and run records.

Corrective work must use append-only/successor artifacts and exact predecessor digest bindings.

## Required successor path

The R1 successor must:

1. implement #342/#343/#344 and back-validate authoritative A2 records;
2. materialize a successor Product Registry projection bound to the exact A2 universe/cutoffs and derive the A-P1 observed set through `population_view_identity_ids`;
3. compile a complete cross-frame candidate-resolution ledger;
4. freeze a rule preventing unresolved adjudication backlog from manufacturing a low resolved-identity yield stop;
5. issue successor discovery accounting / stop-state results;
6. recompute A3/A4 with resolution uncertainty represented correctly;
7. rebuild the unresolved register across all executed F1–F11 packets;
8. recompile A7 and rerun its fail-closed/model gate;
9. emit successor A8 and A-G artifacts;
10. advance this status pointer only after the successor disposition is supported.

## Authority boundary

During corrective review:

- do not use the current A8 package as a final Release-B market denominator;
- do not use the current A8 package as a complete Release-C product evidence denominator;
- do not start integrated Release-D quantitative conclusions from the current A8 denominator;
- do not infer global completeness from bounded exhaustion or protocol saturation;
- do not infer that capability-first or multilingual discovery adds no products from the current point-zero resolved-ID increments;
- do not infer S2 publication authority or v4.2 assessment effect.

Historical exact-head CI/security results remain valid engineering evidence. R1 concerns scientific measurement validity and interpretation, not an assertion that those builds were technically ungreen.

Related contracts: [Release-A Product Discovery Frame Contract](release-a-product-discovery-frame-contract.md), [Release A Analysis Preregistration](release-a-analysis-preregistration.md).
