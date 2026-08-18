# Validation study freeze records

## Purpose

The external validation programme uses content-addressed preregistration records so study inputs and analysis choices are fixed before outcome collection and remain independently auditable afterward.

This record layer implements the pre-outcome contract in `assessment-validation-protocol.md`. It provides integrity and lineage controls. It does not create empirical validation evidence, a release decision, clinical or regulatory evidence, institutional authority, or publication readiness.

## Record graph

The canonical binding direction is:

```text
v4.2 normative resources + software identity
                    |
                    v
       VALIDATION_CASE_MANIFEST
          |       |       |
          |       |       +-- exact evidence-object references + digests
          |       +---------- case instructions + digest
          +------------------ case/evidence manifest identity
                    |
                    | canonical case-manifest digest
                    v
     VALIDATION_STUDY_PARAMETER_SET
          |       |       |
          |       |       +-- study-wide analysis/design parameters
          |       +---------- exact ordered case-manifest set
          +------------------ protocol/analysis/environment identities
                    |
                    | canonical parameter-set digest
                    v
     future outcome datasets and analyses
```

Case manifests do not embed the final study-parameter-set digest. The top-level parameter set binds case-manifest digests, and every future outcome-bearing dataset, analysis, amendment, and result manifest cites the exact parameter-set identifier and digest. This one-way graph avoids a circular content hash.

## Case manifest

`VALIDATION_CASE_MANIFEST.schema.json` describes one immutable study case and evidence universe. The record binds:

- study wave, case, and case-class identifiers;
- held-out or calibration-derived status;
- exact v4.2 normative-resource digests and software commit identity;
- case-instruction reference and digest;
- evidence-manifest reference and digest;
- ordered evidence-object identifiers, bounded references, and SHA-256 digests;
- evidence-access rules;
- public/protected evidence boundary;
- canonical manifest digest.

A public evidence object uses a non-empty `public-ref:` token. Protected evidence uses a non-empty `protected-ref:` token plus its digest. Absolute paths and `file://` references are rejected. Protected bytes, credentials, participant identities, assessor identities, site-private material, and licensed content remain outside public Git.

Changing any governed case input changes the canonical case-manifest digest. Once outcome collection has used a case manifest, changed evidence or instructions define a new study object or reassessment wave.

## Study parameter set

`VALIDATION_STUDY_PARAMETER_SET.schema.json` freezes the study-wide design. A fully valid parameter set requires the referenced case-manifest objects to be available to the validator so each object can be rehashed and checked against its declared digest.

The parameter set freezes:

- protocol reference and digest;
- v4.2 normative-resource and software identity;
- analysis-code identity, environment identity, and random seeds;
- materially different case strata, inclusion criteria, and exclusion criteria;
- exact case-manifest references and digests;
- assessor eligibility, training, conflicts, prior familiarity, evidence access, independent first pass, and post-freeze adjudication;
- all nine reliability field families specified by the protocol;
- distance/weight choices, structural-state handling, robustness estimates, case/assessor clustering, and uncertainty methods;
- the preregistered decision-object-type/state compatibility matrix;
- consequential-disagreement rules with explicit eligible denominators and interval methods;
- precision-planning assumptions, simulation identity, case counts, assessor allocation, and disagreement-prevalence sensitivity;
- recruitment and stopping rules;
- decision-usefulness comparator, primary outcome, defect taxonomy, assignment, counterbalancing, learning/period controls, and adjudicator blinding;
- accessibility user strata, assistive-technology matrix, critical tasks, critical-failure definitions, and primary outcomes;
- parameters for every non-English locale proposed for publication;
- missingness, exclusion, multiplicity, blinding, data-access, amendment, and public/protected boundaries;
- canonical study-parameter-set digest.

The validator requires the actual frozen case count in every stratum to match the precision plan. A stratum with zero cases is invalid. Every referenced case must match the parameter set's study wave, normative identity, class, calibration status, and declared digest.

## Statistical integrity controls

Requirement judgments are nested within cases, and assessors may contribute repeated judgments. The preregistration validator therefore requires `CASE` and `ASSESSOR` as clustering units for every confirmatory reliability family. Treating all requirement-level observations as independent does not satisfy the frozen contract.

`REQUIREMENT_FINDING` explicitly keeps `NOT ASSESSED` outside the ordinal finding-state estimand. Assessment coverage remains a separate field family.

The parameter set must contain exactly these field families once each:

- `REQUIREMENT_APPLICABILITY`
- `REQUIREMENT_FINDING`
- `ASSESSMENT_COVERAGE`
- `CLAIM_STATUS`
- `EVIDENCE_ACCESS_STATE`
- `GAP_REOPENING`
- `TYPED_DECISION`
- `EVIDENCE_SELECTION`
- `CLAIM_EVIDENCE_LINKS`

The exact uncertainty implementation remains a frozen study choice. The record must name it, and the precision plan must encode the case/assessor dependence structure used when selecting the design.

## Decision-state compatibility

The study analysis freezes a compatibility matrix over the existing v4.2 controlled vocabulary. This prevents agreement calculations from comparing semantically unrelated states merely because they share one `decision_state` field.

