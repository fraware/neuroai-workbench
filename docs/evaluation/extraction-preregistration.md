# Extraction evaluation preregistration

Status: `PREREGISTERED` for issue [#38](https://github.com/fraware/neuroai-workbench/issues/38) under epic [#34](https://github.com/fraware/neuroai-workbench/issues/34). PR-13 enables offline comparison of explicitly enabled test-only provider configurations against benchmark stubs only. No external provider execution is authorized.

## Metrics

field precision, field recall, citation accuracy, unsupported-attribution rate, entity-resolution precision, abstention rate, reviewer time saved.

## Stop conditions

Stop when unsupported-attribution or citation errors exceed thresholds, protected disclosure is not preventable, or a provider would be selected solely on aggregate score.

## Boundary

PR-12 defines contract and preregistration. PR-13 executes bounded offline comparison without selecting a provider solely on aggregate score. See [extraction-evaluation.md](extraction-evaluation.md).
