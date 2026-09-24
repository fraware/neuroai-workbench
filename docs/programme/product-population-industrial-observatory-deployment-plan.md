# Product Population → Industrial Observatory deployment plan

**Plan ID:** `PLAN-POPULATION-INDUSTRIAL-OBSERVATORY-v1`  
**Status:** PROGRAMME DEPLOYMENT PLAN — tracked implementation contract, not a scientific finding or publication authorization  
**Repository:** `fraware/neuroai-workbench`  
**Tracking issue:** #313  
**Scheduling model:** dependency- and gate-based only; this plan deliberately contains no month-based timeline

## 1. Purpose

This document is the durable repository reference for extending the NeuroAI Landscape Observatory from a representative product/service landscape into four progressively stronger measurement layers:

- **Release A — Product Population Observatory:** establish a validated exact-product population, discovery-coverage evidence, and bounded population estimates.
- **Release B — Commercial Measurement Layer:** define economically coherent submarkets and estimate market size, adoption, and market share only where defensible denominators exist.
- **Release C — Evidence and Effectiveness Observatory:** link exact products to clinical/scientific evidence, characterize evidence maturity, and compare effectiveness only inside commensurable evidence groups.
- **Release D — Integrated NeuroAI Industrial Observatory:** connect patents, organizations, products, commercial penetration, evidence maturity, geography, capital, dependencies, and governance in a longitudinal evidence graph.

The programme is intentionally cumulative. Release B and Release C may start once Release A has stabilized the relevant product identities and classifications. Release D integrates only evidence objects and relationships that have passed their applicable upstream gates.

This plan governs sequencing, work packages, deliverables, claim boundaries, and release gates. Mutable execution status belongs in issues, pull requests, immutable execution-state records, benchmark records, and release artifacts. A code merge, schema pass, successful collection run, model score, or completed issue does not by itself establish a substantive landscape conclusion.

## 2. Governing invariant

> **Evidence strength and denominator quality set the maximum claim.**

The programme keeps four measurement questions separate:

| Layer | Primary question | Required denominator / reference universe | Prohibited shortcut |
| --- | --- | --- | --- |
| A | What products and services exist? | Defined product population under an explicit discovery protocol | Treating discovered records as a complete global census |
| B | How economically important are they? | Explicit submarket denominator such as revenue, units, users, procedures, or installed systems | Relabelling product counts or actor counts as market share |
| C | What evidence supports their performance or effectiveness? | Commensurable evidence universe defined by population, intervention, comparator, endpoint, and horizon | Ranking heterogeneous products because they share a category label |
| D | How does the industrial system evolve? | Evidence-graded longitudinal graph with explicit source-specific coverage | Collapsing patents, products, capital, adoption, geography, and evidence into one undifferentiated leadership score |

Additional programme invariants:

1. Product existence, commercial availability, deployment, regulatory authorization, effectiveness, adoption, and market position remain distinct typed claims.
2. Exact product/version/jurisdiction identity precedes quantitative aggregation.
3. Automated discovery and model assistance emit candidates, classifications, rankings, or proposed links. They do not independently create canonical truth or publication authority.
4. Open-world search saturation is reported as saturation under a protocol, never as proof of global completeness.
5. Multilingual and jurisdictional coverage are measurement dimensions, not an after-the-fact limitations paragraph.
6. Unresolved identity, provenance, source rights, or evidence linkage remains explicit and cannot be compensated for by source volume, model confidence, capital, or prominence.
7. Population estimates, market estimates, comparative-effectiveness results, and longitudinal associations each require their own validation and uncertainty treatment.
8. Release publication remains a separate governed act from candidate generation, technical verification, human review, and analytical computation.

## 3. Scope and non-goals

### 3.1 In scope

The programme covers identifiable products and services that satisfy the approved NeuroAI research boundary and the frozen product inclusion standard, including clinical, research, consumer, workplace, wellness, accessibility, entertainment/XR, and non-traditional form factors where the required neural or neurocognitive evidence exists.

The programme may also represent:

- product families and exact product versions/configurations;
- software and service layers materially coupled to a product capability;
- investigational and research-use systems;
- jurisdiction-specific regulatory and commercial states;
- discontinued or superseded products where needed for longitudinal analysis;
- organizations, patents, trials, publications, regulatory records, commercial observations, financing events, deployment evidence, and supply dependencies linked to exact products.

### 3.2 Explicit non-goals

This plan does not authorize:

- an assertion that every NeuroAI product worldwide has been identified;
- market-share language without an explicit economic or adoption denominator;
- comparative-effectiveness rankings across non-commensurable products or endpoints;
- conversion of company marketing claims into independent evidence of effectiveness;
- conversion of patent ownership into proof of product implementation, commercialization, or market leadership;
- country or company “leadership” rankings assembled from heterogeneous metrics;
- causal claims from descriptive correlations unless a separate causal design establishes them;
- redistribution of licensed or protected source material beyond applicable rights;
- any change to the v4.2 assessment-kernel requirement meanings.

## 4. Dependency architecture

The controlling dependency chain is:

```text
P0  Measurement foundation
 |
 v
A   Product Population Observatory
 |\
 | \
 v  v
B   C
Commercial Measurement      Evidence & Effectiveness
 \ /
  v
D   Integrated NeuroAI Industrial Observatory
```

The dependency is semantic, not merely chronological:

- **P0 → A:** exact product identity and inclusion semantics must exist before population-scale counting.
- **A → B:** market measurement needs stable product/submarket membership and a known coverage state.
- **A → C:** evidence synthesis needs stable exact-product identity and claim decomposition.
- **A/B/C → D:** the integrated layer must preserve the provenance, uncertainty, and claim boundaries of every upstream object.

## 5. Phase P0 — Measurement foundation

### P0 objective

Freeze the measurement object and research contract needed for population-scale product analysis. P0 is complete only when later counts can be traced back to a stable definition of what was counted.

### P0.1 — Product measurement contract

Define the exact semantics of:

- product;
- service;
- product family;
- exact product/version/configuration;
- jurisdiction-specific product instance;
- active product;
- announced product;
- manufacturing / pre-delivery product;
- commercially sold consumer product;
- commercially sold research platform;
- regulated medical product;
- investigational system;
- research-only system;
- deployment;
- installed base;
- discontinued / withdrawn / superseded product;
- software-only or cloud/service layer;
- component versus full system.

The contract must resolve difficult cases such as:

- one physical device with several software subscriptions;
- one product sold under multiple regional names;
- materially different firmware/software configurations;
- cleared components embedded in a broader investigational system;
- research prototypes that never become products;
- products announced but not delivered;
- OEM components;
- products that are discontinued but remain deployed;
- bundled hardware–software–service systems.

**Deliverable:** [Product Measurement Contract v1.0](product-measurement-contract.md).

### P0.2 — Execute and freeze D4

Complete the real human product edge-case benchmark and reference-standard workflow.

Minimum benchmark strata:

- clear neural-sensing positives;
- clear non-neural biosensing negatives;
- products using neural capability without conventional neurotechnology branding;
- wellness and broad physiological-sensing boundary cases;
- ear-EEG / hearables and non-traditional form factors;
- multimodal neural + physiological systems;
- software/service interpretation layers;
- research platforms;
- regulated products;
- investigational systems;
- discontinued/superseded products;
- multilingual and multi-jurisdiction examples.

The classification output must preserve:

```text
INCLUDE
EXCLUDE
BORDERLINE
ABSTAIN
```

Required freeze evidence:

- independent human review;
- disagreement accounting;
- adjudication provenance;
- inter-rater agreement and calibration analysis;
- error taxonomy;
- locked held-out membership inaccessible to tuning;
- coverage accounting across required dispositions and strata;
- contamination/exposure and rights review;
- opaque membership/disposition commitments.

Model or pipeline performance on the frozen held-out D4 set is a separate evaluation step. P0.2 does not claim G2 or model-evaluation passage. Any automated boundary classifier used as a production filter must separately satisfy its applicable held-out evaluation and role-narrowing requirements before scaled use.

**Execution protocol:** [D4 Product Reference Standard execution protocol](../methodology/d4-product-reference-standard-execution-protocol.md).

**Deliverable:** `D4 Product Reference Standard v1.0`.

### P0.3 — Exact-product ontology and registry schema

Implement the frozen P0.1 Product Measurement Contract without collapsing canonical identity levels.

The canonical graph separates:

```text
PRODUCT family identity          # only where an evidenced family exists
PRODUCT offering identity
SYSTEM product-configuration identity
evidence-backed family/offering/configuration relations
```

The “exact product/version registry” is a reproducible analytical projection over those canonical objects and scoped assertions. It is not a new canonical entity class, and raw registry-row cardinality is not a product denominator.

Minimum projection fields include:

```text
registry_row_id
registry_projection_version
input_release_or_snapshot_id
input_release_or_snapshot_digest
product_offering_id
product_family_id
configuration_system_id
configuration_coverage_state
organization_relationship_refs[]
offering_kind
primary_enumeration_role
jurisdiction_scope
world_time_cutoff
knowledge_time_cutoff
first_observed_at
last_observed_at
lifecycle_state
access_commercial_state
regulatory_state
deployment_state
form_factor[]
signal_or_sensing_modality[]
inference_capability[]
intervention_output_capability[]
deployment_context[]
target_population[]
boundary_disposition_ref
projected_assertion_refs[]
source_observation_refs[]
identity_state
review_state
```

Population-view eligibility is a separate derived projection over those rows. Minimum eligibility fields include:

```text
eligibility_record_id
registry_row_id
canonical_counting_identity_id
population_view_id
population_view_policy_id
currentness_policy_id
eligibility_state
eligibility_reason_codes[]
boundary_disposition_ref
input_release_or_snapshot_id
input_release_or_snapshot_digest
```

P0.3 must preserve:

