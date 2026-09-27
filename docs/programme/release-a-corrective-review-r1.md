# Release A corrective review R1

**Tracking issue:** #410  
**Audit baseline:** `1928eca5063840083b663e15d2c6f68b653b2766`  
**Historical A8 package SHA-256:** `71ff7a917e9104ca279352643afbaebabc19c362527d36bcbfab1311aef73190`  
**Historical A-G packet SHA-256:** `33dc577617518df8f88a6faf38ef0b6b6b0c06ec91e004776cf74d64d9f69c92`  
**Disposition:** `CORRECTIVE_REVIEW_R1_OPEN`

## Purpose

This record preserves the post-completion adversarial audit that reopened Release A. It does not mutate or invalidate historical packet bytes. It separates engineering reproducibility from scientific sufficiency.

Recent Release-A PR heads, including A7, A8, A-G and the completion-status change, passed their required CI, CodeQL and Dependency Review gates. The corrective review was triggered by semantic and measurement findings discovered after the reconstruction gate.

## Verified strengths

The audit confirmed:

- the six A1 seed offering identities have separate canonical PRODUCT authority through PR #349;
- the A2 analysis universe binds that authority through PR #351;
- F9 has a frozen per-actor enumeration procedure and immutable completion-ledger lineage;
- F2/F3/F9 bounded-source execution records explicit protocol-bounded exhaustion;
- F7/F9/F11 remain excluded from the primary unseen-population estimator;
- A7 fails closed rather than inventing an unseen-population estimate;
- A8 explicitly prohibits market-share, comparative-effectiveness, national-leadership and global-census claims;
- A-G reconstructs its required headlines through immutable upstream digest bindings.

## Corrective findings

### R1-1 — authoritative capture eligibility is stored rather than fully derived

Issue #342 remains open. The generic capture validator checks that an estimator-eligible capture is `INCLUDE_RESOLVED` and belongs to an estimator-eligible frame, but does not derive the stored flag from exact target-view Product Registry qualification under the same frozen universe.

### R1-1b — historical A-P1 observed denominator is inconsistent with the frozen machine predicate

The A1 seed Product Registry contains six canonical OFFERING rows, but the frozen A-P1 predicate requires `currentness_state == CURRENT` and a current lifecycle state.

Under that predicate:

- NextSense Smartbuds qualifies;
- Muse S Athena qualifies;
- EMOTIV EPOC X qualifies;
- Synchron Stentrode qualifies;
- Flow FL-100 does not qualify (`currentness_state=UNRESOLVED`, `lifecycle_state=UNRESOLVED`);
- Modius Spero does not qualify (`currentness_state=UNRESOLVED`, `lifecycle_state=UNRESOLVED`).

The frozen seed projection therefore yields four A-P1 identities. Historical A7/A8 instead fix `N_observed=6` to the six A1 identity IDs.

The audit also found stored `capture_estimation_eligible=true` rows for Flow and/or Modius in F2, F1 and F4, demonstrating that #342 affects current results.

In addition, the seed registry rows bind knowledge cutoff `2026-09-24T21:00:00Z`, whereas the A2 analysis universe binds `2026-10-24T23:59:59Z`. A successor Product Registry projection at the exact A2 universe/cutoffs is required before authoritative target-view eligibility and the corrected A-P1 observed denominator are frozen.

### R1-2 — round-start identity baseline is not generically proven

Issue #343 remains open. `known_identity_set_sha256` is included in deterministic run identity, but the generic authoritative run validator does not receive the actual round-start canonical OFFERING set, recompute the digest and derive the round summary from the same set.

### R1-3 — stored run stop state is not generically derived from stop evidence

Issue #344 remains open. `evaluate_frame_stop()` exists, but the generic run validator does not require the stored terminal state to equal the state derived from the frozen rule and explicit execution evidence.

### R1-4 — resolved-identity yield is confounded by unresolved adjudication