The current analysis matrix is:

| Decision object type | Admissible analysis states |
| --- | --- |
| `CLAIM ADJUDICATION` | `SUPPORTED WITHIN BOUNDED SCOPE`, `PARTIALLY SUPPORTED`, `UNSUPPORTED`, `CONTRADICTED`, `ASSESSMENT INCOMPLETE` |
| `LEGAL OR REGULATORY AUTHORIZATION` | `AUTHORIZED WITHIN BOUNDED SCOPE`, `NOT AUTHORIZED`, `AUTHORIZATION NOT ASSESSED`, `NOT APPLICABLE`, `ASSESSMENT INCOMPLETE` |
| `CONFORMANCE DECISION` | `CONFORMS FOR BOUNDED SCOPE`, `CONDITIONAL CONFORMANCE`, `NO CONFORMANCE DECISION — BLOCKED`, `NOT APPLICABLE`, `ASSESSMENT INCOMPLETE` |
| `PROHIBITED-USE DECISION` | `PROHIBITED OR DISPROPORTIONATE USE`, `NOT APPLICABLE`, `ASSESSMENT INCOMPLETE` |
| `REOPENING DECISION` | `REOPENED`, `NOT APPLICABLE`, `ASSESSMENT INCOMPLETE` |

All matrix entries are checked against `CONTROLLED_VOCABULARIES_v4.2.json`.

The v4.2 vocabulary does not define a generic positive "permissive" state for `PROHIBITED-USE DECISION`, nor a generic "not reopened" state for `REOPENING DECISION`. The preregistration therefore represents these consequential differences as presence/absence analyses over the exact positive state in an explicitly eligible denominator. It does not invent synthetic decision states.

The minimum consequential-disagreement contract includes:

- requirement `PASS` versus `FAIL`;
- claim `SUPPORTED WITHIN BOUNDED SCOPE` versus `UNSUPPORTED`;
- claim `SUPPORTED WITHIN BOUNDED SCOPE` versus `CONTRADICTED`;
- `AUTHORIZED WITHIN BOUNDED SCOPE` versus `NOT AUTHORIZED` within legal/regulatory authorization;
- `CONFORMS FOR BOUNDED SCOPE` versus `NO CONFORMANCE DECISION — BLOCKED` within conformance;
- presence/absence of `PROHIBITED OR DISPROPORTIONATE USE` in cases whose frozen design requires prohibited-use evaluation;
- presence/absence of `REOPENED` in cases containing a frozen reopening-trigger condition.

Each rule carries an explicit denominator and uncertainty-interval method.

## Precision planning and stopping

The parameter set identifies planning assumptions separately from observed outcomes. Simulation or analytic design work binds its implementation reference, digest, environment identity, random seeds, clustering model, target precision, final case counts, final assessor allocation, and sensitivity to plausible consequential-disagreement prevalence.

The frozen stopping contract requires:

- an explicit recruitment target;
- `outcome_adaptive_stopping = false`;
- `interim_outcome_access = false`;
- a prespecified under-recruitment rule.

Under-recruitment or operational interruption is recorded as a deviation. It does not create an undeclared outcome-adaptive stopping rule.

## Linguistic and accessibility boundaries

The accessibility arm freezes representative-user strata, assistive-technology combinations, critical tasks, and critical-failure definitions. Automated accessibility regression checks remain separate engineering evidence.

`proposed_non_english_publication_locales` may be empty. An empty set creates no non-English locale publication-readiness claim. When a locale is listed, exactly one corresponding locale-parameter record is required with terminology-review, comprehension-test, and decision-critical-term definitions.

## Amendments

`VALIDATION_PROTOCOL_AMENDMENT.schema.json` records a plan change after freeze. An amendment binds:

- predecessor parameter-set identifier and digest;
- successor parameter-set identifier and digest;
- timestamp and rationale;
- changed fields;
- affected cases, outcomes, and analyses;
- outcome-data-access state at the time of amendment;
- impact on primary, secondary, or exploratory analyses;
- canonical amendment digest.

Predecessor and successor identifiers must differ, as must their digests. The predecessor remains addressable. When parameter-set objects are supplied to the validator, both lineage digests are independently recomputed.

A protocol deviation records what occurred under the frozen plan. An amendment changes the declared plan. These records have different meanings and should not be substituted for each other.

## Validation surface

`neuroai_workbench.validation_study` provides:

- `current_v42_normative_identity()`
- `finalize_case_manifest()`
- `validate_case_manifest()` / `validate_case_manifest_file()`
- `finalize_study_parameter_set()`
- `validate_study_parameter_set()` / `validate_study_parameter_set_file()`
- `load_case_manifests()`
- `finalize_protocol_amendment()`
- `validate_protocol_amendment()` / `validate_protocol_amendment_file()`

The study-parameter validator is intentionally fail-closed when case manifests are omitted. Cross-record integrity is part of preregistration validity.

## Execution boundary

#196 implements this record layer. #197 selects and freezes genuine study cases. #198 performs the pre-outcome precision analysis used to select counts. Completion of the record layer alone does not satisfy #193 and does not authorize outcome collection.