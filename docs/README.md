# Documentation map

Audience-oriented index for the NeuroAI Workbench. Root project files remain the primary landing surfaces; this tree holds durable architecture, governance, operations, and reference material.

## Architecture

| Document | Purpose |
| --- | --- |
| [overview.md](architecture/overview.md) | System architecture and component boundaries |
| [data-storage-boundaries.md](architecture/data-storage-boundaries.md) | Five-store model and storage roles |
| [vision-and-target-architecture.md](architecture/vision-and-target-architecture.md) | Seven-layer Observatory v2 programme target and transition gates |
| [observatory-v2-ontology.md](architecture/observatory-v2-ontology.md) | Target entities, observations, assertions, relationships, events, and assessment dependencies |
| [observatory-v2-migration-boundary.md](architecture/observatory-v2-migration-boundary.md) | Narrow source/time-unresolved exception for lossless predecessor migration |
| [temporal-model.md](architecture/temporal-model.md) | Valid-time, knowledge-time, observation succession, and as-of semantics |
| [entity-identity-model.md](architecture/entity-identity-model.md) | Stable IDs, resolution proposals, lineage, and no-silent-merge rules |
| [s2-s3-evidence-contract.md](architecture/s2-s3-evidence-contract.md) | Public evidence metadata versus protected/restricted evidence bytes |
| [release-model-v2.md](architecture/release-model-v2.md) | Immutable S2 authority, projection boundary, and v2 migration release gates |
| [compatibility-identity.md](architecture/compatibility-identity.md) | Package version, runtime pin, S2 WORKBENCH_VERSION, producer commit, and schema version |
| [static-to-operational.md](architecture/static-to-operational.md) | Archive versus operational programme layout |
| [release-attestation.md](architecture/release-attestation.md) | Default proportional release-control profile |
| [governance-single-authority.md](architecture/governance-single-authority.md) | Designated authority and default/high-assurance profiles |
| [institutional-deployment-profile.md](architecture/institutional-deployment-profile.md) | Controls required before an institutional pilot claim |
| [compatibility-identity.md](architecture/compatibility-identity.md) | Package version, runtime pin, S2 WORKBENCH_VERSION, producer commit, and schema version |

## Governance

| Document | Purpose |
| --- | --- |
| [evidence-boundary.md](governance/evidence-boundary.md) | What software can and cannot decide |
| [unesco-alignment.md](governance/unesco-alignment.md) | UNESCO-facing withheld-claim language |
| [retention-and-access.md](data-governance/retention-and-access.md) | Retention and access notes for programme stores |

## Architecture decision records

Individual ADRs under [`adr/`](adr/) preserve focused architectural decisions and their rationale. ADR 0014 is the accepted temporal implementation ADR. ADR 0015 and ADR 0016 are implementation ADRs for provenance and identity references. ADR 0017 expands the typed delta vocabulary without RFC-6902 patch. ADR 0019 records the PRE-G2 held-out benchmark implementation lineage (`#272` then `#275`) without G1/G2 approval claims.

## Operations

| Document | Purpose |
| --- | --- |
| [deployment.md](operations/deployment.md) | Local and container deployment |
| [pilot-runbook.md](operations/pilot-runbook.md) | Controlled local pilot procedure |
| [release-process.md](operations/release-process.md) | Software release integrity and canonical release attestation |
| [github-governance-setup.md](operations/github-governance-setup.md) | Branch protection and required checks |
| [github-required-checks.md](operations/github-required-checks.md) | Repository-owned required-check contract |
| [hosted-ci-empty-steps.md](operations/hosted-ci-empty-steps.md) | Hosted jobs with empty `steps: []` are infrastructure failure, not test results |
| [extending-observatory.md](operations/extending-observatory.md) | Contributor guide for programmes, adapters, predicates, entity kinds, delta ops |
| [pr-229-231-233-integration.md](operations/pr-229-231-233-integration.md) | Local integration of Observatory v2 docs, CT.gov discovery, and pinned transport |
| [observatory-automation.md](operations/observatory-automation.md) | Monitoring operating model, programme control, verification |
| [collector-contracts.md](operations/collector-contracts.md) | Collector ingestion contracts |
| [shadow-refresh-evaluation.md](operations/shadow-refresh-evaluation.md) | Non-canonical shadow refresh evaluation |
| [shadow-cycle-43-execution.md](operations/shadow-cycle-43-execution.md) | #43 core-cycle acceptance summary |
| [deferred-governance.md](operations/deferred-governance.md) | Current release-governance status and remaining real decision boundary |
| [protected-governance-execution.md](operations/protected-governance-execution.md) | Optional high-assurance governance profile |
| [governance-transaction-recovery.md](operations/governance-transaction-recovery.md) | Crash-consistent governance write recovery |
| [governing-input-migration.md](operations/governing-input-migration.md) | Governing-input lineage and migration |
| [public-data-release.md](operations/public-data-release.md) | Bootstrap and publish to `neuroai-observatory-data` |
| [post-publication-withdrawal-drill.md](operations/post-publication-withdrawal-drill.md) | Withdrawal and correction drill |
| [independent-review-acceptance.md](operations/independent-review-acceptance.md) | Optional external independent-review evidence |

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
| [assistance.md](reference/assistance.md) | Controlled assistance records |
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
| [successor-releases.md](reference/successor-releases.md) | Successor candidate and default canonical release semantics |
| [governance-records.md](reference/governance-records.md) | Optional high-assurance governance record semantics |

## Release boundaries

| Document | Purpose |
| --- | --- |
| [v0.3-foundation-boundary.md](releases/v0.3-foundation-boundary.md) | v0.3 foundation, software-release, canonical-publication, and deployment states |

## Evaluation

| Document | Purpose |
| --- | --- |
| [assessment-validation-protocol.md](evaluation/assessment-validation-protocol.md) | Pre-outcome reliability, decision-usefulness, accessibility, and linguistic-validation protocol contract |
| [extraction-evaluation.md](evaluation/extraction-evaluation.md) | Preregistration, offline comparison, dispositions |
| [entity-resolution-report.md](evaluation/entity-resolution-report.md) | Entity-resolution benchmark corpora and metrics |

## Security

| Document | Purpose |
| --- | --- |
| [review-checklist.md](security/review-checklist.md) | Local-profile security review checklist |
| [model-assistance-boundary.md](security/model-assistance-boundary.md) | Assistance authority boundary |
| [collector-threat-model.md](security/collector-threat-model.md) | Collector-specific threat analysis |
| [pinned-dns-transport.md](collector/pinned-dns-transport.md) | DNS-pinned production HTTP transport boundary |

Root `THREAT_MODEL.md` and `SECURITY.md` remain the programme-level threat and reporting entrypoints.
