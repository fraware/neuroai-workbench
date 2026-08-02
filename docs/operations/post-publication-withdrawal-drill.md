# Post-publication withdrawal drill

This runbook exercises controlled withdrawal of a published observatory successor release or public assessment artifact after publication. It is documentation only. No automated withdrawal is authorized by this drill.

## Purpose

Verify that the programme can:

1. Detect a material post-publication defect or boundary violation.
2. Preserve immutable predecessor and successor records.
3. Communicate withheld claims and unresolved risks without silent overwrite.
4. Coordinate human decisions across security, methodology, data governance, accessibility, domain, and affected-community tracks.

Passing this drill establishes procedural readiness only. It does not prove that a withdrawal was correct, complete, or authorized.

## Preconditions

- A published successor release or public artifact exists with recorded predecessor identity, checksums, and withheld-claims appendix.
- Independent review disposition records exist or their absence is explicitly documented as a blocker.
- Incident route, evidence custodians, and decision authorities are named outside the application.

## Drill roles

| Role | Responsibility |
|---|---|
| Incident coordinator | Declares drill start, preserves timestamps, ensures records are append-only |
| Evidence custodian | Confirms artifact identity, checksums, and export copies |
| Decision authority | Records human withdrawal disposition; does not rely on software auto-authorization |
| Review track owners | Confirm track-specific residual risks and communication boundaries |
| Communications owner | Drafts public or access-controlled withdrawal language |

## Phase 1 — Detect and freeze

1. Record the triggering signal: security finding, methodological error, data-governance breach, accessibility barrier, domain challenge, or community concern.
2. Freeze the affected release scope artifact and record its SHA-256 digest.
3. Stop treating the published artifact as current for new institutional pilots until human disposition is recorded.
4. Append an incident event; do not mutate historical release records in place.

Checklist:

- [ ] Triggering signal documented with evidence references.
- [ ] Scope artifact frozen and digest recorded.
- [ ] Predecessor release identity preserved.
- [ ] No in-place edit of historical findings or dispositions.

## Phase 2 — Assess impact

1. Identify affected systems, populations, endpoints, jurisdictions, and evidence-freeze boundaries.
2. Classify whether the issue is metadata-only, evidence-gap, review-required, partial reassessment, or full reassessment.
3. Separate capability, authorization, deployment, commercial availability, and conformance states in all language.
4. List downstream generated products (workbooks, documents, PDFs, dashboards) that require republication or withdrawal notice.

Checklist:

- [ ] Exact system and context boundaries preserved in all records.
- [ ] Materiality and reopening effect classified by a human reviewer.
- [ ] Generated products inventoried against canonical records.
- [ ] Missing or inaccessible evidence not converted into automatic failure.

## Phase 3 — Coordinate review tracks

For each required track, record whether the withdrawal trigger affects prior independent review conclusions.

| Track | Drill question |
|---|---|
| Security | Does the defect change the security boundary or deployment posture? |
| Methodology | Does the defect change claim boundaries or requirement interpretation? |
| Data governance | Does the defect affect protected-evidence handling or disclosure? |
| Accessibility | Does the defect affect primary user access or report comprehension? |
| Domain | Does the defect change substantive conclusions or strongest supported claims? |
| Affected community | Does the defect change burden, remedy, or public-facing information? |

Checklist:

- [ ] Each track owner consulted or absence documented as a blocker.
- [ ] New append-only disposition or successor note recorded where conclusions change.
- [ ] Dissent and abstention preserved.
- [ ] No track owner replaced by automated summary output.

## Phase 4 — Withdrawal disposition

1. Record a human withdrawal disposition: `WITHDRAW`, `SUPERSEDE`, `RESTRICT_DISTRIBUTION`, or `MONITOR_ONLY`.
2. Name authority basis, scope, conditions, prohibited inferences, and expiry where applicable.
3. Keep `release_authorization_performed: false` on all software-generated records.
4. Create successor records instead of overwriting predecessor release metadata.

Checklist:

- [ ] Withdrawal disposition recorded by named decision authority.
- [ ] Conditions and prohibited inferences explicit.
- [ ] Canonical machine-readable records updated through successor workflow, not silent edit.
- [ ] Software did not auto-authorize republication.

## Phase 5 — Communicate and retain

1. Publish or access-control the withdrawal notice according to disclosure rules.
2. Update Appendix E withheld claims if outward-facing language changes.
3. Retain all predecessor bytes, event chains, and review records for provenance.
4. Schedule remediation PRs with owners, priorities, and closure conditions.

Checklist:

- [ ] Withdrawal notice bounded and free of unsupported institutional claims.
- [ ] Withheld claims appendix reviewed.
- [ ] Export copies tracked under retention and destruction rules.
- [ ] Remediation items linked to findings register entries.

## Phase 6 — Restore or supersede

1. If republication is required, generate a new successor release from canonical records.
2. Re-run independent review acceptance for the new scope before any institutional-pilot readiness language.
3. Reconcile generated products mechanically against canonical records.
4. Close the drill with an explicit statement of what was and was not established.

Checklist:

- [ ] New successor release preserves predecessor linkage.
- [ ] Independent review tracks re-evaluated for the new scope.
- [ ] Generated products reconcile with canonical records.
- [ ] Drill closure statement lists residual human blockers.

## Explicit non-establishments

This drill does not establish:

- That a withdrawal was legally sufficient in any jurisdiction.
- That all affected users or institutions received notice.
- That the root cause is fully remediated.
- That republication is authorized or safe.
- Security acceptance, conformance, or institutional authority.

## Related documents

- [Independent review acceptance](independent-review-acceptance.md)
- [Release process](release-process.md)
- [Pilot runbook](pilot-runbook.md)
- Issue #10 — Commission independent security, accessibility, and methodological review
- Issue #34 — Operationalize the NeuroAI observatory programme
