# P0.1 Product Measurement Contract adversarial review — R1–R40 + final consistency audit

**Plan binding:** `P0.1`  
**Tracking issue:** #320  
**Parent issue:** #316  
**Review target:** `docs/programme/product-measurement-contract.md`  
**Review disposition on predecessor text:** `REVISE_BEFORE_FREEZE`  
**Current state:** all identified R1–R40 findings and the final pre-review consistency corrections below are incorporated in the current candidate; human freeze disposition remains pending

## 1. Purpose

This record documents the adversarial pre-freeze review of Product Measurement Contract v1.0.

The review asks whether the contract is strong enough to support:

- D4 product-boundary calibration;
- exact-product registry implementation;
- Release-A product counting;
- open-world population estimation;
- later commercial and effectiveness layers;

without silently changing the approved D1 research boundary or introducing denominator ambiguity.

This record is methodological review evidence only. It does not freeze P0.1, execute D4, pass P0-G, establish a product population, or authorize publication.

## 2. Exact governing evidence checked

The review checked the contract against the exact approved research-contract line:

```text
D1:
LANDSCAPE_RESEARCH_CONTRACT_v0.1
canonical JSON SHA-256:
7d270002094dcdecb703d5b70ef2268e4869005c284ffd98db3eb936641a78cb

G1 disposition:
HUMAN_G1_DISPOSITION_2026-09-05_D1_D2_v0.1
canonical JSON SHA-256:
ed6489fe1085b5aec1b594970dd1c574b57bd6bbd25a659643e9bd1b7b72d8ef
decision:
APPROVE
```

Relevant approved D1 constraints include:

- no global-completeness claim in the open-world product discovery track;
- four-way boundary dispositions `INCLUDE / EXCLUDE / BORDERLINE / ABSTAIN`;
- attributable evidence required for inclusion;
- proxy-only evidence cannot establish inclusion;
- expert review required for governed boundary membership;
- open-world unknowns remain explicit;
- gray-third discovery is retrieval-only, not a canonical population class;
- concentration claims require a validated analytical denominator;
- product existence does not establish effectiveness or regulatory authorization.

The review also checked the current Observatory v2 ontology, entity identity model, temporal model, evidence boundary, D4 benchmark schema/evaluator semantics, and Release-A population-estimation objective.

## 3. Review method

The contract was attacked from five directions:

1. **Construct validity** — does the counted object match the intended product/service construct?
2. **Identity validity** — could one real-world object become multiple counts, or different objects collapse into one?
3. **Temporal validity** — could current, historical, announced, discontinued, and deployed states be conflated?
4. **Denominator validity** — could heterogeneous object types or population views be aggregated into an invalid count?
5. **Reference-standard validity** — could D4 benchmark membership or benchmark semantics be confused with operational population inclusion?

The review favored false non-merges and explicit unresolved states over silent identity aggregation or unsupported denominator expansion.

## 4. Findings and resolutions

