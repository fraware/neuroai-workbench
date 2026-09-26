# Release-A Product Discovery Frame Contract v1.0

**Plan binding:** `P0.4`  
**Tracking issue:** #326  
**Depends on:** P0.3 exact-product registry projection v1.0  
**Status:** `FROZEN_v1.0` upon merge to `main`

## Purpose

Release A is an open-world discovery programme. No single source is a complete NeuroAI product universe. This contract makes the search process reproducible enough to measure marginal yield, source overlap, multilingual gain, capability-first gain, and the residual unseen population without pretending that search saturation proves global completeness.

The deduplication target is the P0.3 canonical offering identity. Multiple source observations, aliases, distributor pages, trial records, regulatory records, or repeated queries that resolve to one offering remain one product identity.

## Controlled discovery frames

| ID | Frame | Main evidence channel |
| --- | --- | --- |
| F1 | First-party product discovery | manufacturer/vendor product catalogues, manuals, official documentation and archived official pages |
| F2 | Regulatory discovery | device, authorization, listing and regulator records |
| F3 | Clinical/trial discovery | trial registries and study records |
| F4 | Scientific/research discovery | publications, research instrumentation and research-platform documentation |
| F5 | Commercial/ecosystem discovery | specialist distributors, procurement, accelerator/investor portfolios and industry directories |
| F6 | Capability-first discovery | function/capability searches designed to recover weakly labelled and non-traditional products |
| F7 | Expert nominations | structured expert seeds and edge cases |
| F8 | Local-language discovery | native-language sources/query families for selected jurisdictions |
| F9 | Curated-actor seed discovery | known Observatory actors and other predeclared organization seeds, resolved through attributable product evidence |
| F10 | Patent-commercialization crossover | patent assignees/inventors and patent-linked commercialization leads followed to attributable product evidence |
| F11 | Snowball expansion | validated products, developers, distributors, trials and related-product links expanded under recorded parent-seed provenance |

A source can be observed through only the frame whose declared retrieval mechanism produced that capture. Post-hoc relabelling solely to improve population estimation is prohibited.

The machine-readable frozen register is `src/neuroai_workbench/resources/discovery/PRODUCT_DISCOVERY_FRAME_REGISTER.v1.0.json`. It fixes frame classes, source/query families, dependence notes, estimation eligibility and stopping rules for v1.0.

F7, F9 and F11 are excluded from the primary v1.0 capture estimator. Expert nominations and curated known-actor seeds are purposive; snowball expansion is path-dependent on already discovered identities. All three still contribute to the observed product registry and to zero-capture/coverage-risk diagnostics. F1–F6, F8 and F10 are estimation-eligible in the frozen v1.0 register, subject to the dependence and model-admissibility rules preregistered in P0.5.

F5 deliberately retains distributor/procurement, funding-investor-accelerator and structured-directory channels under one commercial/ecosystem class only when the exact source class remains recorded on the underlying observation. P0.5 must test whether that aggregation is defensible for estimation; it may predeclare finer analytical groupings if dependence diagnostics require them. F9, F10 and F11 remain distinct because curated actor seeds, patent-to-product crossover, and snowballing have materially different selection mechanisms.

## Capture unit

For Release-A offering-level estimation, one capture history belongs to one resolved in-scope `PRODUCT` identity at `identity_level = OFFERING`.

For product (i):

```text
C_i = (F1_i, F2_i, ..., F11_i)
```

where each component is binary after within-frame deduplication.

A product observed 12 times in F1 is one F1 capture. The same product observed in F1, F2 and F4 contributes the history `(1,1,0,1,0,0,0,0,0,0,0)` in the complete F1–F11 register.

Capture histories must remain tied to one exact:
- registry projection version;
- population view;
- analysis-jurisdiction scope;
- world-time cutoff;
- knowledge-time cutoff;
- language-scope identifier;
- discovery-frame register version.

The implementation fails closed if capture histories from different analytical universes are combined.

## Run and round accounting

Every product-discovery observation records:
- frame ID/version;
- discovery round;
- query/seed provenance;
- exact query family;
- source class/channel;
- source observation reference;
- source language;
- jurisdiction;
- candidate key;
- resolved canonical offering ID where available;
- scope/identity outcome;
- whether the observation is eligible for population-estimation capture.

For each round and frame report:
- raw candidates;
- newly resolved in-scope offering identities;
- duplicate identities already known at round start;
- within-round duplicate captures of the same resolved identity;
- EXCLUDE;
- BORDERLINE;
- ABSTAIN;
- unresolved identity;
- failed/inaccessible leads;
- marginal new-identity yield;
- duplicate yield.

