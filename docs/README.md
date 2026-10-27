# NeuroAI Workbench documentation

NeuroAI Workbench provides offline-capable, local-first assessment and evidence review. Authorized Observatory source acquisition operates separately through a network-enabled collector. This index organizes the public user and contributor documentation.

The workbench records provenance and review decisions. Software integrity checks do not establish clinical efficacy, scientific completeness, regulatory approval, or permission to publish protected data.

## Get started

- [Installation and first assessment](../README.md#install)
- [Command-line reference](reference/cli.md)
- [Local user interface](reference/review-ui.md)
- [Working with evidence](reference/evidence-exchange.md)
- [Reports and exports](reference/reports.md)

## Concepts and architecture

- [Architecture overview](architecture/overview.md)
- [Offline assessment and governed online source acquisition](architecture/online-first-acquisition.md)
- [Entity and identity model](architecture/entity-identity-model.md)
- [Evidence storage boundaries](architecture/data-storage-boundaries.md)
- [Temporal model](architecture/temporal-model.md)
- [Observatory source records](reference/observatory.md)
- [Assessment dependencies](reference/assessment-dependencies.md)

## Assessment and scientific methodology

- [Assessment validation protocol](evaluation/assessment-validation-protocol.md)
- [Review and adjudication](reference/review.md)
- [Evidence and authority limits](governance/evidence-boundary.md)
- [Research and publication reproducibility](architecture/publication-reproducibility.md)
- [Release A scientific status](programme/release-a-completion-status.md)
- [Release A corrective scientific review](programme/release-a-corrective-review-r1.md)

Assessment methods, product inclusion criteria, and publication decisions are governed independently of this software repository. The existence of source records or a passing test is insufficient evidence for a completed scientific census or population estimate.

## Security and data handling

- [Security policy](../SECURITY.md)
- [Threat model](../THREAT_MODEL.md)
- [Data governance](../DATA_GOVERNANCE.md)
- [Retention and access](data-governance/retention-and-access.md)
- [Local deployment](operations/deployment.md)

The included local web server does not implement network authentication. Follow the [security policy](../SECURITY.md) before deploying outside a trusted workstation.

## For contributors

- [Contributing](../CONTRIBUTING.md)
- [Development tests and quality checks](../CONTRIBUTING.md#development)
- [Architecture decision records](adr/)
- [Release process](operations/release-process.md)
- [Changelog](../CHANGELOG.md)

Technical design records and historical experiment materials are retained for engineering provenance. They do not constitute public release authorizations, scientific findings, or deployment instructions. Verify current versions and the relevant scientific protocol before relying on dated status records.
