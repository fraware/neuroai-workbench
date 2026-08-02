# Collector contracts

This page indexes the versioned collector contracts introduced for issue #35. These schemas define metadata and provenance only. They do not perform retrieval and do not establish authenticity or substantive truth.

## Schemas

| Contract | Resource | Purpose |
| --- | --- | --- |
| Collection request | `collection-request.schema.json` | Registry-bound retrieval intent with configuration hash |
| Collection result | `collection-result.schema.json` | Successful retrieval provenance and quarantine pointer |
| Collection failure | `collection-failure.schema.json` | Visible failure record with retry state |
| Quarantine record | `quarantine-record.schema.json` | Quarantined byte metadata and approval gate |

Package location: `src/neuroai_workbench/resources/collector/`.

## Handoff boundary

```text
registry allowlist
  -> collection request
  -> collector retrieval (separate deployment)
  -> quarantine record (PENDING_HUMAN_APPROVAL)
  -> human/quarantine approval
  -> monitoring record_snapshot
  -> comparison and adjudication (existing monitoring pipeline)
```

The collector never calls monitoring adjudication APIs and never writes monitoring snapshots directly.

## Related documents

- [Collector threat model](../security/collector-threat-model.md)
- [ADR 0008 — Collector deployment boundary](../adr/0008-collector-deployment-boundary.md)
- [Observatory automation operating model](observatory-automation.md)

## Implementation

The hardened HTTP collector core lives in `src/neuroai_workbench/collector/`. It performs registry-bound retrieval with injectable transports for offline unit tests, writes quarantine bytes and schema-validated provenance records, and never calls monitoring snapshot or adjudication APIs.

## Verification note

Unit tests under `tests/unit/test_collector_schemas.py` validate closed-field contracts and reject adversarial payloads. `tests/unit/test_collector_http.py` and `tests/unit/test_collector_adversarial.py` exercise SSRF, DNS rebinding, redirect abuse, archive bombs, timeouts, and conditional GET behavior without external network access. Passing tests establishes structural behavior for the tested cases only; they do not establish retrieval safety in production or source authenticity.