| ID | Finding | Risk if unresolved | Candidate correction |
| --- | --- | --- | --- |
| R1 | Exact D1/G1 binding was implicit | Later contract revisions could drift from the approved boundary without detection | Bind exact D1 artifact/digest and G1 disposition/digest; state that P0.1 cannot redefine scope |
| R2 | Service representation was underspecified against the current ontology | P0.3 would have to invent entity semantics during implementation | Represent an independently countable service as a `PRODUCT` offering with an explicit service/offering kind under v1.0 |
| R3 | “Product-like” investigational systems could contaminate product counts | Stable research systems could be counted as products without an offering identity | Require a stable external/formal investigational product identity; otherwise retain `SYSTEM` outside product counts |
| R4 | Announcement-only objects were ambiguous in the main current view | “Product count” could change depending on an unstated treatment of announced products | Define A-P1 as announcement-inclusive offering inventory and add A-P6 for released/externally accessible offerings |
| R5 | Discontinued but still deployed systems disappeared from current analysis | Commercial lifecycle could be confused with real-world installed/deployed presence | Add A-P7 current deployed legacy view |
| R6 | Broad counts mixed integrated systems, components, and standalone services | A single count could be misread as complete end-user systems or distinct technologies | Add mandatory enumeration role and require role composition in broad counts |
| R7 | OEM/private-label offerings had no separate technical-equivalence view | Commercial labels could inflate perceived technology diversity | Add A-P8 technical-implementation view; equivalence requires attributable evidence and never mutates product identity |
| R8 | Population-estimation unit was not locked | Capture histories could mix family/product/configuration or lifecycle universes, invalidating unseen-population estimates | Bind each estimator to one boundary contract, identity level, population view, roles, cutoffs, jurisdiction and discovery-frame universe |
| R9 | D1 boundary evidence rules were not explicit at the count interface | Identity resolution or a single company claim could be misread as sufficient for inclusion | Restate attributable-evidence, proxy, expert-review, abstention, borderline-rationale, unknown and gray-third rules |
| R10 | Post-freeze P0.1 changes did not explicitly trigger D4 compatibility review | A frozen D4 reference standard could be reused under changed enumeration semantics without revalidation | Require D4 compatibility review and, where affected, successor D4 review/re-freeze |
| R11 | D4 benchmark disposition was conflated with operational product inclusion | Counted products could appear to require D4 held-out membership, or D4 could be misused as the population registry | Separate D4 reference-standard membership from operational D1-governed product dispositions; record exact validation/reference-standard version |
| R12 | Enumeration-role cardinality was unspecified | Role-composition counts could double count one offering and A-P4 membership could be ambiguous | Require exactly one `primary_enumeration_role`; represent secondary relationships/context separately |
| R13 | A-P3 excluded commercially sold research platforms | Commercial access and research-use access were incorrectly treated as mutually exclusive | Allow A-P2 and A-P3 to overlap; require an explicit projection if disjoint categories are needed |
| R14 | A-P8 clustering could be formed post hoc from source overlaps | Technical-equivalence clustering could alter capture histories and bias unseen-population estimates | Make A-P8 descriptive by default; require preregistered frozen deterministic equivalence before using it as an estimation unit |
| R15 | A-P8 technical-implementation unit was product-level ambiguous | One product can contain multiple materially distinct current configurations | Define A-P8 over exact CONFIGURATION identities/equivalence clusters while preserving product identities |
| R16 | Operational boundary-disposition provenance was underspecified | A counted product could lack an attributable governed inclusion record or exact validation lineage | Require decision, rationale, role, timestamp, exact-object binding, contract/protocol ID, and exact reference-standard identity/version |
| R17 | Observed and estimated population semantics were not explicitly separated | The unseen residual could be misreported as individually identified or human-adjudicated products | Define N_observed, N_estimated and N_unseen separately; prohibit item-level interpretation of the latent residual |
| R18 | Enumeration-role uncertainty and true out-of-vocabulary roles were conflated | Role-specific analyses could hide uncertainty or misuse OTHER as an unknown state | Add `UNRESOLVED` separately from `OTHER_REVIEW_REQUIRED`; retain unresolved roles in A-P1 while excluding them from role-specific views |
| R19 | FAMILY/OFFERING/CONFIGURATION were treated like entity types | P0.3 could invent a parallel ontology inconsistent with Observatory v2 | Map FAMILY and OFFERING to PRODUCT identity levels and CONFIGURATION to PRODUCT_CONFIGURATION SYSTEM identity |
| R20 | Family creation could be synthetic one-per-offering | Family counts could be mechanically inflated without source-backed family identity | Create FAMILY PRODUCT entities only for evidenced/meaningful family groupings |
| R21 | A-P8 could fabricate a configuration for every offering | Technical-implementation counts could become a relabelled offering count | Include only evidenced PRODUCT_CONFIGURATION SYSTEM identities; report missing-configuration coverage |
| R22 | “Exact product/version row” risked becoming a third canonical entity | Registry flattening could duplicate PRODUCT/SYSTEM identity semantics | Define registry rows as deterministic analytical projections over PRODUCT offering + optional configuration SYSTEM |
| R23 | Current projections lacked a versioned currentness policy | Stale evidence could be carried forward by implementation-specific judgment | Bind `currentness_policy_id` to every CURRENT view/count/estimate |
| R24 | Registry projection omitted required capability/context dimensions | The registry could not reproduce the working-methodology product analyses | Include sensing, inference, output, form factor, context, target population and state fields as evidence-backed projection attributes |
| R25 | “Market-facing product” terminology implied commercialization | Investigational/research offering identity could be mistaken for commercial state | Rename to product/service offering identity and keep commercial state separate |
| R26 | Preferred present-tense product view was unspecified | Announcement-inclusive A-P1 could be quoted as “currently available products” | Require A-P6 for currently released/externally accessible wording; reserve A-P1 for offering-inventory language |
| R27 | Family/offering/configuration joins lacked governed relation semantics | Flattened registry joins could be inferred from names, developer, branding or proximity | Require evidence-backed directed family↔offering and offering↔configuration relations; unresolved joins stay unresolved |
| R28 | Registry row grain was underspecified | Jurisdiction/cutoff variants could be mistaken for distinct products or irreproducible snapshots | Define a deterministic projection key over offering, optional configuration, jurisdiction, cutoffs and projection version |
| R29 | Flat projection could widen assertion scope | Configuration-level regulatory/capability claims could leak to sibling configurations or whole families | Retain exact assertion refs/subjects/scopes for every projected state/capability and prohibit scope widening |
| R30 | Registry row cardinality could be mistaken for product count | Multi-configuration/jurisdiction projections could inflate denominators | Count canonical IDs/equivalence clusters at the declared identity level; never raw registry rows |
| R31 | Residual wording still treated D4 as operational scope authority | The reference standard could be misread as the population registry or item-level adjudicator | Replace operational D4 wording with approved D1 boundary + governed operational disposition; retain D4 only as validation/reference standard |
| R32 | Controlling deployment plan still assumed one canonical exact-product object | Plan and contract encoded incompatible identity models, inviting implementation drift | Rewrite P0.3 plan around PRODUCT family/offering + SYSTEM configuration identities and analytical registry projection |
| R33 | P0.2/P0-G conflated D4 freeze with model held-out evaluation | Could leak held-out material before freeze or falsely imply G2/model-validation passage | Require calibration/adjudication/split-lock/commitments/freeze at P0.2; keep model held-out evaluation as a separate gate before automated scaled filtering |
| R34 | Boundary uncertainty was excluded but not propagated | INCLUDE-only estimates could look more certain than the observed BORDERLINE/ABSTAIN/unresolved mass warrants | Report boundary-state counts and preregister sensitivity/bounds where material without promoting ambiguous cases |
| R35 | N_estimated could be read as an absolute world census | Capture models cannot identify classes with effectively zero capture probability in every declared frame | Define N_estimated conditionally on the declared frame/language/jurisdiction/model universe and require residual zero-capture coverage risk |
| R36 | Organization linkage was missing from the registry projection | A flat organization field could collapse developer/owner/manufacturer/distributor roles or propagate company claims | Retain typed evidence-backed organization relationship refs instead of one organization ID |
| R37 | Observation chronology was implicit | Analysts could confuse Observatory observation time with launch/validity time | Add first/last observed metadata traceable to observations and explicitly separate knowledge time from world time |
| R38 | D4 case packets did not bind the hardened identity level/role model | FAMILY/OFFERING/CONFIGURATION/SYSTEM cases could be reviewed as though interchangeable | Extend D4 controlled case bindings and calibration coverage to preserve entity type, identity level, system/offering role and enumeration role |
| R39 | Population-view state predicates were not version-bound | Different P0.3 implementations could produce different A-P2/A-P3/A-P6 numerators while claiming the same view | Bind every view/count/estimate to a versioned population_view_policy_id implementing the frozen P0.1 semantics |
| R40 | Final D4 sampling could omit newly material P0.1 identity boundaries | The held-out reference standard could validate old strata yet miss component/service/SYSTEM identity failures relevant to Release A | Require private final-sampling diagnostic coverage of the P0.1 identity/enumeration boundaries, bound through sampling/coverage digests without changing public v0.2 required_strata |

