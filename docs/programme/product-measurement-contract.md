# Product Measurement Contract v1.0

**Plan binding:** `P0.1` in [Product Population → Industrial Observatory deployment plan](product-population-industrial-observatory-deployment-plan.md)  
**Tracking issue:** #316  
**Parent gate:** #315 / `P0-G`  
**Status:** CANDIDATE FOR FREEZE — adversarial-review corrections incorporated; human freeze disposition pending. This is a substantive measurement contract, not a schema, benchmark result, population estimate, market estimate, effectiveness result, or publication authorization

## 1. Purpose

This contract defines the object that the Product Population Observatory will count and characterize.

Its purpose is to prevent product discovery, benchmarking, counting, market analysis, evidence synthesis, and longitudinal integration from silently using different meanings of “product”.

The contract governs:

- the distinction between organization, product family, product, exact configuration, service, component, and technical system;
- the identity boundary for global and jurisdiction-specific counting;
- lifecycle, commercial, deployment, and regulatory state semantics;
- treatment of versions, aliases, rebrands, OEM/private-label products, bundles, apps, subscriptions, and research/investigational systems;
- the interface between D4 scope labels and downstream count eligibility;
- temporal semantics;
- aggregation and denominator rules;
- evidence requirements for product existence and product-state claims;
- prohibited inferences.

Machine-readable schemas, validators, migrations, and registry implementation belong to `P0.3`. This document freezes the measurement semantics those implementations must preserve.

### 1.1 Exact governing research-contract binding

This contract is a downstream enumeration contract under the already approved D1 research boundary. It does not redefine NeuroAI scope.

The exact controlling identities are:

```text
D1 artifact:
  LANDSCAPE_RESEARCH_CONTRACT_v0.1
D1 canonical JSON SHA-256:
  7d270002094dcdecb703d5b70ef2268e4869005c284ffd98db3eb936641a78cb

G1 disposition:
  HUMAN_G1_DISPOSITION_2026-09-05_D1_D2_v0.1
G1 canonical JSON SHA-256:
  ed6489fe1085b5aec1b594970dd1c574b57bd6bbd25a659643e9bd1b7b72d8ef
```

P0.1 refines how in-scope product/service objects are represented, deduplicated, temporally projected, and counted. It cannot broaden or narrow the approved D1 research boundary by itself.

A future substantive change to D1 requires its own governed successor and human disposition. P0.1 must then receive an explicit compatibility review before using the successor boundary.


## 2. Governing rule

> Exact identity and explicit state precede aggregation.

No product-level count or comparison is valid until the programme can answer:

1. **What object is this?**
2. **At what identity level is it represented?**
3. **Is it in scope under D4?**
4. **What was its state at the specified world-time and knowledge-time cutoff?**
5. **What source/observation supports that identity and state?**
6. **Does the requested denominator count product identities, exact configurations, product families, services, components, deployments, users, units, revenue, procedures, or something else?**

Evidence strength sets the maximum claim.

## 3. Separation of object classes

The programme must not collapse the following into one identifier:

```text
ORGANIZATION
PRODUCT FAMILY
MARKET-FACING PRODUCT / SERVICE
EXACT TECHNICAL CONFIGURATION
COMPONENT
SOFTWARE / SERVICE LAYER
RESEARCH OR INVESTIGATIONAL SYSTEM
DEPLOYMENT INSTANCE
REGULATORY RECORD
STUDY / TRIAL
```

The existing Observatory v2 ontology remains the architectural base: organizations, systems, products, studies, trials, sources, observations, assertions, relationships, and events remain distinct object families.

### 3.1 Organization

An organization is a legal, institutional, or otherwise controlled actor identity.

An organization is never itself a product count.

One organization may:

- develop zero products;
- develop one product;
- develop multiple product families;
- sell products developed by another organization;
- acquire a product without changing the product's identity;
- discontinue one product while remaining an active organization.

### 3.2 Product family

A **product family** is a source-supported grouping of related market-facing or programme-facing products that share a stable lineage or family identity.

Examples of family-level grouping include:

- successive hardware generations sold under one family name;
- a named platform with several exact configurations;
- a regulated device family with multiple jurisdiction-specific configurations.

A family is an aggregation object, not the default Release-A exact-product counting unit.

A family identity does not establish that every family member has the same:

- capability;
- hardware;
- software/model;
- intended use;
- regulatory state;
- evidence maturity;
- commercial state;
- deployment state.

### 3.3 Market-facing product

A **market-facing product** is an identifiable named offering represented to an external user, customer, researcher, clinician, institution, or trial programme as a coherent product object.

The offering may be:

- hardware;
- software;
- a hardware–software bundle;
- a device–software–service stack;
- a research platform;
- a regulated medical product;
- a formally named investigational product/offering;
- a separately offered service.

