# Entity resolution evaluation report

## Scope

Engineering behavioral evaluation of entity-resolution proposals against annotated cases. Outcomes do not establish substantive accuracy, regulatory authorization, or conformance.

## Corpora

| Corpus | Location | Status |
| --- | --- | --- |
| Synthetic blinded stub | `resources/entities/RESOLUTION_BENCHMARK_BLINDED.json` | CI fixture (5 cases) |
| Ops annotated set | `$NEUROAI_OPS_WORKSPACE/evaluation/entity/` | Protected ops; ≥50 cases when mined |
| Public ID subset | shadow cohort public IDs under `examples/shadow_refresh/` | Redistribution-safe IDs only |

## Metrics

When `expected.entity_id` / abstain annotations are present, `run_blinded_benchmark` reports:

- precision / recall
- top-k hit rate
- abstention count
- false-merge / false-split counts

Without annotations, only case pass rate is reported (precision/recall remain null).

## Human confirmation

Non-exact matches still require human confirmation (`auto_confirmed=false`). Software proposals never mutate canonical entity registries.

## Reproduction

```powershell
python -c "from pathlib import Path; from neuroai_workbench.entities.benchmark import run_blinded_benchmark; print(run_blinded_benchmark(Path('workspaces/entity-bench')))"
```

Ops-gated mining and annotated evaluation remain local under `NEUROAI_OPS_WORKSPACE`.
