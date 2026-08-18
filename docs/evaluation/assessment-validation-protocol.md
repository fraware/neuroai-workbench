# Assessment validation protocol contract

## Status and purpose

This document defines the pre-outcome contract for the external validation programme tracked in #190 and #191. It specifies the empirical object, freeze boundary, assessor design, agreement estimands, adjudication boundary, decision-usefulness comparison, accessibility study, linguistic study, precision design, and reproducibility requirements.

The protocol is an engineering and study-design artifact. It contains no empirical outcomes and establishes no claim that the instrument is reliable, valid, accessible, useful, clinically effective, conformant, authorized, or publication-ready.

The study remains pre-outcome until #193 freezes the genuine case battery and every outcome-sensitive parameter through the content-addressed record layer defined in #196. #197 selects the real cases, and #198 performs the design-stage precision analysis used to choose counts.

## Object under study

The validation target is the v4.2 assessment object model, not a single aggregate score. The model contains 78 normative requirement findings plus typed claims, evidence and access states, gaps, provenance relationships, and decision objects. Its decision model separates claim adjudication, legal or regulatory authorization, conformance, prohibited-use decisions, and reopening decisions.

The primary empirical units are:

- case × requirement applicability state;
- case × requirement finding state;
- case × claim status where claims are in scope;
- case × evidence/access state;
- case × gap or reopening action;
- case × typed decision object;
- case × traceability relation where assessors select from a common frozen evidence universe;
- assessor × case workflow outcome for decision-usefulness analyses;
- participant × critical task for accessibility analyses;
- participant × decision-critical term or task for linguistic analyses.

`NOT ASSESSED`, uncertain applicability, unavailable evidence, and private-evidence requirements are observed structural states. They stay separate from substantive success and failure.

## Study architecture

The programme uses distinct study arms because reliability, usefulness, accessibility, and linguistic validity answer different empirical questions.

### Training and dry-run arm

Training cases establish familiarity with the object model, controlled vocabularies, evidence boundaries, and workbench mechanics. Instructions may change during this arm. Training-case records are excluded from confirmatory estimates.

A study assessor receives no case-specific feedback about a frozen outcome case until the independent first-pass record for that case is fixed.

### Reliability arm

Multiple assessors independently evaluate the same frozen case and evidence package. Each first-pass assessment is fixed prior to adjudication. The reliability arm estimates where the instrument yields the same substantive interpretation and where disagreement occurs.

### Decision-usefulness arm

A controlled comparison tests whether workflow structure changes a prespecified decision-relevant outcome under the same underlying normative content and frozen evidence universe. #193 freezes the exact comparator and assignment design.

### Accessibility arm

Representative users perform decision-relevant workbench tasks using interaction modes and assistive technologies relevant to the target population. Automated accessibility tests remain engineering regression evidence and form a separate evidence class.

### Linguistic arm

A locale-specific arm is activated for each non-English locale proposed for publication. It tests whether decision-critical terminology and task instructions preserve intended meaning in context.

## Frozen study records

The freeze uses a one-way content-addressed graph:

```text
v4.2 resources + software identity
              |
              v
 VALIDATION_CASE_MANIFEST
              |
              | canonical case-manifest digest
              v
 VALIDATION_STUDY_PARAMETER_SET
              |
              | canonical parameter-set digest
              v
 future outcome datasets, analyses, amendments, and result manifests
```

A `VALIDATION_CASE_MANIFEST` binds at least:

- study-wave identifier;
- case identifier and case-class identifier;
- held-out or calibration-derived status;
- assessment-object-model version;
- controlled-vocabulary digest;
- normative-requirement-set digest;
- assessment-schema digest;
- software commit identity used in the study;
- evidence-manifest reference and digest;
- ordered evidence-object identifiers, bounded references, and SHA-256 digests;
- public/protected evidence boundary;
- case-instruction reference and digest;
- permitted evidence-access rules;
- canonical case-manifest digest.