The existence of a market-facing product does not establish purchase availability, deployment, effectiveness, authorization, adoption, or revenue.

### 3.4 Exact technical configuration

An **exact technical configuration** is the narrowest configuration level required to preserve materially different capability, intended use, intervention, or regulatory/evidence meaning.

An exact configuration may bind, where relevant:

- hardware generation;
- sensor/electrode architecture;
- form factor;
- firmware;
- software release;
- model/decoder version;
- stimulation/control algorithm;
- accessories required for the claimed capability;
- intended use or indication;
- jurisdiction-specific configuration.

The exact configuration is the preferred unit for evidence linkage and comparative-effectiveness work where evidence is configuration-specific.

### 3.5 Service

A **service** is independently countable only if all of the following are true:

1. it is externally identifiable as an offering;
2. it is supplied to an external user/customer/institution/researcher;
3. it performs or materially enables an in-scope NeuroAI capability;
4. its identity can be distinguished from the parent hardware/product with attributable evidence.

A service that merely describes internal company operations is not independently countable.

Under the v1.0 Observatory ontology, an independently countable service is represented as a canonical `PRODUCT` offering with an explicit service/offering-kind role. This contract does not silently invent a new `SERVICE` entity type. A later ontology successor may introduce a dedicated service entity only through reviewed schema evolution and an explicit compatibility/migration decision.

### 3.6 Component

A **component** is a separately identifiable product or device that forms part of a larger system.

A component may be independently represented where it has one or more of:

- independent commercial identity;
- independent regulatory identity;
- independent procurement identity;
- independent technical evidence material to the research question.

Component status must remain explicit.

A component must not be silently treated as equivalent to the full system in which it may be used.

### 3.7 Research or investigational system

A research or investigational `SYSTEM` is not automatically a `PRODUCT`.

It enters the product/service population only when evidence supports a stable external product/service offering identity in addition to a stable technical-system identity. Relevant evidence may include a formally named investigational product, a trial/regulatory product identity, an externally offered research platform, or another source-backed programme/product identity that satisfies D4.

At minimum, a product-countable investigational offering requires:

- a stable named external product/service or formal investigational-product identity;
- attributable developer/operator identity;
- a repeatable or formally specified configuration;
- an external research, trial, regulatory, commercial, or programme record supporting that offering identity.

A stable research system that lacks an external product/service offering identity remains a `SYSTEM`. It may be represented in the wider technology/system landscape but stays outside product/service population counts.

A one-off laboratory apparatus described only as an experimental setup remains outside the product denominator unless a later attributable record establishes a qualifying product/service identity.

### 3.8 Enumeration role

Every product/service identity eligible for Release-A counting must carry exactly one `primary_enumeration_role` so heterogeneous offerings are not silently combined or double counted in role composition.

The v1.0 semantic roles are:

```text
INTEGRATED_SYSTEM
COMPONENT_OR_SUBSYSTEM
STANDALONE_SOFTWARE_OR_SERVICE
OTHER_REVIEW_REQUIRED
```

Interpretation:

- `INTEGRATED_SYSTEM` — a complete externally identifiable offering containing the required in-scope capability at the level presented to a user, researcher, clinician, institution, or trial programme.
- `COMPONENT_OR_SUBSYSTEM` — a separately identifiable component, module, sensor, electrode array, SDK-bound subsystem, or other part of a broader system.
- `STANDALONE_SOFTWARE_OR_SERVICE` — independently offered software, API, analytics, or service operating on externally supplied or linked signals without constituting the complete hardware/system offering.
- `OTHER_REVIEW_REQUIRED` — an offering whose primary enumeration role cannot be assigned without review.

The primary role is assigned from the level at which the offering itself is externally presented, contracted, procured, or supplied. Downstream reuse of an integrated product as a component of another system does not automatically change its primary enumeration role. Secondary technical relationships and deployment contexts are represented separately.

Enumeration role is distinct from deployment context, form factor, lifecycle state, and commercial state.

A broad count containing more than one enumeration role must be labelled as a count of **offering identities** and must report the role composition. It must not be presented as the number of complete end-user systems or the number of distinct technologies.

## 4. Product-population inclusion boundary

### 4.1 Scope classification, reference-standard membership, identity, and state are separate

The approved D1 boundary answers:

> Does this candidate belong in the study's product/service scope?

The D4 Product Reference Standard supplies held-out human-adjudicated cases used to evaluate whether a model, rule system, or review procedure applies that boundary correctly. D4 membership is not required for every operational product candidate.

Operational Release-A candidates receive governed boundary dispositions under the same approved D1 four-way semantics and evidence rules. The operational disposition process must be versioned and validated against D4 as applicable.

Identity resolution separately answers:

> Which exact product/service object does this candidate refer to?

Lifecycle evidence separately answers:

> What state was that object in at the relevant time?

These must remain separate decisions.

### 4.2 Approved four-way boundary dispositions

The controlled D4 disposition set is:

```text
INCLUDE
EXCLUDE
BORDERLINE
ABSTAIN
```

Interpretation:

- **INCLUDE** — evidence supports inclusion under the exact approved D1 product research boundary.
- **EXCLUDE** — evidence supports exclusion under that boundary.
- **BORDERLINE** — attributable evidence places the candidate on a genuine governed boundary and an expert-reviewed final disposition records that boundary with rationale.
- **ABSTAIN** — available evidence is insufficient for a responsible scope classification.

D4 classification does not establish exact identity, availability, effectiveness, deployment, or authorization.

### 4.3 Eligibility for primary Release-A counts

A candidate is eligible for a primary product-population count only when:

```text
governed operational boundary disposition = INCLUDE
under the approved D1 semantics
AND
the operational disposition procedure/reference-standard version is recorded
AND
identity state = RESOLVED at the counting level
AND
applicable temporal state is representable
AND
required source/observation provenance exists
```

A candidate does not need to be a member of the held-out D4 benchmark. D4 evaluates the boundary process; it is not the population registry.

`BORDERLINE`, `ABSTAIN`, and unresolved-identity records remain visible in uncertainty/coverage reporting but stay outside the primary count.

`EXCLUDE` records remain available for benchmark/evaluation provenance but stay outside the product population.

### 4.4 D1 evidence rules at the D4/count interface

A governed operational boundary disposition used for Release-A counting must preserve the approved D1 evidence rules and the approved four-way semantics validated by D4:

- attributable evidence is required;
- proxy-only evidence cannot establish `INCLUDE`;
- NeuroAI boundary membership requires the approved expert-review process;
- insufficient evidence routes to `ABSTAIN`;
- `BORDERLINE` requires recorded rationale;
- open-world unknowns remain explicit;
- gray-third/capability-first discovery is retrieval-only and is not a canonical population class.

Identity resolution alone never authorizes `INCLUDE`.

A single company representation may support the bounded claim that an offering was represented by that company. It does not, by itself, satisfy the governed operational inclusion decision where D1 requires multi-signal attributable evidence plus expert review.

### 4.5 Operational boundary-disposition record

Every operational boundary disposition used for Release-A eligibility must preserve, at minimum:

```text
decision
rationale
adjudicator_role
timestamp
exact_object_binding
boundary_contract_id
disposition_protocol_id
reference_standard_id
reference_standard_version
```

The operational record is distinct from D4 held-out membership.

A model prediction, classifier score, retrieval rank, or automated rule may support routing or review, but cannot substitute for the governed disposition record where D1 requires expert review.



## 5. Identity levels and counting unit

The programme uses at least three non-interchangeable identity levels.

### 5.1 Family identity

```text
FAMILY
```

Used for:

- lineage;
- family portfolio summaries;
- grouping related configurations.

Not the default exact-product denominator.

### 5.2 Commercial / programme product identity

```text
PRODUCT
```

Represents one externally identifiable named product/service or formal investigational product object.

This is the default Release-A global product/service identity level.

### 5.3 Exact configuration identity

```text
CONFIGURATION
```

Represents a materially distinct technical or intended-use configuration associated with one or more product identities. A configuration is usually product-specific, but evidence-supported OEM/private-label equivalence may link more than one commercial offering to the same or substantially equivalent technical implementation without merging their commercial product identities.

Used for:

- product-state assertions that differ by configuration;
- regulatory mapping;
- study/effectiveness evidence;
- materially distinct capability analysis.

### 5.4 Jurisdiction is normally state, not identity

The same product sold or studied in multiple jurisdictions remains one global product identity unless jurisdiction changes the underlying product/configuration materially.

Jurisdiction-specific:

- authorization;
- labeling;
- availability;
- reimbursement;
- deployment;
- intended use;

are assertions about the product/configuration.

They do not automatically create new global product identities.

### 5.5 Global count versus jurisdictional count

For a global unique-product view:

```text
N_global = number of unique canonical product identities
```

A product present in five jurisdictions counts once globally.

For a jurisdictional availability view:

```text
N_j = number of unique product identities with a qualifying state in jurisdiction j
```

The same product may count once in each applicable jurisdiction.

Jurisdictional counts must not be summed and relabelled as the global unique-product count.

## 6. Material-change rule for versions and configurations

A new exact configuration identity is required where evidence supports a change that materially alters one or more of:

- neural/neurophysiological sensing modality;
- electrode/sensor architecture relevant to capability;
- stimulation/intervention mechanism;
- decoder/model capability relevant to the research question;
- output/control pathway;
- form factor where it changes capability or deployment context materially;
- intended use or clinical indication;
- product-level regulatory identity;
- required hardware–software composition;
- performance/effectiveness evidence applicability;
- safety profile or use constraints in a way that makes prior evidence non-transferable.

