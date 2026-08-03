# v2.2.0 to v2.3.0 canonical migration

## Objective

This procedure converts the supplied v2.2.0 consolidated workbook, consolidated report, and complete programme archive into a deterministic migration baseline for the v2.3.0 successor.

The v2.2.0 files are preserved byte-for-byte as update checkpoints. They are neither treated as the final current release nor edited in place. The migration separates two questions:

1. Did the repository preserve the existing programme state without loss?
2. What substantive changes belong in the v2.3.0 successor?

The first question is addressed by this pipeline. Evidence refresh, discovery, new adjudications, and revised analysis occur in later successor phases.

## Authority transition

During migration, authority moves domain by domain:

```text
validated canonical repository data
> generated analytical and narrative products
> preserved historical files and folders
```

A domain becomes repository-authoritative only after its identifiers, counts, values, provenance, and historical semantics reconcile. Conflicts must be recorded explicitly. The pipeline never selects a value silently.

## Inputs

The operator supplies five external inputs:

- v2.2.0 consolidated XLSX;
- v2.2.0 consolidated DOCX;
- complete programme ZIP;
- the 48-sheet disposition map;
- the migration contract.

The XLSX, DOCX, and ZIP remain outside Git. Only the software, contract, dispositions, and safe test fixtures belong in this repository.

## Command

Install the native product dependencies, then run:

```bash
python scripts/migrate_v22_consolidated.py \
  --workbook /controlled/input/UNESCO_NeuroAI_All_Data_Combined_v2.2.0.xlsx \
  --report /controlled/input/UNESCO_NeuroAI_All_Reports_Findings_and_Conclusions_Combined_v2.2.0.docx \
  --archive /controlled/input/01_START_CURRENT_AND_ORIGINAL.zip \
  --sheet-map examples/migration/V2_2_WORKBOOK_SHEET_DISPOSITIONS.csv \
  --contract examples/migration/V2_2_MIGRATION_CONTRACT.json \
  --output /controlled/output/v2.3.0-rc1-migration
```

## Generated records

The pipeline produces:

- deterministic JSON exports for all workbook sheets;
- a workbook sheet inventory;
- a DOCX structure inventory covering paragraphs, headings, tables, sections, styles, and core properties;
- a complete ZIP-member inventory;
- a check-level parity ledger;
- a machine-readable reconciliation report;
- an output package manifest with SHA-256 identities.

Formula cells are preserved as formula records. Empty rows are excluded from canonical sheet exports while their workbook coordinates remain recoverable through `_source_row`.

## Current parity contract

The initial contract verifies:

- 48 workbook sheets;
- 223 organization rows;
- 224 source rows;
- 78 kernel requirements;
- 312 assessment findings;
- 44 claims;
- 52 evidence objects;
- 38 endpoints;
- 60 assessment gaps;
- 78 comparative-matrix rows;
- 100 indexed CSV datasets;
- 10,727 raw CSV rows;
- 455 indexed JSON files;
- 1,436 file-manifest rows;
- all four assessment-level status and object counts;
- 4,267 DOCX paragraphs;
- 349 DOCX tables;
- 107 DOCX sections;
- 1,344 files in the supplied archive.

These values define import parity for the supplied checkpoint. They do not define the eventual v2.3.0 counts.

## Pass and failure semantics

A zero-failure result permits canonical import work to proceed. It does not authorize a substantive refresh by itself.

Any mismatch fails closed and must be classified as one of:

- input identity mismatch;
- parser or migration defect;
- duplicate or omitted record;
- intentional successor change applied too early;
- historical inconsistency requiring explicit resolution.

The source checkpoint must never be modified to make a check pass.

## Verified reference execution

The supplied programme corpus produced:

- 54 checks;
- 54 passes;
- zero failures;
- reconciliation status `PASS`.

That execution establishes structural and count parity for the supplied inputs. The generated artifacts remain external operational records and are not committed to the software repository.

## Successor sequence

After parity:

1. import canonical domains in bounded increments;
2. reconcile identifiers and provenance for each domain;
3. generate v2.2-equivalent products from canonical records;
4. execute current source retrieval and discovery as a separate delta;
5. adjudicate accepted changes;
6. recompute landscape, observatory, comparison, and implementation analyses;
7. generate the v2.3.0 release candidate from canonical state.

## Boundaries

This migration records structure, identity, and parity. It does not establish scientific truth, regulatory status, clinical value, system conformance, or currentness. It does not modify historical assessment determinations, generate new findings, or infer missing values.