A machine-readable `PRODUCT_DISCOVERY_RUN` record binds every frame/round execution to its exact query/seed set, analysis universe, digest of identities known at round start, exact capture IDs, and stop state. This prevents later recomputation from silently changing the new-versus-duplicate baseline.

Language and jurisdiction contributions are reported after exact-offering deduplication and distinguish unique resolved identities from identities that were genuinely new relative to the round-start known set.

## Frame overlap and dependence

Release A records the complete pairwise frame-overlap matrix over resolved in-scope identities. Independence is never assumed from frame labels.

For every frame pair the analysis must preserve:
- observed shared identities;
- frame-specific totals;
- known nesting or source inheritance;
- common upstream feeds where known;
- common query seeds where known.

Population models in P0.5/A7 must treat frame dependence as an empirical/model-selection problem.

## Multilingual and capability-first comparisons

F6 is the controlled capability-first frame used for the A3 recall study.

For A3, engineers follow the frozen preregistration
`RELEASE_A_A3_CAPABILITY_RECALL_PREREGISTRATION.v1.0.json`. That artifact binds
the conventional terminology search-family set and the capability-expanded
search-family set, plus the `ΔN_capability` metrics contract, **before** any
yield difference is computed or interpreted. Post-hoc family edits after seeing
`ΔN_capability` are prohibited. Increments count only exact canonical offering
IDs; raw search hits are not the increment unit. Freeze alone does not compute
`ΔN_capability`, allocate identity, or start A4+.

Executed A3 results are recorded in
`RELEASE_A_A3_CAPABILITY_FIRST_RECALL_STUDY.v1.0.json`, which binds the
preregistration digest, F1–F6 source-packet digests, measured `ΔN_capability`,
and companion false-positive / unresolved / duplicate rates. The key result is
the measured exact-offering increment, not a raw F6 hit count.

F8 is the controlled local-language frame used for A4. Matched language/jurisdiction analyses must compare the same product-identity and population-view semantics.

For A4, engineers follow the frozen preregistration
`RELEASE_A_A4_MULTILINGUAL_SENSITIVITY_PREREGISTRATION.v1.0.json`. That artifact
binds the matched English (`S_ENGLISH` = F1–F6) versus English+native
(`S_ENGLISH_PLUS_NATIVE` = F1–F6+F8) protocol and the `ΔN_multilingual` /
per-stratum `Δ_j` metrics contract to the frozen
`EN_PLUS_PRIORITY_NATIVE_v1` language/jurisdiction strata
(`RELEASE_A_LANGUAGE_JURISDICTION_STRATA.v1.0.json`, digest `25010299…`)
**before** any yield difference is computed or interpreted. Languages and
strata must not be chosen, added, dropped, or relabelled because they looked
fruitful during exploratory or F8 work. Increments count only exact canonical
offering IDs; raw search hits are not the increment unit. Required companion
metrics include unique-product gain, false-positive / unresolved / duplicate
rates, capability gain, and source-class gain. Freeze alone does not compute
`ΔN_multilingual`, allocate identity, or start A5+.

Executed A4 results are recorded in
`RELEASE_A_A4_MULTILINGUAL_COVERAGE_SENSITIVITY_STUDY.v1.0.json`, which binds
the preregistration digest, language-strata digest `25010299…`, F1–F6+F8
source-packet digests, measured `ΔN_multilingual`, companion rates, capability
gain, source-class gain, and an explicit substantive-conclusion-change
statement. The key result is the measured exact-offering increment under the
matched English versus English+native design, not a raw F8 hit count.

For A5, engineers follow the frozen preregistration
`RELEASE_A_A5_SNOWBALL_DISCOVERY_PREREGISTRATION.v1.0.json`. That artifact
binds the controlled snowball edge taxonomy (product→organization;
organization→other product; product→trial; product→regulatory;
product→publication; product→distributor/procurement; product→related product;
product→related capability query), parent-seed provenance rules, the
`Y_r`/`D_r`/`X_r`/`U_r`/`m_r` metrics contract, marginal-yield decomposition
dimensions, and the permitted stop descriptions **before** any round yield is
computed or interpreted. Every generated object re-enters as a candidate; a
snowball edge itself never establishes inclusion or canonical identity. F11
remains the path-dependent diagnostic execution substrate and stays excluded
from the primary unseen-population estimator. Freeze alone does not compute
round metrics, allocate identity, or start A6+.

Executed A5 results are recorded in
`RELEASE_A_A5_CONTROLLED_SNOWBALL_DISCOVERY_STUDY.v1.0.json`, which binds the
preregistration digest, F11 execution-packet digest, parent-seed provenance on
every edge, candidate re-entry, per-round `Y_r`/`D_r`/`X_r`/`U_r`/`m_r`,
marginal-yield decomposition, and stop-state evidence. The key result is the
measured round ledger under the frozen snowball protocol, not an edge count.

