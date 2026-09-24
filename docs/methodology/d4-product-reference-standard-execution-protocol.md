# D4 Product Reference Standard execution protocol

**Plan binding:** `P0.2` in [Product Population → Industrial Observatory deployment plan](../programme/product-population-industrial-observatory-deployment-plan.md)  
**Tracking issue:** #318  
**Parent gate:** #315 / `P0-G`  
**Depends on:** P0.1 Product Measurement Contract substantive freeze  
**Status:** EXECUTION PROTOCOL CANDIDATE — no real D4 membership or human dispositions are stored in this repository

## 1. Purpose

This protocol defines how to execute, adjudicate, and freeze the real D4 Product Reference Standard.

D4 measures one construct:

> Whether an exact product/service candidate belongs inside the approved NeuroAI product/service research boundary.

D4 does **not** establish:

- global product completeness;
- product identity by itself;
- current commercial availability;
- deployment;
- regulatory authorization;
- safety;
- effectiveness;
- market share;
- publication authority;
- G2 passage.

The real benchmark membership, human dispositions, reviewer records, rationales, source material, and commitment secret remain in S3-controlled research storage. This public protocol defines the execution semantics and the evidence that a later public freeze may bind.

## 2. Verified starting state

The public Workbench already contains the PRE-G2 D4 evaluation scaffold:

- `src/neuroai_workbench/resources/benchmarks/D4_PRODUCT_PRE_G2.contract.json`;
- public benchmark schema version `0.2`;
- benchmark kind `PRODUCT`;
- current public state `DRAFT_UNFROZEN`;
- approved D1 canonical boundary semantics;
- approved G1 disposition reference;
- human boundary dispositions `INCLUDE`, `EXCLUDE`, `BORDERLINE`, and `ABSTAIN`;
- required product strata:
  - `CLINICAL`;
  - `CONSUMER`;
  - `WORKPLACE`;
  - `RESEARCH`;
  - `ENTERTAINMENT_XR`;
  - `WELLNESS`;
  - `AMBIGUOUS_BIOSIGNAL`;
  - `NONTRADITIONAL_FORM_FACTOR`;
  - `MULTILINGUAL`;
  - `MULTI_JURISDICTION`;
- required double-label subset;
- null membership and disposition commitments;
- `g2_passed=false`.

The Workbench also contains current v0.2 benchmark-freeze and held-out-run manifest validators. P0.2 uses those existing controls; it does not create a parallel benchmark authority.

## 3. Governing semantic boundaries

### 3.1 Scope, identity, and state remain separate

For every candidate, reviewers answer the D4 scope question using the approved D1 boundary.

The reviewer does not turn D4 into a product-registry adjudication.

The following remain separate tasks:

```text
D4 scope disposition
!= exact product identity resolution
!= lifecycle/commercial state
!= regulatory state
!= deployment state
!= effectiveness evidence
```

The [Product Measurement Contract](../programme/product-measurement-contract.md) governs those distinctions.

### 3.2 Human disposition domain

Every resolved human D4 decision uses exactly one of:

```text
INCLUDE
EXCLUDE
BORDERLINE
ABSTAIN
```

Interpretation:

- `INCLUDE`: evidence supports inclusion under the frozen product boundary.
- `EXCLUDE`: evidence supports exclusion under the frozen product boundary.
- `BORDERLINE`: the case sits on a genuine governed boundary that remains analytically useful as a resolved borderline case.
- `ABSTAIN`: evidence is insufficient for a responsible resolved inclusion/exclusion/borderline judgment.

`ABSTAIN` is a human boundary disposition. It is not unresolved reviewer disagreement.

### 3.3 Adjudication state

Adjudication state remains orthogonal:

```text
AGREE
ADJUDICATED
DISAGREE_UNADJUDICATED
```

- `AGREE`: independent reviewer dispositions agree and the final disposition matches them.
- `ADJUDICATED`: initial reviewer records required adjudication and a governed final disposition exists.
- `DISAGREE_UNADJUDICATED`: disagreement remains unresolved; final disposition is null.

