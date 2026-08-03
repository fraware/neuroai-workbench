# Publication products

**Control identifier:** NEUROAI-PRODUCT-DOCS-1.0  
**Governing issues:** [#42](https://github.com/fraware/neuroai-workbench/issues/42), epic [#34](https://github.com/fraware/neuroai-workbench/issues/34)

## Invariant

Excel, Word, PDF, Markdown, and dashboard products are deterministic projections of canonical JSON through a shared query layer. Generation confirms layout and identity only; it does not establish scientific truth or institutional authority. Generators are views.

## Query depth

| Depth | Use | Projection |
| --- | --- | --- |
| `summary` | Interactive preview | Thin org/source fields (3 each) or compact counts/reopening IDs |
| `full` | Publication builds | Rich org/source fields plus every first-class sheet whose canonical section is present |

`generate_publication_set` requires `depth="full"` and `limit=None`. Preview callers may use `depth="summary"` with a finite `limit`. Missing canonical sections are omitted and never invented.

## Full-depth sheet coverage

Sheets appear only when the corresponding canonical data exists.

### Full observatory release (example: v1.4 evidence-depth fixture)

| Sheet | Canonical source |
| --- | --- |
| `release_summary` | Metadata + validation |
| `coverage_counts` | Coverage metrics |
| `organizations` | Organization records (roles, countries/regions, evidence/claim fields) |
| `aliases` | Split alias rows from organization `aliases` lists |
| `sources` | Source register |
| `organization_resolution` | Resolution records |
| `regional_expansion` | Regional expansion records |
| `ownership_capital_events` | Capital and ownership events |
| `models` | Representative model records |
| `models_datasets` | Model/dataset registry objects |
| `trial_sites` | Trial-site relationships |
| `participant_authority` | Participant-authority relationships |
| `suppliers` | Supplier-dependency relationships |
| `data_quality_findings` | Data-quality findings |
| `coverage_exit_conditions` | Coverage exit-condition rows when present |
| `methodology_source_universes` | Methodology source-universe rows when present |
| `system_relationships` / `systems` | Only when those lists exist |
| `captures` | Only when present |
| `candidates` / `adjudications` / `source_checks` | Change-candidate and adjudication shapes when present (including non-v1.6 keys) |
| `evidence_register` | Only when an evidence-register list exists on the release |
| Assessment/provenance sheets | `findings`, `evidence`, `gaps`, `requirement_results`, `provenance` when present |
| `projection_limits` / `verification` | Query metadata, release hash, withheld claims |

### Compact successor snapshot (example: v1.7)

| Sheet | Canonical source |
| --- | --- |
| `successor_counts` / `baseline_counts` / `delta_counts` | Count maps |
| `reopening_decisions` | Full reopening rows at `depth=full` |
| `delta_records` | Flattened delta sections |
| `assessment_successor_delta` | Assessment successor delta object |
| `provenance_links` | Provenance map or link list |
| `verification` | Release hash, depth/limit, withheld claims |

## Supported formats

| Product | Format | Status |
| --- | --- | --- |
| Analytical workbook | Native xlsx (openpyxl) or CSV-in-ZIP fallback | Implemented |
| Current-state executive report | Markdown | Implemented |
| Observatory dashboard | Static HTML | Implemented |
| PDF export | Optional reportlab product with multi-page appendix tables | Implemented when extra installed |
| Word export | Optional python-docx product with appendix tables from the same query graph | Implemented when extra installed |

## Excel verification sheet

Native workbooks expose a single `verification` sheet that merges release identity, query depth/limit metadata, format marker, and withheld-claims rows. A second sheet named `verification1` must not appear.

## Usage

```powershell
python -c "from pathlib import Path; from neuroai_workbench.products.generate import generate_publication_set; print(generate_publication_set(Path('examples/observatory/canonical_successor_snapshot_v1.7.json'), Path('artifacts/products')))"
```

## Accessibility notes (dashboard)

- Logical heading order (`h1` then `h2`)
- Table captions and `scope` attributes on headers
- Status communicated with text labels inside pills, not color alone
- System light/dark contrast via `prefers-color-scheme`
- Descriptive page title and meta description

## Verification

```powershell
python -m pytest tests/unit/test_products_excel.py tests/unit/test_products_reconciliation.py tests/unit/test_products_native.py -q
```

Cross-format reconciliation tests assert identical release SHA-256 and withheld-claims language across Markdown, HTML, and PDF outputs. `test_products_native.py` hard-requires openpyxl / python-docx / reportlab and asserts a single `verification` sheet, real DOCX/PDF containers, and substantive sheet coverage for the v1.4 full release and v1.7 compact successor. CI job `product-native` installs hashed pins from `requirements/constraints.txt` and runs these tests; the packages remain optional extras for end-user installs.

## Residual limitations

- Optional Word/PDF dependencies remain outside the core install (extra `products`); CI pins them for native-path proof only.
- Full-depth sheets only project fields present on the canonical release; missing sections are omitted rather than invented.
- HTML dashboard is static; no remote assets or telemetry are included.
- DOCX/PDF appendices can be large for full releases; they remain projections, not authoritative masters.
