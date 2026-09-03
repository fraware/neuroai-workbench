# PRE-G2 benchmark data boundary

This document governs the D3 patent and D4 product benchmark scaffold introduced before G2. The scaffold is mechanical infrastructure only. Schema validity, commitment equality, fixture tests, and metric calculations do not establish scientific validity, G1 approval, G2 freeze, publication authority, or v4.2 assessment findings.

## Store boundary

Public S1 may contain benchmark schemas, validation and evaluation code, cryptographic commitment descriptors, protocol metadata, and synthetic test fixtures. Real held-out membership, human labels, adjudication packets, licensed source bytes, and commitment nonces remain controlled in S3. Public manifests must fail closed if they contain fields reserved for those S3 materials.

A public commitment descriptor is evidence that one controlled payload can later be checked against one digest under the declared scheme. It does not disclose or authenticate the underlying benchmark, establish label quality, prove representativeness, or authorize release. Commitments use deterministic canonical JSON plus a domain separator and a secret nonce of at least 32 bytes. The nonce is retained in S3 until a governed verification or reveal process exists.

## Human and model roles

Human annotations, disagreement, abstention, and final adjudication are distinct records in the controlled benchmark process. Model outputs remain untrusted drafts and may support triage or analysis only. A model prediction cannot populate, replace, or satisfy a gold-label or final-adjudication requirement.

The repository fixtures are intentionally synthetic. Their annotations and model predictions exist only to test software boundaries. They must never be counted as benchmark observations or scientific validation evidence.

## Evaluation contract

D3 must measure patent positives, negatives, deceptive negatives, borderline cases, missing or short abstracts, multi-year and multi-jurisdiction coverage, multilingual cases, and gray capability boundaries. D4 must measure clinical, consumer, workplace, research, entertainment/XR, wellness, ambiguous-biosignal, nontraditional-form-factor, multilingual, and multi-jurisdiction cases.

Both contracts require reporting by language, jurisdiction, text state, and edge-case type. Core evaluation includes precision, recall, false-negative rate, abstention rate, calibration error, threshold reporting, and explicit false-negative analysis. These are evaluation requirements; the scaffold contains no measured result.

## Threat analysis and fail-closed controls

The principal added risks are accidental publication of held-out membership or labels, disclosure of licensed bytes or commitment nonces, model-output elevation into label authority, premature G2 freeze claims, and benchmark leakage that invalidates later evaluation. Public-manifest validation therefore rejects reserved S3 fields recursively, requires `g1_approved=false`, `g2_frozen=false`, and `contains_real_heldout_labels=false`, preserves the model/human authority distinction, and refuses inconsistent commitment states.

A future G2 freeze requires a separate governed change after G1 approval, actual S3 benchmark construction, human adjudication, leakage review, split commitment creation, and explicit freeze disposition. This PRE-G2 scaffold cannot perform that transition.