The top-level `VALIDATION_STUDY_PARAMETER_SET` binds the exact case-manifest identifiers and digests plus all study-wide design and analysis parameters. Case manifests do not embed the final parameter-set digest. This direction avoids a circular content hash. Every future outcome-bearing dataset, analysis, amendment, and result manifest cites the exact parameter-set identifier and digest.

Safe public manifests may expose bounded references and digests. Participant, clinical, site, licensed, credential, and private evidence bytes remain outside public Git.

A case whose governed inputs change after first assessment is a new study object. Later evidence may support a separate reassessment wave with a distinct digest lineage.

## Case selection

The case battery must contain materially different NeuroAI contexts. Material difference is defined through decision-relevant variation in deployment state, evidence structure, system configuration, participant or affected-community context, and likely decision consequences.

At least two materially different context classes are required. #193 freezes the final strata, case counts, inclusion criteria, exclusion criteria, and sampling rationale after the pre-outcome precision analysis.

A battery composed solely of examples used to tune the instrument is inadmissible as a confirmatory held-out battery. Any calibration-derived case retained in the study is declared and analyzed separately from held-out cases.

## Assessor design

Each frozen reliability case is assessed independently by at least three assessors unless the preregistered precision analysis in #198 justifies a different allocation and #193 records that justification.

The assessor specification freezes:

- eligibility and domain-experience criteria;
- training requirements;
- conflicts of interest and prior involvement with each case;
- prior familiarity with the instrument;
- evidence-access permissions;
- rules for requesting additional evidence;
- timing and interruption rules where time is measured;
- treatment of abstention, uncertainty, and unresolved evidence needs;
- independent first-pass status;
- adjudication only after first-pass freeze.

Independent assessment ends when the assessor submits the frozen first-pass record. Agreement is never negotiated during this phase.

## Adjudication boundary

Adjudication follows independent record freeze and creates a derived record. Source assessments remain immutable.

An adjudicated outcome may serve as a diagnostic reference for error analysis. The term ground truth is reserved for an independently observed target explicitly represented in the study design.

The adjudication record preserves links to every source assessment and classifies the resolution mechanism where possible, including:

- different evidence interpretation;
- different applicability interpretation;
- missed evidence;
- ambiguous instrument language;
- conflicting source evidence;
- insufficient evidence;
- data-entry or workflow error;
- legitimate unresolved expert disagreement.

For the decision-usefulness arm, outcome adjudicators are blinded to workflow assignment whenever artifact presentation permits it.

## Reliability analysis

Reliability is estimated by field family. A project-wide agreement number is insufficient as a primary result.

### Primary estimand table

| Field family | Primary population | Primary estimate | Required companion analyses | Robustness estimate |
| --- | --- | --- | --- | --- |
| Requirement applicability | All assigned requirement judgments | Exact agreement + nominal Krippendorff alpha | state frequencies, confusion matrix, case-stratified estimates | Gwet AC1 |
| Requirement finding state | Requirements jointly treated as substantively assessed | Ordinal Krippendorff alpha over `FAIL`, `PARTIAL`, `PASS` | exact agreement, weighted disagreement, confusion matrix, consequential-disagreement rate | Gwet AC2 with prespecified weights |
| Assessment coverage | All assigned requirements | state-specific agreement and disagreement rate | reason distribution, evidence-access cross-tabulation | nominal agreement sensitivity analysis |
| Claim status | In-scope claims independently reviewed | Nominal Krippendorff alpha | exact agreement and full confusion matrix | Gwet AC1 |
| Evidence access/state | In-scope evidence judgments | Nominal Krippendorff alpha | exact agreement and state-specific disagreement | Gwet AC1 |
| Gap state / reopening action | Cases where a gap or reopening action is available | Nominal Krippendorff alpha | exact action agreement and consequential-disagreement rate | Gwet AC1 |
| Typed decision state | Decisions stratified by `decision_object_type` | Nominal Krippendorff alpha within type | exact agreement, confusion matrix, consequential-disagreement rate | Gwet AC1 |
| Evidence selection | Common frozen evidence universe | Pairwise/multi-rater set overlap summarized by case | Jaccard distribution and omitted-critical-evidence analysis | sensitivity to adjudicated critical-evidence subset |
| Claim-to-evidence links | Common frozen claim/evidence universe | Edge-set overlap summarized by case | descriptive decomposition against adjudicated reference where available | Jaccard edge overlap |

