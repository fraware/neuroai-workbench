# Held-out benchmark boundary

This document defines the PRE-G2 software boundary for D3 patent and D4 product evaluation after the approved D1 construct-validity remediation. It is an execution scaffold only. It does not freeze D3 or D4, pass G0 or G2, establish scientific representativeness, mutate canonical S2, authorize publication, or alter any v4.2 assessment finding.

## Governing research-contract binding

The benchmark contract schema is version `0.2`. Its boundary semantics are bound to the approved D1 canonical JSON SHA-256 `7d270002094dcdecb703d5b70ef2268e4869005c284ffd98db3eb936641a78cb` and the attributable G1 disposition already referenced by the packaged D3/D4 drafts.

D1 governs boundary membership with four human dispositions: `INCLUDE`, `EXCLUDE`, `BORDERLINE`, and `ABSTAIN`. The benchmark evaluator preserves those dispositions directly. A resolved human disposition is never stored as `POSITIVE`, `NEGATIVE`, or `UNRESOLVED`.

Reviewer/adjudication state is a separate dimension. `AGREE` and `ADJUDICATED` are resolved states and require one governed boundary disposition plus recorded rationale. `DISAGREE_UNADJUDICATED` represents genuine unresolved reviewer disagreement and requires a null final boundary disposition. Human `ABSTAIN` is a resolved governed disposition for insufficient evidence; it is not an alias for unresolved disagreement.

## G2 coverage versus sampling strata

G2 requires frozen human-adjudicated positive, negative, and borderline patent/product cases with provenance. The PRE-G2 contract operationalizes those minimum boundary-outcome requirements as `INCLUDE`, `EXCLUDE`, and `BORDERLINE` under the exact D1 domain. `ABSTAIN` remains allowed and must be preserved when evidence is insufficient, but it is not a minimum G2 disposition-count requirement in the approved D1 condition.

Boundary outcomes and sampling/coverage strata are orthogonal. The patent contract therefore no longer treats `POSITIVE`, `NEGATIVE`, or `BORDERLINE` as strata. Patent strata cover semantically deceptive negatives, missing/short abstracts, temporal and jurisdictional variation, multilingual cases, and gray-capability discovery. Product strata cover deployment/application contexts and edge conditions including ambiguous biosignal and nontraditional form factors, plus multilingual and multi-jurisdiction coverage. A case may carry any permitted boundary disposition independently of its strata.

Presence of every required stratum or disposition does not establish representativeness, sample-size sufficiency, or open-world completeness. Sampling design, reviewer recruitment, subgroup sizes, statistical uncertainty, and final freeze authority remain controlled research decisions.

## Versioned binary projection

Precision, recall, false-negative rate, probability calibration, and Brier score are computed only under the explicit projection `D1_INCLUDE_EXCLUDE_BINARY_V1`:

- human `INCLUDE` is the binary positive class;
- human `EXCLUDE` is the binary negative class;
- human `BORDERLINE` and human `ABSTAIN` are excluded from binary denominators and reported as separate routing targets;
- unresolved reviewer disagreement is excluded from binary denominators and remains separately counted;
- model outputs use the same four-way routing domain: `INCLUDE`, `EXCLUDE`, `BORDERLINE`, `ABSTAIN`;
- model `BORDERLINE`, model `ABSTAIN`, and missing predictions on human `INCLUDE` cases count as effective false negatives for the projected recall/FNR calculation;
- the optional probability field is `probability_include` and is interpreted only as probability of `INCLUDE` under this named projection.

This projection is an evaluation view over the D1 boundary; it does not replace or narrow the research contract itself. Any later change to these projection rules requires an explicit versioned successor rather than reinterpretation of previously frozen metrics.

## Routing and disagreement reporting

The evaluator reports binary metrics and four-way routing separately. For human `BORDERLINE` and human `ABSTAIN` cases it reports model routing counts, missing predictions, and exact-route rates. It also retains a resolved human-disposition × model-routing matrix and descriptive prediction counts for unresolved adjudication rows. Those descriptive counts do not convert unresolved cases into model-facing truth.

Subgroup reports apply the same structure by stratum, language, jurisdiction, and text availability by default. This exposes where binary performance or borderline/abstention routing changes across declared groups without asserting statistical significance, fairness, safety, or external validity.

## Custody and leakage boundary

Held-out membership, final human dispositions, individual reviewer dispositions, adjudication packets, rationale records, and any licensed or otherwise controlled source material remain in S3-controlled research storage. The public repository may contain only synthetic fixtures, public benchmark contracts/schemas, aggregate evaluation logic, documentation, and opaque commitments.

Prediction rows are treated as untrusted model or rule-system output. Recursive leakage guards reject human boundary disposition, adjudication state, reviewer disposition, source text, held-out membership, and equivalent oracle fields. Legacy `prediction=POSITIVE|NEGATIVE` and `gold_label=POSITIVE|NEGATIVE|UNRESOLVED` forms fail closed under schema/evaluator version `0.2`; callers must migrate explicitly to four-way boundary semantics.

When a benchmark is eventually frozen after the applicable governance conditions, membership and label/disposition payloads are committed with `HMAC_SHA256_DOMAIN_CANONICAL_JSON_V1`. The HMAC secret remains in S3 and must contain at least 32 bytes. Membership and disposition commitments use distinct domain separators. Public commitments establish payload identity only; they do not establish label correctness, representativeness, completeness, or independent adjudication.

## Controlled sequence to G2

Before G2 can be considered, the actual S3 D3/D4 sets must be constructed under this contract; include the declared strata and minimum `INCLUDE`/`EXCLUDE`/`BORDERLINE` coverage; preserve attributable reviewer/adjudication provenance and rationale; double-label the strategically selected subset; lock a held-out test split inaccessible to tuning; record contamination/exposure controls; and produce opaque public commitments without disclosing benchmark membership or labels. G2 remains false until the resulting evidence package receives the required governance disposition.

All functions in `neuroai_workbench.evaluation_benchmarks` are offline and side-effect free. They do not perform network I/O, write repositories or workspaces, mutate S2, create release attestations, or invoke the v4.2 assessment engine.