Two additional consistency corrections were made during implementation:

- add `cancelled` to lifecycle state because the current-offering views use that state;
- treat A-P8 as an analytical equivalence-cluster count, not a canonical-identity merge.

## 5. Resulting population-view architecture

The corrected candidate contract distinguishes:

```text
A-P1  CURRENT_IDENTIFIABLE_OFFERING_INVENTORY
A-P2  CURRENT_COMMERCIALLY_ACCESSIBLE
A-P3  CURRENT_RESEARCH_OR_INVESTIGATIONAL_ACCESS
A-P4  CURRENT_INTEGRATED_END_USER_SYSTEMS
A-P5  HISTORICAL_CUMULATIVE_OFFERINGS
A-P6  CURRENT_RELEASED_OR_EXTERNALLY_ACCESSIBLE
A-P7  CURRENT_DEPLOYED_LEGACY
A-P8  CURRENT_DISTINCT_TECHNICAL_IMPLEMENTATIONS
```

These views intentionally answer different questions.

A-P1 is the broad inventory of current identifiable offering identities and includes supported announcement/pre-delivery objects.

A-P6 is the narrower view for offerings that have progressed beyond announcement/development representation.

A-P7 captures products no longer offered but still documented in current deployment.

A-P8 is a configuration-SYSTEM technical-equivalence analytical view and cannot replace commercial-offering identity. Offerings with unresolved configuration evidence reduce A-P8 coverage rather than receiving fabricated configuration identities.

