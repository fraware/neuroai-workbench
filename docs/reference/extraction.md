# Bounded observatory source extraction

The offline extraction contract freezes disclosure policy, citation requirements, and preregistered benchmark stubs for issue [#38](https://github.com/fraware/neuroai-workbench/issues/38) under epic [#34](https://github.com/fraware/neuroai-workbench/issues/34). Default-off provider adapters and offline benchmark comparison are covered in [extraction-evaluation.md](../evaluation/extraction-evaluation.md). No external provider calls are performed by the default workbench.

## Contract surfaces

Schemas under `src/neuroai_workbench/resources/extraction/` and validation under `src/neuroai_workbench/extraction/`.

## Citation rule

Every non-abstained proposed field must cite a request-local excerpt with matching hash and byte offsets. Unsupported fields belong in `abstentions`.

## Disclosure rule

Default policy `EXTRACTION_DEFAULT_v1` allows only `PUBLIC_SYNTHETIC` and `PUBLIC_SOURCE_EXCERPT`. Protected classes are default-deny.

## Benchmark registry

Preregistered classic stubs live in `benchmarks/source_extraction/MANIFEST.json`. The public/synthetic scale pack (≥150 cases) is `CORPUS_PUBLIC_SCALE.json` with `MANIFEST_SCALE.json`. `CapturedResponseReplayProvider` is the primary accuracy lane; `fake-offline` remains `CONTRACT_FIXTURE_NON_ACCURACY`. See [extraction-evaluation.md](../evaluation/extraction-evaluation.md).

## Offline evaluation

Evaluation compares at least two explicitly enabled offline configurations against preregistered benchmark stubs. Aggregate scores are reported but no configuration is recommended solely on aggregate score. See [extraction-evaluation.md](../evaluation/extraction-evaluation.md).

## Authority boundary

Extraction output proposes records only. See [model-assistance-boundary.md](../security/model-assistance-boundary.md) and [ADR 0005](../adr/0005-controlled-language-model-assistance.md).
