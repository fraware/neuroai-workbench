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

### Adapters and scheduler

Source-type adapters wrap the HTTP collector core:

| Adapter | Identifier | Typical source classes |
| --- | --- | --- |
| HTML page | `html` | Official company and product pages |
| JSON API | `json_api` | Public JSON APIs and bibliographic metadata |
| XML / RSS / Atom | `xml_feed` | Syndication and procedural guidance feeds |
| Clinical / regulatory registry stub | `registry_stub` | Regulatory records and trial registries |
| Controlled authenticated download stub | `auth_download` | `CONTROLLED_AUTHENTICATED_DOWNLOAD` |

`CollectionScheduler` consumes `neuroai-monitor plan` output, selects an adapter from registry `source_class` and URL shape, and writes quarantine records only. Kill switches can disable collection globally, per source, per adapter, or monitoring handoff. Runtime credentials for the authenticated download stub are supplied through a `CredentialProvider` outside collection records; embedded URL credentials are refused.

Retrieval identity is distinct from source identity. The scheduler normalizes http(s) URLs and coalesces duplicate retrieval targets into one HTTP fetch, then fans out per-`source_id` outcomes sharing the same capture `record_id`. Run metrics report `unique_retrievals` versus logical source outcomes. Registry validation emits non-fatal `DUPLICATE_RETRIEVAL_URL` warnings when multiple sources share one normalized URL.

Quarantine approval (`APPROVED_FOR_HANDOFF`) is required before `prepare_monitoring_handoff` returns bytes for a separate human-gated `record_snapshot` call. The collector package never invokes `record_snapshot`, change-candidate creation, or adjudication APIs.

## Verification note

Unit tests under `tests/unit/test_collector_schemas.py` validate closed-field contracts and reject adversarial payloads. `tests/unit/test_collector_http.py` and `tests/unit/test_collector_adversarial.py` exercise SSRF, DNS rebinding, redirect abuse, archive bombs, timeouts, and conditional GET behavior without external network access. `tests/unit/test_collector_adapters_scheduler.py` exercises adapter selection, scheduler plan consumption, quarantine approval gating, credential refusal, kill switches, and architecture boundaries using mock transports only. Passing tests establishes structural behavior for the tested cases only; they do not establish retrieval safety in production or source authenticity.
