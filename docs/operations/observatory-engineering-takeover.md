# NeuroAI Observatory engineering takeover — programme control

**Control identifier:** NEUROAI-ENG-TAKEOVER-1.0  
**Status:** Active after monitoring foundation merge (PR #32)  
**Governing epic:** [#34](https://github.com/fraware/neuroai-workbench/issues/34)

## Invariant

Automation may schedule, retrieve, preserve, compare, propose, validate, and render. Named humans retain substantive classification, entity-resolution approval, assessment reopening, and canonical release authority. Never infer scientific truth, regulatory authorization, clinical value, conformance, or UNESCO endorsement from software success.

## Normative PR order

PR-00 CodeQL authority → PR-01 monitoring foundation → Wave 1 storage/data (PR-02..04) → Wave 2 collector (PR-05..07) → Wave 3 review queue (PR-08..09) → Wave 4 entities/extraction (PR-10..13) → Wave 5 shadow (PR-14) → Wave 6 delta/release (PR-15..20) → Wave 7 products/acceptance (PR-21..23).

Later stages may split for reviewability but must not leapfrog dependencies for canonical publication.

## Locked decisions

1. CodeQL Option A: Default Setup disabled; Advanced `.github/workflows/codeql.yml` retained; required check context `codeql`.
2. Public data repository name: `neuroai-observatory-data` (ADR-0009).
3. One capability per PR; mandatory PR description template on epic #34 / plan.

## Authority exclusions (always stated)

No UNESCO endorsement; no regulatory/clinical/conformance claim from software gates; generated Excel/Word/PDF/dashboard are views never canonical inputs; absence of evidence ≠ automatic FAIL.