- nullable/unresolved family and configuration bindings instead of fabricating entities;
- assertion subject/scope through analytical flattening;
- typed organization relationship references rather than one ambiguous organization field;
- observation chronology separate from world-time product state;
- exact operational boundary-disposition provenance and D4/reference-standard lineage;
- deterministic view-neutral registry-row grain;
- deterministic population-view eligibility keys separate from registry-row identity;
- canonical-ID deduplication at the declared population-view identity level;
- technical-equivalence relationships without silent identity merge;
- versioned currentness policy for every current projection;
- versioned machine predicates for every A-P1–A-P8 population view;
- exact frozen contract, operational-disposition-protocol, reference-standard and discovery-frame-register digests, Release-A preregistration ID, and analysis execution pin in governed count/estimate metadata.

**Deliverables:** ontology/schema changes where required, registry-projection schema, identity and linkage rules, validators, adversarial fixtures, and migration/compatibility notes.

### P0.4 — Discovery-frame contract

Every product discovery source family receives a declared frame record. The complete register has an immutable register ID/version and canonical digest that later population analyses must bind.

```text
frame_id
source_universe
source_class
language
jurisdiction
query_or_seed_protocol
execution_mode
observation_window
deduplication_boundary
coverage_state
termination_rule
rights_class
```

The discovery system must preserve which frame found each candidate and on which discovery round.

**Deliverable:** `Product Discovery Frame Register v1.0` with immutable register identity and canonical digest.

### P0.5 — Preregister Release-A estimands

Predeclare the primary measurements before population estimation is fit to the observed capture histories.

At minimum:

```text
N_observed
N_estimated
N_unobserved = N_estimated - N_observed
Coverage = N_observed / N_estimated
```

plus:

- marginal new-product yield by round/channel;
- duplicate yield by round/channel;
- excluded and unresolved candidate rates;
- English-only versus multilingual incremental yield;
- conventional terminology versus capability-first incremental yield;
- subgroup estimates by product family and jurisdiction where supported;
- observed BORDERLINE/ABSTAIN/unresolved candidate accounting;
- predeclared boundary-uncertainty sensitivity/bounds where material;
- explicit zero-capture/coverage-risk analysis for the declared discovery-frame universe.

**Deliverable:** `Release A Analysis Preregistration v1.0`.

### P0 gate — `P0-G`

P0 passes only when all of the following are true:

- product inclusion semantics are frozen;
- D4 has completed human calibration, final human adjudication, held-out split lock, commitment generation and reference-standard freeze;
- exact-product identity rules are frozen;
- discovery frames and termination semantics are defined;
- primary Release-A estimands and population-model comparison rules are preregistered;
- duplicate-resolution and unresolved-identity rules are frozen;
- multilingual and non-traditional discovery strata are defined.

A passing P0 gate does not establish any global product count, pass G2, or establish model/pipeline held-out performance. Release-A execution must remain human-governed unless and until any automated production filter separately passes its applicable evaluation gate.

## 6. Release A — Product Population Observatory

### A objective

Move from representative product cases to a validated exact-product analytical registry projection backed by canonical PRODUCT/SYSTEM identities, with measured discovery coverage and bounded estimates of the residual unseen product population.

### A1 — Seed registry construction

Create canonical PRODUCT offering/family identities and PRODUCT_CONFIGURATION SYSTEM identities from validated existing evidence, then generate exact-product registry projection rows under the frozen P0.1/P0.3 semantics. Seed evidence may include:

- current Observatory organizations with product evidence;
- representative product/service cases;
- regulatory records;
- trial records;
- research platforms;
- current commercial product pages;
- previously adjudicated non-traditional cases.

Organization records must not be mechanically converted into product counts. One organization may relate to zero, one, or many product offerings/configurations through typed evidence-backed relationships. Registry rows remain analytical projections and are never counted directly.

For every seed, record:

- canonical offering identity and, where evidenced, family/configuration identity;
- typed organization relationships;
- state projection at the declared world-time/knowledge-time cutoffs, with population-view/currentness eligibility computed separately;
- source observation and observation chronology;
- evidence state and governed boundary disposition;
- relevant jurisdiction scope;
- applicable capability/context classification;
- unresolved family/configuration/linkage/state fields.

**Output:** high-confidence seed canonical identity graph plus exact-product registry projection and separate population-view eligibility projection.

### A2 — Multi-frame product discovery

Run independently attributable discovery frames. Minimum source families:

- **F1 — first-party product discovery:** company product catalogues, manuals, documentation, archived official pages;
- **F2 — regulatory discovery:** device and authorization records;
- **F3 — clinical/trial discovery:** trial registries and study records;
- **F4 — scientific/research discovery:** publications, laboratory instrumentation, research-platform documentation;
- **F5 — commercial/ecosystem discovery:** specialist distributors, procurement, accelerator/investor portfolios, industry directories;
- **F6 — capability-first discovery:** searches driven by function/capability instead of category branding;
- **F7 — expert nominations:** structured expert seeds and edge cases;
- **F8 — local-language discovery:** native-language sources and query families for selected jurisdictions.

Every raw candidate retains frame-level discovery provenance and round history.

For population estimation, capture histories are constructed only after governed boundary review and identity resolution at the exact preregistered estimation unit:

```text
C_i = (F_1, F_2, ..., F_k)
```