A new exact configuration is **not** required solely for:

- cosmetic changes;
- packaging changes;
- routine bug fixes with no material capability/evidence effect;
- documentation changes;
- ordinary manufacturing-lot changes;
- price changes;
- distributor changes;
- ownership changes.

Where materiality is unresolved, preserve the predecessor identity and create an unresolved configuration-split proposal. Do not silently split or merge.

## 7. Names, aliases, rebrands, OEMs, and ownership changes

### 7.1 Alias or renamed product

A naming change does not create a new product identity when evidence supports continuity of the same underlying product.

Represent:

```text
canonical_label
aliases[]
former_labels[]
source_specific_labels[]
```

where supported.

### 7.2 Rebrand

A rebrand remains the same product identity only when evidence supports substantive continuity.

If a rebrand introduces materially different configuration, use a successor or distinct configuration identity.

### 7.3 OEM / private-label product

An OEM/private-label offering may have:

- a distinct **commercial product identity**, while
- sharing a substantially equivalent **technical configuration** with another product.

Do not collapse commercial identity and technical equivalence.

Where separately branded and externally offered, retain separate product identities linked by an evidence-supported OEM/technical-equivalence relationship.

For technical-performance or comparative-effectiveness analysis, avoid treating technical duplicates as independent interventions merely because their commercial labels differ.

Technical equivalence must itself be evidence-supported. Unresolved suspected equivalence does not authorize a merge or cluster assignment.

### 7.4 Acquisition or corporate transfer

Acquisition, licensing, or transfer of a product does not by itself create a new product identity.

Represent organizational ownership/development transitions separately.

If the product itself changes materially, apply the material-change rule.

## 8. Hardware–software–service bundles

### 8.1 Integrated bundle

A device–software–service bundle is one product identity when the bundle is externally represented, procured, or used as one coherent offering and its constituent layers are not independently offered in a way material to the study.

### 8.2 Separately offered software or subscription

A software or subscription layer may be a separate service identity when:

- it is separately named;
- it is separately offered, licensed, contracted, or subscribed;
- it provides material in-scope capability not reducible to a trivial companion interface;
- independent evidence can support its identity.

The parent product must retain a relationship to the service.

### 8.3 Companion app

A companion app is not automatically a separate service.

Treat it as part of the product where it primarily:

- configures the device;
- displays device outputs;
- handles account/session management;
- provides routine firmware/software interface functionality.

It becomes separately countable only if it meets the service criteria in §3.5.

### 8.4 API or developer platform

An externally offered API/platform may be independently countable if it exposes an in-scope capability to external developers or institutions under a stable offering identity.

Internal APIs are not separate product objects.

## 9. Product-state model

No single field called `commercialized`, `active`, or `approved` is sufficient.

At minimum, the programme must represent distinct state axes for:

1. **existence / representation state**;
2. **development / lifecycle state**;
3. **access / commercial state**;
4. **regulatory state**;
5. **deployment state**;
6. **evidence state**.

P0.3 may choose exact controlled values. It must preserve the separations below.

### 9.1 Existence / representation state

Answers:

> What evidence establishes that this named object is represented as existing?

Possible evidence classes include:

- official current representation;
- authoritative regulatory/trial record;
- scientific/research record;
- company representation only;
- unresolved.

Existence evidence does not establish effectiveness or availability.

### 9.2 Development / lifecycle state

Must distinguish, where evidence supports:

- announced;
- in development;
- manufacturing / pre-delivery;
- released;
- cancelled;
- discontinued;
- withdrawn;
- superseded;
- unresolved.

A null end date does not mean “currently active”.

### 9.3 Access / commercial state

Must distinguish forms of external access such as:

- not externally offered;
- preorder / reservation;
- directly commercially sold;
- research-use sold/licensed;
- prescription / clinical commercial access;
- trial/investigational access;
- institutional service access;
- discontinued/unavailable;
- unresolved.

These states may vary by jurisdiction.

### 9.4 Regulatory state

Regulatory state is jurisdiction- and configuration-specific.

Keep distinct:

- no controlling record established;
- investigational authorization/permission where applicable;
- filing/submission;
- designation;
- clearance;
- approval/authorization;
- conformity marking;
- withdrawal/recall;
- other jurisdiction-specific states.

Registration/listing presence is not equivalent to authorization.

A cleared/authorized component does not automatically confer that state on a broader investigational system.

### 9.5 Deployment state

Deployment requires evidence of actual use in a specified context.

Distinguish:

- intended/marketed use;
- trial use;
- research deployment;
- documented clinical deployment;
- documented consumer/user access;
- documented workplace/institutional deployment;
- unresolved.

