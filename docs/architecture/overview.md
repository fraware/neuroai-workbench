# Architecture

## Design objective

The workbench is a local evidence and decision environment for exact, versioned NeuroAI assessments. It keeps protected bytes inside a user-controlled workspace and separates mechanical integrity from substantive judgment.

## Core components

- `validation.py` performs schema and semantic validation.
- `workspace.py` controls case lifecycle, ordinary assessment saves, assessment history, and recoverable save transactions.
- `evidence.py` preserves evidence bytes and checks digests.
- `events.py` appends and verifies the event hash chain.
- `review.py` is a typed public collaborative-review facade over the private record engine. It explicitly exports the hardened proposal-application functions and preserves narrow historical private-hook test semantics without package-level or `sys.modules` substitution. Normal production calls use a direct fast path.
- `_review_records.py` is the private record engine for review assignments, lineage, statements, dispositions, appeals, dissent, and reporting. Its historical source still contains the pre-#122 proposal-apply routine for compatibility history, but importing the public `review` facade pins the private engine module object's proposal-application attributes to the hardened `proposal_application.py` callables. Supported application paths use the hardened implementation.
- `proposal_application.py` applies exact accepted review wording and derives local assessment-edit authority from active review assignments.
- `assistance.py` records provider-neutral model requests, responses, dispositions, and exact accepted assistance application without calling a provider.
- `exchange.py` records minimum-necessary custodian metadata exchange.
- `reports.py` renders deterministic projections.
- `cli.py` provides reproducible command-line operations.

## Storage model

```text
workspace/
  cases/
    CASE-ID/
      assessment.json
      persistence.json
      events.jsonl
      evidence/...
      reviews/
        assignments/*.json
        statements/*.json
        dispositions/*.json
        appeals/*.json
        appeal_dispositions/*.json
        applications/*.json
      assistance/
        requests/*.json
        responses/*.json
        dispositions/*.json
        applications/*.json
      history/
        assessments/<sha256>.json
      transactions/
        assessment-saves/
          AST-.../
            transaction.json
            before-assessment.json
            before-persistence.json
      snapshots/...
      exports/...
```

Temporary predecessor snapshots exist only as needed for a prepared transaction and are removed after terminal commit or rollback.

## Proposal application

Disposition and assessment mutation are separate operations.

Assistance application requires each patch to match an exact recorded `(target_path, proposed_text)` suggestion. `ACCEPTED_AS_DRAFT` selects the full suggestion set; `PARTIALLY_USED` selects a non-empty proper subset.

Review application accepts one exact `proposed_change` under an `ACCEPTED` disposition. `PARTIALLY_ACCEPTED` is not executable because the current record does not encode exact accepted successor wording.

Application also requires an active local `LEAD_ASSESSOR` or `DECISION_AUTHORITY` assignment covering each target. Assignment hashes, lineage, and event correspondence are verified. Authority and predecessor field values are checked again inside the case mutation lock immediately before persistence.

The local role graph coordinates this reference workflow only. It does not authenticate identities or create external institutional authority.

## Transactional ordinary save

`Workspace.save_case` remains the assessment mutation path used by proposal application. Each save first recovers any earlier prepared assessment-save transaction, then creates a self-hashed transaction record for the new mutation.

The save preserves content-addressed predecessor assessment bytes, writes the successor assessment and persistence state, writes any exclusive application record, and commits one transaction-keyed `ASSESSMENT_SAVED` event. A failure before that event is durable rolls back the controlled files. A prepared transaction found later is either completed from a matching durable event or rolled back to the verified predecessor state. Corrupt transaction metadata, predecessor snapshots, event history, or divergent durable state stop automatic recovery.

Assessment-history objects are re-hashed when loaded or reused; the content-addressed filename alone is not trusted.

## Event model

Proposal application records one physical `ASSESSMENT_SAVED` event. Logical actions such as `ASSISTANCE_PROPOSAL_APPLIED` and `REVIEW_PROPOSAL_APPLIED` are embedded in that event under `related_events` along with apply provenance.

Consumers that need proposal-application semantics should inspect `ASSESSMENT_SAVED.payload.related_events` rather than assume a second standalone event.

## Trust and decision boundaries

The local server provides no identity proof or tenant isolation. Hashes establish recorded-byte consistency, not source authenticity or substantive correctness. The default assistance workflow makes no external model call. Filesystem transactions coordinate cooperative local writers; they are not a substitute for institutional deployment controls.

The engine keeps software validity, evidence integrity, event integrity, review-record integrity, model-exchange integrity, and typed decisions separate. A valid hash chain, recorded role, or accepted proposal does not itself establish conformance or release authority.