## 6. Minimum governed count metadata

The corrected candidate requires every Release-A count or estimate to bind:

```text
boundary_contract_id
boundary_contract_digest
registry_projection_version
input_release_or_snapshot_id
input_release_or_snapshot_digest
population_view_policy_id
boundary_disposition_protocol_id
boundary_disposition_protocol_digest
candidate_review_protocol_id
candidate_review_protocol_digest
review_completion_state
reference_standard_id
reference_standard_version
reference_standard_contract_digest
reference_standard_validation_state
population_view_id
identity_level
included_enumeration_roles
jurisdiction_scope
world_time_cutoff
knowledge_time_cutoff
currentness_policy_id
analysis_preregistration_id
analysis_execution_pin
observed_or_estimated
estimation_status
discovery_frame_register_id
discovery_frame_register_digest
discovery_frame_universe
discovery_protocol_id
population_model_id
population_model_digest
uncertainty_state
```

This is a central precondition for denominator validity.

## 6.1 v1.0 ontology projection clarified by the review

The corrected candidate now preserves the existing v2 object model:

```text
PRODUCT + identity_level=FAMILY
  -> only where a source-supported family identity exists

PRODUCT + identity_level=OFFERING
  -> market/research/investigational product or service offering

SYSTEM + system_role=PRODUCT_CONFIGURATION
  -> exact/bounded technical configuration linked to an offering

SYSTEM without qualifying offering identity
  -> technology/system landscape only, outside product offering counts
```

The exact-product registry is a projection joining these canonical objects and scoped assertions. It is not another entity family.

## 6.2 Final pre-review consistency audit

A final repository- and methodology-level audit after the R1–R40 merge identified thirty-four residual consistency defects. These are corrections to the same candidate contract and dependent execution documents, not a new substantive research direction.

