# Shadow refresh evaluation

## Purpose

Shadow refresh evaluation rehearses the monitoring, review, and delta workflow on a bounded source cohort without publishing a canonical observatory successor, modifying assessments, or making substantive NeuroAI findings. It validates operations only.

Parent epic: [#34](https://github.com/fraware/neuroai-workbench/issues/34). Evaluation issue: [#43](https://github.com/fraware/neuroai-workbench/issues/43).

## Authority boundary

Shadow refresh artifacts are marked `SHADOW_EVALUATION_NOT_CANONICAL`. They do not:

- mutate canonical observatory state;
- reopen or modify assessments automatically;
- establish regulatory authorization, clinical effectiveness, or conformance;
- authorize live network retrieval over protected or archive sources without human approval.

Passing go/no-go thresholds in a synthetic or shadow run does not authorize the first canonical successor release.

## Protected operations path

Live shadow refresh runs use a protected workspace path:

```text
runs/shadow-refresh-YYYYMM/
```

Each run directory should contain, at minimum:

- `freeze-manifest.json` — frozen configuration hashes and cohort reference;
- `cohort/` — cohort definition copy or content-addressed reference;
- `captures/` — immutable retrieval records when an approved collector is used;
- `candidates/` and `adjudications/` — structured review artifacts;
- `refresh-candidate.json` — non-canonical refresh package when applicable;
- `go-no-go-metrics.json` — computed evaluation metrics;
- `evaluation-report.md` — human-readable summary and unresolved risks.

Example public scaffolding lives under `examples/shadow_refresh/`. Synthetic fixtures under `tests/fixtures/shadow_refresh/` support schema and metrics stub tests only.

## Human approval requirement

A live shadow refresh over 20–30 real sources requires explicit human approval before:

- enabling network collection against non-synthetic URLs;
- accessing protected programme archives or licensed evidence;
- exporting draft publication products outside the protected workspace;
- comparing reopening recommendations against external expert judgment at scale.

Software scaffolding can validate records and compute rehearsal metrics. It cannot substitute for those approvals.

## Cohort definition

Frozen shadow cohorts are **reviewed exact `source_id` manifests**. Regex discovery is an optional helper only and cannot write the freeze artifact.

- Synthetic rehearsal fixture: `examples/shadow_refresh/SHADOW_REFRESH_COHORT_v202608.json` (25 synthetic URLs under `https://synthetic.example/neuroai/shadow/...`).
- Reviewed ops-bound freeze: `examples/shadow_refresh/SHADOW_REFRESH_COHORT_REVIEWED_v202608.json` (25 exact registry IDs with human `coverage_label`, `selection_rationale`, `reviewer`, and `reviewed_at`).

Each member requires `source_id`, `coverage_label` (equal to `cohort_category`), and review provenance. Categories cover:

- PRIMA / Science Corporation (not Meta research pages);
- Synchron;
- Paradromics;
- Brain2Qwerty;
- FDA adaptive DBS / neurological regulatory surfaces (not supplier neuromodulation pages);
- BrainGate2 T15 publications and programme sources;
- registries and EU medical-device sector pages (not mislabeled as SAFETY_SUPPLIER);
- ownership, funding, safety, and supplier-dependency categories.

`run_shadow_refresh.py` loads `--cohort-manifest` (defaulting to the reviewed ops or examples path). Use `--discover-only` to emit non-authoritative regex candidates.

## Configuration freeze

Before retrieval, record a freeze manifest that captures SHA-256 hashes for:

- source monitor registry;
- monitoring and reopening policies;
- approved collector configuration;
- workbench package identity;
- entity-resolution rules;
- extraction configuration;
- reviewer roster.

See `examples/shadow_refresh/SHADOW_REFRESH_FREEZE_MANIFEST_v202608.example.json`.

## Go/no-go metrics

The metrics schema and `compute_go_no_go_metrics()` stub measure:

- retrieval success and failure rates;
- unchanged versus changed capture proportions;
- candidate precision, recall, and unsupported-candidate rate;
- entity-resolution precision;
- reviewer agreement and adjudication time;
- model assistance time saved and errors introduced;
- reopening precision and false-positive rate;
- provenance closure;
- publication reconciliation errors;
- operational cost by source class.

Threshold defaults live in `DEFAULT_GO_NO_GO_THRESHOLDS`. Recommendations are `GO`, `NO_GO`, or `INCOMPLETE` based on threshold comparison. Synthetic stub output remains non-canonical.

## Commands (scaffolding)

Validate the cohort fixture:

```python
from pathlib import Path
from neuroai_workbench.util import load_json
from neuroai_workbench.shadow_refresh import validate_shadow_refresh_cohort, validate_shadow_artifact_status

cohort = load_json(Path("examples/shadow_refresh/SHADOW_REFRESH_COHORT_v202608.json"))
assert not validate_shadow_refresh_cohort(cohort)
assert not validate_shadow_artifact_status(cohort)
```

Compute metrics from synthetic run results:

```python
from pathlib import Path
from neuroai_workbench.util import load_json
from neuroai_workbench.shadow_refresh import compute_go_no_go_metrics

results = load_json(Path("tests/fixtures/shadow_refresh/synthetic_run_results.json"))
metrics = compute_go_no_go_metrics(results)
```

## Live cohort collection (ops-gated)

Allowlisted live retrieval over the reviewed 25-source cohort is available only when both gates are set:

```bash
export NEUROAI_OPS_WORKSPACE=/path/to/NeuroAI_Operations_Starter_v0.1.0
export NEUROAI_LIVE_COLLECTION=1
python scripts/run_shadow_refresh.py --live --run-month YYYYMM
```

Behavior:

- Loads the reviewed exact-ID cohort (never regex freeze).
- Promotes HTTP `not_due` members into an evaluation due set for one-shot retrieval; `CONTROLLED_LOCAL_INPUT` / `network_access_required=false` stay manual and never enter the HTTP collector.
- Writes quarantine-only under `runs/shadow-refresh-YYYYMM/captures/quarantine/` in the ops workspace.
- Emits public summary counts, capture digests (hashes/sizes/status only), and go/no-go metrics.
- Remains `SHADOW_EVALUATION_NOT_CANONICAL`; monitoring handoff stays disabled; no canonical successor is published.
- CI stays network-free. The integration test `tests/integration/test_ops_live_cohort.py` skips unless `NEUROAI_LIVE_COLLECTION=1`.

Do not commit protected capture bodies, quarantine trees, or ops ZIP extracts into git.

## Wave 2 closure command (ops-gated)

Software/ops steps that do not forge dual-human review completions:

```bash
export NEUROAI_OPS_WORKSPACE=/path/to/NeuroAI_Operations_Starter_v0.1.0
export NEUROAI_LIVE_COLLECTION=1   # required only for HTTP_ERROR retries
# Quarantine successes must already be APPROVED_FOR_HANDOFF (per-record); this script does not auto-approve.
python scripts/close_shadow_refresh_43.py --sample-size 5
```

This writes evaluation-only artifacts under `runs/shadow-refresh-YYYYMM-live/wave2-closure/` (handoff of pre-approved quarantine records only, first-capture candidates, dual-review scaffolding, offline entity/extraction dispositions, `go-no-go-metrics.json`, formal disposition). Public digests/metrics may land in `examples/shadow_refresh/SHADOW_REFRESH_WAVE2_PUBLIC_SUMMARY_v202608.json`. Capture bodies stay in the ops workspace.

## Residual blockers for closing #43

Observed live cohort collection and Wave 2 software scaffolding are evaluation evidence only. Closing [#43](https://github.com/fraware/neuroai-workbench/issues/43) still requires:

- dual human review sample opinions recorded against observed captures/candidates (scaffolding exists; completions must be human);
- formal `GO` only after dual review (software records `WITHHELD` / `NO_GO` until then);
- protected archive and network access approvals where applicable (#44);
- human decisions on unresolved retrieval outcomes (for example ACCESS_DENIAL / URL replacement) without converting them into `FAIL` findings.

Independent security, accessibility, and methodological review (#10) is an optional recommended follow-up for institutional-pilot readiness language. It is not a release blocker for successor `AUTHORIZED` or `PUBLISHED` gates.

## Wave 3 — Non-canonical full evaluation cycle

Extends quarantine-only live collection into a scripted evaluation operating cycle:

```text
plan → live collect → quarantine → per-record APPROVED_FOR_HANDOFF → --approve-handoff consent → record_snapshot
  → compare_snapshots → create_change_candidate → adjudicate
  → build_refresh_candidate → compile_adjudicated_delta → apply_delta (candidate successor)
  → reopening analysis → depth=full publications
```

Library: `neuroai_workbench.shadow_refresh.cycle`. Script: `scripts/run_evaluation_cycle.py`.

### Offline (CI-safe, default)

```bash
python scripts/run_evaluation_cycle.py --mode offline
python -m pytest tests/unit/test_shadow_evaluation_cycle.py -q
```

Uses fixture snapshot pairs (no network, no `NEUROAI_LIVE_COLLECTION`). Emits a candidate successor and full-depth publication products under the run output directory. Status remains `SHADOW_EVALUATION_NOT_CANONICAL`.

### Live (ops-gated)

```bash
export NEUROAI_OPS_WORKSPACE=/path/to/NeuroAI_Operations_Starter_v0.1.0
export NEUROAI_LIVE_COLLECTION=1
# After live collect, approve quarantine records per-record (APPROVED_FOR_HANDOFF), then:
python scripts/run_evaluation_cycle.py --mode live --approve-handoff --sample-size 5
```

Requires both env gates plus explicit `--approve-handoff`. That flag consents only to evaluation-only handoff of quarantine records already `APPROVED_FOR_HANDOFF`; it does not auto-approve pending captures. Collector monitoring handoff stays disabled. Capture bodies remain in the ops workspace; do not commit them.

### Boundaries retained

- Per-source outcome taxonomy includes success, 304, changed / no-change, redirect failure, access denial, robots/terms, JS-render, content-type, timeout, withdrawal, and URL replacement needed — typed outcomes only, never automatic `FAIL` findings.
- Adjudication scaffolding does not forge dual human review or formal `GO`.
- Candidate successor is not an `AUTHORIZED` / `PUBLISHED` observatory release (#41 remains separate).
- Reopening analysis does not mutate assessments.
- CI stays network-free; live path is ops-gated only.