The frozen marginal-yield rule measures new **resolved canonical identities**. Current execution contains substantial unresolved candidate mass while allocating zero new canonical identities after A1.

Post-checkpoint unresolved capture rows:

| Frame | UNRESOLVED_IDENTITY capture rows |
| --- | ---: |
| F1 | 22 |
| F4 | 43 |
| F5 | 38 |
| F6 | 48 |
| F8 | 12 |
| F10 | 65 |
| F11 | 12 |
| **Total** | **240** |

Those rows contain 168 globally distinct `candidate_key` strings before governed cross-frame identity deduplication.

This does not prove that 168 new products exist. It proves that low new-resolved-ID yield is compatible with a material unresolved backlog. A successor rule must establish enough resolution/adjudication completeness for marginal-yield interpretation.

### R1-5 — A3/A4 point-zero interpretation is resolution-censored

Historical outputs:

- `delta_n_capability = 0`;
- `delta_n_multilingual = 0`.

The executed F6 arm includes 48 unresolved captures, and F8 includes 12 unresolved captures plus substantial abstain mass. The historical zero values are valid as counts of additional **resolved canonical offering IDs**. They are not yet sufficient evidence that capability-first or native-language discovery produces zero incremental relevant products.

### R1-6 — the historical A8 unresolved register is bounded-checkpoint-only

A8 reports 416 unresolved candidates, derived from the bounded A2 checkpoint:

- F3: 310;
- F9: 106.

It omits later unresolved rows from F1/F4/F5/F6/F8/F10/F11. A successor Release-A unresolved register must cover the full executed discovery history and distinguish capture-row count from deduplicated candidate identity.

### R1-7 — A7 is appropriately conservative but must be recompiled

Historical A7:

- `N_observed = 6`;
- `N_estimated = null`;
- outcome `FAIL_CLOSED`;
- reasons `CAPTURE_TABLE_TOO_SPARSE` and `INSUFFICIENT_MULTI_FRAME_OVERLAP`.

This fail-closed result is retained. The successor A7 compile must use corrected authoritative capture eligibility and the successor candidate/identity state.

### R1-8 — A-G is a reconstruction gate, not the successor scientific-validity gate

The historical A-G `PASSED` packet demonstrates that required outputs reconstruct through the frozen digest chain. It does not independently prove R1-1 through R1-7.

A successor gate must make scientific blockers explicit and fail closed if any remain.

## Corrective execution order

1. Implement #342, #343 and #344.
2. Materialize a successor Product Registry projection at the exact A2 analysis universe/cutoffs and derive the target A-P1 identity set through the frozen machine predicate.
3. Back-validate all existing authoritative A2 captures/runs without mutating historical packet bytes.
4. Build a cross-frame candidate-resolution ledger for every unresolved/borderline/abstain object capable of changing product-population accounting.
5. Freeze an adjudication-completeness / unresolved-mass rule for marginal-yield interpretation.
6. Execute governed candidate resolution and emit successor round/stop-state evidence.
7. Recompute A3 and A4 under the successor resolved/unresolved state.
8. Rebuild the complete unresolved register.
9. Recompile A7 and rerun the frozen/predeclared model-admissibility logic through a successor specification if the input universe materially changes.
10. Emit successor A8.
11. Run a successor A-G gate that tests both reconstruction and the R1 scientific-integrity obligations.
12. Advance `release-a-completion-status.md` only from that successor evidence.

## Preservation rules

- Historical packets are immutable.
- Existing exact-head-green CI evidence is retained.
- Any new canonical PRODUCT identity requires separate governed identity authority.
- Post-world-cutoff observations cannot be back-projected without explicit support.
- Candidate, product identity, scope inclusion, currentness, commercialization, deployment and effectiveness remain distinct claim dimensions.
- Bounded-source exhaustion and marginal-yield saturation remain protocol statements, not global-census claims.
- No B/C/D denominator consumption until R1 closes.