| ID | Residual inconsistency | Correction |
| --- | --- | --- |
| C1 | The review record still described the corrections as living on the pre-merge branch and its minimum reporting metadata lagged the contract | Make the review state branch-independent and synchronize the governed count metadata |
| C2 | Published count metadata omitted the exact registry projection version and discovery-frame universe needed to reproduce the denominator | Require both fields in every governed Release-A count/estimate |
| C3 | Release-A seed construction still described canonical “exact-product records/objects”, conflicting with the PRODUCT-offering / SYSTEM-configuration model | Define A1 as canonical identity-graph construction plus analytical registry projection; prohibit row-count denominators |
| C4 | Final D4 sampling required private identity/enumeration diagnostic coverage without freezing each candidate's diagnostic assignment or deterministic derivation rule | Bind the diagnostic dimensions or their frozen derivation policy into the candidate-pool freeze |
| C5 | The D4 protocol unnecessarily serialized P0.3 implementation behind full P0.2 completion | Permit P0.3 schema/projection implementation after P0.1 freeze while retaining D4 completion as a P0-G/Release-A operational dependency |
| C6 | Registry-row identity and population-view eligibility were insufficiently separated; binding view/currentness policies into the base row would make the registry view-dependent | Keep the base registry projection view-neutral and add a separate deterministic eligibility projection that binds `population_view_policy_id` and `currentness_policy_id` |
| C7 | The D4 case packet used `candidate_canonical_entity_type` even though some valid boundary cases intentionally have unresolved canonical identity | Replace it with a bound/proposed entity-type field whose controlled domain includes `UNRESOLVED`, and define unresolved/not-applicable identity semantics explicitly |
| C8 | D4 deterministic selection used `canonical_candidate_id`, which is undefined for legitimately unresolved identity cases and can couple sampling to later resolution | Introduce a stable opaque `candidate_selection_id` assigned before sampling and use that ID for deterministic selection |
| C9 | Duplicate candidate bindings were not governed before final held-out selection | Freeze duplicate-resolution state/group, collapse known duplicates unless an identity-boundary exception is predeclared, and keep suspected unresolved duplicates from being treated as independent evidence |
| C10 | Count/projection metadata identified policies and cutoffs but not the immutable input release/snapshot | Bind every governed registry projection/count/estimate to the exact immutable input release/snapshot identity and digest, including that input identity in the deterministic row key |
| C11 | Release-A A2 described capture histories at raw candidate level | Preserve candidate discovery provenance but construct estimation capture histories only after governed inclusion and identity resolution at the preregistered estimation unit |
| C12 | Release-A A7 still used `N_total`, which could contradict the contract's conditional open-world estimand semantics | Use `N_estimated = N_observed + N_unseen` and state explicitly that it is conditional on the declared discovery-frame/language/jurisdiction/model universe |
| C13 | Legacy programme-plan display equations contained malformed Markdown and escaped control characters from earlier authoring | Normalize all affected equations to deterministic fenced-text notation without changing their substantive definitions |
| C14 | Residual “global unique-product count” wording could be misread as a completeness claim even though the contract forbids global-census inference | Use cross-jurisdiction unique-offering terminology and bind it explicitly to the declared discovery/analysis universe |
| C15 | Governed count metadata still lacked exact content/execution identities needed to reproduce the result from an immutable state | Add exact boundary-contract, input-snapshot, operational-disposition-protocol, reference-standard and discovery-frame-register digests plus preregistration ID and an execution pin binding code, environment/configuration and stochastic controls where applicable |
| C16 | Capability-first and multilingual yield diagnostics did not explicitly distinguish raw candidate gain from deduplicated governed product-identity gain | Define the primary diagnostics on the same governed qualifying identity unit/view/cutoffs and report lead/error/duplicate yield separately |
| C17 | Opaque D4 candidate selection IDs lacked an anti-gaming assignment rule | Assign each selection ID once in an append-only controlled ledger before pool freeze/score computation; prohibit regeneration or renumbering based on score order |
| C18 | Required final D4 disposition coverage could be misread as a gold-label sampling quota or invite post-label top-up | Treat disposition coverage as a freeze adequacy criterion only; selection constraints are label-free and a coverage failure forces a successor sampling path rather than post-hoc replacement/top-up, with the previously reviewed sample excluded from a label-informed successor unless a contingency was predeclared |
| C19 | The protocol named a final human D4 freeze decision point without defining its disposition domain or binding it to exact candidate artifacts | Validate candidate successor artifacts first, then record `APPROVE_D4_FREEZE / REQUEST_D4_CHANGES / DEFER_D4_FREEZE`; only exact-artifact approval authorizes the frozen public successor |
| C20 | Release A still requested a generic D4 “evaluation report”, which could conflate human reference-standard freeze with separately gated model/pipeline evaluation | Require human calibration/freeze evidence and include a model/pipeline evaluation report only when such automation is actually used and separately gated |
| C21 | Release A implicitly forced a numerical unseen-population estimate even if the preregistered model family is non-identifiable or diagnostically unstable, and did not explicitly constrain the unseen residual to be non-negative | Require `N_estimated >= N_observed`, prohibit negative unseen mass, preregister model adequacy/identifiability/stability criteria, and permit `ESTIMATE_NOT_IDENTIFIED` / `WITHHELD_METHOD_FAILURE` instead of forcing a total |
| C22 | A purposively selected final D4 double-label subset could be used to imply an overall inter-rater agreement estimate | Treat agreement from a strategic subset as subset-specific; require full double review or a predeclared probability-sampling design for an overall final-benchmark agreement estimate |
| C23 | D4's deliberately stratified edge-case composition could be mistaken for the operational candidate/product base-rate distribution | State that D4 metrics are benchmark-conditional, its class proportions are not prevalence estimates, and population-weighted/operational performance requires a separately justified target distribution/transport design |
| C24 | Access/commercial, regulatory and deployment state were written like scalar fields even though the contract allows overlapping research/commercial access and multiple scoped regulatory/deployment assertions | Represent compatible concurrent access, regulatory and deployment states as scoped multi-value assertions and prohibit forced exclusivity |
| C25 | D4 required human/expert review but did not explicitly bind reviewer qualification, conflicts, distinct-person double review, or independent adjudication | Require controlled reviewer qualification/conflict provenance, independent first-pass reviewers, and a distinct qualified adjudicator for disagreements; otherwise retain unresolved status |
| C26 | The controlling plan still treated jurisdiction as part of “exact product/version/jurisdiction identity”, contradicting P0.1's rule that jurisdiction is normally scoped state rather than identity | Rewrite the plan around exact offering/configuration identity plus jurisdiction-scoped state, creating a distinct configuration only for a material jurisdictional change |
| C27 | P0.5 still used `N_unobserved` while P0.1 uses `N_unseen`, and stated coverage without conditioning on a valid estimate | Standardize on `N_unseen` and define coverage only when an accepted `N_estimated > 0` exists |
| C28 | Candidate-status text said the document itself “freezes” P0.1 semantics before an attributable human approval | State that the document freezes semantics only after exact-digest human approval and recorded `FROZEN_v1.0` status |
| C29 | The contract relied on issue workflow for final freeze authority instead of defining the substantive disposition in the contract itself | Add `APPROVE_FREEZE_v1.0 / REQUEST_CHANGES / DEFER` and require exact-digest attributable approval; continuing execution or merging docs is explicitly not approval |
| C30 | Population-estimation compatibility metadata used `population_view` / `enumeration_roles` while governed count metadata used `population_view_id` / `included_enumeration_roles` | Normalize the estimation-universe fields to the governed count field names so preregistration, computation and reporting bind the same identifiers |
| C31 | Governed count metadata conflated discovery-protocol identity and population-model identity in one `discovery_protocol_or_model_id` field | Split them into independent discovery-protocol and population-model identities/digest, with model fields explicitly not applicable to observed-only counts |
| C32 | D4 calibration/final disjointness was stated only at the case level, allowing the same underlying product/system to leak across splits through aliases, alternate URLs, translations or duplicate records | Require cross-split identity/duplicate review and exclude known or unresolved suspected calibration-equivalent objects from final held-out membership |
| C33 | Higher-level product-family or organization overlap across calibration/final splits could support inflated claims about unseen-family or unseen-actor generalization | Report higher-level overlap and require a predeclared group-disjoint or separately reported group-held-out analysis for any unseen-family/actor generalization claim |
| C34 | Release-A population estimation did not explicitly govern which discovered candidates receive human review, so confidence-/frame-/language-dependent review could bias capture histories while unreviewed candidates disappear | Freeze the candidate-review protocol, require review completion for unadjusted estimation or preregister/model the review-sampling mechanism, report review-completion state, and never treat unreviewed candidates as exclusions |