#193 freezes each distance function, AC2 weight set, structural-state rule, clustering method, and uncertainty procedure. `PASS`, `PARTIAL`, and `FAIL` may be modeled ordinally. `NOT ASSESSED` remains outside that ordinal scale and is analyzed through assessment coverage.

Decision states are stratified by `decision_object_type`. States belonging to different decision types never share an agreement scale solely because they occupy the same storage field.

### Dependence structure

Requirement judgments are nested within cases, and assessors may contribute repeated judgments across cases. Requirement-level observations therefore cannot be treated as independent replicates for confirmatory uncertainty estimation.

Every primary reliability family freezes `CASE` and `ASSESSOR` as clustering units. #198 uses the same dependence structure in design-stage precision analysis. The chosen resampling or model-based interval procedure must preserve the dependence structure represented by the frozen study design.

### Two-stage requirement reliability

An assessor who records `NOT ASSESSED` and an assessor who records `FAIL` have made different classes of judgment. The primary sequence is:

1. estimate agreement about applicability and whether substantive assessment was possible;
2. conditional on joint substantive assessment, estimate agreement over `PASS`, `PARTIAL`, and `FAIL`;
3. report how often stage-one disagreement prevents stage-two comparison.

## Consequential disagreement

Chance-corrected coefficients can remain high when high-stakes disagreements are sparse. Consequential disagreement is therefore reported directly with prespecified eligible denominators.

The minimum taxonomy contains:

- requirement `PASS` versus `FAIL`;
- claim `SUPPORTED WITHIN BOUNDED SCOPE` versus `UNSUPPORTED`;
- claim `SUPPORTED WITHIN BOUNDED SCOPE` versus `CONTRADICTED`;
- `AUTHORIZED WITHIN BOUNDED SCOPE` versus `NOT AUTHORIZED` within `LEGAL OR REGULATORY AUTHORIZATION`;
- `CONFORMS FOR BOUNDED SCOPE` versus `NO CONFORMANCE DECISION — BLOCKED` within `CONFORMANCE DECISION`;
- presence versus absence of `PROHIBITED OR DISPROPORTIONATE USE` among cases whose frozen design requires `PROHIBITED-USE DECISION` evaluation;
- presence versus absence of `REOPENED` among cases containing a frozen reopening-trigger condition;
- evidence-availability disagreement that changes whether a consequential conclusion can be supported.

The v4.2 controlled vocabulary contains no generic positive permissive state for `PROHIBITED-USE DECISION` and no generic negative reopening state. The study therefore uses presence/absence analysis in explicitly eligible denominators instead of inventing states outside the controlled vocabulary.

Each consequential rule freezes its numerator interpretation, eligible denominator, case/assessor dependence structure, and interval method. Reports preserve numerator, denominator, case distribution, and uncertainty where the denominator supports estimation.

## Assessor uncertainty and calibration

If confidence is collected, it is recorded separately from evidence state. The confidence scale, calibration target, binning or continuous calibration method, and overconfidence definition are frozen prior to outcome inspection.

Adjudicated consensus may serve as a diagnostic calibration target. An independently observed target is preferred where one genuinely exists. Confidence is interpreted probabilistically only when the elicitation and calibration procedure supports that interpretation.

## Decision-usefulness design

The usefulness study asks whether workflow structure changes decision quality or traceability. Satisfaction is never the sole primary usefulness outcome.

