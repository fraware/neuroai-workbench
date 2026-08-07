# Cross-case assessment portfolio analysis

`neuroai-portfolio` compares completed NeuroAI assessments without rewriting them. It is intended for programme-level research questions such as:

- Which requirements are repeatedly weak across different system classes?
- Which requirements remain unassessed across the whole portfolio?
- Which modules have the highest concentration of partial or missing evidence?
- Where does one case differ materially from the others?
- Which requirements are consistently supported across all assessed systems?

## Run a comparison

Pass two or more completed assessment JSON files:

```bash
neuroai-portfolio \
  Brain2Qwerty.json \
  FDA_Adaptive_DBS.json \
  BrainGate2_T15.json \
  PRIMA.json \
  --output-dir portfolio-output
```

The command supports both historical three-pilot assessment records and the PRIMA/current assessment shape. Input files remain unchanged.

## Outputs

The output directory contains:

- `portfolio-analysis.json` — complete normalized analysis;
- `portfolio-matrix.csv` — one row per requirement and one status column per case;
- `portfolio-summary.md` — compact human-readable research summary.

The JSON includes per-case status/evidence/gap counts, module summaries, recurrent weaknesses, universal blind spots, common strengths, case outliers, and the complete requirement matrix.

## Status normalization

Historical spellings are mapped into a small comparison vocabulary:

- `PASS`
- `PARTIAL`
- `FAIL`
- `NOT_ASSESSED`
- `NOT_APPLICABLE`
- `UNRESOLVED`

The original source status is retained in each normalized finding. Unknown or empty statuses become `UNRESOLVED`; they are not guessed into another state.

## Recurrent weakness ranking

A requirement is considered weak for comparison when its recorded status is `FAIL`, `NOT_ASSESSED`, `PARTIAL`, or `UNRESOLVED`.

Ranking first favors requirements weak in more cases, then uses a simple severity weight (`FAIL` 4, `NOT_ASSESSED` 3, `PARTIAL` 2, `UNRESOLVED` 1) to order ties. This is a research-prioritization heuristic, not a conformance score.

`universal_blind_spots` is narrower: it contains only requirements explicitly recorded as `NOT_ASSESSED` in every case.

`common_strengths` contains only requirements recorded as `PASS` in every case.

## Outliers

The analysis flags two useful case-level patterns:

- `UNIQUE_FAIL`: one case records `FAIL` and no other case does;
- `PASS_WHERE_OTHERS_WEAK`: one case records `PASS` and every other available case is weak.

These flags identify useful comparison targets. They do not imply that one system is better or worse overall.

## Interpretation

Portfolio analysis is descriptive. Differences may reflect system architecture, evidence availability, assessment scope, public/private evidence boundaries, or instrument-version differences. Use the matrix to choose where to inspect source findings and evidence, not as a standalone ranking of systems.