The final audit also rechecked the contract against the current Observatory v2 PRODUCT/SYSTEM ontology, conservative identity-resolution rules, two-axis temporal model, evidence/decision boundary, 23 September working methodology, product/services working analysis, and integrated-report denominator cautions. No additional unresolved semantic contradiction was identified in those source materials.

## 7. Residual methodological risks

The adversarial review does not eliminate the following later risks:

### 7.1 Technical-equivalence evidence

A-P8 will require a graded equivalence relation or equivalent implementation contract. P0.1 defines the semantic boundary but P0.3/Release A must still specify how strong the evidence must be to cluster two offerings.

### 7.2 Operational boundary-review scaling

Approved D1 requires expert review for governed boundary membership. Release A will need an operational review design that scales without weakening that authority boundary. D4 evaluates that process; it does not replace it.

### 7.3 Currentness under sparse evidence

The temporal model prevents a null end date from meaning “current”, but operational rules will still need explicit currentness evidence windows and stale-evidence handling in P0.3/P0.4.

### 7.4 Population-estimation dependence

Even with a fixed estimand, discovery frames are dependent. Release A must therefore compare multiple-systems/source-dependence models and report sensitivity. P0.1 only prevents unit mismatch.

### 7.5 International product equivalence

Regional branding, modified labeling, hardware variants, and jurisdiction-specific configurations will remain a major identity-resolution burden. The contract prevents silent merge but cannot resolve those cases without evidence.

## 8. Pre-freeze review conclusion

The predecessor contract should not be frozen.

With R1–R40 and C1–C34 incorporated, the candidate contract is methodologically stronger and is suitable to advance to **human freeze review** once the exact final correction head passes the repository's required checks and the merged candidate is confirmed unchanged on `main`.

The appropriate next disposition after successful PR review is one of:

```text
APPROVE_FREEZE_v1.0
REQUEST_CHANGES
DEFER
```

Only an attributable human disposition can move the contract from `CANDIDATE FOR FREEZE` to `FROZEN_v1.0`.

## 9. Non-claims

This review does not establish:

- correctness of future product identities;
- completeness of the product population;
- adequacy of D4 human labels;
- population-estimation validity;
- market share;
- effectiveness;
- G2 passage;
- P0-G passage;
- canonical S2 authority;
- publication authority.
