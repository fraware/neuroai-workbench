# Held-out benchmark data governance

This PRE-G2 control note supplements `DATA_GOVERNANCE.md` for D3 patent and D4 product evaluation. It does not freeze a benchmark or create G1/G2 approval.

Held-out membership, gold labels, raw reviewer labels, adjudication packets, HMAC secrets, licensed source records, and any private benchmark construction notes remain in S3-controlled research storage. They are excluded from the public software repository, public Observatory S2, model prompts unless a separately approved controlled evaluation architecture explicitly permits them, CI logs, issue/PR text, and generated public products.

The public repository may contain synthetic fixtures, code, documentation, aggregate metric outputs, and opaque keyed commitments. The commitment secret is a controlled credential-like research secret and must not be committed, logged, embedded in artifacts, or reused as an application credential. A public HMAC value is a payload-identity commitment only; it does not authorize disclosure of the committed material.

Double-labeling and adjudication records remain attributable controlled research records. Disagreement states are retained. `DISAGREE_UNADJUDICATED` and `ABSTAIN_UNRESOLVED` are not silently converted into binary gold labels for scoring. If a later adjudication resolves a case, the controlled record must preserve the predecessor disagreement and the adjudication provenance; a benchmark re-freeze requires a successor commitment rather than silent replacement.

Before a held-out run, operators must bind the model or pipeline identity, code/configuration digest, benchmark commitments, evaluation protocol, threshold/abstention policy, and observation time. Development-set tuning and held-out evaluation remain separate. Results exported from S3 should be aggregate unless a reviewed disclosure decision permits item-level material. Small subgroup outputs require disclosure review where they could reveal membership or controlled labels.

Retention, access control, lawful use of licensed data, reviewer confidentiality, and deletion remain governed by the strongest applicable S3 policy. The software scaffold does not establish lawful basis, licence rights, data minimisation sufficiency, or external institutional authorization.