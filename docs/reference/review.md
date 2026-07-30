# Collaborative review records

The workbench can record local reviewer assignments, review statements, disagreements, and human dispositions without changing the assessment automatically.

## Boundary

The reference workflow records a claimed reviewer identifier and role. It does not authenticate a person, verify an institutional appointment, or confer legal or scientific decision authority. Authentication belongs to a separate institutional deployment architecture.

## Roles

Supported roles include lead assessor, decision authority, domain reviewer, methods reviewer, security reviewer, legal or regulatory reviewer, participant representative, and observer. Each assignment has an explicit typed scope such as `ASSESSMENT:*` or `FINDING:NK-01-R01`.

## Statements

A reviewer statement targets an assessment, finding, claim, decision, or gap. It records the reviewer position, rationale, evidence references, conditions, proposed change, assessment hash, and assignment linkage. Positions include agreement, conditional agreement, disagreement, and abstention.

Statements are immutable records. They do not edit the assessment.

## Dispositions

A lead assessor or decision authority with a covering assignment can record an accepted, partially accepted, rejected, or deferred disposition. A disposition is also immutable and cannot update the assessment. Any resulting assessment edit must use the ordinary save workflow, with its own attribution, validation, event, and review.

## Integrity

Assignments, statements, and dispositions are individually hashed and linked to the case event chain. Verification detects altered records, unresolved targets, unknown evidence references, missing assignments, duplicate dispositions, and invalid decision-role linkage.

Hash validity proves record consistency only. It does not prove that a reviewer is who they claim to be or that their reasoning is correct.

## CLI

```bash
neuroai-workbench review-assign WORKSPACE CASE REVIEWER DOMAIN_REVIEWER \
  --scope FINDING:NK-01-R01 --actor lead-assessor

neuroai-workbench review-submit WORKSPACE CASE REVIEWER FINDING NK-01-R01 DISAGREE \
  --rationale "The claim should remain bounded." --evidence-id EV-PR-001

neuroai-workbench review-dispose WORKSPACE CASE STATEMENT_ID PARTIALLY_ACCEPTED \
  --rationale "Record the disagreement; edit separately." --actor lead-assessor

neuroai-workbench review-verify WORKSPACE CASE
neuroai-workbench review-report WORKSPACE CASE --output review.md
```