Unresolved disagreement stays outside binary performance denominators and cannot be silently coerced into a gold label.

## 4. Controlled storage boundary

### 4.1 S3-controlled material

The following remain outside public Git and public S2:

- real candidate IDs where disclosure would expose membership;
- real benchmark membership;
- source text or licensed/private source material;
- item-level reviewer dispositions;
- reviewer identities beyond approved controlled role references;
- reviewer rationales;
- adjudication packets;
- final item-level dispositions;
- held-out split membership;
- candidate-pool membership;
- exposure/contamination records that reveal membership;
- HMAC commitment key;
- selection-control material whose disclosure would expose held-out membership.

### 4.2 Public/repository-safe material

The public repository may contain:

- this execution protocol;
- synthetic fixtures;
- aggregate calibration statistics after disclosure review;
- public benchmark contract metadata;
- opaque membership/disposition commitments;
- freeze manifest metadata;
- aggregate boundary-disposition counts;
- protocol/report SHA-256 digests;
- aggregate required-strata coverage evidence;
- validation output that contains no held-out membership.

## 5. Case object and review packet

Each controlled D4 case must bind one exact candidate object.

Minimum controlled case fields:

```text
case_id
candidate_object_binding
candidate_object_type
candidate_identity_state
product_measurement_contract_version
product_measurement_contract_digest
evidence_packet_version
source_observation_refs
language
jurisdiction
text_or_evidence_availability
declared_strata[]
candidate_pool_origin
review_state
```

The review packet must contain enough attributable evidence to decide scope without requiring the reviewer to infer product identity from a name alone.

The packet may include controlled source excerpts or source references as permitted by rights. Those bytes do not enter public Git.

## 6. Reviewer record

Each independent review record must preserve:

```text
case_id
decision
rationale
adjudicator_role
timestamp
exact_object_binding
review_round
review_protocol_version
```

These fields preserve the approved D1 human-review requirement.

Additional controlled fields may record uncertainty notes or requested evidence, provided they do not alter the four-way disposition domain.

## 7. Stage 1 — Real 60-case calibration round

### 7.1 Objective

The calibration round tests whether independent human reviewers can apply the product boundary consistently enough to proceed to final held-out construction.

It is not the final held-out benchmark.

### 7.2 Calibration size

The calibration round contains exactly **60 real cases**.

All 60 receive independent double review.

Calibration membership remains S3-controlled.

### 7.3 Calibration coverage

The 60-case set must deliberately cover:

- clear in-scope product/service cases;
- clear out-of-scope cases;
- true boundary/borderline cases;
- insufficient-evidence cases where they arise;
- clinical products;
- consumer products;
- workplace-facing products or candidates;
- research platforms;
- entertainment/XR applications;
- wellness products;
- ambiguous biosignal products;
- non-traditional form factors;
- multilingual cases;
- multi-jurisdiction cases;
- software/service interpretation layers;
- regulated products;
- investigational systems;
- discontinued/superseded cases that test temporal and identity boundaries.

A case may satisfy several coverage dimensions.

Coverage dimensions do not predetermine the human disposition.

### 7.4 Calibration independence

Reviewer A and Reviewer B must:

- review the same controlled evidence packet;
- record their first-pass disposition independently;
- not see the other reviewer’s disposition or rationale before both first-pass records are frozen;
- not see model/pipeline predictions for the candidate;
- not use held-out model output to resolve ambiguity.

### 7.5 Calibration output

For each case, preserve both first-pass reviews.

Then classify:

- exact agreement;
- disagreement requiring adjudication;
- unresolved disagreement;
- human `ABSTAIN`;
- evidence insufficiency;
- product-identity ambiguity;
- product-state ambiguity that reviewers incorrectly treated as scope;
- recurring contract/instruction ambiguity.

## 8. Stage 2 — Calibration analysis

### 8.1 Required aggregate analyses

Compute, at minimum:

- exact four-way agreement rate;
- reviewer-disposition cross-tabulation;
- per-disposition agreement;
- disagreement count and rate;
- adjudication count and rate;
- unresolved disagreement count;
- human `ABSTAIN` count;
- disagreement rate by declared D4 stratum;
- disagreement rate by language;
- disagreement rate by jurisdiction where interpretable;
- identity-vs-scope error count;
- state-vs-scope error count.

### 8.2 Reliability statistics

Report raw agreement as the primary descriptive statistic.

A chance-corrected nominal agreement statistic such as Cohen’s kappa may be reported as a secondary diagnostic because there are two independent first-pass reviewers. Its limitations under imbalanced class prevalence must be stated.

If confidence intervals are reported, the exact interval method must be predeclared in the calibration-analysis record.

No single agreement statistic automatically authorizes final freeze.

### 8.3 Error taxonomy

Calibration analysis must classify recurring disagreement mechanisms.

At minimum distinguish:

```text
SCOPE_BOUNDARY_AMBIGUITY
IDENTITY_AMBIGUITY
STATE_SCOPE_CONFLATION
INSUFFICIENT_EVIDENCE
SOURCE_CONFLICT
MULTILINGUAL_INTERPRETATION
NONTRADITIONAL_FORM_FACTOR
AMBIGUOUS_BIOSIGNAL
SOFTWARE_SERVICE_BOUNDARY
COMPONENT_SYSTEM_BOUNDARY
TEMPORAL_STATUS_CONFUSION
OTHER_DOCUMENTED
```

This taxonomy is diagnostic. It does not replace the four-way D1 disposition.

## 9. Stage 3 — Human calibration disposition

Calibration ends with an attributable human methodological disposition.

Permitted disposition classes for this protocol are:

```text
READY_FOR_FINAL_SAMPLING
REVISE_REVIEW_INSTRUCTIONS
REVISE_PRODUCT_MEASUREMENT_CONTRACT
EXPAND_OR_REBALANCE_CANDIDATE_POOL
HALT_FOR_METHOD_REVIEW
```

### 9.1 `READY_FOR_FINAL_SAMPLING`

Use only when the human reviewer of the calibration evidence concludes that the boundary instructions are sufficiently stable for final benchmark construction.

### 9.2 `REVISE_REVIEW_INSTRUCTIONS`

Use when disagreements arise from operational instructions without changing the underlying P0.1 measurement semantics.

The revised instructions receive a successor version. A new calibration round or targeted re-calibration is required before final selection if the change could materially affect dispositions.

### 9.3 `REVISE_PRODUCT_MEASUREMENT_CONTRACT`

Use when calibration reveals a substantive ambiguity in the P0.1 contract itself.

This returns execution to P0.1 change control. Final D4 selection cannot proceed under conflicting measurement semantics.

### 9.4 `EXPAND_OR_REBALANCE_CANDIDATE_POOL`

Use when candidate coverage is insufficient to support final stratified selection.

### 9.5 `HALT_FOR_METHOD_REVIEW`

Use for contamination, rights, reviewer-independence, or construct-validity failures that require a broader methodological review.

## 10. Stage 4 — Freeze the final candidate pool

### 10.1 Separation from calibration

The final held-out candidate pool must be disjoint from the 60 calibration cases.

Calibration cases may remain a development/calibration resource but cannot enter the final held-out membership.

### 10.2 Candidate-pool freeze

Before final selection, freeze:

- candidate membership;
- exact-object bindings;
- declared strata;
- language;
- jurisdiction;
- evidence-availability state;
- applicable rights class;
- pool-construction protocol;
- candidate-pool canonical digest.

No model/pipeline result from the system under evaluation may be used to add, remove, or reorder candidates after pool freeze.

### 10.3 Final sample size

This protocol intentionally does not invent a final held-out sample size.

The final sampling plan must be frozen after calibration and before held-out selection. It must state:

- target total sample size;
- minimum boundary-disposition coverage objective;
- required D4 stratum coverage;
- subgroup-analysis objectives;
- desired uncertainty/precision for headline evaluation metrics;
- reviewer-resource constraints;
- how overlapping strata are handled;
- double-label design.

