# Operational due-cycle executor

**Status:** engineering implementation for issue #153  
**Scope:** registered-universe collection execution, retry, concurrency, resumability, and operational accountability  
**Authority boundary:** operational execution only

## Objective

The operational observatory must execute every due source in the declared monitoring universe with explicit accountability, bounded resource use, deterministic recovery, and no semantic escalation from retrieval mechanics into assessment or governance conclusions.

The core invariant is:

> every due logical source is attributable to one explicit operational outcome, and an interrupted executor can resume the exact run without duplicating already committed retrieval work.

This architecture does not claim that the registered universe is exhaustive, that retrieved sources are true, that retrieval failures are assessment failures, or that a completed run authorizes canonical publication.

## Execution model

A monitoring plan remains the scheduling authority for what is due. The collector groups due logical sources by normalized retrieval target. Source identity and retrieval identity remain distinct: one network retrieval can fan out to multiple source records when they intentionally resolve to the same lexical retrieval target.

The executor uses two bounded concurrency controls:

- a global worker limit across independent retrieval targets;
- a per-resolved-host semaphore limit.

The shared host request-rate limiter is synchronized and paces scheduler-owned requests instead of converting expected host throttling into synthetic source failures.

Output ordering is independent of task completion order. Source outcomes are sorted by source identity and target results by retrieval-target identity before deterministic summary hashing.

## Request-local security state

DNS-rebinding state is scoped to one logical HTTP fetch. Redirect hops inside that fetch share a DNS guard session so address-set changes remain detectable. Concurrent independent fetches use separate sessions backed by the same injected resolver and cannot clear or mutate each other's rebinding observations.

Authenticated downloads use a request-local authenticated transport. The shared collector transport is never replaced or mutated. This prevents a concurrent public or differently authenticated source from inheriting another source's Authorization header.

## Retry policy

Retries are an operational mechanism, not evidence adjudication.

The scheduler retries only explicitly transient classes:

- `TIMEOUT`;
- `NETWORK_ERROR`;
- HTTP 408, 425, 429, 500, 502, 503, and 504.

Security, policy, credential, content, size, decompression, redirect, and other permanent failures are not retried automatically. HTTP status classes outside the allowlisted transient set are final for that run.

Retry delay is bounded exponential backoff controlled by collector configuration. Attempt counts are propagated into the persisted failure record. No retry loop can exceed `max_attempts`.

A final typed retrieval failure remains an operational source outcome. It does not mutate an assessment finding.

## Deterministic run identity

The run binding contains the exact:

- monitoring plan digest;
- source-registry digest;
- collector configuration and digest;
- scheduler configuration and digest;
- retrieval-target set;
- pre-execution source outcomes such as explicit kill-switch or policy states.

The canonical operational run ID is derived from the hash of this binding. Re-executing the exact same plan/configuration/target set therefore resolves to the same run identity when resumability is enabled.

## Durable ledger

The run ledger is operational state under the quarantine root and is outside canonical assessment/evidence state.

It consists of:

1. one immutable hash-bound run manifest;
2. one independently hash-bound checkpoint file per retrieval target;
3. one hash-bound final or incomplete summary.

Per-target checkpoint files eliminate a global mutable-ledger bottleneck. Independent workers never update the same target file.

Target states include:

- `PENDING`;
- `ATTEMPTING`;
- `RETRY_WAIT`;
- `RESULT`;
- `FAILURE`;
- `POLICY_BLOCK`;
- `INTERNAL_ERROR`.

`RESULT`, `FAILURE`, and `POLICY_BLOCK` are terminal operational target states. `INTERNAL_ERROR` is explicitly non-terminal so an executor fault can be resumed without being reclassified as a source retrieval failure.

## Crash recovery

Each network attempt receives a deterministic request ID derived from run ID, target ID, and attempt number.

Collector result/failure records are durable independently of the target checkpoint. On resume, the executor indexes durable collector records by request ID. If a process failed after persisting a result/failure but before updating its target checkpoint, the next executor invocation reconstructs that attempt from the durable record and performs no duplicate network request.

If a target already has a terminal, hash-valid checkpoint, resume performs no work for that target.

Manifest substitution, checkpoint target substitution, hash corruption, duplicate durable request IDs, and summary corruption fail closed.

## Run completion semantics

The executor separates source-level operational failure from executor incompleteness.

`COMPLETE`
: every due logical source has an accountable result/skip/final operational state and no source retrieval failed.

`COMPLETE_WITH_SOURCE_FAILURES`
: every due logical source is accountable, with one or more final typed retrieval failures.

`INCOMPLETE_INTERNAL_ERROR`
: at least one retrieval target did not reach a terminal operational state because of executor/runtime failure.

A run with source failures can therefore be operationally complete. A run with internal executor gaps cannot.

## SLO evidence

The deterministic summary exposes at least:

- logical source count;
- retrieval-target count;
- completed retrieval-target count;
- collection attempts;
- retries;
- resumed targets;
- recovered durable attempts;
- coalesced source fan-out;
- source success/failure/skip/incomplete counts;
- per-host target and attempt counts;
- source-accountability coverage;
- target-execution coverage.

The operational target for a completed due cycle is:

- source-accountability coverage = `1.0`;
- target-execution coverage = `1.0`.

These SLOs establish execution accountability only.

## Performance contract

The deterministic CI stress fixture covers at least 248 logical sources with realistic target coalescing. It proves that:

- one logical retrieval target produces one network attempt absent retries;
- fan-out does not multiply network work;
- global and per-host concurrency limits are respected;
- output remains deterministic under concurrent completion;
- restart performs zero duplicate work for committed targets;
- runtime overhead remains comfortably bounded with a zero-latency fake transport.

Internet latency is deliberately excluded from the CI performance threshold so the test detects algorithmic regressions without becoming flaky.

## Boundaries

This executor does not establish:

- completeness beyond the declared source universe;
- source truth;
- scientific validity;
- clinical or regulatory status;
- assessment failure from retrieval failure;
- system conformance;
- human governance approval;
- institutional authority;
- UNESCO endorsement;
- release or publication authority.

Open-world discovery remains a subsequent expansion layer. Real canonical release remains governed by the separate governance and release-authority stack.
