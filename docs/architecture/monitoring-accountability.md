# Monitoring accountability over the effective source namespace

**Issue:** #155  
**Scope:** operational source coverage reconciliation  
**Authority:** execution accountability only

## Objective

An observatory cannot claim operational maturity from a monitor-registry count alone. The effective source namespace and the monitoring registry are separate governed objects. Every effective source must have one explicit operational disposition.

The allowed dispositions are:

- `MONITORED` — one active monitor record binds the source into recurring due planning;
- `MANUAL_ONLY` — explicit current eligibility/access semantics call for controlled manual collection;
- `EXEMPT_WITH_RATIONALE` — explicit evidence establishes why recurring collection is currently outside scope;
- `GAP` — no legitimate operational disposition exists yet.

`GAP` is a first-class defect state. It must never be hidden by inventing an exemption.

## Reconciliation invariants

The evaluator binds exact input bytes by SHA-256 and rejects or reports:

- duplicate effective source IDs;
- multiple monitor records for one source;
- multiple explicit non-monitor records for one source;
- monitor records for no effective source;
- non-monitor records for no effective source;
- simultaneous monitor and non-monitor disposition for the same effective source;
- unsupported accountability states;
- exemptions/manual records without rationale;
- malformed supporting digests;
- uncovered effective sources.

A report is `complete=true` only when every effective source has exactly one legitimate disposition and no orphan/duplicate/ambiguous record remains.

## Relationship to the due-cycle executor

Issue #153 provides the concurrent, retrying, resumable execution engine. Issue #155 provides the universe-coverage contract.

The operational chain is therefore:

`effective source namespace -> monitoring accountability -> monitoring registry / manual queue -> due plan -> due-cycle executor -> source accountability SLO`

The executor cannot compensate for a source omitted from the monitoring model. Conversely, a complete monitoring-accountability projection does not prove that a due cycle actually executed. Both layers are needed.

## Real-data integration

The real projection must be produced from the current canonical/identity/eligibility objects. The current 224-record monitoring registry cannot be extrapolated into an assumed 248-record policy.

For every effective source absent from the monitor registry:

1. inspect the exact current source-identity and access/eligibility record;
2. classify it as `MANUAL_ONLY` only when those records support controlled manual handling;
3. classify it as `EXEMPT_WITH_RATIONALE` only when a versioned evidence record explicitly supports that scope treatment;
4. otherwise leave it as `GAP` and create/retain a visible remediation item.

## Scheduled evidence

The workbench sample monitor registry is suitable for planner smoke testing. It is not production-universe evidence.

The repository that owns the current private operational source data should run the real-registry reconciliation workflow, because cross-repository checkout of private source data would create unnecessary credential and disclosure complexity.

The resulting public-safe summary can expose counts and digests without exposing protected evidence.

## Boundary

Zero-gap accountability means every source in the **declared effective namespace** has an explicit operational disposition. It does not mean the observatory has discovered every relevant source in the world.

It also does not establish source truth, scientific validity, assessment validity, clinical/regulatory status, system conformance, human governance approval, UNESCO endorsement, or release authority.
