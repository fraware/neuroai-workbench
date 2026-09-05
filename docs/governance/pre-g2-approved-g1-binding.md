# PRE-G2 approved G1 binding

**Status:** PRE-G2 cross-repository binding only  
**Workbench baseline:** `b9e4e1f6101887ab378f6408bd07421ba1d8ae48`  
**Observatory G1 transition:** `e12b0fdffcaa2c73c723574f8718241b9cd0cd89`

## Purpose

The D3 patent and D4 product benchmark scaffolds were originally merged while G1 was unapproved. An attributable human `APPROVE` disposition has now been recorded in `fraware/neuroai-observatory-data` for the exact corrected D1/D2 identities. This Workbench change binds the existing PRE-G2 draft contracts to that external governance record without freezing benchmark membership or labels and without claiming G2 passage.

## Exact governance reference

Authoritative Observatory record:

`curation/HUMAN_G1_DISPOSITION_2026-09-05_D1_D2_v0.1.json`

Exact source identities:

- Observatory main SHA: `e12b0fdffcaa2c73c723574f8718241b9cd0cd89`
- Git blob SHA: `ed42dc5b77cf011562db8c8c39bc9e71968fdb37`
- canonical JSON SHA-256: `ed6489fe1085b5aec1b594970dd1c574b57bd6bbd25a659643e9bd1b7b72d8ef`
- disposition ID: `HUMAN_G1_DISPOSITION_2026-09-05_D1_D2_v0.1`
- decision: `APPROVE`

The canonical SHA-256 is computed from UTF-8 JSON using sorted keys, compact separators and non-finite values forbidden, matching the deterministic JSON convention used by the PRE-G2 benchmark machinery.

The approved research artifacts remain:

- D1 canonical JSON SHA-256: `7d270002094dcdecb703d5b70ef2268e4869005c284ffd98db3eb936641a78cb`
- D2 canonical JSON SHA-256: `bd9451a5084485ef7a36251b0bc39d486fe0c2174636171a29ec03d7010cbf1d`

`G1_D1_D2_DISPOSITION_REFERENCE.json` is a local offline reference to these public identities. It does not issue or authenticate the human decision; the authoritative decision remains the Observatory record and its attributable underlying issue comment.

## Resulting D3/D4 state

Both packaged public benchmark contracts change only their G1 reference state:

- `state = DRAFT_UNFROZEN` remains unchanged;
- `g1_gate_state = APPROVED_REFERENCE_PROVIDED`;
- `g1_disposition_id` and `g1_disposition_sha256` bind the exact record above;
- `membership_commitment = null`;
- `label_commitment = null`;
- `g2_passed = false`;
- membership, gold labels, reviewer labels, adjudication packets and commitment keys remain `S3_CONTROLLED`.

This transition establishes the exact post-G1 governance reference needed by later D3/D4 work. It does not establish that the current PRE-G2 evaluation representation is semantically complete relative to the approved D1 contract, and it does not authorize real benchmark freeze.

## Construct-validity blocker before real freeze

Issue #290 records a post-G1 audit finding that must be resolved before real D3/D4 labels are frozen. Approved D1 uses four governed boundary dispositions: `INCLUDE`, `EXCLUDE`, `BORDERLINE`, and `ABSTAIN`. The existing PRE-G2 evaluator currently exposes `POSITIVE`/`NEGATIVE`/`UNRESOLVED` gold labels and `POSITIVE`/`NEGATIVE`/`ABSTAIN` model outputs, with `BORDERLINE` represented only as a coverage stratum. That representation cannot directly encode a resolved human `BORDERLINE` disposition and does not clearly separate a governed human `ABSTAIN` disposition from unresolved reviewer disagreement.

No real benchmark is affected yet because no real D3/D4 held-out set has been frozen. The scaffold must either preserve the approved D1 boundary disposition as an orthogonal first-class field and explicitly define any binary scoring projection, or record and approve a narrower binary benchmark task with predeclared treatment of `BORDERLINE` and human `ABSTAIN`. Silent coercion is prohibited.

## Next controlled boundary

After issue #290 is resolved, G2 requires actual human-labeled D3/D4 sets, including the declared patent/product edge-case strata, a strategically double-labeled subset with disagreement preservation and adjudication provenance, a locked held-out split inaccessible to tuning, an exposure/contamination register, and opaque membership/label commitments generated with an S3-held secret. Only those resulting records can support a later G2 disposition.

No real held-out member, label, source text, licensed byte, reviewer packet, commitment key, or test membership belongs in this public repository.

## Non-claims

This binding does not pass G0 or G2, establish scientific truth or benchmark adequacy, resolve issue #290, resolve PATSTAT redistribution rights, authorize online-first Phase 4, mutate canonical S2, authorize publication, or alter any v4.2 assessment finding.
