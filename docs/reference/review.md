# Collaborative review records

The workbench records local reviewer assignments, assignment lineage, review statements, disagreements, appeals, and human dispositions without changing the assessment automatically.

## Authority boundary

The reference workflow records a claimed reviewer identifier and role under `authority_profile: LOCAL_UNAUTHENTICATED_ATTRIBUTION`. It does not authenticate a person, verify an institutional appointment, or confer legal, scientific, clinical, regulatory, canonical-release, publication, or UNESCO authority. Authentication and delegated authority belong to separate institutional deployment and governance architectures.

Self-assignment of `LEAD_ASSESSOR` or `DECISION_AUTHORITY` remains refused so a distinct assigning actor is recorded within the local profile.

## Assignment lineage

Assignments are immutable, individually hashed records. The first record in a lineage uses transition `CREATED`. A later change appends one successor record:

- `SUPERSEDES` creates a new effective assignment with a new reviewer, role, or scope;
- `REVOKES` terminates the predecessor assignment without creating a new effective assignment.

Every successor binds the predecessor assignment ID and SHA-256, records the transition actor, time, and rationale, and emits a case event. The predecessor file remains byte-identical. Verification rejects missing predecessors, hash substitution, branching successors, cycles, non-active predecessors, invalid transition state, and revocation records that alter the predecessor reviewer, role, or scope.

Effective authority is derived from the unique lineage tip. A predecessor with a `SUPERSEDES` successor is reported as `SUPERSEDED`. A predecessor with a `REVOKES` successor is reported as `REVOKED`. Only an active lineage tip may authorize a new statement or disposition.

The current-assignment assigner (tip `assigned_by`) or a covering active decision-role assignment may supersede an assignment. The assigned reviewer may relinquish their own assignment through revocation, but may not appoint a successor. Prior assigners in the lineage do not retain perpetual transition authority after supersession. This is a local workflow rule and carries no external authority claim.

## Historical statements

Statements retain the assignment IDs that authorized them. Later revocation or supersession does not erase a statement that was validly submitted while its assignment was active. Verification uses half-open intervals (`assigned_at <= t < transition_at`) so authority is unambiguous at the exact transition instant, preserving historical attribution without granting a revoked assignment current authority. Assignment records must match exactly one corresponding case event; verification never silently repairs mismatches.

## Roles and scopes

Supported roles include lead assessor, decision authority, domain reviewer, methods reviewer, security reviewer, legal or regulatory reviewer, participant representative, and observer. Each assignment has an explicit typed scope such as `ASSESSMENT:*` or `FINDING:NK-01-R01`.

## Statements

A reviewer statement targets an assessment, finding, claim, decision, or gap. It records the reviewer position, rationale, evidence references, conditions, optional `proposed_change`, assessment hash, and assignment linkage. Positions include agreement, conditional agreement, disagreement, and abstention.

Statements are immutable records. They do not edit the assessment.

## Dispositions

A lead assessor or decision authority with a covering effective assignment may record an accepted, partially accepted, rejected, or deferred disposition only when the statement's `assessment_sha256` still matches the current assessment. Stale statements must be reaffirmed or succeeded before disposition. A disposition is immutable and cannot update the assessment.

Application has stricter semantics than disposition:

- `ACCEPTED` may be applied only when the statement contains one exact, non-empty `proposed_change`.
- `review-apply` requires exactly one explicit field patch whose value equals that `proposed_change` byte-for-value and whose path lies within the statement target.
- `PARTIALLY_ACCEPTED` is deliberately refused by `review-apply` because one free-text proposal does not encode the exact accepted substring or successor wording. Record a successor statement containing the exact accepted wording, dispose that successor, then apply it.
- `REJECTED` and `DEFERRED` cannot be applied.

Acceptance is not application. Statement and disposition bytes remain unchanged.

## Assessment-edit authority

`review-apply` requires an active local `LEAD_ASSESSOR` or `DECISION_AUTHORITY` assignment covering the statement target. Assignment records must have valid hashes, valid lineage, and exactly matching assignment events on a valid event chain.

The application record binds the statement digest, disposition digest, before-assessment digest, planned after-assessment digest, exact predecessor field value, exact accepted successor value, before/after field digests, application digest, and authority-assignment IDs and digests.

Authority is revalidated inside the case mutation lock immediately before persistence. The predecessor field value is also rechecked inside that lock. Revocation, supersession, event-chain corruption, or concurrent field mutation causes the operation to fail closed.

These local assignments do not authenticate the actor or establish institutional delegation, scientific correctness, release authority, or regulatory/legal effect.

## Transaction and event semantics

`review-apply` uses transactional `Workspace.save_case`. The ordinary save path preserves the content-addressed predecessor assessment, writes the successor assessment and persistence state, writes the application record as an exclusive case-contained record, and commits one physical `ASSESSMENT_SAVED` event.

The logical `REVIEW_PROPOSAL_APPLIED` action appears inside that event's `related_events` payload. It is not a second independently committed event. This prevents an assessment/application mutation from becoming durable without corresponding event provenance, or a proposal-apply event from becoming durable independently of the assessment save.

A pre-event failure rolls back the assessment, persistence record, application record, and any newly created history object. A later save recovers any remaining `PREPARED` transaction by verifying whether its transaction-keyed `ASSESSMENT_SAVED` event committed. Corrupt journals, predecessor snapshots, event chains, or divergent durable state block automatic recovery.

## Appeals and dissent preservation

Appeals are append-only records under `reviews/appeals/`. Each appeal binds a source statement ID and SHA-256, records the appellant, covering assignment IDs, appeal type, grounds, requested resolution, evidence references, and assessment hash, and emits a case event. Supported appeal types are `RECONSIDERATION`, `PROCEDURAL_OBJECTION`, `MINORITY_REPORT`, and `ABSTENTION_CLARIFICATION`.

Filing an appeal does not modify the source statement, prior disposition, or assessment. Disposing an original statement does not erase dissent; an appeal may be filed after a statement disposition. Duplicate appeals for the same source statement are refused without an explicit successor record.

Appeal dispositions are append-only under `reviews/appeal_dispositions/`. Only an active covering decision role may dispose an appeal. Authority is evaluated at disposition time. Outcomes are `UPHELD`, `PARTIALLY_UPHELD`, `DENIED`, `DEFERRED`, and `WITHDRAWN`. Disposing an appeal does not modify the appeal bytes and does not grant assessment-edit authority.

Reports display the original position, appeal type and grounds, requested resolution, outcome, and rationales. Local reviewer and decision-role identifiers remain claimed workflow attributions under `LOCAL_UNAUTHENTICATED_ATTRIBUTION`; they do not authenticate a person or establish institutional authority.

## Integrity and concurrency

Assignment creation, supersession, revocation, statement submission, disposition, appeal filing, appeal disposition, and proposal application use the case mutation lock at their mutation boundary. Proposal application additionally performs optimistic assessment-digest checks and field-level predecessor checks.

Verification detects altered records, unresolved targets, unknown evidence references, invalid assignment lineages, missing assignment authority at the recorded time, duplicate dispositions, invalid decision-role linkage, and missing appeal or appeal-disposition event correspondence.

Hash validity proves record consistency only. It does not prove reviewer identity, independence, reasoning quality, substantive correctness, or institutional authority.

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
  --rationale "The claim should remain bounded." \
  --proposed-change "Exact successor wording." \
  --evidence-id EV-PR-001

neuroai-workbench review-dispose WORKSPACE CASE STATEMENT_ID ACCEPTED \
  --rationale "Exact proposed wording accepted for separate application." \
  --actor lead-assessor

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
