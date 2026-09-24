# Release A Analysis Preregistration v1.0

**Plan binding:** `P0.5`  
**Tracking issue:** #327  
**Depends on:** P0.3 exact-product registry and P0.4 discovery-frame contract  
**Status:** `FROZEN_v1.0` upon merge to `main`

## 1. Purpose

This preregistration fixes the Release-A measurement targets, discovery universe, multilingual sensitivity design,
and model-comparison rules before unseen-population models are fit to observed product capture histories.

It governs product-population estimation only. It creates no global-census, market-share, effectiveness, or
product-importance claim.

> The target population, identity unit, language/discovery universe, and model-comparison rule are fixed before
> model fitting.

## 2. Primary quantities

For one preregistered estimation universe `u`:

```text
N_observed(u)
N_estimated(u)
N_unobserved(u) = N_estimated(u) - N_observed(u)
Coverage(u) = N_observed(u) / N_estimated(u)
```

`N_observed` is the number of distinct resolved in-scope canonical PRODUCT offering identities qualifying
for the exact population view at the declared world-time and knowledge-time cutoffs.

`N_estimated` is a model-based estimate of the same target population under the same declared discovery
universe. It is never raw registry-row cardinality.

`N_unobserved` is a latent residual count, not a generated list of hypothetical product identities.

## 3. Exact estimand boundary

Every estimation universe binds:

- Product Measurement Contract v1.0 and semantic blob;
- D4 Product Reference Standard v1.0 working reference;
- Product Registry v1.0;
- Product Population View Policy v1.0;
- Product Currentness Policy v1.0;
- identity level `OFFERING`;
- included enumeration roles;
- one population view;
- analysis-jurisdiction scope;
- world-time cutoff;
- knowledge-time cutoff;
- `EN_PLUS_PRIORITY_NATIVE_v1` language scope;
- Product Discovery Frame Register v1.0;
- the exact v1.0 estimation-eligible frame set.

Capture histories from different universes fail closed instead of being pooled.

## 4. Primary and secondary estimands

### 4.1 Primary — A-P1 current identifiable offering inventory

Identity unit: resolved canonical PRODUCT offering.

Default included enumeration roles:

```text
INTEGRATED_SYSTEM
COMPONENT_OR_SUBSYSTEM
STANDALONE_SOFTWARE_OR_SERVICE
```

A-P1 asks how many currently identifiable in-scope offerings exist under the declared boundary, cutoff,
geographic/language scope, and discovery protocol.

### 4.2 Primary — A-P6 current released or externally accessible offerings

A-P6 uses the same identity unit with the narrower A-P6 access predicate. A-P1 and A-P6 are estimated
separately; their capture histories and totals are never substituted for one another.

### 4.3 Secondary — A-P4 integrated end-user systems

A-P4 is secondary and uses only `INTEGRATED_SYSTEM` offerings. It receives an unseen-population estimate
only if its capture table supports a stable model.

### 4.4 A-P8 technical implementations

A-P8 is **not enabled for unseen-population estimation in v1.0**. It uses configuration/equivalence semantics
rather than the OFFERING identity unit. Enabling A-P8 requires a preregistration successor after technical
equivalence is frozen before capture-history construction. Post-hoc equivalence clustering is prohibited.

Jurisdiction- or product-class-specific estimates are secondary and require adequate capture support.

## 5. Frozen discovery universe

The primary v1.0 estimator uses exactly:

```text
F1  first-party
F2  regulatory
F3  clinical/trial
F4  scientific/research
F5  commercial/ecosystem
F6  capability-first
F8  local-language
F10 patent-commercialization crossover
```

F7 expert nominations, F9 curated known-actor seeds, and F11 snowball expansion remain valuable discovery
routes but are deliberately excluded from the primary unseen estimator because their selection is purposive
or path-dependent. Products found only through those frames remain part of `N_observed_total`.

The full source mechanisms and stop rules are frozen in
`PRODUCT_DISCOVERY_FRAME_REGISTER.v1.0.json`. Frame inclusion is not selected after observing which
combination produces a preferred population estimate.

## 6. Frozen multilingual sensitivity scope

English is the global baseline. The primary matched native-language sensitivity uses:

| Stratum | Native language | Jurisdiction(s) | Why it is in v1.0 |
| --- | --- | --- | --- |
| CN_ZH_HANS | Simplified Chinese | China | high-priority East Asian coverage probe with substantial BCI translation/product activity and likely local-source dependence |
| JP_JA | Japanese | Japan | known Japanese product evidence and mature research/medical-technology source environment |
| KR_KO | Korean | South Korea | Korean EEG/research-product evidence and likely local-language discovery gain |
| ES_ES | Spanish | Spain | multiple developers in the controlled set and Spanish-language product documentation |
| FR_FR | French | France | controlled French actor/product evidence and French-language product/regulatory documentation |
| DACH_DE | German | Germany, Austria, Switzerland | German-language research and medical-technology coverage across the DACH region |

For each stratum, compare matched English-only discovery against English-plus-native discovery and report
unique resolved-offering gain, duplicate rate, excluded/unresolved rate, capability gain, and source-class gain.

Additional languages may be explored supplementally. They do not retroactively alter the v1.0 headline
multilingual sensitivity without a preregistration successor.

## 7. Discovery measurements

Report by frame and round where applicable:

- raw candidate count;
- new resolved in-scope offerings;
- identities already known at round start;
- within-round duplicate captures;
- EXCLUDE / BORDERLINE / ABSTAIN / unresolved-identity counts;
- failed or inaccessible leads;
- marginal new-identity yield;
- duplicate yield;
- pairwise frame overlap;
- language and jurisdiction contribution;
- capability-first incremental recall;
- English-only versus English-plus-native incremental recall;
- stopping state and reason.

