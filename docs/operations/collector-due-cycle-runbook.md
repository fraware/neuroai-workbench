# Collector due-cycle operating runbook

This runbook covers the registered-universe operational collector introduced under issue #153. It does not activate human governance, mutate assessment findings, or authorize canonical release.

## Preconditions

Before a live due-cycle execution:

1. Generate or verify the monitoring plan against the exact source-registry digest.
2. Confirm collector and scheduler configuration values, especially worker limits, per-host worker limit, host request rate, timeouts, retry count, and response-size limits.
3. Confirm runtime credentials are supplied only through the configured credential provider. Never put credentials in source URLs, plan records, run ledgers, Git, CI logs, or artifacts.
4. Confirm the quarantine root is on the intended protected/local storage boundary.
5. Keep handoff disabled unless the separately governed handoff operation is explicitly intended.

## Normal execution

`CollectionScheduler.run_plan(...)` derives a deterministic run binding and run ID when resumability is enabled.

During execution inspect the final run summary for:

- `status`;
- `execution_status`;
- `counts.total`;
- `counts.retrieval_target_groups`;
- `counts.collection_attempts`;
- `counts.retries`;
- `counts.recovered_attempts`;
- `counts.resumed_targets`;
- `slo.source_accountability_coverage`;
- `slo.target_execution_coverage`;
- per-host attempt counts;
- source-level typed failures.

A healthy completed cycle has both accountability coverage values at `1.0`.

`COMPLETE_WITH_SOURCE_FAILURES` is an operationally complete run. Review its typed source failures, but do not translate them into assessment failures.

## Resume after interruption

Reinvoke the exact same plan with the exact same registry, collector configuration, scheduler configuration, and source/target bindings.

The executor verifies the existing immutable run manifest. Terminal target checkpoints are skipped. Incomplete target checkpoints are resumed.

If a collector result or failure was durably written before a process interruption but its target checkpoint was not updated, the deterministic request ID permits recovery of that durable record without another network fetch.

Do not delete checkpoints simply to force a retry. If evidence indicates a ledger is corrupt, preserve the affected files for diagnosis and start a deliberately new execution only after determining why the binding or hash failed.

## Incomplete internal execution

`INCOMPLETE_INTERNAL_ERROR` means the executor failed to establish a terminal operational state for at least one target.

Actions:

1. inspect the target checkpoint's `internal_error` diagnostic;
2. preserve the run manifest and checkpoint;
3. fix the executor/runtime cause;
4. invoke the exact run again so resumability handles completed and incomplete targets correctly;
5. confirm no terminal target was fetched again;
6. confirm both accountability coverage values reach `1.0`.

An internal executor error must never be relabeled as a source retrieval failure.

## Retry handling

Automatic retry is limited to configured transient classes and transient HTTP statuses. A final typed failure after exhaustion remains visible in the summary.

Do not broaden retry classes to bypass:

- SSRF/DNS rebinding controls;
- redirect policy;
- credential policy;
- robots or terms policy;
- content-type policy;
- response-size limits;
- decompression-bomb controls;
- quarantine validation.

## Rate and concurrency tuning

Use `max_workers` to bound global independent-target concurrency and `max_workers_per_host` to bound simultaneous work against one resolved host.

The scheduler also paces requests through the per-host requests-per-minute limiter. Raising concurrency above host-rate capacity does not improve sustained throughput and increases queueing.

Tune using observed due-cycle telemetry. Prefer more cross-host concurrency over aggressive same-host concurrency.

## Ledger integrity failures

The executor fails closed on:

- run-manifest hash mismatch;
- run-binding substitution;
- target-checkpoint hash mismatch;
- target identity/binding mismatch;
- duplicate durable records for one deterministic request ID;
- run-summary hash mismatch.

Do not repair these records manually in place. Determine the source of corruption first and preserve the original bytes for audit.

## Operational acceptance after deployment

For each controlled live cycle record:

- exact plan/registry/configuration identity;
- logical sources due;
- unique retrieval targets;
- attempts/retries;
- completed targets;
- source-accountability coverage;
- target-execution coverage;
- typed failures by class;
- resumed/recovered work;
- wall-clock execution telemetry outside the deterministic semantic summary.

The operational target is 100% accountability for every source declared due in each completed cycle.

## Meaning of completion

Operational completion establishes that the declared due-cycle was executed accountably. It does not establish open-world completeness, source truth, assessment validity, human governance approval, or publication authority.
