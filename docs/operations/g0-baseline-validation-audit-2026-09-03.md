# G0 baseline validation audit — 2026-09-03

Status: **EVIDENCE COLLECTION — NOT A G0 PASS DECISION**

This note records the controlled validation used to distinguish failures already present on the frozen Workbench baseline from failures introduced by the G0 pinned-transport repair. It is an operational evidence record. It does not authorize research-gate progression, substantive acceptance, publication, or a G0 state transition.

## Frozen baseline under test

- Repository: `fraware/neuroai-workbench`
- Baseline branch: `main`
- Baseline commit: `33414065e53c45221d29209ef4703b6d900781f7`
- Baseline commit subject: `Control: enforce fail-closed scan audit on live shadow captures (#265)`
- Baseline commit verification limitation: the commit record states that hosted CI, CodeQL, and Dependency Review terminated before runner steps and therefore claims no executed test or quality pass.

The audit branch `control/g0-baseline-validation-audit-2026-09-03` was created directly from that exact baseline commit. Its intended changes are documentation only: this evidence record and its documentation-map entry. No runtime code, test expectation, schema, dependency, workflow, or authorization rule is changed by the audit branch.

A pull-request CI run on this branch is therefore used as a controlled baseline execution of the repository's existing validation contract. Before any result is classified as baseline evidence, the PR diff must still be verified to contain documentation-only changes and its base must still resolve to the frozen baseline above.

## Transport-repair comparison point

The active transport repair is Workbench PR #267 (`fix/g0-pinned-urllib3-transport`). The comparison evidence head used here is:

- PR #267 base: `33414065e53c45221d29209ef4703b6d900781f7`
- PR #267 evidence head: `ff7d0d9418d8ab0875a9fe2700c261c6f578e1e4`
- CI run: `33736995045` — **failure**
- Source-health run: `33736995154` — **success**

For CI run `33736995045`, the quality job reached `ruff check .` successfully and failed at `ruff format --check .`. Both Python 3.11 and Python 3.12 jobs also reported failures in the validation sequence. Those failures are not classified here as pre-existing baseline defects or transport-repair regressions until the controlled baseline run provides comparison evidence.

The successful source-health run is bounded operational evidence about the source-health workflow at that PR head. It is not evidence of scientific truth, substantive source acceptance, publication authority, or G0 PASS.

## Classification protocol

After the documentation-only baseline PR executes, each failing check is classified using the smallest claim supported by direct comparison:

- **BASELINE-REPRODUCED** only when the same validation contract fails on the documentation-only baseline branch.
- **PR-INTRODUCED** only when the baseline execution passes the relevant contract and the transport-repair branch fails it, or when a direct differential isolates the transport change as the cause.
- **UNRESOLVED** when the available runs do not support either attribution.

A green check establishes only the mechanics covered by that check. It does not compensate for a failed governed check and does not establish a higher-level authority state.

## Gate and authority boundary

G0 remains blocked unless and until its complete acceptance criteria are satisfied and the designated controller explicitly records G0 as PASS. No statement in this audit can perform that reclassification.

G1/D1 remains paused while G0 is not controller-classified PASS. This audit does not authorize work on the paused research-contract deliverables.

The programme boundaries remain unchanged: collection is not substantive truth; candidate state is not acceptance; acceptance is not authorization; authorization is not publication; CI success is not publication authority.

## Evidence update discipline

Run identifiers, commit identities, changed-file scope, and check outcomes must be recorded from GitHub evidence. Later findings are appended or explicitly supersede earlier provisional classifications; historical evidence is not rewritten to manufacture a cleaner control record.

The next update to this note must record the documentation-only PR number, exact tested head/base identities, exact CI run identifiers, changed-file verification, and the resulting failure classification. If the baseline cannot execute, the inability to classify remains explicit.
