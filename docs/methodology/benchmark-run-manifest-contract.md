# Benchmark freeze and held-out run manifest contract

This PRE-G2 contract binds benchmark identity to later evaluation evidence without creating G1 approval, G2 approval, canonical S2 authority, publication authority, or v4.2 assessment effects.

## Current manifest contract

The current freeze/run manifest schema is `0.2`. It is a successor to the historical `0.1` scaffold and is specifically aligned to the post-#291 D3/D4 public benchmark contract schema `0.2`. Historical v0.1 manifest semantics are not silently reinterpreted as current freeze evidence.

A current freeze manifest is structurally valid only when it is checked against the exact supplied `FROZEN_COMMITMENTS_ONLY` public benchmark contract. The manifest binds the canonical SHA-256 identity of that public contract, the exact approved D1 canonical SHA-256, the exact attributable G1 disposition identifier/digest, the current four-way D1 boundary semantics and `D1_INCLUDE_EXCLUDE_BINARY_V1` projection, and the exact keyed membership/disposition commitments carried by the public contract.

The freeze also records aggregate boundary-disposition counts and requires at least one frozen human `INCLUDE`, `EXCLUDE`, and `BORDERLINE` case. Human `ABSTAIN` and unresolved reviewer disagreement remain separately countable and cannot substitute for required G2 boundary coverage. Required patent/product strata must exactly match the supplied public contract and are backed by a controlled strata-coverage report digest.

Sampling protocol, human-review provenance, adjudication protocol/accounting, boundary-coverage evidence, strata-coverage evidence, and exposure/contamination evidence are bound by identifiers and/or SHA-256 digests. The human-review contract explicitly preserves D1's required disposition fields: `decision`, `rationale`, `adjudicator_role`, `timestamp`, and `exact_object_binding`. A non-empty double-label subset is required structurally. These controls establish evidence identity, not the truth, independence, adequacy, or scientific quality of the underlying private records.

All real benchmark membership, item-level human dispositions, reviewer records, rationales, adjudication packets, licensed source material, and HMAC keys remain in S3-controlled research storage. The freeze manifest uses the conservative rights-containment state `S3_CONTROLLED_NO_REDISTRIBUTION_AUTHORITY_CLAIMED` and requires a rights-review reference. That state does not establish lawful use or redistribution permission; it prevents the technical freeze record from being misread as such authority.

A successor freeze must bind the predecessor manifest SHA-256. Root freezes cannot name a predecessor. Known or unresolved held-out contamination fails closed.

## Held-out evaluation run

A held-out run manifest binds the exact freeze-manifest digest and inherited public-contract digest to an exact Workbench commit, pipeline artifact, configuration, threshold policy, abstention policy, subgroup plan, observation time, prediction artifact, and aggregate result. It must also bind metric schema `0.2` and `D1_INCLUDE_EXCLUDE_BINARY_V1`, and it requires the explicit development boundary `HELD_OUT_NOT_USED_FOR_TUNING`.

The held-out run permits only `AGGREGATE_ONLY` export at PRE-G2. The run validator revalidates the supplied freeze/public-contract pair before accepting the run binding. Known or unresolved contamination fails closed.

## Authority boundary

The freeze and run manifests remain candidate evidence. `g2_passed=false`, `canonical_s2_authority=false`, `publication_authority=false`, and `assessment_effect=NONE` are mandatory. Human governance must separately evaluate the scientific evidence package and issue any successor G2 disposition.

Manifest SHA-256 values provide exact payload identity. Structural validation does not establish scientific representativeness, sample-size sufficiency, label truth, reviewer independence, absence of undisclosed contamination, source-rights compliance, model independence, statistical adequacy, or G2 passage. Those propositions require their own controlled evidence and human review.
