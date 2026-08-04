# Collaborative review records

The workbench records local reviewer assignments, assignment lineage, review statements, disagreements, appeals, and human dispositions without changing the assessment automatically.

## Authority boundary

The reference workflow records a claimed reviewer identifier and role under `authority_profile: LOCAL_UNAUTHENTICATED_ATTRIBUTION`. It does not authenticate a person, verify an institutional appointment, or confer legal, scientific, clinical, regulatory, or release authority. Authentication and delegated authority belong to the separate institutional deployment and final governance architectures.

Self-assignment of `LEAD_ASSESSOR` or `DECISION_AUTHORITY` remains refused so a distinct assigning actor is recorded within the local profile.

## Assignment lineage

Assignments are immutable, individually hashed records. The first record in a lineage uses transition `CREATED`. A later change appends one successor record:

- `SUPERSEDES` creates a new effective assignment with a new reviewer, role, or scope;
- `REVOKES` terminates the predecessor assignment without creating a new effective assignment.

Every successor binds the predecessor assignment ID and SHA-256, records the transition actor, time, and rationale, and emits a case event. The predecessor file remains byte-identical. Verification rejects missing predecessors, hash substitution, branching successors, cycles, non-active predecessors, invalid transition state, and revocation records that alter the predecessor reviewer, role, or scope.

Effective authority is derived from the unique lineage tip. A predecessor with a `SUPERSEDES` successor is reported as `SUPERSEDED`. A predecessor with a `REVOKES` successor is reported as `REVOKED`. Only an active lineage tip may authorize a new statement or disposition.

The current-assignment assigner (tip `assigned_by`) or a covering active decision-role assignment may supersede an assignment. The assigned reviewer may relinquish their own assignment through revocation, yet may not appoint a successor. Prior assigners in the lineage do not retain perpetual transition authority after supersession. This is a local workflow rule and carries no external authority claim.

## Historical statements

Statements retain the assignment IDs that authorized them. Later revocation or supersession does not erase a statement that was validly submitted while its assignment was active. Verification uses half-open intervals (`assigned_at <= t < transition_at`) so authority is unambiguous at the exact transition instant, preserving historical attribution without granting a revoked assignment current authority. Assignment records must match exactly one corresponding case event; verification never silently repairs mismatches.

## Roles and scopes

Supported roles include lead assessor, decision authority, domain reviewer, methods reviewer, security reviewer, legal or regulatory reviewer, participant representative, and observer. Each assignment has an explicit typed scope such as `ASSESSMENT:*` or `FINDING:NK-01-R01`.

## Statements

A reviewer statement targets an assessment, finding, claim, decision, or gap. It records the reviewer position, rationale, evidence references, conditions, proposed change, assessment hash, and assignment linkage. Positions include agreement, conditional agreement, disagreement, and abstention.

Statements are immutable records. They do not edit the assessment.

## Dispositions

A lead assessor or decision authority with a covering effective assignment may record an accepted, partially accepted, rejected, or deferred disposition only when the statement's `assessment_sha256` still matches the current assessment. Stale statements must be reaffirmed or succeeded before disposition. A disposition is immutable and cannot update the assessment. Any resulting assessment edit must use the ordinary save workflow, with its own attribution, validation, event, and review. `review-apply` bridges `ACCEPTED` or `PARTIALLY_ACCEPTED` dispositions into that ordinary edit with explicit field patches, optimistic concurrency, recoverable prior assessment history, and a `REVIEW_PROPOSAL_APPLIED` event; it leaves statement and disposition bytes unchanged.

## Appeals and dissent preservation

Appeals are append-only records under `reviews/appeals/`. Each appeal binds a source statement ID and SHA-256, records the appellant, covering assignment IDs, appeal type, grounds, requested resolution, evidence references, and assessment hash, and emits a case event. Supported appeal types are `RECONSIDERATION`, `PROCEDURAL_OBJECTION`, `MINORITY_REPORT`, and `ABSTENTION_CLARIFICATION`.

Filing an appeal does not modify the source statement, prior disposition, or assessment. Disposing an original statement does not erase dissent; an appeal may be filed after a statement disposition. Duplicate appeals for the same source statement are refused without an explicit successor record.

Appeal dispositions are append-only under `reviews/appeal_dispositions/`. Only an active covering decision role may dispose an appeal. Authority is evaluated at disposition time. Outcomes are `UPHELD`, `PARTIALLY_UPHELD`, `DENIED`, `DEFERRED`, and `WITHDRAWN`. Disposing an appeal does not modify the appeal bytes and does not grant assessment-edit authority.

Reports display the original position, appeal type and grounds, requested resolution, outcome, and rationales. Local reviewer and decision-role identifiers remain claimed workflow attributions under `LOCAL_UNAUTHENTICATED_ATTRIBUTION`; they do not authenticate a person or establish institutional authority.

## Integrity and concurrency

Assignment creation, supersession, revocation, statement submission, disposition, appeal filing, and appeal disposition are serialized through the case mutation lock. This prevents cooperative writers from creating two successors or accepting a statement or appeal concurrently with revocation. Assignment, statement, disposition, appeal, and appeal-disposition records remain individually hashed and linked to the case event chain.

Verification detects altered records, unresolved targets, unknown evidence references, invalid assignment lineages, missing assignment authority at the recorded time, duplicate dispositions, invalid decision-role linkage, and missing appeal or appeal-disposition event correspondence.

Hash validity proves record consistency only. It does not prove reviewer identity, independence, reasoning quality, or institutional authority.

## CLI

```bash
neuroai-workbench review-assign WORKSPACE CASE REVIEWER DOMAIN_REVIEWER \
  --scope FINDING:NK-01-R01 --actor lead-assessor

neuroai-workbench review-supersede WORKSPACE CASE ASSIGNMENT_ID REVIEWER_2 METHODS_REVIEWER \
  --scope FINDING:NK-01-R01 \
  --rationale "Transfer the methods review." \
  --actor lead-assessor

neuroai-workbench review-revoke WORKSPACE CASE ASSIGNMENT_ID \
  --rationale "Reviewer availability ended." \
  --actor REVIEWER

neuroai-workbench review-submit WORKSPACE CASE REVIEWER FINDING NK-01-R01 DISAGREE \
  --rationale "The claim should remain bounded." --evidence-id EV-PR-001

neuroai-workbench review-dispose WORKSPACE CASE STATEMENT_ID PARTIALLY_ACCEPTED \
  --rationale "Record the disagreement; edit separately." --actor lead-assessor

neuroai-workbench review-apply WORKSPACE CASE STATEMENT_ID \
  --expected-assessment-sha256 CURRENT_SHA256 \
  --patches-file patches.json \
  --actor lead-assessor

neuroai-workbench review-appeal-file WORKSPACE CASE STATEMENT_ID MINORITY_REPORT \
  --grounds "The minority position remains material." \
  --requested-resolution "Preserve the disagreement in the final record." \
  --appellant-id REVIEWER

neuroai-workbench review-appeal-dispose WORKSPACE CASE APPEAL_ID DENIED \
  --rationale "The original disposition stands; dissent remains recorded." \
  --actor lead-assessor

neuroai-workbench review-appeal-list WORKSPACE CASE

neuroai-workbench review-verify WORKSPACE CASE
neuroai-workbench review-report WORKSPACE CASE --output review.md
```
