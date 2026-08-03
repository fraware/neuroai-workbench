# Bounded offline extraction evaluation

Offline extraction evaluation covers preregistered metrics, default-off provider adapters, benchmark comparison, and immutable human disposition records for issue [#38](https://github.com/fraware/neuroai-workbench/issues/38) under epic [#34](https://github.com/fraware/neuroai-workbench/issues/34). No external provider execution is authorized by default.

## Preregistration

Status: `PREREGISTERED`.

### Metrics

field precision, field recall, citation accuracy, unsupported-attribution rate, entity-resolution precision, abstention rate, reviewer time saved.

### Stop conditions

Stop when unsupported-attribution or citation errors exceed thresholds, protected disclosure is not preventable, or a provider would be selected solely on aggregate score.

## Scope

- Provider adapters remain disabled by default. Only the test-only `fake-offline` adapter may run, and only when explicitly enabled.
- Evaluation compares at least two offline configurations against preregistered benchmark stubs in `benchmarks/source_extraction/`.
- Every proposed field must cite a request-local excerpt; evaluation rejects citation failures through the extraction contract.
- Human disposition records are immutable, hash-linked sidecars under `extraction_eval/`.
- No network or external provider calls are performed.

## Running offline comparison

```python
from neuroai_workbench.extraction import run_bounded_offline_evaluation

report = run_bounded_offline_evaluation()
assert report["selection_refused"] is True
assert report["recommended_config_id"] is None
```

## Provider configuration

```python
from neuroai_workbench.extraction import ExtractionProviderConfig, resolve_provider

config = ExtractionProviderConfig(
    config_id="CFG-FAKE-BASELINE",
    provider_id="fake-offline",
    model_id="fake-offline-baseline-v1",
    enabled=True,
)
provider = resolve_provider(config)
```

Disabled or unregistered providers raise `ProviderExecutionRefusedError`.

## Disposition workflow

1. `record_extraction_request` stores the bounded request.
2. `record_extraction_response` validates contract and disclosure controls.
3. `dispose_extraction_response` records a final human disposition (`ACCEPTED_AS_DRAFT`, `PARTIALLY_USED`, or `REJECTED`).
4. `verify_extraction_records` checks hash linkage and tamper evidence.

Disposition records do not mutate canonical observatory or assessment state.

## Selection boundary

Comparison reports per-metric trade-offs only. Aggregate scores are reported for transparency, but no configuration is recommended solely from aggregate score.

## Withheld claims

Evaluation scores synthetic benchmark stubs only. They do not establish provider superiority, extraction accuracy, legal authorization, or release authority.

See also [extraction.md](../reference/extraction.md).