For A6, engineers follow the frozen preregistration
`RELEASE_A_A6_COVERAGE_SATURATION_PREREGISTRATION.v1.0.json`. That artifact
binds A2–A5 digests, the Coverage and Saturation Report contract, reuse of the
declared round-metrics and decomposition dimensions, and the permitted stop
descriptions **before** any coverage/saturation interpretation. Permitted stop
language remains limited to saturation under the declared protocol,
budget/coverage termination, bounded-source exhaustion, or unresolved-source
barrier. Protocol saturation must never be converted into a claim of global
completeness. Freeze alone does not emit the report, allocate identity, or
start A7+.

Executed A6 results are recorded in
`RELEASE_A_A6_PRODUCT_DISCOVERY_COVERAGE_SATURATION_REPORT.v1.0.json`, which
binds the A6 preregistration digest, A2–A5 digests, the A5 round-metrics
ledger and decompositions, the F1–F11 coverage/stop inventory under permitted
stop descriptions, and explicit refusal of global-completeness claims. The key
result is protocol coverage/saturation under declared protocols, not a census
of every relevant product worldwide.

Before A7 fitting, engineers freeze
`RELEASE_A_A7_CAPTURE_HISTORY_DATASET.v1.0.json` and
`RELEASE_A_A7_POPULATION_MODEL_SPECIFICATION.v1.0.json`. The capture-history
dataset compiles exact-offering captures across F1–F11 under one analysis
universe, reproduces source-packet digests, and exposes an estimator-eligible
subset that contains no F7/F9/F11 records. The model-specification lock binds
declared model families, acceptance/fail-closed criteria, and the observed
offering universe to that capture history **before** any unseen-population
model is fit. Freeze alone does not emit the Population Estimation Report,
allocate identity, or start A8 / A-G. A valid later A7 outcome may be that no
defensible unseen-population estimate exists under the preregistered
acceptance criteria.

Executed A7 results are recorded in
`RELEASE_A_A7_PRODUCT_POPULATION_ESTIMATION_REPORT.v1.0.json`, which binds the
frozen capture-history and model-specification digests, reports `N_observed`
separately from any estimate, and records model-family status under the
preregistered acceptance criteria. Under the current sparse eligible capture
table the admissible outcome is fail-closed with no headline unseen-population
estimate. The report does not start A8 / A-G.

Before A8 package materialization, engineers freeze
`RELEASE_A_A8_PACKAGE_MANIFEST_CONTRACT.v1.0.json`. That contract binds the
required Release-A package components, claim-class separations (observed fact /
derived quantitative result / bounded inference / policy interpretation),
forbidden claim classes (including market share, comparative effectiveness,
national leadership, invented `N_estimated`, F9-exhaustion-as-global-completeness,
and open-world-saturation-as-census), headline denominator/population-view rules,
D4 version/working-summary binding only, and exact upstream digests through A7.
Freeze alone does not emit the Product Population Release Package or start A-G.
A7 fail-closed `N_observed=6` with no `N_estimated` remains preserved.

Executed A8 results are recorded in
`RELEASE_A_A8_PRODUCT_POPULATION_RELEASE_PACKAGE.v1.0.json`, which binds the
frozen A8 contract digest and exact A1–A7 upstream digests, packages the
Product Registry, D4 working-summary binding, Frame Register, A3/A4/A6/A7
reports, analytical figure tables, source/coverage/uncertainty register, and
explicit unresolved-candidate register. Headline counts name denominators and
population views. The package preserves A7 fail-closed (`N_estimated` remains
null) and does not start A-G.

Before A-G reconstruction execution, engineers freeze
`RELEASE_A_AG_RECONSTRUCTION_PROTOCOL.v1.0.json`. That protocol binds the exact
A8 package digest, the twelve reconstruction fields (counted object, exact
identity, source observations, source frames, language/jurisdiction scope,
world/knowledge cutoffs, discovery stopping rule, observed versus estimated,
model assumptions, uncertainty, unresolved evidence, publication authority),
and the required headlines including at least one frame stop-state claim.
Freeze alone does not emit a PASSED or UNPASSED A-G outcome and does not
authorize Release B/C/D.

Executed A-G results are recorded in
`RELEASE_A_AG_RECONSTRUCTION_PACKET.v1.0.json`. Automated checks walk the A8
package to upstream digests and source packets for each required headline. The
packet emits an explicit `PASSED` or `UNPASSED` outcome with an evidence table.
A-G does not authorize Release B/C/D.

Incremental yield is always computed after exact-product deduplication.

## Stopping semantics

