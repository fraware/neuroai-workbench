# Static archive to operational programme

## Separation of responsibilities

The organized programme archive is immutable historical evidence. It is not the daily working directory.

The operational system has four stores:

1. **Archive** — predecessor releases, reports, spreadsheets, original packages, and verification records.
2. **Canonical workbench state** — current observatory releases, assessments, evidence references, reviews, and decisions.
3. **Monitoring queue** — source plans, snapshots, change candidates, and adjudications.
4. **Generated products** — Excel, Word, Markdown, PDF, dashboards, manifests, and release ZIPs.

Only canonical machine-readable records are edited through controlled operations. Human-readable reports and workbooks are generated views.

## Folder model

```text
NeuroAI-Operations/
├── 01_CONFIG/
│   ├── source_registry.json
│   ├── monitoring_policy.json
│   └── reopening_policy.json
├── 02_INCOMING/
├── 03_WORKBENCH/
│   ├── workspace.json
│   ├── observatory/
│   └── cases/
├── 04_REVIEW_QUEUE/
├── 05_RELEASES/
│   ├── current/
│   └── historical/
└── 99_ARCHIVE_READ_ONLY/
```

The workbench's monitoring state is stored under `03_WORKBENCH/observatory/monitoring`. The review queue is a presentation layer over candidate and adjudication records, not a separate source of truth.

## Relationship to assessments

Observatory records answer what exists and what changed. Assessments answer what the evidence supports for an exact system boundary. An accepted observatory change can produce one of the following effects:

- no assessment effect;
- metadata update;
- evidence-gap update;
- review required;
- partial reassessment;
- full reassessment.

The effect remains a human adjudication. A release package can queue the action but cannot change the assessment automatically.

## Generated deliverables

The combined Excel workbook and Word compendium should be regenerated from canonical records. They remain useful release and stakeholder products, but neither is an operational database.