The final sample size must be justified by the measurement objective and uncertainty plan, not chosen after seeing held-out model performance.

## 11. Stage 5 — Deterministic final selection

### 11.1 Predeclared constraints

Before selection, freeze:

- candidate-pool digest;
- target sample size;
- required stratum coverage;
- any stratum quotas;
- any jurisdiction/language quotas;
- double-label subset rule;
- fixed stratum/constraint priority order;
- deterministic selection algorithm version.

### 11.2 Deterministic score

Within the frozen candidate pool, assign each candidate a deterministic selection score:

```text
selection_score =
SHA256(
  "NEUROAI:D4:FINAL_SELECTION:V1"
  || candidate_pool_digest
  || canonical_candidate_id
)
```

The candidate ID and pool digest remain controlled if disclosure would reveal held-out membership.

### 11.3 Selection rule

Sort candidates by ascending `selection_score`.

Apply the predeclared coverage/quota constraints in the frozen priority order.

The selection procedure must:

- be deterministic;
- avoid repeated random draws until a preferred sample appears;
- avoid using model predictions;
- preserve a record of excluded candidates and exclusion reason;
- fail closed if the frozen pool cannot satisfy required constraints.

If constraints are infeasible, issue a successor sampling protocol/candidate-pool disposition rather than silently relaxing them.

## 12. Stage 6 — Final human review

### 12.1 First-pass review

Final held-out items are reviewed under the frozen review protocol.

Reviewers do not receive model predictions.

### 12.2 Double-label design

The final benchmark must contain a non-empty strategically selected double-labeled subset, consistent with the public benchmark contract.

The final sampling protocol must predeclare how that subset is selected.

Full double review of the final benchmark is permitted and is preferred where reviewer capacity allows. If only a subset is double-reviewed, the protocol must state the rationale and how disagreement risk is audited outside the subset.

### 12.3 Adjudication

For double-labeled items:

- exact agreement may resolve to `AGREE`;
- disagreement may receive a governed adjudication and become `ADJUDICATED`;
- genuine unresolved disagreement remains `DISAGREE_UNADJUDICATED`.

For every resolved item, record:

- final D1 boundary disposition;
- rationale;
- adjudicator role;
- timestamp;
- exact-object binding.

Human `ABSTAIN` remains a valid resolved disposition where evidence is insufficient.

## 13. Stage 7 — Exposure and contamination review

Maintain a controlled exposure register for the final held-out set.

At minimum record:

- whether candidate membership was exposed to the pipeline/model team;
- whether item-level human dispositions were exposed;
- whether source text or benchmark packets were placed in model prompts;
- whether the system under evaluation retrieved benchmark-specific material;
- whether any tuning used final held-out outcomes;
- any known prior benchmark exposure.

The public freeze may proceed only with the current required state:

```text
NO_KNOWN_CONTAMINATION_REVIEWED
```

Known or unresolved contamination fails closed under the current manifest validator.

This state is a reviewed declaration. It is not cryptographic proof that no exposure ever occurred.

## 14. Stage 8 — Rights review

Before freeze, record the controlled rights review covering:

- source-use rights;
- licensed/proprietary material;
- reviewer confidentiality;
- redistribution constraints;
- public aggregate disclosure.

The current public freeze manifest requires:

```text
S3_CONTROLLED_NO_REDISTRIBUTION_AUTHORITY_CLAIMED
```

This conservative state does not establish lawful use or redistribution permission.

## 15. Stage 9 — Freeze membership and dispositions

### 15.1 Canonical controlled payloads

Freeze separate canonical controlled payloads for:

- final membership;
- final human dispositions/adjudication outcomes.

The exact private payload format must be versioned and deterministic.

### 15.2 Opaque commitments

Generate domain-separated HMAC-SHA256 commitments using the current Workbench commitment scheme:

```text
HMAC_SHA256_DOMAIN_CANONICAL_JSON_V1
```

The secret contains at least 32 bytes and remains in S3.

Membership and disposition payloads use distinct domain separators.

