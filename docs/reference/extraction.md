# Bounded observatory source extraction

PR-12 freezes the offline extraction contract, disclosure policy, and preregistered benchmark stubs for issue [#38](https://github.com/fraware/neuroai-workbench/issues/38). PR-13 adds default-off provider adapters, offline benchmark comparison, and immutable human disposition records under epic [#34](https://github.com/fraware/neuroai-workbench/issues/34). No external provider calls are performed.

## Contract surfaces

Schemas under `src/neuroai_workbench/resources/extraction/` and validation under `src/neuroai_workbench/extraction/`.

## Citation rule

Every non-abstained proposed field must cite a request-local excerpt with matching hash and byte offsets. Unsupported fields belong in `abstentions`.

## Disclosure rule

Default policy `EXTRACTION_DEFAULT_v1` allows only `PUBLIC_SYNTHETIC` and `PUBLIC_SOURCE_EXCERPT`. Protected classes are default-deny.

## Benchmark registry

Preregistered stubs live in `benchmarks/source_extraction/`.

## Offline evaluation

PR-13 compares at least two explicitly enabled offline configurations against preregistered benchmark stubs. Aggregate scores are reported but no configuration is recommended solely on aggregate score. See [extraction-evaluation.md](../evaluation/extraction-evaluation.md).

## Authority boundary

Extraction output proposes records only. See [model-assistance-boundary.md](../security/model-assistance-boundary.md) and [ADR 0005](../adr/0005-controlled-language-model-assistance.md).