where `i` is the unique qualifying canonical identity or other explicitly preregistered estimation unit, never an unreconciled raw candidate row. Duplicate observations collapse into the same unit-level capture history. BORDERLINE, ABSTAIN and unresolved-identity candidates remain in coverage/uncertainty accounting and are not silently converted into population members.

**Output:** multi-frame raw candidate ledger plus unit-resolved capture-history dataset.

### A3 — Capability-first recall study

Measure what conventional neurotechnology terminology misses.

Search families include, where consistent with the frozen product boundary:

- attention and vigilance estimation;
- fatigue or drowsiness;
- cognitive load and workload;
- affective or stress-state inference;
- adaptive interfaces;
- neurofeedback and cognitive training;
- behavioral personalization using brain/body-state signals;
- neural decoding and device control;
- neural sensing embedded in earbuds, headphones, eyewear, headbands, or other ordinary form factors.

Primary diagnostic:

```text
Delta_N_capability =
N_all_discovery
-
N_conventional_terminology
```

For the primary product-yield comparison, both `N_all_discovery` and `N_conventional_terminology` are deduplicated governed qualifying identities under the same frozen boundary, population view, cutoff pair, identity level, and review policy. Raw candidate/lead yield is reported separately, with false-positive and unresolved rates.

Report incremental qualifying-identity yield by product class and jurisdiction where the matched design supports it.

**Output:** `Capability-First Recall Study`.

### A4 — Multilingual coverage study

Select language/jurisdiction strata using evidence such as patent activity, known product activity, strategic relevance, likely English-language discovery bias, and expert input.

For each selected stratum, run matched discovery protocols:

```text
S_English
```

versus

```text
S_English_plus_Native
```

Measure:

```text
Delta_j =
N_j_English_plus_Native
-
N_j_English
```

where both terms count deduplicated governed qualifying identities under the same frozen boundary, population view, identity level, cutoff pair, and matched English/native discovery-frame design. Candidate-level lead gain, error rate, duplicate rate, capability gain, and source-class gain are reported separately.

The result must identify which substantive conclusions change when native-language discovery is included.

**Output:** `Multilingual Product Coverage Sensitivity Report`.

### A5 — Snowball discovery

Validated products and organizations generate controlled discovery edges:

```text
Product -> Organization
Organization -> Other products
Product -> Trial
Product -> Regulatory record
Product -> Publication
Product -> Distributor / procurement record
Product -> competitor / alternative candidate
Product -> related capability query
```

Every edge-generated object re-enters as a candidate and remains subject to the same inclusion and identity rules.

Track each round (r):

```text
Y_r = new validated products
```

```text
D_r = duplicate candidates
```

```text
X_r = excluded candidates
```

```text
U_r = unresolved candidates
```

**Output:** round-level discovery ledger.

### A6 — Discovery saturation analysis

Measure marginal yield:

```text
m_r = Y_r / Candidates_r
```

and decompose it by:

- source frame;
- language;
- jurisdiction;
- product class;
- capability family;
- discovery round.

Stopping language is restricted to:

- saturation under the declared protocol;
- budget/coverage termination;
- source exhaustion within a bounded frame;
- unresolved source barrier.

It must never be described as proof that every relevant product worldwide has been found.

**Output:** `Product Discovery Coverage and Saturation Report`.

### A7 — Unseen-population estimation

Estimate, conditional on the exact preregistered discovery-frame/language/jurisdiction/model universe:

```text
N_estimated = N_observed + N_unseen
```

using preregistered model families and sensitivity checks. `N_estimated` is not an absolute world-total claim and must preserve residual zero-capture/coverage uncertainty.

At minimum compare:

1. directly observed count;
2. simple capture–recapture diagnostics;
3. log-linear multiple-systems estimation;
4. models with source dependence;
5. stratified models by product class and/or geography;
6. Bayesian sensitivity models where justified.

The naïve two-source estimator

```text
N_hat = (n_1 * n_2) / m
```

is diagnostic only unless independence assumptions are defensible.

Preferred reporting form:

```text
Directly observed product population: N_observed
Estimated identifiable population under protocol P: interval [L, U]
Estimated observed fraction: interval [a, b]
Major residual uncertainty: named classes/jurisdictions/source barriers
```

Population estimates must include model diagnostics, dependence assumptions, sensitivity analysis, and limitations.

**Output:** `Product Population Estimation Report`.

### A8 — Product population release package

Release A produces:

- `Product Registry Projection v1.0` plus canonical identity graph and eligibility projection;
- D4 reference-standard version and human calibration/freeze evidence, plus any separately gated model/pipeline evaluation report actually used for automated filtering;
- Discovery Frame Register;
- Capability-First Recall Study;
- Multilingual Coverage Sensitivity Report;
- Coverage and Saturation Report;
- Population Estimation Report;
- analytical workbook;
- reproducible product figures;
- source/coverage/uncertainty register;
- public evidence objects permitted by rights and publication authority;
- explicit unresolved/unknown register.

Permitted headline figures may include products by:

- form factor;
- capability;
- deployment context;
- commercialization state;
- regulatory state;
- evidence state;
- jurisdiction;