For F9 curated-actor execution, engineers follow the frozen procedure
`RELEASE_A_F9_ACTOR_ENUMERATION_PROCEDURE.v1.0.json`, append-only
`RELEASE_A_F9_ACTOR_COMPLETION_LEDGER_NNN.v1.0.json` successor files, and
immutable historical packets with successor protocol packets when earlier
tranches omit candidates. One convenient product-detail page is not actor
exhaustion for catalogue actors; boundary objects stay in the candidate
manifest. F9 remains diagnostic-only for primary estimation.

For F2/F3 bounded-frame execution, engineers follow the frozen provider/query
universes `RELEASE_A_F2_PROVIDER_QUERY_UNIVERSE.v1.0.json` and
`RELEASE_A_F3_PROVIDER_QUERY_UNIVERSE.v1.0.json`. Those artifacts bind exact
providers, query parameters, pagination/termination rules, and frozen
record-ID denominators. Example FDA/ClinicalTrials.gov identity lookups are not
exhaustion. Regulatory and trial records remain candidates until offering
identity and scope are dispositioned separately. Failed authoritative lookups
are retried only as successor observations.

For F1/F4/F5/F6/F11 open-world execution, engineers follow the frozen shared
round protocol `RELEASE_A_OPEN_WORLD_ROUND_PROTOCOL.v1.0.json` and the per-frame
query universes `RELEASE_A_F{1,4,5,6,11}_OPEN_WORLD_QUERY_UNIVERSE.v1.0.json`.
Those artifacts bind the A2 checkpoint, declared query seeds for at least R1–R3,
independence/temporal fail-closed rules, and the literal marginal-yield stop
parameters. Freezing those contracts does not itself establish saturation;
executed round summaries must still satisfy the stop rule. F11 remains
diagnostic-only for the primary unseen-population estimator.

For F8 local-language execution, engineers follow the frozen language/jurisdiction
strata `RELEASE_A_LANGUAGE_JURISDICTION_STRATA.v1.0.json` (binding
`EN_PLUS_PRIORITY_NATIVE_v1` before yield interpretation), the F8 round protocol
`RELEASE_A_F8_ROUND_PROTOCOL.v1.0.json`, and the F8 query universe
`RELEASE_A_F8_OPEN_WORLD_QUERY_UNIVERSE.v1.0.json`. F8 remains estimation-eligible
at frame level under the same literal marginal-yield bar as F1/F4/F5/F6/F11.

For F10 patent-commercialization crossover, engineers follow the frozen
patent/assignee candidate universe
`RELEASE_A_F10_PATENT_ASSIGNEE_CANDIDATE_UNIVERSE.v1.0.json`. Patent and assignee
matches are retrieval leads only; product identity requires separate attributable
product evidence; commercialization is not inferred from patent ownership;
semantic similarity does not create product links. F10 stops only after bounded
exhaustion of that frozen candidate set.

A frame can stop only with one of:

```text
SATURATION_UNDER_DECLARED_PROTOCOL
BOUNDED_FRAME_EXHAUSTED
BUDGET_COVERAGE_TERMINATION
UNRESOLVED_SOURCE_BARRIER
```

or remain `CONTINUE`.

For F1, F4, F5, F6, F8 and F11, v1.0 uses a marginal-yield rule requiring at least 3 completed rounds and 2 literal consecutive qualifying rounds with marginal new-identity yield <= 0.05, with at least 20 raw candidates in each qualifying round. F2, F3, F9 and F10 stop only after exhaustion of their declared bounded input/provider universe. F7 ends at its predeclared nomination limit and is not estimation-eligible.

A marginal-yield stop rule is frame-specific and predeclares:
- minimum completed rounds;
- number of consecutive low-yield rounds;
- maximum marginal new-identity yield considered low;
- minimum raw-candidate count per evaluated round.

A bounded registry/API frame can instead stop through demonstrated source exhaustion under its declared pagination/denominator logic.

Only the literal final consecutive rounds can satisfy a consecutive-low-yield stop rule. An intervening round below the minimum raw-candidate threshold breaks the qualifying tail; low-volume rounds cannot be skipped to manufacture apparent saturation.

No stop state means that every relevant product worldwide has been found.

## Population-estimation boundary

Capture-recapture and multiple-systems models can use only frames marked `capture_estimation_eligible = true` in the same frozen frame register.

Strongly nested/dependent frames must remain identifiable so P0.5 can compare alternative frame groupings and dependence models.

The primary observed registry can include validated products from non-estimation frames. `N_observed` and the capture-history model universe therefore require explicit compatibility metadata; products found only through excluded frames remain observed products and are reported as a sensitivity/coverage class.

## Boundary

This contract measures discovery coverage. It does not establish global completeness, market share, product effectiveness, or product importance.
