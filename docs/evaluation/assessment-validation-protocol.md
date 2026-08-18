# Assessment validation protocol contract

## Status and purpose

This document defines the pre-outcome contract for the external validation programme tracked in #190 and #191. It specifies what is being evaluated, which records are frozen before analysis, how assessor disagreement is measured, how adjudication is separated from independent assessment, and how accessibility, linguistic validity, and decision usefulness are studied without conflating those questions.

The protocol is an engineering and study-design artifact. It contains no empirical outcomes and does not establish that the instrument is reliable, valid, accessible, useful, clinically effective, conformant, authorized, or publication-ready.

The study-parameter set described here remains incomplete until #193 freezes the actual case battery, assessor counts, precision targets, comparator assignment, critical-task definitions, and any locale-specific parameters. Those values must be committed before outcome collection.

## Object under study

The validation target is the v4.2 assessment object model, not a single aggregate score. The model contains 78 normative requirement findings plus typed claims, evidence and access states, gaps, provenance relationships, and decision objects. Its design explicitly separates claim adjudication, legal or regulatory authorization, conformance, prohibited-use decisions, and reopening decisions.

The primary empirical units are therefore:

- case × requirement applicability state;
- case × requirement finding state;
- case × claim status where claims are in scope;
- case × evidence/access state;
- case × gap or reopening action;
- case × typed decision object;
- case × traceability relation where assessors select from a common frozen evidence universe;
- assessor × case workflow outcomes for decision-usefulness analyses;
- participant × critical task for accessibility analyses;
- participant × decision-critical term or task for linguistic analyses.

`NOT ASSESSED`, uncertain applicability, unavailable evidence, and private-evidence requirements are substantive states. They are not numerical middle points and must not be recoded as success or failure.

## Study architecture

The programme uses separate study arms because reliability, usefulness, accessibility, and linguistic validity answer different questions.

### Training and dry-run arm

Training cases establish familiarity with the object model, controlled vocabularies, evidence boundaries, and workbench mechanics. They may be used to improve instructions before the study parameter set is frozen. Training-case records are excluded from confirmatory empirical estimates.

No study assessor receives case-specific feedback about a frozen outcome case before completing that case independently.

### Reliability arm

Multiple assessors independently evaluate the same frozen case and evidence package. Each first-pass assessment is frozen before adjudication. The reliability arm measures where the instrument yields the same substantive interpretation and where it does not.

### Decision-usefulness arm

A controlled comparison tests whether the workbench workflow changes a prespecified decision-relevant outcome relative to a comparator that uses the same underlying instrument content and frozen evidence. The comparator must be specified in #193 so that the study does not accidentally compare different evidence or different normative content.

### Accessibility arm

Representative users perform critical workbench tasks using the interaction modes and assistive technologies relevant to the target population. Automated accessibility tests remain useful regression evidence but are not substitutes for this arm.

### Linguistic arm

A locale-specific arm is required only for a non-English locale proposed for publication. It tests whether decision-critical terminology and task instructions preserve intended meaning in context.

## Frozen study object

Every outcome-bearing case must be frozen before the first independent assessment of that case. A case manifest must bind at least:

- study wave identifier;
- case identifier and case-class identifier;
- assessment-object-model version;
- controlled-vocabulary version or digests;
- normative-requirement-set digest;
- software commit or release identity used in the study;
- evidence-manifest digest;
- ordered evidence-object identifiers and SHA-256 digests where the objects may be disclosed;
- protected evidence references and their digests where bytes cannot be public;
- public/private evidence boundary;
- case instructions and their digest;
- permitted evidence-access rules;
- study-parameter-set identifier and digest from #193.

The public repository may contain safe manifests and digests. Protected participant, clinical, site, licensed, credential, or private evidence bytes remain outside public Git.

A case whose governed inputs change after first assessment is a new study object. Later evidence may support a separate reassessment wave; it must not silently replace the original case.

## Case selection

The case battery must contain materially different NeuroAI contexts. Diversity is defined by decision-relevant differences in deployment state, evidence structure, system configuration, participant or affected-community context, and likely decision consequences; superficial variation in product names is insufficient.

At least two materially different context classes are required. The final strata, case counts, inclusion criteria, exclusion criteria, and sampling rationale are frozen in #193 after a precision analysis and before outcome collection.

Case selection must avoid a battery composed only of examples already used to tune the instrument. Any calibration-derived case that remains in the study must be declared and analyzed separately from genuinely held-out cases.