only with the applicable observed or estimated denominator stated.

### A gate — `A-G`

Release A passes only when a reviewer can reconstruct:

1. what was counted;
2. how offering/configuration identity, deduplication, and unresolved identity were handled;
3. what source frames were searched;
4. which languages/jurisdictions were included;
5. how discovery rounds terminated;
6. what was directly observed;
7. what was estimated;
8. what assumptions drive the unseen-population estimate;
9. what uncertainty remains;
10. which stronger global-completeness claims remain prohibited.

## 7. Release B — Commercial Measurement Layer

### B objective

Measure economically coherent NeuroAI submarkets using explicit denominators and source-graded commercial evidence. Release B replaces vague “market share” language with denominator-specific measures.

### B1 — Economic market ontology

Create a market taxonomy separate from the technical capability taxonomy.

Candidate submarkets may include:

- consumer brain-sensing wearables;
- research EEG systems;
- research optical/neuroimaging platforms;
- clinical EEG and remote monitoring;
- non-invasive therapeutic neuromodulation;
- implantable therapeutic neurotechnology;
- assistive implantable BCI;
- neural software/analytics platforms;
- neuro-data services.

Submarket membership requires an explicit rule. Products may participate in more than one economic segment only where the analytical model handles overlap without double counting.

**Output:** `NeuroAI Economic Market Taxonomy v1.0`.

### B2 — Denominator contract by submarket

For each submarket (m), predeclare the primary and secondary measures.

Examples:

| Submarket | Primary denominator | Secondary measures |
| --- | --- | --- |
| Consumer wearables | revenue or units | active users, subscriptions |
| Research EEG | revenue or installed systems | institutional customers |
| Remote monitoring | patients monitored | revenue, active sites |
| Therapeutic neuromodulation | procedures or installed systems | revenue |
| Implantable BCI | implants / participants | active clinical sites |
| Software/analytics | recurring revenue or licenses | enterprise customers |

Distinct market-share quantities remain separate:

```text
S_revenue(i,m) = R(i,m) / sum_j R(j,m)
```

```text
S_units(i,m) = U(i,m) / sum_j U(j,m)
```

```text
S_installed(i,m) = I(i,m) / sum_j I(j,m)
```

```text
S_users(i,m) = A(i,m) / sum_j A(j,m)
```

Product-count composition is not market share.

**Output:** `Submarket Denominator Register v1.0`.

### B3 — Commercial evidence hierarchy

Every commercial observation receives a source/evidence tier. A starting hierarchy:

- **C1:** audited filing / statutory financial report;
- **C2:** regulatory, reimbursement, or official administrative dataset;
- **C3:** procurement or institutional purchasing/deployment record;
- **C4:** company-disclosed quantitative metric;
- **C5:** independently reported estimate with disclosed methodology;
- **C6:** modeled estimate from observed inputs such as price × units/customers;
- **C7:** qualitative commercial presence only.

The hierarchy controls permitted claims; it is not a generic quality score.

**Output:** `Commercial Evidence Register`.

### B4 — Missing-value and private-company estimation

Where direct commercial data do not exist, estimates use explicit models and uncertainty.

Example:

```text
R_i = P_i * Q_i
```

with uncertain inputs:

```text
P_i ~ D_P; Q_i ~ D_Q
```

which implies a revenue distribution:

```text
R_i ~ D_R
```

and a market-share distribution:

```text
S_i ~ R_i / sum_j R_j
```

The programme must publish assumptions, input sources, interval estimates, sensitivity analysis, and the distinction between observed and modeled quantities.

**Output:** submarket estimation models and diagnostics.

### B5 — Concentration and commercialization analysis

Where denominators permit, calculate separate metrics such as:

- CR3;
- CR5;
- HHI;
- revenue concentration;
- unit concentration;
- installed-base concentration;
- procedure concentration;
- geographic concentration.

Keep these distinct from patent concentration, product-count concentration, venture-capital concentration, or actor density.

Represent commercialization as a vector rather than a binary:

```text
M_i =
(availability, deployment, adoption, revenue, regulation, manufacturing scale)
```

**Output:** market structure and commercial maturity analyses.

### B6 — Commercial measurement release package

Release B produces:

- Economic Market Taxonomy;
- Submarket Denominator Register;
- Commercial Evidence Register;
- source-specific market-size estimates;
- actor shares only for defensible denominators;
- concentration analyses;
- commercialization-state profiles;
- uncertainty/sensitivity annex;
- analytical workbook and figure data.

### B gate — `B-G`

For every quantitative commercial claim, the following chain must be recoverable:

```text
Claim
 -> Submarket definition
 -> Denominator
 -> Product membership
 -> Source evidence
 -> Estimation method
 -> Uncertainty
 -> Review state
```

If the denominator is missing or unstable, the output remains descriptive and no market-share claim is permitted.

## 8. Release C — Evidence and Effectiveness Observatory

### C objective

Link exact products to scientific, clinical, regulatory, and real-world evidence; characterize evidence maturity; and conduct comparative synthesis only where products and studies are genuinely commensurable.

