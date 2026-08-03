# Entity resolution evaluation report

**Governing issues:** [#37](https://github.com/fraware/neuroai-workbench/issues/37), tracking [#75](https://github.com/fraware/neuroai-workbench/issues/75)

## Boundary

Measured precision, recall, false-merge, false-split, and abstention counts are engineering behavioral metrics against annotated synthetic/public cases. They do not establish substantive entity identity, regulatory authority, or clinical correctness. Non-exact matches still require human confirmation. Issue [#37](https://github.com/fraware/neuroai-workbench/issues/37) layers 5–6 (relationship ranking / model-assisted suggestions) remain deferred until corpus metrics justify them.

## Corpora

| Corpus | Location | Size | Role |
| --- | --- | --- | --- |
| Blinded stub | `RESOLUTION_BENCHMARK_BLINDED.json` | 5 | Fast CI smoke |
| Public annotated subset | `RESOLUTION_BENCHMARK_PUBLIC_SUBSET.json` | ≥20 (21) | CI metrics |
| Public/synthetic scale | `RESOLUTION_BENCHMARK_PUBLIC_SCALE.json` | ≥200 (200) | Frozen train/dev/test partitions; multilingual, adversarial, relationship-ambiguity coverage |
| Ops annotated draft | ops `evaluation/entity/RESOLUTION_BENCHMARK_OPS_GE60.json` | ≥60 | Ops-gated only; protected annotations are never committed |

## Frozen partitions (scale corpus)

| Partition | Cases | Role |
| --- | --- | --- |
| train | 140 | Development / calibration against public synthetic labels |
| dev | 30 | Held-out tuning checks |
| test | 30 | Held-out reporting |

Partitions are frozen in-repo via `entities.corpus_scale` and regenerable deterministically. Ops ≥60 remains separate and ops-gated.

## Public coverage

The public subset and scale corpus span renames, acquisitions, parent/sub mentions, lab-name collisions, product-vs-company, sponsor-vs-site, abbreviations, historical IDs, CJK/Arabic/mixed-script variants, adversarial near-collisions, and relationship-ambiguity abstention labels using synthetic redistribution-safe strings only.

## How to measure

```python
from neuroai_workbench.entities import load_public_scale_corpus, run_blinded_benchmark
from tests.fixtures.entities.helpers import seed_entity_workspace

workspace = seed_entity_workspace(tmp_path)
report = run_blinded_benchmark(workspace, use_public_scale=True)  # or partition="test"
print(report["metrics"])  # precision, recall, false_merge_count, false_split_count, abstention_count
```

Ops-gated full ≥60 run requires `NEUROAI_OPS_WORKSPACE` and does not commit protected annotations to the software repository.

### Residual gaps (honest)

- Seed registry used in CI is tiny (two synthetic entities); scale-corpus case pass rate is not a claim of production resolver accuracy.
- Ops ≥60 protected annotations stay out of git; expanding that lane remains an ops-workspace task.
- No private neural data or protected capture bodies are present in these corpora.

See also [entities.md](../reference/entities.md).
