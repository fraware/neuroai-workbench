# Release A Analysis Preregistration v1.0

**Plan binding:** `P0.5`  
**Tracking issue:** #327  
**Depends on:** P0.3 exact-product registry and P0.4 discovery-frame contract  
**Status:** `FROZEN_v1.0` upon merge to `main`

## Purpose

This preregistration fixes the Release-A measurement targets and model-comparison rules before unseen-population models are fit to observed product capture histories.

It governs population estimation only. It does not establish a global census, market size, market share, product effectiveness, or product importance.

The controlling rule is:

> The target population, observed identity unit, estimation-frame set, sensitivity sets, holdback diagnostic, and reporting rule are fixed before model fitting.

## Primary quantities

For one preregistered estimation universe (u):

```text
N_observed(u)
N_estimated(u)
N_unobserved(u) = N_estimated(u) - N_observed(u)
Coverage(u) = N_observed(u) / N_estimated(u)
```

`N_observed` is the number of distinct resolved in-scope canonical PRODUCT offering identities qualifying for the exact population view at the declared world-time and knowledge-time cutoffs.

`N_estimated` refers to the same target population under the same identity, temporal, jurisdiction, language and discovery semantics. It is never registry-row cardinality.

`N_unobserved` is a latent residual count. It is not a set of synthetic or inferred product identities.

## Exact estimand boundary

Every estimation universe binds:

- Product Measurement Contract v1.0 and exact semantic blob;
- D4 Product Reference Standard v1.0 working reference;
- Product Registry v1.0;
- Product Population View Policy v1.0;
- Product Currentness Policy v1.0;
- identity level `OFFERING`;
- exact included enumeration roles;
- one population view;
- analysis-jurisdiction scope;
- world-time cutoff;
- knowledge-time cutoff;
- language-scope identifier;
- Product Discovery Frame Register v1.0;
- the exact primary estimation-frame set;
- frame-set sensitivity policy;
- late-round holdback policy;
- model-reporting policy.

Capture histories from incompatible universes fail closed instead of being pooled.

## Frozen primary and secondary estimands

### A-P1 — primary

Current identifiable offering inventory.

The primary denominator includes exactly:

```text
INTEGRATED_SYSTEM
COMPONENT_OR_SUBSYSTEM
STANDALONE_SOFTWARE_OR_SERVICE
```

at canonical PRODUCT `OFFERING` identity level.

### A-P6 — primary

Current released or externally accessible offerings, with the same identity and enumeration-role semantics as A-P1 and the narrower frozen A-P6 access/deployment predicate.

A-P1 and A-P6 are estimated separately.

### A-P4 — secondary

Current integrated end-user systems. This uses only `INTEGRATED_SYSTEM` offerings and is estimated only if the observed capture table supports stable estimation.

### A-P8 — descriptive only in v1.0

A-P8 technical-implementation counts are not an unseen-population estimand in this preregistration. A future A-P8 estimate requires a separately frozen technical-equivalence contract before capture construction and a successor preregistration.

No jurisdiction- or product-class-specific unseen estimate is silently added later. Such estimates require a preregistered successor/supplement before model fitting if the discovery data support them.

## Primary estimation-frame set

The frozen primary estimator uses only frames whose v1.0 selection mechanisms are eligible for population estimation:

```text
F1  first-party product discovery
F2  regulatory discovery
F3  clinical/trial discovery
F4  scientific/research discovery
F5  commercial/ecosystem discovery
F6  capability-first discovery
F8  local-language discovery
F10 patent-commercialization crossover
```

F7 expert nominations, F9 curated-actor seeds and F11 snowball expansion contribute to the observed registry and coverage diagnostics but not to the primary unseen estimator.

The following frame-set sensitivities are mandatory:

```text
NO_PATENT_CROSSOVER
  F1 F2 F3 F4 F5 F6 F8

CONVENTIONAL_SOURCE_CORE
  F1 F2 F3 F4 F5

NO_CAPABILITY_OR_LOCAL_LANGUAGE
  F1 F2 F3 F4 F5 F10
```

These alternatives are fixed now. They cannot be selected later because they yield a preferred population size.

