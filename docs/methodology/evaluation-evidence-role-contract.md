# PRE-G2 evaluation evidence-role contract

Status: PRE-G2 technical contract. This document creates no benchmark membership, human label, scientific finding, G2 passage, S2 authority or publication authority.

## Why this contract exists

A held-out benchmark may contain observations selected for different scientific purposes. A probability sample can support inference to a declared finite population when its frame, inclusion probabilities, estimator and uncertainty method are correctly specified. A deliberately enriched challenge set can diagnose failure modes and construct coverage, but its raw class balance and error rates do not estimate population prevalence or population performance.

The Workbench therefore treats these as different evidence roles instead of allowing one undifferentiated held-out result to acquire a population interpretation after the fact.

## Evidence roles

`POPULATION_PROBABILITY_AUDIT` is the only role that may declare `population_generalizable=true`. The plan must bind the target frame, probability sampling design, inclusion-probability evidence, estimator, uncertainty method, denominator semantics and predeclared population estimands. The validator checks that those identities exist and are cryptographically bound; it does not certify that the estimator, weights or variance calculation are scientifically correct.

`CHALLENGE_CONSTRUCT_COVERAGE` must declare `population_generalizable=false`. It may deliberately enrich hard negatives, boundary cases, model disagreements, retrieval misses and other required strata. It cannot carry a population frame, inclusion-probability manifest, population estimator or population uncertainty method, and it cannot report prevalence or population retrieval recall. Classification, routing, abstention, calibration and subgroup diagnostics remain permitted when presented explicitly as challenge-set results.

The controlled pooling policy is `NO_CROSS_ROLE_POOLING`. Results may be discussed together only as separately identified evidence; a raw aggregate that mixes probability and challenge components cannot be represented as a population estimate.

## Versioning and binding

Existing benchmark freeze and run manifests remain schema v0.2 and retain their exact meaning. This change does not silently reinterpret them.

The new evidence-role binding layer is schema v0.3:

1. a `BENCHMARK_FREEZE_EVALUATION_BINDING` binds an exact validated v0.2 freeze manifest to an exact predeclared evaluation plan;
2. a `HELD_OUT_EVALUATION_COMPONENT_BINDING` binds one exact aggregate held-out result to one component of that frozen evaluation plan and therefore to one evidence role.

Changing the plan, component, evidence role, frozen benchmark or aggregate result changes the corresponding digest and invalidates the binding.

For future real G2 work, a bare v0.2 freeze is a structural precursor. The complete evidence package should also contain the v0.3 evaluation binding before population or challenge results are interpreted.

## D3 / PATSTAT implication

Roman Jurowetzki's historical PATSTAT work can supply sampling signals and candidate strata, but its model labels are not the human D3 reference standard. A future D3 may contain both a probability-audit component and a challenge component. The probability component must retain known inclusion probabilities and a declared uncertainty estimator. The challenge component may oversample difficult cases but cannot be used to infer patent prevalence or retrieval recall.

The public Workbench does not implement or infer the missing historical PATSTAT second-stage estimator. Until the full design is available and independently audited, an unsupported population estimator must remain outside the validated contract.

## D4 implication

Open-world product discovery does not currently establish a probability sampling frame. D4 can therefore use `CHALLENGE_CONSTRUCT_COVERAGE` to build a rigorous human-adjudicated edge-case benchmark across the controlled PRODUCT strata. A future probability-audit component is allowed only if a defensible product population frame and probability design are separately established and bound.

## S3 boundary

Real membership, inclusion probabilities, reviewer records, adjudication records, source evidence, weights and other oracle material remain controlled S3 evidence. Public Git may contain schemas, validators, synthetic fixtures and opaque digests only.

## What validation does not prove

Successful validation establishes structural consistency and fail-closed evidence-role semantics only. It does not establish population-frame completeness, correct inclusion probabilities, estimator unbiasedness, confidence-interval coverage, label truth, reviewer independence, benchmark adequacy, absence of all contamination, PATSTAT redistribution rights, G0/G2/G5 passage, publication authority or assessment effects.
