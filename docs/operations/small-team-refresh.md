# Small-team observatory refresh

`neuroai-refresh` is the primary operator command for the small NeuroAI research team. It wraps the existing live evaluation-cycle engine and produces the information needed to decide what to inspect next.

The command is intentionally practical: one run plans due sources, performs live collection, hands eligible captures into the evaluation workspace, compares snapshots, creates change candidates, builds a non-canonical v2.3 development successor, computes assessment-impact recommendations, and regenerates the full publication set.

## Run it

A real predecessor JSON is required. The command does not silently fall back to the synthetic CI fixture.

```bash
neuroai-refresh \
  --ops-workspace /path/to/Operations_Starter \
  --predecessor /path/to/current-release.json
```

`NEUROAI_OPS_WORKSPACE` may be used instead of `--ops-workspace`.

The command itself is the explicit opt-in to live collection, so operators do not also need to export `NEUROAI_LIVE_COLLECTION=1`. Lower-level collector APIs retain their own live-network gate.

By default the run uses:

- the operations source registry at `01_CONFIG/source_monitor_registry_v1.5.json`;
- a 25-source sample, matching the reviewed refresh cohort;
- refresh version `v2.3.0-dev`;
- the current UTC date as the evidence cutoff;
- a timestamped run directory under `runs/v23-refresh/`.

Override paths or the sample size only when the research task requires it:

```bash
neuroai-refresh \
  --ops-workspace /path/to/Operations_Starter \
  --predecessor /path/to/current-release.json \
  --sample-size 25 \
  --output-dir /path/to/run-output
```

## What you get

Every completed run writes the detailed `evaluation-cycle-report.json` produced by the existing cycle engine and a compact `UPDATE_SUMMARY.json` for daily use.

The compact summary answers five questions:

1. How many sources were checked?
2. Which sources changed?
3. Which sources need retrieval attention?
4. Which candidate changes or assessment impacts need inspection?
5. Where are the candidate successor and regenerated outputs?

The terminal view is deliberately short. Use `--json` for machine-readable stdout.

## Capture handoff

The command consents to handoff of captures already marked `APPROVED_FOR_HANDOFF`. It does not invent or silently approve evidence. If a run obtains fresh successful captures but none are eligible for handoff, `UPDATE_SUMMARY.json` makes that the first next action: approve the successful captures you want to use and rerun the refresh.

For a five-person team this is the only remaining manual boundary in the normal live path. A later #120 improvement may collapse validation and trusted-team handoff into one explicit run option if repeated operation shows that the extra pass provides no useful review value.

## Interpretation

The refresh output is a development candidate, not a publication event. The practical rule is simple:

- use the candidate successor and publication set to inspect the new state;
- use the source-attention list to repair failed retrievals;
- use assessment-impact recommendations to decide whether any completed assessment deserves human re-review;
- keep the current predecessor untouched until the team intentionally promotes a successor.

Completed assessments are not automatically edited by `neuroai-refresh`.

## Recommended team loop

For routine work:

1. run `neuroai-refresh`;
2. read the terminal summary;
3. inspect only changed or attention-needed sources;
4. review any assessment-impact recommendations;
5. use the regenerated XLSX/DOCX/PDF/HTML views for analysis;
6. project the accepted public data subset to `neuroai-observatory-data` when the candidate is ready.

This workflow is the preferred path for issue #120. The lower-level `neuroai-monitor` commands remain available for debugging, targeted source work, and custom experiments.
