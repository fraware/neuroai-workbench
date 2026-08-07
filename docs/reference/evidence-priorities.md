# Evidence collection priorities

`neuroai-portfolio` also writes an evidence-collection queue derived from the recorded cross-case assessment findings.

The queue is intended to answer a practical team question: after comparing the completed assessments, which requirements deserve evidence work next?

## Outputs

Alongside the portfolio JSON, matrix, and summary, the command writes:

- `evidence-priorities.json`
- `evidence-priorities.csv`
- `evidence-priorities.md`

Each priority records the requirement and module, P0/P1/P2 priority, urgency, recommended research focus, number of weak cases, zero-evidence cases, per-case statuses and evidence counts, and any gap actions already recorded in the source assessments.

## Ordering

The queue avoids an opaque aggregate score. It sorts lexicographically by:

1. requirement priority (`P0`, then `P1`, then `P2`);
2. universal blind spots first;
3. number of weak cases;
4. number of cases with zero cited evidence;
5. the existing portfolio weakness weight as a tie-breaker;
6. requirement ID for stable output.

This keeps the ordering inspectable and easy to change as the research programme learns more.

## Recommended focus

The queue assigns one of four practical research directions:

- `ESTABLISH_BASELINE_EVIDENCE` — every case records the requirement as `NOT_ASSESSED`;
- `RESOLVE_NEGATIVE_OR_CONTRADICTORY_EVIDENCE` — at least one case records `FAIL`;
- `EXPAND_DIRECT_EVIDENCE` — the requirement is weak and at least one case cites no direct evidence;
- `CLOSE_PARTIAL_EVIDENCE` — evidence exists, but recorded findings remain partial or unresolved.

These labels organize research work. They do not rescore systems or replace review of the underlying findings and sources.

## Small-team use

A useful weekly loop is:

1. run `neuroai-portfolio` over the current completed assessments;
2. take the top `NOW` items as the evidence-search backlog;
3. inspect the recorded per-case gap actions instead of rewriting them by hand;
4. feed newly verified public evidence into the observatory refresh;
5. rerun the portfolio after substantive assessment updates.
