# Collector contracts

This page indexes the versioned collector contracts introduced for issue #35. These schemas define metadata and provenance only. They do not perform retrieval and do not establish authenticity or substantive truth.

## Schemas

| Contract | Resource | Purpose |
| --- | --- | --- |
| Collection request | `collection-request.schema.json` | Registry-bound retrieval intent with configuration hash |
| Collection result | `collection-result.schema.json` | Successful retrieval provenance and quarantine pointer |
| Collection failure | `collection-failure.schema.json` | Visible failure record with retry state |
| Quarantine record | `quarantine-record.schema.json` | Quarantined byte metadata and approval gate |
| Structured adapter contract | `structured-adapter-contract.schema.json` | Adapter completeness, reviewed hosts, and capability declaration |
| Normalized study record | `normalized-study-record.schema.json` | CT.gov field projection for mechanical change detection |
| Normalized device record | `normalized-device-record.schema.json` | FDA pathway-linked device projection |
| Normalized publication record | `normalized-publication-record.schema.json` | PubMed/PMC/Crossref metadata projection |

Per-adapter contracts are versioned as `adapter-contract-<adapter_id>.json` beside these schemas. `PARTIAL` means reviewed identifier- or query-bound retrieval paths exist; `SCAFFOLD_NOT_COMPLETE` means the adapter refuses live collection.

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

| Adapter | Identifier | Typical source classes | Completeness |
| --- | --- | --- | --- |
| HTML page | `html` | Official company and product pages | fallback |
| JSON API | `json_api` | Public JSON APIs | generic |
| XML / RSS / Atom | `xml_feed` | Syndication and procedural guidance feeds | generic |
| Clinical / regulatory HTTP capture | `clinical_regulatory_http_capture` | Selected regulatory/publication landing pages without structured IDs | page capture only |
| ClinicalTrials.gov structured | `clinicaltrials_gov` | Trial registry/page classes with NCT ID or search query | `PARTIAL` (study + search/pagination + field digests) |
| FDA device structured | `fda_device` | Regulatory records with explicit PMA/HDE/De Novo/510(k) IDs → openFDA | `PARTIAL` (pathway linkage) |
| PubMed / PMC / Crossref | `pubmed_crossref` | Publication classes with PMID, PMCID, or DOI | `PARTIAL` |
| FDA MAUDE | `fda_maude` | `FDA_MAUDE_RECORD` | `SCAFFOLD_NOT_COMPLETE` |
| FDA recall | `fda_recall` | `FDA_RECALL_RECORD` | `SCAFFOLD_NOT_COMPLETE` |
| WHO ICTRP | `who_ictrp` | `WHO_ICTRP_RECORD` | `SCAFFOLD_NOT_COMPLETE` |
| EU CTIS | `eu_ctis` | `EU_CTIS_RECORD` | `SCAFFOLD_NOT_COMPLETE` |
| Neuroscience archives | `neuroscience_archive` | `NEUROSCIENCE_DATASET_RECORD` | `SCAFFOLD_NOT_COMPLETE` |
| Patents / grants | `patents_grants` | `PATENT_OR_GRANT_RECORD` | `SCAFFOLD_NOT_COMPLETE` |
| Controlled authenticated download stub | `auth_download` | `CONTROLLED_AUTHENTICATED_DOWNLOAD` | stub |

Do not claim observatory-grade registry completeness from page capture alone. Structured adapters retrieve selected identifier-bound or query-bound payloads only. HTML remains the fallback when no structured identifier or dedicated source class applies. Scaffold adapters refuse live retrieval with an explicit non-substantive failure; that refusal is not a scientific `FAIL` finding.

`CollectionScheduler` consumes `neuroai-monitor plan` output, selects an adapter from registry `source_class` and URL shape, and writes quarantine records only. Kill switches can disable collection globally, per source, per adapter, or monitoring handoff. Runtime credentials for the authenticated download stub are supplied through a `CredentialProvider` outside collection records; embedded URL credentials are refused.

Retrieval identity is distinct from source identity. The scheduler normalizes http(s) URLs and coalesces duplicate retrieval targets into one HTTP fetch, then fans out per-`source_id` outcomes sharing the same capture `record_id`. Run metrics report `unique_retrievals` versus logical source outcomes. Registry validation emits non-fatal `DUPLICATE_RETRIEVAL_URL` warnings when multiple sources share one normalized URL.

Quarantine approval (`APPROVED_FOR_HANDOFF`) is required before `prepare_monitoring_handoff` returns bytes for a separate human-gated `record_snapshot` call. The collector package never invokes `record_snapshot`, change-candidate creation, or adjudication APIs.

## Verification note

Unit tests under `tests/unit/test_collector_schemas.py` validate closed-field contracts and reject adversarial payloads. `tests/unit/test_collector_http.py` and `tests/unit/test_collector_adversarial.py` exercise SSRF, DNS rebinding, redirect abuse, archive bombs, timeouts, and conditional GET behavior without external network access. `tests/unit/test_collector_adapters_scheduler.py` exercises adapter selection, scheduler plan consumption, quarantine approval gating, credential refusal, kill switches, and architecture boundaries using mock transports only. Passing tests establishes structural behavior for the tested cases only; they do not establish retrieval safety in production or source authenticity.