Potential applicability to a context is not deployment.

### 9.6 Evidence state

Evidence state describes the basis of a claim.

It must preserve distinctions among:

- company representation;
- regulatory/administrative record;
- trial record;
- scientific publication;
- independent study;
- procurement/deployment record;
- modeled/derived estimate;
- unresolved.

Source class and review state remain separate from the substantive claim itself.

## 10. Temporal semantics

The product registry uses the existing two-axis temporal model.

### 10.1 World time

World-time fields represent when a state applies:

```text
valid_from
valid_until
```

Unknown boundaries remain unknown.

### 10.2 Knowledge time

Knowledge-time fields represent programme handling:

```text
observed_at
adjudicated_at
published_at
release_id
```

A source publication date remains separate.

### 10.3 Current-product projection

“Current” is derived.

A current product/configuration projection must consider:

- valid-time information;
- lifecycle assertions;
- supersession;
- discontinuation/withdrawal evidence;
- unresolved conflicts;
- jurisdiction;
- evidence cutoff;
- canonical publication state.

Do not select the latest timestamp and assume currentness.

### 10.4 World change versus correction

A real product transition creates successor state.

An Observatory correction preserves the erroneous predecessor representation in history and adds correction provenance.

Do not rewrite historical releases to make prior errors disappear.

### 10.5 Count cutoffs

Every Release-A count or population estimate must bind two cutoffs:

```text
world_time_cutoff
knowledge_time_cutoff
```

The world-time cutoff specifies the date/period for which the product state is being represented.

The knowledge-time cutoff specifies the latest Observatory evidence/observation state allowed into that analysis.

A count described as “current as of date T” is incomplete unless its knowledge-time cutoff is also declared. Later-discovered historical evidence may change a retrospective world-time projection without changing the original knowledge-time-as-of result.


## 11. Primary Release-A population views

The programme must never publish an unlabeled “global product count”.

Every count names:

- population view;
- identity level;
- enumeration role(s);
- jurisdiction scope;
- world-time cutoff;
- knowledge-time cutoff.

### 11.1 `A-P1 CURRENT_IDENTIFIABLE_OFFERING_INVENTORY`

Count canonical `PRODUCT` offering identities that:

- have a governed operational `INCLUDE` disposition under the approved D1 boundary;
- have resolved product/service offering identity;
- have a declared enumeration role;
- are not evidenced as discontinued, cancelled, withdrawn, or superseded out of the applicable current offering view;
- have sufficient provenance for their current representation/state at the declared cutoffs.

This broad inventory **does include** current officially represented announced, in-development, manufacturing/pre-delivery, commercially accessible, research-use, and investigational offerings when their product/service identity is supported.

It excludes research `SYSTEM` objects that lack a qualifying product/service offering identity.

A-P1 is an **offering inventory**, not a market denominator, installed-base denominator, end-user-system denominator, or distinct-technology denominator. It must be reported with enumeration-role composition.

### 11.2 `A-P2 CURRENT_COMMERCIALLY_ACCESSIBLE`

Subset of A-P1 with evidence supporting current commercial or paid external access under the declared jurisdiction/access rules.

Announcement-only, internal-only, and investigational-only offerings are excluded unless the applicable access evidence also establishes qualifying commercial access.

### 11.3 `A-P3 CURRENT_RESEARCH_OR_INVESTIGATIONAL_ACCESS`

Subset of A-P1 whose evidenced external access is research-use, trial, or investigational.

A-P3 and A-P2 are allowed to overlap. A research platform sold or licensed commercially to laboratories may legitimately satisfy both views. These views answer different questions and must not be summed as disjoint categories unless an explicit mutually exclusive projection is defined.

### 11.4 `A-P4 CURRENT_INTEGRATED_END_USER_SYSTEMS`

Subset of A-P1 with enumeration role `INTEGRATED_SYSTEM`.

Use this view where the research or public-facing question concerns complete user/researcher/clinician-facing systems rather than components, subsystems, or standalone service layers.

### 11.5 `A-P5 HISTORICAL_CUMULATIVE_OFFERINGS`

All resolved in-scope `PRODUCT` offering identities observed in the declared historical window, including discontinued, cancelled, withdrawn, and superseded offerings.

This view is not a current-market denominator.

### 11.6 `A-P6 CURRENT_RELEASED_OR_EXTERNALLY_ACCESSIBLE`

Subset of A-P1 that excludes announcement-only and pre-delivery-only offerings.

An offering qualifies when evidence supports at least one of:

- commercial external access;
- research-use external access;
- trial/investigational access;
- documented external deployment/access under the applicable state rules.

A-P6 is the preferred view when the question is how many identifiable offerings have progressed beyond announcement/development representation.

### 11.7 `A-P7 CURRENT_DEPLOYED_LEGACY`

