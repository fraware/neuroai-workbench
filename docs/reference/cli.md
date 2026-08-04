# CLI reference

Use `neuroai-workbench <command> --help` for complete arguments.

| Command | Purpose |
|---|---|
| `init` | Create a local workspace. |
| `doctor` | Check runtime and workspace state. |
| `serve` | Run the local browser application. |
| `case-create` | Create a blank v4.2 case. |
| `case-import` | Import a valid v4.2 assessment. |
| `case-list` | List controlled cases. |
| `case-show` | Export assessment JSON to stdout or a file. |
| `case-save` | Replace assessment JSON, optionally requiring validity. |
| `validate` | Run schema and semantic controls. |
| `summary` | Report counts and mechanical P0 blockers. |
| `snapshot` | Freeze a case-state copy. |
| `evidence-add` | Register evidence bytes and optionally link an evidence object. |
| `evidence-verify` | Recompute registered evidence digests. |
| `events-verify` | Verify the event hash chain. |
| `bundle` | Create a controlled ZIP export. |
| `migrate` | Additively migrate v4.1.2 to v4.2. |
| `programme-adapt` | Convert a programme completed-assessment record into native v4.2 with an adapter report. |
| `report` | Render a deterministic Markdown assessment report. |
| `assist-request` | Create a bounded provider-neutral model-assistance request. |
| `assist-record` | Validate and record a structured model response. |
| `assist-dispose` | Record human acceptance, partial use, rejection, or pending review. |
| `assist-apply` | Apply an accepted assistance proposal through an ordinary assessment edit. |
| `assist-verify` | Verify assistance request, response, and disposition hashes and references. |
| `compare` | Compare existing finding states across cases. |

Every command that reports validity includes a boundary statement. Scripts must preserve that statement in downstream reporting.

## Collaborative review

```bash
neuroai-workbench review-assign WORKSPACE CASE REVIEWER DOMAIN_REVIEWER --scope FINDING:NK-01-R01 --actor lead-assessor
neuroai-workbench review-supersede WORKSPACE CASE ASSIGNMENT_ID REVIEWER_2 METHODS_REVIEWER \
  --scope FINDING:NK-01-R01 --rationale "Transfer the methods review." --actor lead-assessor
neuroai-workbench review-revoke WORKSPACE CASE ASSIGNMENT_ID \
  --rationale "Reviewer availability ended." --actor REVIEWER
neuroai-workbench review-submit WORKSPACE CASE REVIEWER FINDING NK-01-R01 DISAGREE --rationale "Bound the claim" --evidence-id EV-PR-001
neuroai-workbench review-dispose WORKSPACE CASE STATEMENT_ID PARTIALLY_ACCEPTED --rationale "Edit separately" --actor lead-assessor
neuroai-workbench review-apply WORKSPACE CASE STATEMENT_ID --expected-assessment-sha256 CURRENT_SHA256 --patches-file patches.json --actor lead-assessor
neuroai-workbench review-appeal-file WORKSPACE CASE STATEMENT_ID MINORITY_REPORT \
  --grounds "The minority position remains material." \
  --requested-resolution "Preserve the disagreement in the final record." \
  --appellant-id REVIEWER
neuroai-workbench review-appeal-dispose WORKSPACE CASE APPEAL_ID DENIED \
  --rationale "The original disposition stands; dissent remains recorded." --actor lead-assessor
neuroai-workbench review-appeal-list WORKSPACE CASE
neuroai-workbench review-verify WORKSPACE CASE
neuroai-workbench review-report WORKSPACE CASE --output review.md
neuroai-workbench gap-report --assessment assessment.json --output gaps.md
```

Review records are attributable local workflow objects. They do not authenticate identities, confer institutional authority, or mutate assessment findings. Accepted proposals apply only through an explicit ordinary assessment edit (`review-apply` / `assist-apply`).

## Protected-evidence metadata exchange

```bash
neuroai-workbench exchange-create WORKSPACE CASE \
  --evidence-id EV-PR-001 --gap-id GAP-PR-001 \
  --recipient "Evidence custodian" \
  --purpose "Resolve a controlled evidence gap" \
  --requested-material "Access protocol and immutable digest"

neuroai-workbench exchange-record WORKSPACE CASE REQUEST_ID AVAILABLE_UNDER_CONDITIONS \
  --holder "Evidence custodian" --materials-json materials.json
neuroai-workbench exchange-verify WORKSPACE CASE REQUEST_ID
neuroai-workbench exchange-report WORKSPACE CASE REQUEST_ID --output exchange.md
```

These commands exchange metadata and holder representations only. They do not transport evidence bytes, create disclosure duties, grant access, or verify material held outside the workbench.