The comparator uses the same frozen case evidence and normative instrument content. #193 freezes the exact workflow difference, comparator identity and digest, assignment scheme, primary outcome, critical-defect taxonomy, and adjudication rule.

The preferred allocation is counterbalanced:

- each case appears in both workflows across different assessors;
- one assessor sees a given frozen case in one workflow only;
- assessor and case assignment follows the frozen balancing or randomization rule;
- training precedes outcome tasks and is excluded from analysis;
- case order and period/learning controls are prespecified;
- outcome adjudicators are blinded to workflow where feasible.

Candidate primary outcomes must have an explicit decision consequence, such as a prespecified critical assessment-defect rate, omission of action-critical evidence or gaps, or an incorrect consequential next action. Time-on-task, interaction burden, workload, and satisfaction are secondary unless burden is the declared study question.

A critical assessment defect is defined before outcome collection. Examples include unsupported decision wording, omitted blocking evidence, a missed contradictory source, an unresolved dependency represented as resolved, or a next action inconsistent with the frozen evidence state.

## Accessibility arm

Accessibility validation uses representative users and the interaction modes they depend on. #193 freezes representative-user strata, assistive-technology combinations, critical tasks, critical-failure definitions, assistance rules, and primary outcomes.

Critical tasks cover decision-relevant surfaces as applicable:

- locating and opening evidence;
- understanding evidence/access state;
- navigating requirement findings;
- entering or reviewing a finding and rationale;
- identifying unresolved gaps;
- reviewing typed decision objects;
- recognizing disagreement or reopening state;
- generating or inspecting a human-readable output.

Primary accessibility outcomes are task success and critical task failure. A critical failure prevents task completion, causes loss or material misinterpretation of decision-relevant information, or requires assistance outside the defined independent workflow.

Completion time is secondary and requires an appropriate within-population comparator for interpretation.

## Linguistic-validation arm

A linguistic arm is required for every non-English locale proposed for publication. Software string coverage alone is engineering evidence and does not establish linguistic validity.

The study tests:

- technical terminology;
- evidence-access and uncertainty language;
- applicability and finding states;
- decision-critical action labels;
- prohibition, authorization, conformance, and reopening language where present;
- comprehension of bounded-scope and boundary statements.

Subject-matter terminology review and task-based comprehension are required. Back-translation is optional as a diagnostic method.

#193 freezes the set of non-English publication locales. An empty set creates no non-English locale publication-readiness claim. Every listed locale requires exactly one frozen locale-parameter record.

## Precision and sample-size plan

The first validation wave is primarily an estimation study. #198 chooses candidate case and assessor allocations through a pre-outcome precision analysis whose planning inputs remain distinct from observed study outcomes.

Before outcome collection, the frozen parameter set identifies:

- primary reliability coefficient or coefficients driving precision planning;
- planning ranges and their source or rationale;
- target interval width or decision-relevant precision criterion;
- case and assessor clustering structure;
- simulation or analytic procedure;
- analysis-code reference and digest;
- environment reference and digest;
- random seeds;
- final case count per context stratum;
- final assessor allocation;
- sensitivity to plausible consequential-disagreement prevalence.

The final parameter set must contain the same case count per stratum as the exact referenced case-manifest set.

Recruitment and stopping rules are frozen before outcomes. `outcome_adaptive_stopping` and `interim_outcome_access` are false in the pre-outcome parameter set. Under-recruitment or interruption is handled through the prespecified rule and, when applicable, a protocol-deviation record.

## Missingness, exclusions, and protocol deviations

Structural assessment states remain observed data. `NOT ASSESSED`, uncertain applicability, and evidence-unavailable states are not recoded as missingness.

True missingness includes an assigned assessment that was not submitted, an interrupted task without an outcome, corrupt study data, or a measurement omitted for reasons outside represented instrument states.

Primary analyses do not silently impute substantive finding states. Missingness is reported by case, assessor, arm, and reason. Sensitivity analysis is required where missingness can change interpretation.

