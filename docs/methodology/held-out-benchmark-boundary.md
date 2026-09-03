# Held-out benchmark boundary

This document defines the PRE-G2 software boundary for D3 patent and D4 product evaluation. It is an execution scaffold only. It does not approve G1, freeze D3 or D4, pass G2, establish scientific representativeness, mutate canonical S2, authorize publication, or alter any v4.2 assessment finding.

## Custody and identity

Held-out membership, gold labels, individual reviewer labels, adjudication packets, and any licensed or otherwise controlled source material remain in S3-controlled research storage. The public repository may contain only synthetic fixtures, the benchmark contract, aggregate evaluation logic, and opaque commitments.

When a benchmark is frozen after the applicable governance gate, membership and label payloads are committed with `HMAC_SHA256_CANONICAL_JSON_V1`. The HMAC secret remains in S3 and must contain at least 32 bytes. The public commitment is evidence that a later controlled payload can be checked against the frozen identity; it does not reveal the payload and does not establish that the labels are correct, representative, complete, or independently adjudicated.

A public benchmark contract has two PRE-G2 states: `DRAFT_UNFROZEN` and `FROZEN_COMMITMENTS_ONLY`. Both require `g2_passed=false`, `canonical_s2_authority=false`, `publication_authority=false`, and `assessment_effect=NONE`. `DRAFT_UNFROZEN` may remain at `g1_gate_state=NOT_APPROVED` or carry a structurally bound reference to an already approved G1 disposition. `FROZEN_COMMITMENTS_ONLY` is valid only when `g1_gate_state=APPROVED_REFERENCE_PROVIDED` and the contract contains a non-empty G1 disposition identifier plus its exact SHA-256 digest. The validator checks the reference structure and binding fields; it does not authenticate, issue, or substantively validate the G1 governance decision.

## D3 and D4 coverage scaffold

The D3 patent scaffold requires positive, negative, semantically deceptive negative, borderline, missing-or-short-abstract, multi-year, multi-jurisdiction, multilingual, and gray-capability strata.

The D4 product scaffold requires clinical, consumer, workplace, research, entertainment/XR, wellness, ambiguous-biosignal, nontraditional-form-factor, multilingual, and multi-jurisdiction strata.

These strata are minimum evaluation coverage requirements. Presence of every stratum is not evidence that the benchmark is representative of the open world or that the chosen sample size is sufficient. Sampling design, label protocol, reviewer recruitment, subgroup sizes, statistical uncertainty, and final freeze authority remain separate controlled decisions.

## Label and disagreement semantics

The scoring interface permits binary controlled gold labels only when the adjudication state is `AGREE` or `ADJUDICATED`. `DISAGREE_UNADJUDICATED` and `ABSTAIN_UNRESOLVED` must carry `UNRESOLVED` and are excluded from binary performance denominators. The unresolved count remains visible. This prevents disagreement from being silently converted into a model-facing truth label.

Prediction rows are treated as untrusted model or rule-system output. Recursive leakage guards reject fields that expose held-out membership, ground truth, adjudication state, reviewer labels, or equivalent oracle information. The guard is structural and cannot prove that an external model was never exposed to the benchmark through another channel; benchmark operations must separately control access and contamination.

## Metrics and abstention

Evaluation reports precision, recall, effective false-negative rate, coverage, explicit abstention count, missing-prediction count, probability coverage, and Brier score when probabilities are supplied. Recall and false-negative rate use all scoreable positive gold cases in the denominator. Positive abstentions and missing predictions therefore count as effective misses instead of disappearing from recall. Precision is computed over answered positive predictions. Coverage remains separate so selective answering is visible.

The evaluator also reports the same metrics across declared subgroup fields, defaulting to stratum, language, jurisdiction, and text availability. These aggregates expose performance heterogeneity; they do not by themselves establish statistical significance, fairness, safety, or external validity.

## Execution sequence

Before any model selection or threshold tuning against the held-out sets, the applicable research contract and taxonomy must receive the required G1 governance disposition. The exact G1 disposition identifier and digest are then bound into the benchmark contract before D3/D4 membership and labels can enter `FROZEN_COMMITMENTS_ONLY`. The controlled S3 payloads receive opaque commitments and remain unavailable for tuning. Model comparison uses a separate development set and then a controlled held-out evaluation. G2 can be considered only from the resulting evidence package plus the required human governance review.

All functions in `neuroai_workbench.evaluation_benchmarks` are offline and side-effect free. They do not perform network I/O, write repositories or workspaces, mutate S2, create release attestations, or invoke the v4.2 assessment engine.