F5 source classes remain separately observable. Dependence across distributor/procurement, structured-directory, and funding/investor/accelerator channels must be reported rather than hidden by the common F5 label.

## Discovery measurements

Release A reports, by frame and round where applicable:

- raw candidates;
- new resolved in-scope offerings;
- identities already known at round start;
- within-round duplicate captures;
- EXCLUDE / BORDERLINE / ABSTAIN / unresolved-identity counts;
- failed or inaccessible leads;
- marginal new-identity yield;
- duplicate yield;
- pairwise frame overlap;
- source-class dependence;
- language and jurisdiction contribution;
- capability-first incremental recall;
- English-only versus English-plus-native-language incremental recall;
- stopping state and reason.

## Observed identities versus the model zero cell

Let:

```text
N_observed_total
    = all resolved offerings in the target registry view

N_observed_capture_support
    = observed offerings captured by >=1 frame used in the selected estimator

N_observed_external_only
    = N_observed_total - N_observed_capture_support
```

A multiple-systems model fitted to the selected frames estimates `N_model_total`. Its implied zero-capture cell is:

```text
N_zero_capture_model
    = N_model_total - N_observed_capture_support
```

Known products found only through excluded/non-estimation frames occupy part of that zero-capture region. They are known observations, not unseen products.

For a model coherent with the known evidence:

```text
N_unobserved
    = N_zero_capture_model - N_observed_external_only
    = N_model_total - N_observed_total
```

A model with `N_model_total < N_observed_total` fails the known-observation consistency check. Its raw result may be retained as a diagnostic, but it is not a headline estimate and is never silently floored.

## Preregistered model families

Every primary universe compares the same six families:

1. **Observed-only baseline.** Reports the known population and makes no unseen-population claim.
2. **Pairwise capture-recapture diagnostic.** Exposes overlap/dependence behavior. It is diagnostic-only by default.
3. **Log-linear independence baseline.** Main-effects multiple-systems model. It is headline-admissible only when source construction and empirical diagnostics do not contradict the relevant independence assumptions.
4. **Log-linear dependence interactions.** Interaction structures are restricted to dependencies declared in the frozen frame register and scientifically motivated source-sharing relationships. Post-hoc interactions chosen only because they change the estimate are prohibited.
5. **Stratified dependence model.** Used only where a predeclared stratum has adequate capture support and the within-stratum model is identifiable.
6. **Bayesian/hierarchical sensitivity model.** Used to assess capture heterogeneity, sparse cells and plausible dependence structures. Prior choices and prior sensitivity are reported.

## Pre-fit model-specification lock

The six model families above are frozen at P0.5, but family names alone do not remove analytical degrees of freedom. Before any Release-A capture table is supplied to a fitted unseen-population model, the implementation must freeze a versioned model-specification manifest for that exact estimation universe.

The pre-fit manifest must bind, as applicable:

- the exact log-linear interaction hierarchy or deterministic candidate-generation rule and the model-comparison criterion;
- any structural-zero treatment and any frame combinations prohibited by design;
- the exact stratification variables, pooling/collapse rules, and minimum support required to fit a stratum;
- the Bayesian/hierarchical likelihood, prior distributions, hyperparameters, sampler settings, convergence criteria, posterior summaries, and prior-sensitivity variants;
- the uncertainty-interval construction rule for each model family;
- the late-round predictive discrepancy measure and pass/fail interpretation;
- numerical-stability and identifiability thresholds used for headline admissibility.

That manifest must be frozen without using observed population estimates, model totals, or interval widths to choose a preferred specification. If a model is later revised because diagnostics reveal a defect, the revised specification is a named successor or sensitivity analysis; it does not silently replace the preregistered fit.

This pre-fit implementation lock is part of the Release-A analysis contract. P0.5 freezes the estimands, model families, sensitivities, and lock requirement; it does not authorize fitting a model whose exact specification remains mutable.

## Model diagnostics and inadmissibility

Every fitted unseen-population model reports:

- convergence and numerical stability;
- frame dependence;
- source-class dependence;
- capture heterogeneity;
- sparse and zero overlap cells;
- identifiability;
- sensitivity to the three frozen alternative frame sets;
- boundary/identity uncertainty;
- known external-only identities;
- residual zero-capture risk;
- late-round predictive behavior;
- uncertainty interval;
- spread relative to other admissible models.

A model is not headline-admissible if it:

- fails to converge;
- is non-identifiable or numerically unstable;
- produces a total or uncertainty interval below the known observed target population;
- relies on an independence assumption contradicted by source construction or observed overlap;
- depends on a post-hoc frame regrouping, identity change or boundary change chosen because it improves the result;
- is unsupported by the capture-table density required for its parameters or stratum;
- changes materially under one frozen frame-set sensitivity without that instability remaining explicit.

## Late-round predictive check

For each iterative marginal-yield frame with enough completed rounds, the final completed discovery round is used as a predictive diagnostic.

A provisional model is fit using earlier-round information. The number of offerings first discovered in the held-back final round is then compared with the model's predicted residual unseen mass and uncertainty. This diagnostic does not convert the held-back round into an independent random sample; it tests whether a model that claims little unseen mass is immediately contradicted by continued discovery.

Final Release-A population estimates are refit on all eligible discovery data after this diagnostic.

## Reporting rule: no winner by convenience

Release A does not select one estimator because it produces the smallest interval or the most appealing population size.

For every primary estimand:

1. report the directly observed count;
2. report every preregistered model family and its diagnostic status;
3. mark each unseen-population model as headline-admissible or diagnostic-only/failed;
4. if at least one non-diagnostic model is admissible, report the conservative envelope spanning the lower and upper uncertainty bounds of all admissible model families;
5. if admissible models disagree strongly, preserve the full envelope and model-specific results instead of choosing one;
6. if no unseen-population model is admissible, report the observed count and coverage-risk diagnostics without a forced estimate.

The model envelope is a robustness device, not a formal posterior or confidence interval pooled across model classes.

## Required sensitivities

Every primary result includes:

### Unresolved identity
Unresolved candidates remain separate. Explicit hypothetical bounds may be shown, but unresolved candidates are not relabelled as verified offerings.

### BORDERLINE / ABSTAIN
Primary observed counts remain INCLUDE-only. Any operational BORDERLINE/ABSTAIN mass is reported separately with a clearly hypothetical inclusion sensitivity if useful.

### Currentness uncertainty
Products with unresolved currentness remain outside primary current views and are reported separately.

### Multilingual gain
Report identities uniquely found through local-language discovery and compare against the matched English/conventional search scope.

### Enumeration role
Report integrated systems, components/subsystems and standalone software/services separately as well as the exact primary-view total.

### Frame set
Report the frozen primary frame set and all three mandatory alternative frame sets above.

## Zero-capture and out-of-frame risk

The coverage report explicitly examines:

- products found only through F7 expert nominations;
- products found only through F9 curated-actor seeds;
- products found only through F11 snowball expansion;
- products uniquely found through local-language discovery;
- products uniquely found through patent-commercialization crossover;
- products first discovered in late rounds;
- source classes or jurisdictions with blocked/weak access;
- product classes with systematically low capture probability;
- disagreement between predicted unseen mass and subsequent discovery.

These are coverage-risk diagnostics, not evidence that the unseen population has been enumerated.

## Frozen v1.0 decisions

Before A7 model fitting, v1.0 fixes:

- A-P1 and A-P6 as primary unseen-population estimands;
- A-P4 as the only frozen secondary unseen-population estimand;
- OFFERING as the estimation identity unit;
- the complete primary enumeration-role set for A-P1/A-P6;
- F1-F6, F8 and F10 as the primary estimation frames;
- F7, F9 and F11 as observed-registry/diagnostic frames only;
- the three mandatory alternative frame sets;
- the six model families;
- pairwise capture-recapture as diagnostic-only by default;
- the late-round predictive check;
- the conservative admissible-model envelope reporting rule;
- observed external-only identities as known members of the model zero-capture region;
- all required uncertainty sensitivities;
- failure to identify a stable unseen-population model as an admissible scientific result.
