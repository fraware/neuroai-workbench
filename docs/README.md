# Documentation map

Audience-oriented index for the NeuroAI Workbench. Every page below has a distinct purpose. Root entrypoints (`README.md`, `AGENTS.md`, `THREAT_MODEL.md`, `DATA_GOVERNANCE.md`, `SECURITY.md`, `CHANGELOG.md`) remain the primary landing surfaces; this tree holds durable architecture, governance, operations, and reference material.

## Architecture

| Document | Purpose |
| --- | --- |
| [overview.md](architecture/overview.md) | System architecture and component boundaries |
| [data-storage-boundaries.md](architecture/data-storage-boundaries.md) | Five-store model and storage roles |
| [static-to-operational.md](architecture/static-to-operational.md) | Archive versus operational programme layout |
| [institutional-deployment-profile.md](architecture/institutional-deployment-profile.md) | Controls required before an institutional pilot claim |

## Governance

| Document | Purpose |
| --- | --- |
| [evidence-boundary.md](governance/evidence-boundary.md) | What software can and cannot decide |
| [unesco-alignment.md](governance/unesco-alignment.md) | UNESCO-facing withheld-claim language |
| [retention-and-access.md](data-governance/retention-and-access.md) | Retention and access notes for programme stores |

## Architecture decision records

Individual ADRs under [`adr/`](adr/). Do not mash ADRs into a single blob. Current records: offline-first local-only, filesystem workspaces, no aggregate conformance score, normative kernel change control, controlled language-model assistance, single-writer event chain, transactional evidence registration, collector deployment boundary, canonical data and evidence stores.

## Operations

| Document | Purpose |
| --- | --- |
| [deployment.md](operations/deployment.md) | Local and container deployment |
| [pilot-runbook.md](operations/pilot-runbook.md) | Controlled local pilot procedure |
| [release-process.md](operations/release-process.md) | Software release integrity steps |
| [github-governance-setup.md](operations/github-governance-setup.md) | Branch protection and required checks |
| [ai-agent-development.md](operations/ai-agent-development.md) | Cursor/agent handoff protocol and eval harness |
| [observatory-automation.md](operations/observatory-automation.md) | Monitoring operating model, programme control, verification |
| [collector-contracts.md](operations/collector-contracts.md) | Collector ingestion contracts |
| [shadow-refresh-evaluation.md](operations/shadow-refresh-evaluation.md) | Non-canonical shadow refresh rehearsal |
| [governing-input-migration.md](operations/governing-input-migration.md) | Governing-input lineage and migration |
| [public-data-release.md](operations/public-data-release.md) | Bootstrap and publish to `neuroai-observatory-data` |
| [post-publication-withdrawal-drill.md](operations/post-publication-withdrawal-drill.md) | Withdrawal and correction drill |
| [independent-review-acceptance.md](operations/independent-review-acceptance.md) | Optional independent-review tracks and checklists |

## Reference

| Document | Purpose |
| --- | --- |
| [cli.md](reference/cli.md) | CLI surface |
| [api.md](reference/api.md) | HTTP API surface |
| [web-ui.md](reference/web-ui.md) | Local assessment browser UI |
| [review-ui.md](reference/review-ui.md) | Monitoring review UI |
| [observatory.md](reference/observatory.md) | Observatory record semantics |
| [programme-adapter.md](reference/programme-adapter.md) | PRIMA programme adapter |
| [reports.md](reference/reports.md) | Deterministic assessment reports |
| [assistance.md](reference/assistance.md) | Model-assistance records |
| [review.md](reference/review.md) | Collaborative review records |
| [review-queue.md](reference/review-queue.md) | Monitoring review queue API |
| [evidence-exchange.md](reference/evidence-exchange.md) | Protected-evidence exchange |
| [entities.md](reference/entities.md) | Entity registry and resolver |
| [extraction.md](reference/extraction.md) | Bounded source extraction contract |
| [assessment-dependencies.md](reference/assessment-dependencies.md) | Assessment dependency graph |
| [adjudicated-delta.md](reference/adjudicated-delta.md) | Adjudicated delta packages |
| [analytical-workbook.md](reference/analytical-workbook.md) | Generated analytical workbook views |
| [publication-products.md](reference/publication-products.md) | Generated publication products |
| [reopening-engine.md](reference/reopening-engine.md) | Assessment reopening recommendations |
| [successor-releases.md](reference/successor-releases.md) | Observatory successor release states |

## Evaluation

| Document | Purpose |
| --- | --- |
| [extraction-evaluation.md](evaluation/extraction-evaluation.md) | Preregistration, offline comparison, dispositions |
| [entity-resolution-report.md](evaluation/entity-resolution-report.md) | Entity-resolution benchmark corpora and metrics |

## Security

| Document | Purpose |
| --- | --- |
| [review-checklist.md](security/review-checklist.md) | Local-profile security review checklist |
| [model-assistance-boundary.md](security/model-assistance-boundary.md) | Model-assistance authority boundary |
| [collector-threat-model.md](security/collector-threat-model.md) | Collector-specific threat analysis |

Root `THREAT_MODEL.md` and `SECURITY.md` remain the programme-level threat and reporting entrypoints.
