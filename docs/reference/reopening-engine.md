# Assessment reopening engine

The reopening engine connects adjudicated observatory delta operations to assessment dependency manifests and produces reviewable recommendations without modifying assessments automatically.

## Rule result versus human decision

Each recommendation records:

- `rule_reopening_effect` — deterministic output from dependency matching and triage defaults.
- `suggested_observatory_decision` — mapped observatory vocabulary when applicable.

Human confirmation is stored separately in a `REOPENING_HUMAN_CONFIRMATION` record with:

- `human_reopening_effect` — may confirm, modify, decline, or leave undetermined.
- `authority_claim` — named local workflow identity only; not authenticated institutional authority.
- `human_rationale` — required rationale distinct from the rule rationale.

Neither record performs an assessment mutation.

## Vocabulary alignment

Monitoring reopening effects:

- `NO_EFFECT`
- `METADATA_UPDATE_ONLY`
- `EVIDENCE_GAP_UPDATE`
- `REVIEW_REQUIRED`
- `PARTIAL_REASSESSMENT_REQUIRED`
- `FULL_REASSESSMENT_REQUIRED`
- `UNDETERMINED`

Observatory reopening decisions include:

- `NO_REOPENING_TRIGGER_IDENTIFIED`
- `UPDATE_REQUIRED_NO_ASSESSMENT_REOPEN`
- `METADATA_UPDATE_ONLY`
- `REOPEN_REQUIRED`
- `REOPENING_EXECUTED_RECORD_UPDATED_OPEN_CONDITIONS`

The engine maps rule effects to suggested observatory decisions for reconciliation only. Executed observatory states remain human-controlled.

## PRIMA v1.7 regression

`tests/fixtures/reopening/prima_v17_regression.json` locks expected strongest rule effects for the four reference assessments against `examples/observatory/canonical_successor_snapshot_v1.7.json`.

## Boundary

Dependency impact analysis under encoded rules does not decide scientific truth, clinical significance, legal effect, conformance, or final reassessment scope.