### C1 — Product-linked evidence graph

Represent relationships among:

```text
PRODUCT
  -> CLAIM
  -> STUDY
  -> POPULATION
  -> INTERVENTION
  -> COMPARATOR
  -> OUTCOME
  -> FOLLOW-UP
  -> REGULATORY RECORD
```

Each evidence object records:

- study design;
- sample size;
- population;
- intervention/configuration;
- comparator;
- endpoint;
- follow-up;
- jurisdiction;
- sponsor/funding relationship;
- publication/registration state;
- risk-of-bias assessment where applicable;
- exact product/version binding;
- evidence source and observation.

**Output:** evidence-graph schema and ingestion pipeline.

### C2 — Evidence acquisition

Primary source classes include:

- trial registries;
- peer-reviewed scientific literature;
- regulatory reviews and decision records;
- clinical-study reports where accessible and permitted;
- independent validation studies;
- systematic reviews;
- appropriately characterized real-world evidence;
- company-sponsored studies retained with sponsor metadata.

Sponsor identity is recorded as evidence context; it is not an automatic validity decision.

**Output:** product-linked evidence registry.

### C3 — Product-claim decomposition

Material company/product claims are converted into typed propositions.

A claim such as “improves sleep” must resolve, where evidence permits:

```text
product/configuration
population
claimed intervention
outcome
comparator
time horizon
effect direction/magnitude
claim source
claim date
```

Insufficiently specified claims remain explicitly insufficiently specified rather than being silently interpreted.

**Output:** Product Claim Register.

### C4 — Separate evidence claim classes

The system must distinguish:

- technical performance;
- analytical validity;
- clinical efficacy;
- real-world effectiveness;
- safety;
- usability/adherence;
- regulatory status;
- adoption.

A laboratory decoding metric does not establish clinical effectiveness. Regulatory authorization does not establish superiority. Commercial popularity does not establish efficacy.

### C5 — Evidence maturity profile

Use a multidimensional profile instead of a single opaque score.

Candidate dimensions:

| Dimension | Example states |
| --- | --- |
| Independent evidence | none / limited / substantial |
| Study design | uncontrolled / observational / randomized |
| Replication | none / internal / external |
| Sample scale | exploratory / moderate / large |
| Outcome relevance | surrogate / functional / clinical |
| Follow-up | short / intermediate / longitudinal |
| Regulatory review | none / reviewed / authorized for defined indication |
| Real-world evidence | absent / limited / substantial |
| Cross-study consistency | unresolved / mixed / consistent |

If an aggregate index is later introduced, the underlying dimensions and weights must remain visible and validated.

**Output:** product-level evidence maturity profiles.

### C6 — Comparability graph

Two products enter the same comparative component only where the evidence is sufficiently aligned on:

```text
(population, indication, intervention objective, comparator, endpoint, horizon)
```

The comparability relation is evidence-based, not category-name-based.

Disconnected products remain non-comparable. “Comparison unsupported” is an admissible and important result.

**Output:** Comparability Graph and eligibility rules.

### C7 — Formal evidence synthesis

For eligible comparison components:

- use direct pairwise synthesis where justified;
- use meta-analysis only where design and outcome assumptions permit;
- consider network meta-analysis only where the evidence network is connected and transitivity/consistency assumptions are defensible;
- use structured narrative synthesis where quantitative pooling would be invalid.

Every synthesis records:

- inclusion criteria;
- study selection;
- risk of bias;
- heterogeneity;
- effect measure;
- sensitivity analysis;
- model assumptions;
- evidence certainty/limitations.

**Output:** comparative-effectiveness reviews for eligible groups.

### C8 — Claim–evidence gap analysis

For each product:

```text
G_i =
Claims_i - IndependentlySupportedClaims_i
```

Possible claim dispositions:

```text
SUPPORTED
PARTIALLY_SUPPORTED
CONTEXT_DEPENDENT
INSUFFICIENT_INDEPENDENT_EVIDENCE
CONTRADICTED
NOT_ASSESSED
```

Aggregate analysis may estimate category-specific evidence gaps only when claim selection and evidence-review coverage are explicit.

**Output:** `Claim–Evidence Concordance Report`.

### C release package

Release C produces:

- NeuroAI Evidence Graph;
- Product Claim Register;
- scientific/clinical evidence registry;
- evidence maturity profiles;
- Comparability Graph;
- comparative syntheses for eligible groups;
- claim–evidence concordance analysis;
- explicit non-comparability records;
- reproducible review/search protocols.

### C gate — `C-G`

No comparative-effectiveness statement passes unless:

```text
Commensurability
+
Evidence quality
+
Appropriate synthesis
+
Traceable product identity
```

are all satisfied.

A product may appear in the Evidence Observatory without being eligible for comparative-effectiveness analysis.

## 9. Release D — Integrated NeuroAI Industrial Observatory

### D objective

Integrate validated upstream evidence into a longitudinal industrial observatory that connects invention, organizations, products, commercialization, deployment, evidence maturity, geography, capital, dependencies, and governance without collapsing their distinct semantics.

### D1 — Unified longitudinal graph