## Assessor design

Each frozen reliability case is assessed independently by at least three assessors unless the preregistered precision analysis in #193 justifies a different design.

The assessor specification must freeze:

- eligibility and domain-experience criteria;
- training requirements;
- conflicts of interest and prior involvement with each case;
- prior familiarity with the instrument;
- evidence-access permissions;
- whether an assessor is allowed to request additional evidence;
- timing and interruption rules if time is an outcome;
- the treatment of abstention, uncertainty, and unresolved evidence needs.

Independent assessment ends when the assessor submits the frozen first-pass record. Assessors do not negotiate agreement during that phase.

## Adjudication boundary

Adjudication follows independent record freeze. It creates a new derived record and never rewrites the independent assessments.

An adjudicated outcome may be used as a diagnostic reference for error analysis. It is not called ground truth unless an independent external ground-truth source exists and is explicitly represented by the study design.

The adjudication record must preserve links to every source assessment and classify the reason for resolution where possible, such as:

- different evidence interpretation;
- different applicability interpretation;
- missed evidence;
- ambiguous instrument language;
- conflicting source evidence;
- insufficient evidence;
- data-entry or workflow error;
- legitimate unresolved expert disagreement.

For the decision-usefulness arm, outcome adjudicators should be blinded to workflow assignment whenever the artifacts can be presented without revealing the arm.

## Reliability analysis

Reliability is estimated by field family. A single project-wide agreement number is not a sufficient primary result.

### Primary estimand table

| Field family | Primary population | Primary estimate | Required companion analyses | Robustness estimate |
| --- | --- | --- | --- | --- |
| Requirement applicability | All assigned requirement judgments | Exact agreement + nominal Krippendorff alpha | state frequencies, confusion matrix, case-stratified estimates | Gwet AC1 |
| Requirement finding state | Requirements jointly treated as substantively assessed | Ordinal Krippendorff alpha over `FAIL`, `PARTIAL`, `PASS` | exact agreement, weighted disagreement, confusion matrix, consequential-disagreement rate | Gwet AC2 with prespecified weights |
| `NOT ASSESSED` / unresolved coverage | All assigned requirements | state-specific agreement and disagreement rate | reason distribution, evidence-access cross-tabulation | nominal agreement sensitivity analysis |
| Claim status | In-scope claims independently reviewed | Nominal Krippendorff alpha | exact agreement and full confusion matrix | Gwet AC1 |
| Evidence access/state | In-scope evidence judgments | Nominal Krippendorff alpha | exact agreement and state-specific disagreement | Gwet AC1 |
| Gap state / reopening action | Cases where a gap or reopening action is available | Nominal Krippendorff alpha | exact action agreement and consequential-disagreement rate | Gwet AC1 |
| Typed decision state | Decisions stratified by `decision_object_type` | Nominal Krippendorff alpha within type | exact agreement, confusion matrix, consequential-disagreement rate | Gwet AC1 |
| Evidence selection | Common frozen evidence universe | Pairwise/multi-rater set overlap summarized by case | Jaccard distribution and omitted-critical-evidence analysis | sensitivity to adjudicated critical-evidence subset |
| Claim-to-evidence links | Common frozen claim/evidence universe | Edge-set overlap summarized by case | precision/recall-like descriptive decomposition against adjudicated reference when available | Jaccard edge overlap |

The exact Krippendorff distance functions and AC2 weights must be frozen in #193. `PASS`, `PARTIAL`, and `FAIL` may be modeled ordinally. `NOT ASSESSED` is excluded from that ordinal scale and analyzed through the separate assessment-coverage estimand.

Decision states must be stratified by decision-object type. For example, a claim-adjudication state and a conformance state do not share one ordinal scale merely because both are stored in the decision register.

### Why two-stage requirement reliability is mandatory

An assessor who marks a requirement `NOT ASSESSED` and an assessor who records `FAIL` have made materially different judgments. Combining those states into one ordinal coefficient would confuse evidence sufficiency with substantive nonconformance.

The primary sequence is therefore:

1. estimate agreement about applicability and whether substantive assessment was possible;
2. conditional on joint substantive assessment, estimate agreement about `PASS` / `PARTIAL` / `FAIL`;
3. report how often disagreement in stage 1 prevents stage-2 comparison.

## Consequential disagreement

Aggregate agreement can look strong when high-stakes disagreements are sparse. The study therefore reports a prespecified consequential-disagreement outcome independently of the chance-corrected coefficients.

