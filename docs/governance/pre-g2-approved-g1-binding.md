# PRE-G2 approved G1 binding

**Status:** PRE-G2 cross-repository binding only  
**Workbench baseline before this binding:** `b9e4e1f6101887ab378f6408bd07421ba1d8ae48`  
**Observatory G1 transition:** `e12b0fdffcaa2c73c723574f8718241b9cd0cd89`

## Purpose

The D3 patent and D4 product benchmark scaffolds were originally merged while G1 was unapproved. An attributable human `APPROVE` disposition has now been recorded in `fraware/neuroai-observatory-data` for the exact corrected D1/D2 identities. The Workbench binding line attaches the existing PRE-G2 draft contracts to that external governance record without freezing benchmark membership or dispositions and without claiming G2 passage.

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

Both packaged public benchmark contracts remain pre-G2 drafts:

- `state = DRAFT_UNFROZEN`;
- `g1_gate_state = APPROVED_REFERENCE_PROVIDED`;
- `g1_disposition_id` and `g1_disposition_sha256` bind the exact record above;
- `membership_commitment = null`;
- `label_commitment = null`;
- `g2_passed = false`;
- membership, final human dispositions, reviewer dispositions, adjudication packets and commitment keys remain `S3_CONTROLLED`.

This transition establishes the exact post-G1 governance reference needed by later D3/D4 work. It does not establish benchmark adequacy, empirical label quality, representativeness or G2 passage.

## Post-G1 construct-validity remediation

Issue #290 identified a representation defect in the inherited PRE-G2 evaluator: approved D1 defines governed human boundary dispositions `INCLUDE`, `EXCLUDE`, `BORDERLINE`, and `ABSTAIN`, while the older scaffold encoded binary `POSITIVE`/`NEGATIVE` gold labels plus `UNRESOLVED` and treated `BORDERLINE` partly as a patent stratum.

The selected remediation is benchmark-contract schema `0.2`, documented in `docs/methodology/held-out-benchmark-boundary.md`. It preserves the exact four-way human disposition, keeps unresolved reviewer disagreement as a separate adjudication state, separates boundary-outcome coverage from sampling strata, and defines the named binary projection `D1_INCLUDE_EXCLUDE_BINARY_V1` for precision/recall/calibration only. Human `BORDERLINE`, human `ABSTAIN`, and unresolved disagreement are never silently coerced into the binary denominator. Model `BORDERLINE`, model `ABSTAIN`, and missing predictions on human `INCLUDE` cases remain visible and count as effective misses in the projected recall/FNR contract.

This semantic remediation changes only the PRE-G2 evaluation representation. It does not alter the approved D1/D2 identities or the recorded G1 decision. Repository history and issue #290 remain the authoritative record of whether the remediation has passed exact-head validation and been merged.

## Next controlled boundary

After the representation remediation is merged and issue #290 is legitimately closed, G2 still requires actual human-labeled D3/D4 sets, including the declared patent/product edge-case strata, minimum `INCLUDE`/`EXCLUDE`/`BORDERLINE` disposition coverage, a strategically double-labeled subset with disagreement preservation and adjudication provenance, a locked held-out split inaccessible to tuning, an exposure/contamination register, and opaque membership/disposition commitments generated with an S3-held secret. Only those resulting records can support a later G2 disposition.

No real held-out member, human disposition, source text, licensed byte, reviewer packet, commitment key, or test membership belongs in this public repository.

## Non-claims

This binding and its semantic remediation do not pass G0 or G2, establish scientific truth or benchmark adequacy, resolve PATSTAT redistribution rights, authorize online-first Phase 4, mutate canonical S2, authorize publication, or alter any v4.2 assessment finding.