Exclusion rules are frozen in #193. A post-outcome exclusion creates a protocol-deviation record and, when it can affect a primary conclusion, included/excluded sensitivity results.

## Multiplicity and exploratory analyses

Primary estimands are identified by field family and study arm. The programme emphasizes estimates and uncertainty intervals.

If the decision-usefulness arm contains more than one confirmatory primary contrast, #193 freezes the multiplicity procedure. Secondary and exploratory analyses remain labeled and retain their original status after outcome inspection.

## Context heterogeneity

Results remain available by materially different case class. A pooled coefficient is accompanied by context-specific estimates and a heterogeneity analysis where context changes evidence availability or decision consequences.

A high pooled estimate cannot erase a low-reliability context containing consequential decisions.

## Data governance and reproducibility

The study separates safe reproducibility metadata from protected study content.

Safe public artifacts may include:

- protocol and amendments;
- study-parameter-set manifest and digest;
- safe case-manifest metadata and digests;
- synthetic study examples;
- analysis-code and environment identity;
- precision-simulation code and seeds;
- aggregate results and safe disagreement summaries;
- dataset and result-manifest digests.

Protected artifacts may include participant identities, assessor identities where disclosure is inappropriate, clinical or site records, licensed evidence, private source material, credentials, and records constrained by consent or data-access terms.

Every reported analysis cites the exact study-parameter-set digest and exact analyzed dataset/result manifest. Reproduction of safe calculations should not require disclosure of protected bytes when digest-bound aggregate or synthetic alternatives are sufficient.

## Amendments and deviations

A parameter change after freeze is an append-only amendment. The amendment records:

- predecessor parameter-set identifier and digest;
- successor parameter-set identifier and digest;
- timestamp;
- rationale;
- changed fields;
- affected cases, outcomes, and analyses;
- outcome-data-access state at the time of the change;
- impact on primary, secondary, exploratory, or no analysis class.

Predecessor and successor records remain independently addressable. An amendment never rewrites historical study records.

A protocol deviation records what occurred under the frozen plan. It does not retrospectively redefine the plan.

## Interpretation rules

Conclusions are bounded by the sampled contexts, assessors, users, comparators, evidence universes, and reference standards.

Appropriately bounded conclusions may state that:

- a named finding-state family showed a reported level of inter-rater agreement in the sampled contexts;
- a specific workflow changed a prespecified critical-defect outcome under the frozen comparison;
- representative users using specified assistive technologies completed named critical tasks at observed rates;
- a named locale preserved decision-critical terminology under the specified linguistic procedure.

The study alone establishes no general validity across unstudied NeuroAI contexts, clinical safety or effectiveness, regulatory or legal authorization, formal conformance, institutional delegation, external endorsement, or repository release decision.

## Pre-outcome execution gate

Outcome collection may start only after #193 has a valid canonical parameter-set identifier and digest whose referenced case manifests also validate. At that point the frozen record set contains no unresolved ambiguity about:

- case strata, inclusion/exclusion rules, and exact evidence universes;
- held-out versus calibration-derived status;
- assessor eligibility, allocation, training, conflicts, prior familiarity, and evidence access;
- primary estimands, distance/weight functions, and structural-state handling;
- case/assessor clustering and uncertainty method;
- precision target, design procedure, analysis implementation, environment, and seeds;
- consequential-disagreement rules, denominators, and intervals;
- decision-state compatibility matrix;
- decision-usefulness comparator, assignment, counterbalancing, primary outcome, and defect taxonomy;
- accessibility user strata, technology matrix, critical tasks, and failure criteria;
- locale-specific parameters for every non-English publication locale;
- missingness, exclusion, multiplicity, blinding, and outcome-access rules;
- recruitment target and stopping rules;
- amendment policy and public/protected boundary.

Completion of the protocol or validator implementation alone does not satisfy this gate.