The taxonomy includes at minimum:

- requirement `PASS` versus `FAIL`;
- `SUPPORTED WITHIN BOUNDED SCOPE` versus `UNSUPPORTED` or `CONTRADICTED` for the same claim;
- `AUTHORIZED WITHIN BOUNDED SCOPE` versus `NOT AUTHORIZED` when a legal or regulatory decision is genuinely within study scope;
- `CONFORMS FOR BOUNDED SCOPE` versus `NO CONFORMANCE DECISION — BLOCKED` when conformance is in scope;
- a prohibited-use decision versus a permissive outcome within the same decision type;
- `REOPENED` versus no reopening where that difference changes the next action;
- a disagreement about evidence availability that changes whether the assessment can support a consequential conclusion.

For each class, report numerator, denominator, case distribution, and uncertainty interval where the denominator supports meaningful estimation. Case-level narratives should explain mechanisms without exposing protected evidence.

## Assessor uncertainty and calibration

If confidence is collected, it must be recorded separately from evidence state. A confident assessor may still face missing evidence; an uncertain assessor may face complete evidence.

The confidence scale, calibration target, binning or continuous calibration method, and overconfidence definition must be frozen before outcome inspection. Adjudicated consensus may be used as a diagnostic target; an external observed target is preferred where one genuinely exists.

No confidence score is interpreted as a probability unless the elicitation protocol and calibration analysis support that interpretation.

## Decision-usefulness design

The usefulness study asks whether workflow structure changes decision quality or traceability. Satisfaction alone is not a primary usefulness outcome.

The comparator must use the same frozen case evidence and the same normative instrument content. #193 freezes the exact workflow difference under test.

The preferred allocation is a counterbalanced design in which:

- each case is assessed under both workflows across different assessors;
- one assessor sees a given frozen case in only one workflow, preventing direct case-memory carryover;
- assessor and case assignment is balanced or randomized according to the frozen plan;
- training precedes outcome tasks and is excluded from analysis;
- outcome adjudicators are blinded to workflow where feasible.

The primary decision-usefulness outcome is frozen in #193. Candidate primary outcomes must be decision-relevant, such as a prespecified critical assessment-defect rate, omission of action-critical evidence/gaps, or incorrect consequential next action. Time-on-task, interaction burden, perceived workload, and satisfaction are secondary unless the study question is explicitly about burden.

A critical assessment defect must be defined before outcome collection and may include only defects with an explicit decision consequence, such as unsupported decision wording, omitted blocking evidence, a missed contradictory source, an unresolved dependency represented as resolved, or a next action inconsistent with the frozen evidence state.

## Accessibility arm

Accessibility validation uses representative users and the interaction modes they actually depend on. The final user strata and technology matrix are frozen in #193.

Critical tasks should cover the workflow surfaces that carry evidence or decision meaning, including as applicable:

- locating and opening evidence;
- understanding evidence/access state;
- navigating requirement findings;
- entering or reviewing a finding and rationale;
- identifying unresolved gaps;
- reviewing typed decision objects;
- recognizing disagreement or reopening state;
- generating or inspecting a human-readable output.

Primary accessibility outcomes are task success and critical task failure. A critical failure is one that prevents task completion, causes loss or misinterpretation of decision-relevant information, or requires an assistance path outside the defined independent workflow.

Record assistance required and qualitative failure mechanism. Completion time is secondary and should not be interpreted as a deficit across assistive-technology users without an appropriate within-population comparator.

Automated accessibility checks remain regression controls. They do not satisfy this representative-user arm.

## Linguistic-validation arm

A linguistic arm is activated only for a locale proposed for publication. Software string coverage is not evidence of linguistic validity.

The study must test:

- technical terminology;
- evidence-access and uncertainty language;
- applicability and finding states;
- decision-critical action labels;
- prohibition, authorization, conformance, and reopening language where present;
- comprehension of bounded-scope and non-claim statements.

Subject-matter terminology review and task-based comprehension are required. Back-translation is optional and should be used when it helps identify semantic drift, not as a ritual substitute for comprehension testing.

Any unresolved ambiguity that can change evidence interpretation or next action blocks a publication-readiness claim for that locale until resolved and retested.

## Precision and sample-size plan

The first validation wave is primarily an estimation study. Case and assessor counts are determined by the precision needed for the primary reliability estimands and consequential-disagreement rates, not by a convenience target.

Before outcome collection, #193 must freeze:

- the primary reliability coefficient(s) that drive precision planning;
- plausible parameter ranges used for planning, with their source or rationale;
- the desired uncertainty width or decision-relevant precision criterion;
- assumed case and assessor clustering structure;
- the simulation or analytic procedure used to evaluate candidate designs;
- the final case count per context stratum;
- the final assessor allocation;
- sensitivity of expected precision to plausible disagreement prevalence.

Simulation code and seeds should be public where they contain no protected information. Planning inputs must be distinguishable from observed study outcomes.

## Missingness, exclusions, and protocol deviations

Structural assessment states are not missing data. `NOT ASSESSED`, uncertain applicability, and evidence-unavailable states remain observed categorical outcomes.

True missingness includes an assigned assessment that was not submitted, an interrupted task without an outcome, corrupt study data, or a measurement omitted for reasons outside the instrument's represented states.

Primary analyses do not silently impute substantive finding states. The protocol must report missingness by case, assessor, arm, and reason. Sensitivity analysis is used if missingness is large enough to change interpretation.

Exclusion rules are frozen in #193. Post-outcome exclusions require a protocol-deviation record and both included/excluded sensitivity results when the exclusion could affect a primary conclusion.

## Multiplicity and exploratory analyses

Primary estimands are identified by field family and study arm. The programme emphasizes estimates and uncertainty intervals over a large family of null-hypothesis tests.

If the decision-usefulness arm contains more than one confirmatory primary contrast, the multiplicity procedure is frozen in #193. Secondary and exploratory analyses are labeled accordingly and may not be promoted to a primary result after outcome inspection.

## Context heterogeneity

Pooling is secondary to interpretability. Results must remain available by materially different case class. A pooled coefficient is reported only with the corresponding context-specific estimates and a discussion of heterogeneity when context changes evidence availability or decision consequences.

A high pooled reliability estimate does not erase a low-reliability context that contains consequential decisions.

## Data governance and reproducibility

The study distinguishes public reproducibility metadata from protected study content.

Safe public artifacts may include:

- protocol and amendments;
- study-parameter-set manifest and digest;
- synthetic study examples;
- case/evidence digests and bounded metadata where disclosure is permitted;
- analysis code and environment identity;
- simulation code used for precision planning;
- aggregate results and safe disagreement summaries;
- result-manifest digests.

Protected artifacts may include participant identities, assessor identities where disclosure is inappropriate, clinical/site records, licensed evidence, private source material, credentials, and any record whose disclosure would violate the study's consent or data-access terms.

Every reported analysis must cite the exact study-parameter-set digest and the exact analyzed dataset/result manifest. Reproduction of reported calculations should not require disclosure of protected bytes when digest-bound aggregate or synthetic alternatives are sufficient.

## Amendments and deviations

Protocol changes after the parameter set is frozen are append-only amendments. An amendment records:

- predecessor protocol/parameter-set digest;
- timestamp;
- rationale;
- changed fields;
- affected outcomes or cases;
- whether anyone approving the amendment had access to outcome data;
- whether the change alters a primary, secondary, or exploratory analysis.

The original protocol remains accessible. Amendments do not overwrite historical study records.

A protocol deviation records what occurred without pretending the protocol changed retrospectively.

## Interpretation rules

The study may support only claims commensurate with its sampled contexts, assessors, users, comparators, and reference standards.

Examples of appropriately bounded conclusions include:

- a named finding-state family showed a reported level of inter-rater agreement in the sampled contexts;
- a specific workflow reduced a prespecified critical-defect outcome under the study design;
- representative users using specified assistive technologies completed named critical tasks at observed rates;
- a named locale preserved decision-critical terminology under the specified linguistic-validation procedure.

The study does not, by itself, establish general validity across unstudied NeuroAI contexts, clinical safety or effectiveness, regulatory or legal authorization, formal conformance, institutional delegation, external endorsement, or a repository release decision.

## Pre-outcome execution gate

Outcome collection may start only after #193 freezes and digests the study parameter set. At that point the protocol must contain no unresolved ambiguity about:

- case strata and inclusion rules;
- assessor allocation;
- primary estimands and distance/weight functions;
- precision target and sample-size design;
- consequential-disagreement definitions;
- decision-usefulness comparator and primary outcome;
- accessibility critical tasks and failure criteria;
- locale-specific parameters for any linguistic arm;
- missingness/exclusion rules;
- amendment authority and data-access boundary.

Closing this documentation issue alone does not satisfy that gate.