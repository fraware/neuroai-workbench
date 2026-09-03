# Benchmark run manifest data governance

Benchmark freeze and held-out run manifests are public-control metadata only. They must not contain held-out item identifiers, gold labels, reviewer labels, adjudication packets, HMAC secrets, licensed source bytes, model prompts containing controlled labels, or personal reviewer information beyond a role/reference needed for attributable operations.

Private benchmark membership, labels, review records, exposure registers, and commitment secrets remain in S3-controlled research storage. Public freeze manifests contain only opaque commitments and non-sensitive control references. Public run manifests contain artifact digests and aggregate-result commitments. At PRE-G2, `AGGREGATE_ONLY` is the only permitted export policy.

A successor freeze must preserve predecessor identity through `predecessor_manifest_sha256`; changed membership or labels therefore receive a new manifest identity instead of silently replacing the earlier freeze. Evaluation runs bind the exact freeze manifest, Workbench commit, pipeline/configuration, threshold policy, abstention policy, subgroup plan, predictions, and aggregate results.

The software validator does not establish lawful basis, licence rights, reviewer consent, confidentiality sufficiency, or the substantive truth of contamination declarations. Those remain controlled governance obligations outside the public module.