Count in-scope product identities that are no longer in the current offering inventory because they are discontinued or superseded, but for which current deployment/use is independently documented at the declared cutoffs.

This view keeps product commercial lifecycle separate from installed/deployed presence.

A historical statement that a product was once deployed is insufficient for A-P7.

### 11.8 `A-P8 CURRENT_DISTINCT_TECHNICAL_IMPLEMENTATIONS`

Analytical view over current exact `CONFIGURATION` identities associated with qualifying current offerings.

A single commercial offering may contribute more than one technical implementation when materially distinct current configurations are supported.

Evidence-supported equivalent configurations may be grouped into a technical-equivalence cluster.

Rules:

- commercial product identities are never merged merely to produce this view;
- configuration identities remain recoverable;
- equivalence requires attributable technical evidence;
- unresolved suspected equivalence remains separate;
- the equivalence method and relation strength must be declared;
- A-P8 is not interchangeable with A-P1 or A-P4.

This view is especially relevant to OEM/private-label offerings, technically identical rebrands, and one product label spanning multiple material configurations.

A-P8 is descriptive by default. It may be used as the unit of an unseen-population estimate only when the technical-equivalence procedure is preregistered and frozen before capture-history construction, applied deterministically to the declared estimation universe, and included in the population-model identity. Post hoc clustering based on observed source overlaps is prohibited for population estimation.

### 11.9 Family and configuration views

Family-level and exact-configuration counts may also be reported.

They must be labeled explicitly:

```text
FAMILY COUNT
OFFERING / PRODUCT COUNT
CONFIGURATION COUNT
TECHNICAL-EQUIVALENCE VIEW
```

and must not be substituted for one another.

## 12. Counting rules

### 12.1 Primary count rule

For a declared population view `V`:

```text
N_V = sum over unique canonical identities i of I(i qualifies for V)
```

where each `i` is a unique canonical identity at the declared counting level.

For A-P8 only, the analytical counting unit is an evidence-defined technical-equivalence cluster under the declared equivalence method. Constituent commercial identities remain preserved and recoverable; A-P8 does not mutate canonical identity.

### 12.2 Duplicate candidates

Multiple observations, source pages, distributor listings, trial records, or regulatory records for the same canonical product do not create additional product counts.

### 12.3 Multiple organizations

A product developed, manufactured, distributed, licensed, or sold by several organizations remains one product identity unless distinct market-facing products exist.

### 12.4 Multiple jurisdictions

A global unique-product count deduplicates across jurisdictions.

Jurisdiction-specific views may count the same product once in each jurisdiction where the qualifying state is supported.

### 12.5 Multi-label analytical categories

Capability, deployment context, form factor, and evidence categories may be multi-label.

Therefore:

```text
sum over category counts N_c may exceed the unique-product denominator
```

because one product may belong to more than one analytical category.

Reports must state whether categories are:

- mutually exclusive;
- hierarchical;
- multi-label.

### 12.6 Components and bundles

A component and an integrated system may both exist as product identities.

A report must choose the appropriate population view and must not sum component-only and full-system counts without stating that both are intentionally included.

### 12.7 Borderline and unresolved records

`BORDERLINE`, `ABSTAIN`, unresolved identity, and unresolved current-state records do not enter the primary numerator.

They are reported as separate uncertainty/coverage quantities.

### 12.8 Population-estimation compatibility contract

Every unseen-population model must bind exactly one declared estimation universe:

```text
boundary_contract_id
boundary_disposition_protocol_id
reference_standard_id
reference_standard_version
reference_standard_validation_state
identity_level
population_view
enumeration_roles
jurisdiction_scope
world_time_cutoff
knowledge_time_cutoff
discovery_frame_universe
```

Capture histories must be constructed at that same unit.

Do not mix:

- family and product identities;
- product and configuration identities;
- current and historical views;
- announcement-inclusive and externally-accessible views;
- component-inclusive and integrated-system-only views;

inside one population estimate unless the model explicitly represents those strata and the estimand is preregistered accordingly.

Estimates from different population views are separate estimands. They cannot be pooled or compared as if they shared one denominator without a declared transformation or joint model.

### 12.9 Minimum count-reporting metadata

Every published Release-A count must state, in machine-readable or table-adjacent form:

```text
boundary_contract_id
boundary_disposition_protocol_id
reference_standard_id
reference_standard_version
reference_standard_validation_state
population_view_id
identity_level
included_enumeration_roles
jurisdiction_scope
world_time_cutoff
knowledge_time_cutoff
observed_or_estimated
discovery_protocol_or_model_id
uncertainty_state
```

A number without this metadata is not a governed Release-A population claim.

### 12.10 Observed versus estimated population semantics

For a declared estimation universe:

```text
N_observed
```

