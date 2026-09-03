# Benchmark freeze and held-out run manifest contract

This PRE-G2 contract binds benchmark identity to later evaluation evidence without creating G1 approval, G2 approval, canonical S2 authority, publication authority, or v4.2 assessment effects.

A freeze manifest is structurally valid only when it references an already-approved G1 disposition by identifier and SHA-256 digest; binds the D3 or D4 benchmark identifier, membership commitment, label commitment, strata-contract version, and adjudication-protocol version; declares S3 custody; records a UTC freeze time; preserves predecessor lineage for successors; and records a reviewed state with no known unresolved held-out contamination. The validator confirms syntax and internal consistency only. It does not authenticate the external governance disposition or establish that the benchmark is scientifically adequate.

A held-out run manifest binds an exact freeze-manifest digest to an exact Workbench commit, pipeline artifact, configuration, threshold policy, abstention policy, subgroup plan, metric schema, observation time, prediction artifact, and aggregate result. It requires an explicit declaration that held-out data was not used for development tuning. It rejects known or unresolved contamination and permits only aggregate export at this PRE-G2 boundary.

The freeze and run manifests remain candidate evidence. `g2_passed=false`, `canonical_s2_authority=false`, `publication_authority=false`, and `assessment_effect=NONE` are mandatory. Human governance must separately evaluate the scientific evidence package and issue any successor G2 disposition.

Manifest SHA-256 values provide exact payload identity. They do not establish truth, provenance outside the bound payload, non-contamination, reviewer independence, sampling validity, model independence, statistical sufficiency, or lawful use of source data. Those propositions require their own evidence and controls.