Represent evidence-graded relationships among:

```text
Patent
 <-> Organization
 <-> Product
 <-> Commercial evidence
 <-> Scientific/clinical evidence
 <-> Deployment
 <-> Geography
 <-> Financing
 <-> Dependency
 <-> Capability
 <-> Context
 <-> Governance concern
```

Every relationship retains:

- exact subject/object identity;
- source/observation provenance;
- evidence tier;
- valid time;
- observation time;
- review state;
- uncertainty/unresolved state.

**Output:** Integrated Industrial Graph schema and validated projection.

### D2 — Longitudinal event model

Track events such as:

- patent filing/publication;
- company formation;
- financing;
- product announcement;
- product launch;
- first documented sale;
- first trial;
- first independent validation;
- regulatory submission;
- authorization;
- first documented deployment;
- adoption milestone;
- acquisition;
- discontinuation/withdrawal.

Events are evidence-bound and temporally explicit.

**Output:** event ontology and longitudinal event register.

### D3 — Transition metrics

Where evidence supports them, estimate distributions such as:

```text
T_{patent -> product}
```

```text
T_{product -> independent evidence}
```

```text
T_{product -> regulatory}
```

```text
T_{product -> deployment}
```

```text
T_{funding -> product}
```

Analyze transition distributions by product class, capability, jurisdiction, and regulatory context only where source coverage is comparable.

**Output:** technology-to-market and product-to-evidence transition studies.

### D4 — Integrated industrial analyses

Candidate analyses include:

- patent intensity versus validated product output;
- financing versus product emergence;
- financing versus evidence maturity;
- commercial presence versus evidence maturity;
- research capacity versus product activity;
- product density versus regulatory pathway;
- multilingual discovery sensitivity versus apparent geographic concentration;
- concentration of critical upstream components;
- product-class differences in commercialization lag;
- product-class differences in independent-evidence lag.

Unless a separate causal design exists, these analyses are descriptive or associational.

### D5 — Multi-layer geography

Represent geography as separate layers:

1. corporate headquarters;
2. R&D;
3. manufacturing;
4. clinical sites;
5. regulatory markets;
6. product deployments;
7. financing;
8. research/public infrastructure;
9. critical supply-chain dependencies.

Do not collapse these into one country ranking.

**Output:** multi-layer geographic and science-diplomacy map.

### D6 — Strategic dependency mapping

Model upstream and enabling dependencies such as:

```text
Product
 -> electrodes / sensors
 -> specialized components
 -> semiconductors
 -> fabrication / manufacturing
 -> AI / cloud / software platforms
 -> clinical infrastructure
 -> research infrastructure
 -> standards / interoperability dependencies
```

Potential outputs include:

- highly concentrated upstream components;
- single/limited-source dependencies;
- jurisdictional dependencies;
- critical clinical/research networks;
- platform dependencies;
- standards/interoperability bottlenecks.

A dependency edge requires source evidence; plausible supply-chain narratives remain hypotheses until supported.

**Output:** Strategic Dependency Register and dependency maps.

### D7 — Governance integration

Apply the mechanism-based chain:

```text
Observed capability
+
Deployment context
->
Mechanism
->
Governance concern
->
Relevant policy instrument
```

Release D adds empirical denominators to the governance layer.

Preferred policy outputs distinguish:

- products possessing a capability;
- products plausibly usable in a context;
- products explicitly marketed for a context;
- products with documented deployment in that context;
- products with independent performance evidence in that context.

This prevents hypothetical applicability from being relabelled as actual deployment prevalence.

**Output:** Capability × Context × Mechanism × Concern crosswalk with empirical denominators.

### D release package

Release D produces:

- Integrated Industrial Graph;
- longitudinal event register;
- transition-metric studies;
- industrial-structure analyses;
- multi-layer geography;
- strategic dependency maps;
- evidence/commercialization/capital cross-analysis;
- governance crosswalk with observed denominators;
- integrated analytical workbook;
- reproducible public report products generated from an authorized state.

### D gate — `D-G`

Release D passes only when:

- upstream A/B/C versions are explicitly pinned;
- graph relationships preserve evidence tiers and uncertainty;
- source-specific coverage differences remain visible;
- longitudinal event semantics are validated;
- no heterogeneous metric is converted into an unsupported aggregate leadership ranking;
- descriptive/associational findings are distinguished from causal claims;
- integrated public products can be regenerated from the exact authorized evidence state.

## 10. Cross-cutting workstreams

These workstreams persist across P0 and Releases A–D.

### W1 — Measurement science

Responsible for:

- estimands;
- denominators;
- preregistration;
- benchmark design;
- population estimation;
- uncertainty;
- sensitivity analysis;
- comparability rules;
- statistical validity.

### W2 — Discovery and acquisition

Responsible for:

- source-universe programmes;
- capability-first discovery;
- multilingual search;
- source-frame manifests;
- capture provenance;
- marginal-yield accounting;
- termination semantics.

### W3 — Identity, provenance, and evidence linkage

Responsible for:

- exact product identity;
- organization/product lineage;
- version/jurisdiction resolution;
- source/observation linkage;
- evidence tiers;
- patent–company–product concordance;
- unresolved-state preservation.

### W4 — Quantitative analysis

Responsible for:

- population estimation;
- commercial estimation;
- concentration measures;
- meta-analysis / evidence synthesis;
- longitudinal transition metrics;
- association analyses;
- reproducible figure/table data.

### W5 — Human and expert review

Responsible for:

- benchmark labeling;
- ambiguous product boundaries;
- identity conflicts;
- evidence adjudication;
- comparability decisions;
- difficult claim–evidence mappings;
- governance crosswalk review.

### W6 — Publication and release

Responsible for:

- analytical workbooks;
- public evidence projections;
- release manifests;
- rights-safe publication products;
- source/coverage/uncertainty tables;
- canonical S2 candidate compilation;
- explicit authorization and publication records.

## 11. Tracking convention

This plan has a stable path and stable section identifiers so implementation work can bind to it without duplicating the strategy in every issue.

### 11.1 Stable work-package IDs

Use the identifiers in this document directly:

```text
P0.1 ... P0.5
P0-G
A1 ... A8
A-G
B1 ... B6
B-G
C1 ... C8
C-G
D1 ... D7
D-G
W1 ... W6
```

### 11.2 Issue titles

Prefer:

```text
[A3] Implement capability-first product discovery study
[B2] Freeze submarket denominator contract
[C6] Build product comparability graph
[D3] Implement longitudinal transition metrics
```

### 11.3 Pull-request binding

Every implementation PR associated with this programme should state:

```text
Plan binding: A3
Tracking issue: #...
Claim boundary affected: ...
Evidence/authority semantics changed: yes/no
Schema/migration changed: yes/no
```

### 11.4 Status tracking

Do not encode rapidly changing execution status into this strategic plan unless the plan itself changes.

Use:

- GitHub issues for active work and acceptance criteria;
- pull requests for implementation review;
- benchmark and evaluation records for research-state evidence;
- immutable execution-state records for gate dispositions where applicable;
- canonical release/authorization records for publication state.

This prevents a durable strategy document from becoming a stale operational dashboard.

### 11.5 Plan changes

Material changes to objectives, estimands, gates, release semantics, or claim boundaries require a dedicated issue and PR.

Git history preserves prior plan states. A plan update must explain:

- what changed;
- why it changed;
- which work-package IDs are affected;
- whether existing outputs require reinterpretation or migration;
- whether evidence, authority, schema, security, or publication semantics change.

Do not silently repurpose an existing work-package ID for a materially different research objective.

## 12. Release-level definition of done

| Release | Definition of done |
| --- | --- |
| P0 | Exact product identity, product inclusion reference standard, discovery frames, and primary estimands are frozen and reviewable |
| A | Observed product population, coverage process, multilingual/capability sensitivity, saturation, and residual-population estimation are reproducible and bounded |
| B | Each quantitative commercial result has an explicit submarket, denominator, evidence chain, estimation method, and uncertainty |
| C | Product-linked evidence is traceable; evidence maturity is explicit; comparative synthesis occurs only in valid comparability groups |
| D | Patents, products, organizations, markets, evidence, geography, capital, dependencies, and governance are connected longitudinally without losing upstream claim boundaries |

## 13. Immediate execution order

The programme's immediate critical path is:

```text
P0.1 Product Measurement Contract
  ->
P0.2 D4 execution and freeze
  ->
P0.3 Exact-product ontology / registry
  ->
P0.4 Discovery-frame contract
  ->
P0.5 Analysis preregistration
  ->
P0-G
  ->
A1/A2 seed + multi-frame discovery
  ->
A3/A4 capability-first + multilingual studies
  ->
A5/A6 snowball + saturation
  ->
A7 population estimation
  ->
A8 / A-G Product Population Observatory release
```

After the relevant Release-A identities and classifications stabilize, Releases B and C may proceed in parallel:

```text
A
|\
| +--> B Commercial Measurement
|
+----> C Evidence & Effectiveness
        \
         +--> D Integrated Industrial Observatory
B -------/
```

Release D remains downstream of the evidence objects it integrates.

## 14. Programme success condition

The programme reaches its intended state when a third party can begin from any major product count, submarket estimate, market-share statement, effectiveness comparison, industrial concentration result, geographic pattern, or governance conclusion and reconstruct:

1. the exact measurement object;
2. the source universe and observation period;
3. identity resolution;
4. discovery method;
5. denominator;
6. automated transformations;
7. human dispositions;
8. uncertainty;
9. evidence linkage;
10. valid-time state;
11. release/authorization state;
12. the stronger inferences that remain unsupported.

The deeper programme objective is to make **what is not known** measurable alongside what is known:

- Release A estimates discovery incompleteness.
- Release B exposes missing or modeled commercial denominators.
- Release C measures gaps between claims and independent evidence.
- Release D identifies weakly observed transitions, dependencies, and industrial relationships.

The Observatory thereby becomes not only a landscape of NeuroAI activity, but a measurement system for the quality, coverage, and uncertainty of knowledge about that landscape.