is the number of directly observed canonical identities that satisfy the governed observed-item eligibility rules.

```text
N_estimated
```

is a model-based estimate of the total population under the declared construct, source-frame universe, cutoff pair, identity level, population view, and model assumptions.

The residual:

```text
N_unseen = N_estimated - N_observed
```

represents latent estimated population mass. It is not a list of individually identified products, does not imply item-level human adjudication for unseen members, and cannot be exposed as though those products had been directly discovered.

Any reported `N_estimated` must therefore distinguish:

- directly observed validated identities;
- estimated unseen residual;
- uncertainty interval;
- model family and diagnostics;
- sensitivity to source dependence and stratification.



## 13. Category-composition versus market-share rule

For category `c`, a Release-A product-composition statistic may be:

```text
Composition_c =
  products in declared Release-A view satisfying category c
  -----------------------------------------------------------
  products in the declared Release-A view
```

This is **product composition**, not economic market share.

Do not call it:

- revenue share;
- unit share;
- user share;
- adoption share;
- installed-base share;
- procedure share.

Those denominators belong to Release B.

## 14. Evidence requirements

### 14.1 Product existence

A candidate product identity may be represented when attributable evidence supports a named external product/service or formal investigational/research offering. This is an entity-existence statement only.

Entry into a governed Release-A product population additionally requires the D4 boundary-membership evidence and expert-review conditions in §4.4.

A first-party source may support:

> Organization X represents product Y as an offering/system.

It does not independently support:

> Product Y is effective, widely deployed, regulator-authorized, or market-leading.

### 14.2 Availability

Availability claims require explicit evidence of the applicable access state.

A generic product page without current ordering/access information does not automatically establish current commercial availability.

### 14.3 Regulatory state

Use the exact controlling regulatory record where making a regulatory claim.

Company statements about regulatory status remain company statements unless independently bound to the controlling record.

### 14.4 Deployment

Deployment claims require evidence of actual deployment/use.

Marketing to a sector or technical suitability for a sector is insufficient.

### 14.5 Effectiveness

Product existence, marketing claims, technical-performance demonstrations, regulatory authorization, and adoption do not independently establish comparative effectiveness.

Effectiveness evidence belongs to Release C.

## 15. Edge-case decision table

| Case | Product identity treatment | Count treatment |
| --- | --- | --- |
| Same product, two official names in two countries, no material configuration difference | One product with aliases/jurisdictional assertions | Once globally; once in each qualifying jurisdictional view |
| Same family, materially different hardware generations | One family, multiple products/configurations | Count at declared level |
| Routine firmware bug fix | Same configuration unless material capability/evidence effect is established | No new product count |
| Software/model update materially changes in-scope capability | New configuration; new product only if market-facing identity also changes materially | Configuration count changes; product count depends on product identity |
| Cleared component inside broader investigational system | Separate component and system identities | Included only in views whose object class admits each; no authorization inheritance |
| Companion app used only to control/display device | Part of product bundle | No separate service count |
| Separately subscribed analytics service with material in-scope function | Separate service linked to parent product | Countable service in applicable views |
| One-off paper prototype with no stable external product/programme identity | Research system, not product | Excluded from product denominator |
| Named investigational system used in a formal trial with stable configuration | PRODUCT only if a stable external product/formal investigational-product identity is evidenced; otherwise SYSTEM | Product counts only if PRODUCT identity + D4 + count eligibility are satisfied |
| Announced product with official page but no delivery | Product identity may exist; lifecycle/access state = announced or pre-delivery | Included in A-P1 if current representation is supported; excluded from A-P2 and A-P6 unless later access evidence qualifies it |
| Product discontinued but still historically important | Preserve product identity and historical assertions | Excluded from A-P1; included in A-P5; if current deployment is independently evidenced, also eligible for A-P7 |
| Acquisition changes developer/owner | Same product unless material product change | No new count solely from acquisition |
| Private-label/OEM copy sold under separate brand | Separate commercial offering identity; technical-equivalence relation only if supported | Separate in A-P1; may collapse only in the explicitly declared A-P8 technical-implementation view |
| Distributor lists same product under multiple pages | One product | Deduplicate |
| Same product sold with optional accessories | Same product unless accessory combination materially changes capability and is offered as distinct configuration | Usually no new product count; configuration rule applies |
| Research headset sold with different software plans | One hardware product plus separate service only where plan meets service criteria | Avoid counting every pricing tier as a product |

## 16. Prohibited inferences

The following transitions are not allowed without separate evidence:

```text
organization exists
  != product exists

product exists
  != product is commercially available

commercially available
  != deployed

deployed
  != widely adopted

company claim
  != independent effectiveness

regulatory registration/listing
  != authorization

component authorization
  != system authorization

patent ownership
  != product implementation

product count
  != market share

product-category composition
  != revenue/adoption share

same family
  != same exact configuration

same technology
  != same product identity

same commercial label
  != identical technical configuration

commercial rebrand
  != independent technical intervention

broad offering-inventory count
  != complete end-user-system count

distinct commercial labels
  != distinct technical implementations

announcement
  != external access

discontinued from offering
  != absent from current deployment

high discovery yield
  != global completeness
```

## 17. Interface to downstream releases

### 17.1 Release A

Uses this contract for:

- exact product/service identity;
- population-view definitions;
- D4 count eligibility;
- deduplication;
- multilingual and capability-first discovery;
- saturation analysis;
- unseen-population estimation under one fixed identity/population/cutoff/frame universe per estimand.

### 17.2 Release B

Release B must define economically coherent submarkets independently of this product identity contract.

Product identity is necessary but not sufficient for:

- revenue denominator;
- unit denominator;
- user denominator;
- installed-base denominator;
- procedure denominator.

### 17.3 Release C

Release C should bind evidence to the narrowest configuration for which evidence applies.

Commercial aliases/OEM products that share a technical configuration must not automatically be treated as independent interventions.

### 17.4 Release D

Release D may connect family, product, configuration, organization, patent, market, evidence, geography, and governance objects, but must preserve each identity level and claim boundary.

## 18. Interface to P0.3 implementation

P0.3 must translate this contract into machine-readable semantics without weakening it.

At minimum, P0.3 must make it possible to represent:

- family identity;
- product identity;
- exact configuration identity;
- v1.0 service representation as a PRODUCT offering with explicit offering kind;
- exactly one `primary_enumeration_role` from `INTEGRATED_SYSTEM / COMPONENT_OR_SUBSYSTEM / STANDALONE_SOFTWARE_OR_SERVICE / OTHER_REVIEW_REQUIRED`;
- aliases and lineage;
- jurisdiction-scoped state;
- lifecycle/access/regulatory/deployment state separation;
- valid time and knowledge time;
- governed operational boundary disposition under the approved D1 semantics;
- operational boundary-disposition protocol identity and exact D4/reference-standard identity/version used;
- identity resolution state;
- source/observation provenance;
- population-view eligibility;
- declared world-time and knowledge-time cutoffs for count projections;
- evidence-supported technical-equivalence relationships without silent identity merges.

P0.3 must include validation tests for the edge cases in §15.

## 19. Freeze criteria

This contract reaches `FROZEN_v1.0` only after review confirms:

1. compatibility with the Observatory v2 ontology;
2. compatibility with the entity identity model;
3. compatibility with the temporal model;
4. compatibility with the evidence/decision boundary;
5. compatibility with data-governance constraints;
6. D4 can apply its scope labels without conflating identity/state;
7. P0.3 can implement the contract without inventing additional identity semantics;
8. the Release-A counting views are unambiguous;
9. the edge-case table has no unresolved contradiction with the counting rules;
10. the exact D1/G1 bindings are correct;
11. service representation is compatible with the current ontology;
12. investigational SYSTEM objects cannot silently enter PRODUCT counts;
13. A-P1 announcement semantics and A-P7 legacy-deployment semantics are unambiguous;
14. population-estimation units and cutoffs are locked by contract;
15. operational boundary dispositions preserve attributable minimum fields;
16. observed identities and the estimated unseen residual cannot be conflated;
17. A-P8 operates at exact-configuration/equivalence-cluster level.

Freeze status does not mean the D4 benchmark has been executed, the registry exists, or Release A has a denominator.

## 20. Change control

After freeze, a material change to any of the following requires a dedicated issue/PR and impact analysis:

- product identity level;
- product/configuration split rule;
- D4 count eligibility;
- current-product projection;
- component/bundle counting;
- service-counting rule;
- OEM/rebrand treatment;
- global-versus-jurisdictional deduplication;
- primary population-view definitions.

A change must state whether previously reported counts require recomputation or reinterpretation.

If D4 has already been frozen, a material change affecting the D1-to-count interface, count eligibility, identity level, enumeration role, or primary population-view semantics triggers a D4 compatibility review. Where the prior D4 dispositions are no longer directly valid under the successor contract, a successor D4 review/re-freeze is required before the new contract is used for governed Release-A counting.

Git history preserves predecessor contract states. Do not silently redefine “product” while reusing the same measurement version.

## 21. Current disposition

This document is a **P0.1 candidate contract with adversarial-review corrections incorporated**. Issue #320 records the pre-freeze review and its predecessor `REVISE_BEFORE_FREEZE` disposition.

It establishes no product count and makes no claim that the existing Observatory contains a complete or statistically estimated product population.

The next programme action after contract review is to freeze P0.1 and execute P0.2 D4 human calibration/adjudication against these semantics before population-scale Release-A interpretation.