## 8. Observed identities versus the model zero cell

Let:

```text
N_observed_total
    = all resolved offerings in the target registry view

N_observed_capture_support
    = observed offerings captured by >=1 frame used in the estimator

N_observed_external_only
    = N_observed_total - N_observed_capture_support
```

A multiple-systems model fitted to the selected estimation frames returns `N_model_total`. Its implied
zero-capture cell is:

```text
N_zero_capture_model
    = N_model_total - N_observed_capture_support
```

Known products discovered only through excluded frames occupy part of that zero-capture region. They are known
observations, not unseen products.

For a model coherent with known evidence:

```text
N_unobserved
    = N_zero_capture_model - N_observed_external_only
    = N_model_total - N_observed_total
```

A model with `N_model_total < N_observed_total` fails the known-observation consistency check. Its raw result
remains diagnostic but cannot support the headline estimate. It is not silently floored.

## 9. Preregistered model families

Every primary estimation universe considers the same six families:

1. **Observed-only baseline.** Known count only; no unseen estimate.
2. **Pairwise capture-recapture diagnostic.** Overlap/dependence diagnostic. The naïve two-source estimator is
   not a headline estimator unless its assumptions are independently defensible.
3. **Log-linear multiple-systems estimation.** Explicit multi-frame capture-table models with zero-cell
   estimation.
4. **Dependence-aware interaction models.** Predeclared/evidence-supported frame interactions where
   dependence diagnostics justify them.
5. **Stratified models.** Fit only where product-class/jurisdiction capture support avoids unstable sparse cells.
6. **Bayesian/hierarchical sensitivity models.** Fit where justified to probe heterogeneity, sparse strata and
   prior sensitivity.

A family may be recorded as not fit when its assumptions or data requirements fail; the reason is part of the
result. No estimator wins because it produces the narrowest interval or the preferred population size.

## 10. Model admissibility and diagnostics

Every fitted model reports:

- convergence and numerical stability;
- frame dependence;
- capture heterogeneity;
- sparse/zero overlap cells;
- identifiability/parameter stability;
- sensitivity to predeclared frame grouping;
- boundary/identity sensitivity;
- known external-only identities;
- residual zero-capture risk;
- held-back discovery-round predictive behavior where feasible;
- estimate/interval and spread across reasonable models.

A model is not headline-admissible if it fails convergence/identifiability, yields a total below the known
observed target population, depends on a contradicted unacknowledged independence assumption, uses post-hoc
frame/identity changes selected for estimate convenience, or is dominated by one arbitrary grouping without
sensitivity analysis.

If no unseen estimator is stable, Release A reports the observed count, model failures, coverage risks and
bounded sensitivities without forcing a population headline.

## 11. Boundary and measurement sensitivities

Every primary estimate reports at least:

- unresolved-identity sensitivity without relabelling unresolved candidates as products;
- BORDERLINE/ABSTAIN mass separately from the INCLUDE-only primary count;
- currentness uncertainty under the frozen currentness predicate;
- multilingual incremental gain;
- integrated-system / component / standalone-software-service decomposition;
- frame-grouping sensitivity for known/nested dependence.

F5's heterogeneous commercial/ecosystem channels receive explicit grouping sensitivity. No grouping is chosen
after seeing which version gives a preferred estimate.

## 12. Zero-capture and out-of-frame risk

Explicitly examine:

- products found only through F7 expert nomination;
- products found only through F9 curated known-actor seeds;
- products found only through F11 snowball expansion;
- products found only through local-language discovery;
- products found only in late/held-back rounds;
- weak/blocked jurisdictions or source classes;
- product classes with systematically low capture probability;
- disagreement between predicted unseen mass and products discovered later.

These diagnose coverage risk; they do not enumerate the remaining unseen set.

## 13. Reporting contract

Preferred reporting form:

```text
Target:
  population view / OFFERING identity / enumeration roles
  jurisdiction / language scope / cutoff pair
  exact F1-F6,F8,F10 discovery universe

Directly observed:
  N_observed_total

Capture support:
  N_observed_capture_support
  N_observed_external_only

Model results:
  family-specific estimates and intervals
  diagnostics and non-fit reasons
  model spread

Selected reporting estimate:
  only if admissibility criteria are satisfied

Estimated residual unseen:
  N_estimated - N_observed_total

Estimated observed fraction:
  N_observed_total / N_estimated

Named residual risks:
  jurisdictions / languages / product classes / source barriers / identity uncertainty
```

No Release-A estimate is described as global completeness, total addressable market, market share, product
effectiveness, or market leadership.

## 14. Frozen v1.0 decisions

Before A7 model fitting:

- A-P1 and A-P6 are primary unseen-population estimands;
- A-P4 is secondary if adequately supported;
- A-P8 unseen estimation is disabled in v1.0;
- OFFERING is the identity unit;
- the estimation frame universe is exactly F1-F6, F8 and F10;
- F7, F9 and F11 remain observed-discovery/coverage-risk routes outside the primary estimator;
- `EN_PLUS_PRIORITY_NATIVE_v1` fixes the six matched non-English sensitivity strata;
- the six model families form the mandatory comparison/consideration set;
- pairwise capture-recapture is diagnostic by default;
- a model total below known observed identities is inadmissible for headline use;
- known external-only identities are removed from the model zero-cell interpretation before any residual is
  called unseen;
- failure to identify a stable unseen-population estimator is an admissible result.
