# Shadow refresh evaluation

## Purpose

Shadow refresh evaluation exercises the monitoring, comparison, development-disposition, delta, reopening, and product-generation workflow on a bounded source cohort. It does not publish a canonical observatory successor, modify assessments, or make substantive NeuroAI findings.

Parent epic: [#34](https://github.com/fraware/neuroai-workbench/issues/34). Core evaluation issue: [#43](https://github.com/fraware/neuroai-workbench/issues/43). Deferred governance issue: [#101](https://github.com/fraware/neuroai-workbench/issues/101).

## Authority boundary

Shadow refresh artifacts are marked `SHADOW_EVALUATION_NOT_CANONICAL`. They do not:

- mutate canonical observatory state;
- reopen or modify assessments automatically;
- establish regulatory authorization, clinical effectiveness, conformance, or institutional endorsement;
- authorize canonical publication;
- bypass operational authorization for network retrieval, protected archives, licensed evidence, or data export.

Engineering completeness does not authorize the first canonical successor release. Human review, owner sign-off, and release authority are deferred to #101.

## Protected operations path

Live shadow refresh runs use a protected workspace path:

```text
runs/shadow-refresh-YYYYMM/
```

Each run directory should contain, at minimum:

- `freeze-manifest.json` — frozen configuration hashes and cohort reference;
- `cohort/` — cohort definition copy or content-addressed reference;
- `captures/` — immutable retrieval records when an approved collector is used;
- `candidates/` — structured comparison candidates;
- `core-closure/` — typed retrieval outcomes, approved evaluation handoffs, candidate records, and core preparation reports;
- `refresh-candidate.json` — non-canonical refresh package when applicable;
- `evaluation-cycle-package.json` — full non-canonical cycle record;
- reconciled XLSX, DOCX, PDF, and dashboard products when generated.

The current compatibility layer serializes deterministic development dispositions through the monitoring decision-record format used by downstream delta code. Those records carry development-only rationale, `governance_layer_applied=false`, no substantive authority, and no release authority. #101 will add governance as a separate overlay without rewriting these records.

Example public scaffolding lives under `examples/shadow_refresh/`. Synthetic fixtures under `tests/fixtures/shadow_refresh/` support schema and engineering tests only.

## Operational authorization boundary

A live shadow refresh over real sources requires explicit operator authorization before:

- enabling network collection against non-synthetic URLs;
- accessing protected programme archives or licensed evidence;
- handing approved quarantine records into the evaluation workspace;
- exporting draft products outside the protected workspace.

These are access, custody, and execution controls. They are distinct from reviewer governance. Core software may execute without reviewer profiles, reviewer opinions, owner approval, or release authorization.

## Cohort definition

Frozen shadow cohorts use exact `source_id` manifests. Regex discovery is an optional helper and cannot write the freeze artifact.

- Synthetic rehearsal fixture: `examples/shadow_refresh/SHADOW_REFRESH_COHORT_v202608.json`.
- Ops-bound exact-ID freeze: `examples/shadow_refresh/SHADOW_REFRESH_COHORT_REVIEWED_v202608.json`.

The existing 25-source manifest retains its selection provenance and covers:

- PRIMA / Science Corporation;
- Synchron;
- Paradromics;
- Brain2Qwerty;
- FDA adaptive DBS and neurological regulatory surfaces;
- BrainGate2 T15 publications and programme sources;
- registries and EU medical-device sector pages;
- ownership, funding, safety, and supplier-dependency categories.

`run_shadow_refresh.py` loads `--cohort-manifest`, defaulting to the ops or example exact-ID manifest. Use `--discover-only` to emit non-authoritative candidates.

## Configuration freeze

Before retrieval, record SHA-256 identities for:

- source monitor registry;
- monitoring and reopening policies;
- approved collector configuration;
- workbench package;
- entity-resolution rules;
- extraction configuration;
- development-disposition configuration;
- governance state, recorded as `DEFERRED` with issue `#101` during core development.

Reviewer rosters and release-authority records are added only by the final governance overlay.

See `examples/shadow_refresh/SHADOW_REFRESH_FREEZE_MANIFEST_v202608.example.json`.

## Core engineering metrics

Core execution measures:

- retrieval attempts, successes, and typed failures;
- unchanged, representation-only, changed, and first-capture outcomes;
- candidate and development-disposition counts;
- entity-resolution and extraction disposition counts;
- delta compilation and deterministic application;
- predecessor immutability;
- reopening recommendation counts with zero assessment mutation;
- provenance closure and manifest integrity;
- publication reconciliation errors;
- operational cost by source class.

Candidate precision, recall, reviewer agreement, disagreement, adjudication time, and final release decisions belong to the deferred governance overlay in #101. Existing synthetic go/no-go fixtures remain non-canonical test assets and do not gate core development.

## Fixture commands

Validate the cohort fixture:

```python
from pathlib import Path
from neuroai_workbench.util import load_json
from neuroai_workbench.shadow_refresh import validate_shadow_refresh_cohort, validate_shadow_artifact_status

cohort = load_json(Path("examples/shadow_refresh/SHADOW_REFRESH_COHORT_v202608.json"))
assert not validate_shadow_refresh_cohort(cohort)
assert not validate_shadow_artifact_status(cohort)
```

Run the full offline engineering cycle:

```bash
python scripts/run_evaluation_cycle.py --mode offline
python -m pytest tests/unit/test_shadow_evaluation_cycle.py -q
```

## Live cohort collection

Allowlisted live retrieval over the 25-source exact-ID cohort is available only when both operational gates are set:

```bash
export NEUROAI_OPS_WORKSPACE=/path/to/NeuroAI_Operations_Starter_v0.1.0
export NEUROAI_LIVE_COLLECTION=1
python scripts/run_shadow_refresh.py --live --run-month YYYYMM
```

Behavior:

- loads the exact-ID cohort and never promotes regex discovery into authority;
- promotes eligible HTTP members into a one-shot evaluation due set;
- keeps `CONTROLLED_LOCAL_INPUT` and `network_access_required=false` records outside the HTTP collector;
- writes quarantine-only under `runs/shadow-refresh-YYYYMM/captures/quarantine/`;
- emits public counts and capture digests without capture bodies;
- remains `SHADOW_EVALUATION_NOT_CANONICAL`;
- keeps monitoring handoff disabled;
- writes no canonical successor;
- keeps CI network-free.

Do not commit protected capture bodies, quarantine trees, ops extracts, or licensed evidence into Git.

## Core preparation command

Prepare typed retrieval outcomes, approved evaluation handoffs, first-capture candidates, and bounded entity/extraction samples without activating governance:

```bash
export NEUROAI_OPS_WORKSPACE=/path/to/NeuroAI_Operations_Starter_v0.1.0
export NEUROAI_LIVE_COLLECTION=1   # required only for live HTTP_ERROR retries
# Successful quarantine records must already be APPROVED_FOR_HANDOFF.
python scripts/close_shadow_refresh_43.py --sample-size 5
```

The script writes under:

```text
runs/shadow-refresh-202608-live/core-closure/
```

Expected outputs include:

- `retrieval_outcomes.json`;
- `evaluation_handoff.json`;
- `change_candidates.json`;
- `entity_disposition_sample.json`;
- `extraction_disposition_sample.json`;
- `core-preparation-report.json`;
- `public-core-summary.json`.

It creates no reviewer profiles, opinions, human residual checklist, owner disposition, go/no-go authorization, or canonical release. Capture bodies remain protected.

## Core completion criteria for #43

Issue #43 tracks the non-canonical engineering cycle only. Human reviewers, owner sign-off, and release authority are deferred to #101 and do not block core development.

Core closure requires:

- typed outcomes for every attempted source, with retrieval failures kept distinct from findings;
- approved evaluation-only handoff for the selected capture sample;
- snapshot comparison and candidate generation;
- development-only dispositions sufficient to exercise deterministic downstream mechanics;
- non-canonical delta compilation and deterministic application;
- predecessor immutability verification;
- reopening analysis with zero assessment mutation;
- full-depth product generation and cross-format reconciliation;
- end-to-end provenance, manifests, hashes, and protected-data boundary verification.

Closing #43 does not authorize a canonical successor. All development successors remain non-canonical until #101 is completed.

## Full non-canonical evaluation cycle

The core operating sequence is:

```text
plan → live collect → quarantine → per-record APPROVED_FOR_HANDOFF → explicit handoff consent → record_snapshot
  → compare_snapshots → create_change_candidate → development disposition
  → build_refresh_candidate → compile delta → apply delta to a candidate successor
  → reopening analysis → full-depth products → reconciliation
```

Library: `neuroai_workbench.shadow_refresh.cycle`. Script: `scripts/run_evaluation_cycle.py`.

### Offline mode

```bash
python scripts/run_evaluation_cycle.py --mode offline
```

Offline mode uses fixture snapshot pairs and opens no network connection. It emits a candidate successor and full-depth products under the run output directory. Status remains `SHADOW_EVALUATION_NOT_CANONICAL`.

### Live mode

```bash
export NEUROAI_OPS_WORKSPACE=/path/to/NeuroAI_Operations_Starter_v0.1.0
export NEUROAI_LIVE_COLLECTION=1
python scripts/run_evaluation_cycle.py --mode live --approve-handoff --sample-size 5
```

Live mode requires both environment gates plus explicit `--approve-handoff`. The flag consents only to evaluation handoff of quarantine records already marked `APPROVED_FOR_HANDOFF`; it does not auto-approve pending captures. Collector monitoring handoff stays disabled.

### Boundaries retained

- Typed source outcomes never become automatic `FAIL` findings.
- Development dispositions exercise deterministic mechanics only and carry no substantive or release authority.
- Candidate successors remain outside `AUTHORIZED` and `PUBLISHED` gates.
- Reopening analysis does not mutate assessments.
- Human governance and canonical release authorization remain deferred to #101.
- CI stays network-free; live paths remain ops-gated.