The public commitment establishes payload identity under possession of the secret. It does not establish benchmark correctness or adequacy.

## 16. Stage 10 — Public D4 contract successor

Create a successor public D4 contract that retains the exact current D1/G1 semantic bindings and changes the benchmark state to:

```text
FROZEN_COMMITMENTS_ONLY
```

Populate:

- membership commitment;
- disposition commitment.

Keep:

```text
g2_passed = false
canonical_s2_authority = false
publication_authority = false
assessment_effect = NONE
```

No item-level benchmark data enters the public contract.

## 17. Stage 11 — D4 freeze manifest

Construct the current v0.2 `BENCHMARK_FREEZE` manifest against the exact frozen public D4 contract.

The manifest must bind the current required fields, including:

- benchmark/public-contract identity;
- D1 canonical digest;
- G1 disposition ID/digest;
- membership/disposition commitments;
- required D1 boundary dispositions;
- aggregate boundary-disposition counts;
- boundary-coverage report digest;
- exact required D4 strata;
- strata-coverage report digest;
- sampling protocol ID/digest;
- human-review provenance digest;
- adjudication protocol ID/digest;
- adjudication-accounting digest;
- double-label subset count;
- rights containment state/reference;
- contamination/exposure state/reference;
- freeze time;
- lineage state.

The freeze record remains PRE-G2 evidence.

## 18. Required aggregate freeze reports

The controlled evidence package must produce canonical aggregate records whose digests can enter the freeze manifest.

### 18.1 Boundary coverage report

Contains aggregate counts for:

```text
INCLUDE
EXCLUDE
BORDERLINE
ABSTAIN
UNRESOLVED_ADJUDICATION
```

At least one frozen resolved case is required for:

- `INCLUDE`;
- `EXCLUDE`;
- `BORDERLINE`.

That structural minimum is not a scientific sample-size sufficiency claim.

### 18.2 Strata coverage report

Records aggregate membership coverage for every required D4 stratum.

A case may count toward several strata.

### 18.3 Adjudication accounting report

Records aggregate:

- first-pass review count;
- double-label count;
- agreement count;
- adjudication count;
- unresolved disagreement count;
- final resolved disposition counts.

No item IDs are included in the public form.

## 19. Validation sequence

Before recording P0.2 complete:

1. validate the exact frozen public D4 contract with the current packaged/public contract validator;
2. validate the exact D4 freeze manifest against that contract;
3. verify all public digests against controlled canonical reports;
4. verify no protected item-level material entered Git/public artifacts;
5. verify the final held-out membership was not used for tuning;
6. verify the exposure register state is acceptable under the current validator;
7. verify the rights review reference exists;
8. preserve all human disagreements and `ABSTAIN` outcomes.

A software validator PASS establishes structural consistency and exact bindings only.

## 20. P0.2 definition of done

P0.2 reaches `COMPLETE_FROZEN_D4` only when:

- the P0.1 Product Measurement Contract is substantively frozen;
- the 60-case human calibration round is complete;
- calibration analysis exists;
- a human calibration disposition authorizes final sampling;
- the final candidate pool and sampling protocol are frozen;
- deterministic final selection is complete;
- final human review/adjudication is complete;
- exposure/contamination review is complete;
- rights review is complete;
- private membership/disposition payloads are frozen;
- public opaque commitments are generated;
- the public D4 contract is `FROZEN_COMMITMENTS_ONLY`;
- the D4 freeze manifest validates against the exact contract;
- no protected item-level material has been published.

P0.2 completion does not pass G2.

## 21. Human decision points

This protocol intentionally retains four substantive human decision points:

1. P0.1 substantive freeze;
2. post-calibration methodological disposition;
3. approval of the final sampling/uncertainty plan;
4. final D4 freeze disposition.

Software may validate structure and deterministic selection. It does not issue those decisions.

## 22. Next dependency

Once P0.2 is complete, P0.3 can implement the exact-product registry against a frozen product boundary and use the frozen D4 reference standard for product-scope validation and evaluation.

P0.2 itself creates no global product denominator. Release A remains downstream of P0-G.
