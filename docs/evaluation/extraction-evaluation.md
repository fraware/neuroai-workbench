# Bounded offline extraction evaluation

Offline extraction evaluation covers preregistered metrics, default-off provider adapters, benchmark comparison, and immutable human disposition records for issue [#38](https://github.com/fraware/neuroai-workbench/issues/38) under epic [#34](https://github.com/fraware/neuroai-workbench/issues/34). No external provider execution is authorized by default.

## Preregistration

Status: `PREREGISTERED`.

### Metrics

field precision, field recall, citation accuracy, unsupported-attribution rate, entity-resolution precision, abstention rate, reviewer time saved.

### Stop conditions

Stop when unsupported-attribution or citation errors exceed thresholds, protected disclosure is not preventable, or a provider would be selected solely on aggregate score.

## Corpora

| Corpus | Location | Size | Role |
| --- | --- | --- | --- |
| Classic stubs | `benchmarks/source_extraction/MANIFEST.json` + `fixtures/` | 3 | CI contract smoke |
| Public/synthetic scale pack | `benchmarks/source_extraction/CORPUS_PUBLIC_SCALE.json` | ≥150 (150) | Annotated regulatory / trial / publication / company (+ funding, safety, contradictory) cases |
| Scale manifest | `benchmarks/source_extraction/MANIFEST_SCALE.json` | 150 fixtures | Preregistered loader for scale evaluation |
| Concrete fixture subset | `benchmarks/source_extraction/fixtures/scale/` | 28 pairs (56 files) | Classic path stubs for a balanced subset; remaining cases use `corpus:` virtual stubs |
| Index fixture | `tests/fixtures/extraction/REAL_SOURCE_CORPUS_MANIFEST.json` | pointer | Points at scale pack + evaluation lanes |

## Evaluation lanes

- **Primary accuracy lane:** `CapturedResponseReplayProvider` (`captured-response-replay`). Requires supplied captured responses; does not call a network provider.
- **Contract fixture lane:** `fake-offline`, labeled `CONTRACT_FIXTURE_NON_ACCURACY` only.
- Live-provider eval remains optional, disclosure-gated, and disposition-recorded (ADR 0005).

## Scope

- Provider adapters remain disabled by default. Only explicitly enabled offline adapters may run.
- Evaluation compares at least two offline configurations against preregistered benchmark stubs / scale corpus.
- Every proposed field must cite a request-local excerpt; evaluation rejects citation failures through the extraction contract.
- Human disposition records are immutable, hash-linked sidecars under `extraction_eval/`.
- No network or external provider calls are performed.

## Running offline comparison

```python
from neuroai_workbench.extraction import run_bounded_offline_evaluation, run_scale_corpus_evaluation

report = run_bounded_offline_evaluation()  # classic 3-fixture contract lane
assert report["selection_refused"] is True

scale = run_scale_corpus_evaluation()  # ≥150 synthetic/public-safe cases
assert scale["fixture_count"] >= 150
assert scale["primary_accuracy_lane"] == "captured-response-replay"
```

## Provider configuration

```python
from neuroai_workbench.extraction import ExtractionProviderConfig, resolve_provider

config = ExtractionProviderConfig(
    config_id="CFG-FAKE-BASELINE",
    provider_id="fake-offline",
    model_id="fake-offline-baseline-v1",
    enabled=True,
    notes="CONTRACT_FIXTURE_NON_ACCURACY",
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

Evaluation scores synthetic / public-safe benchmark fixtures only. They do not establish provider superiority, extraction accuracy, legal authorization, or release authority.

### Residual gaps (honest)

- Compact corpus pack reaches ≥150 annotated cases; only 28 fixture pairs are materialized as individual files (remaining resolve via corpus-pack virtual stubs).
- Captured-response-replay accuracy still needs separately supplied captured model responses; the scale pack annotations alone are not live-model evidence.
- Reviewer correction rate / reviewer time saved remain non-measurable in fully offline bounded evaluation.
- No private neural data or protected capture bodies are committed.

See also [extraction.md](../reference/extraction.md).
