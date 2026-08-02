# Entity resolution evaluation report

**Governing issues:** [#37](https://github.com/fraware/neuroai-workbench/issues/37), tracking [#75](https://github.com/fraware/neuroai-workbench/issues/75)

## Boundary

Measured precision, recall, and false-merge counts are engineering behavioral metrics against annotated synthetic/public cases. They do not establish substantive entity identity, regulatory authority, or clinical correctness. Non-exact matches still require human confirmation.

## Corpora

| Corpus | Location | Size | Role |
| --- | --- | --- | --- |
| Blinded stub | `RESOLUTION_BENCHMARK_BLINDED.json` | 5 | Fast CI smoke |
| Public annotated subset | `RESOLUTION_BENCHMARK_PUBLIC_SUBSET.json` | ≥20 | CI metrics |
| Ops annotated draft | ops `evaluation/entity/RESOLUTION_BENCHMARK_OPS_GE60.json` | ≥60 | Ops-gated only |

## Public subset coverage

The public subset spans renames, acquisitions, parent/sub mentions, lab-name collisions, product-vs-company, sponsor-vs-site, abbreviations, historical IDs, and CJK/Arabic script variants using synthetic redistribution-safe strings only.

## How to measure

```powershell
python -c "from pathlib import Path; from neuroai_workbench.entities.benchmark import load_public_annotated_subset, run_blinded_benchmark; from tests.unit.test_entity_resolver import seed_entity_workspace; print('use seeded workspace + run_blinded_benchmark(..., benchmark_path=...)')"
```

Ops-gated full ≥60 run requires `NEUROAI_OPS_WORKSPACE` and does not commit protected annotations to the software repository.
