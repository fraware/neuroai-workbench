# Collaborative review records

The workbench records local reviewer assignments, assignment lineage, review statements, disagreements, and human dispositions without changing the assessment automatically.

## Authority boundary

The reference workflow records a claimed reviewer identifier and role under `authority_profile: LOCAL_UNAUTHENTICATED_ATTRIBUTION`. It does not authenticate a person, verify an institutional appointment, or confer legal, scientific, clinical, regulatory, or release authority. Authentication and delegated authority belong to the separate institutional deployment and final governance architectures.

Self-assignment of `LEAD_ASSESSOR` or `DECISION_AUTHORITY` remains refused so a distinct assigning actor is recorded within the local profile.

## Assignment lineage

Assignments are immutable, individually hashed records. The first record in a lineage uses transition `CREATED`. A later change appends one successor record:

- `SUPERSEDES` creates a new effective assignment with a new reviewer, role, or scope;
- `REVOKES` terminates the predecessor assignment without creating a new effective assignment.

Every successor binds the predecessor assignment ID and SHA-256, records the transition actor, time, and rationale, and emits a case event. The predecessor file remains byte-identical. Verification rejects missing predecessors, hash substitution, branching successors, cycles, non-active predecessors, invalid transition state, and revocation records that alter the predecessor reviewer, role, or scope.

Effective authority is derived from the unique lineage tip. A predecessor with a `SUPERSEDES` successor is reported as `SUPERSEDED`. A predecessor with a `REVOKES` successor is reported as `REVOKED`. Only an active lineage tip may authorize a new statement or disposition.

The original assigning actor or a covering active decision-role assignment may supersede an assignment. The assigned reviewer may relinquish their own assignment through revocation, yet may not appoint a successor. This is a local workflow rule and carries no external authority claim.

## Historical statements

Statements retain the assignment IDs that authorized them. Later revocation or supersession does not erase a statement that was validly submitted while its assignment was active. Verification checks assignment activity at the statement or disposition timestamp, preserving historical attribution without granting a revoked assignment current authority.

## Roles and scopes

Supported roles include lead assessor, decision authority, domain reviewer, methods reviewer, security reviewer, legal or regulatory reviewer, participant representative, and observer. Each assignment has an explicit typed scope such as `ASSESSMENT:*` or `FINDING:NK-01-R01`.

## Statements

A reviewer statement targets an assessment, finding, claim, decision, or gap. It records the reviewer position, rationale, evidence references, conditions, proposed change, assessment hash, and assignment linkage. Positions include agreement, conditional agreement, disagreement, and abstention.

Statements are immutable records. They do not edit the assessment.

## Dispositions

A lead assessor or decision authority with a covering effective assignment may record an accepted, partially accepted, rejected, or deferred disposition only when the statement's `assessment_sha256` still matches the current assessment. Stale statements must be reaffirmed or succeeded before disposition. A disposition is immutable and cannot update the assessment. Any resulting assessment edit must use the ordinary save workflow, with its own attribution, validation, event, and review.

## Integrity and concurrency

Assignment creation, supersession, revocation, statement submission, and disposition are serialized through the case mutation lock. This prevents cooperative writers from creating two successors or accepting a statement concurrently with revocation. Assignment, statement, and disposition records remain individually hashed and linked to the case event chain.

Verification detects altered records, unresolved targets, unknown evidence references, invalid assignment lineages, missing assignment authority at the recorded time, duplicate dispositions, and invalid decision-role linkage.

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

neuroai-workbench review-verify WORKSPACE CASE
neuroai-workbench review-report WORKSPACE CASE --output review.md
```
