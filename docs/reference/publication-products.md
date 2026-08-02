# Publication products

**Control identifier:** NEUROAI-PRODUCT-DOCS-1.0  
**Governing issues:** [#42](https://github.com/fraware/neuroai-workbench/issues/42), epic [#34](https://github.com/fraware/neuroai-workbench/issues/34)

## Invariant

Excel, Word, PDF, Markdown, and dashboard products are deterministic projections of canonical JSON through a shared query layer. Generation confirms layout and identity only; it does not establish scientific truth or institutional authority. Generators are views.

## Query depth

| Depth | Use | Projection |
| --- | --- | --- |
| `summary` | Interactive preview | Thin org/source fields (3 each) or compact counts/reopening IDs |
| `full` | Publication builds | Rich org/source fields plus available relationships, delta records, reopening detail, assessment/provenance sheets |

`generate_publication_set` requires `depth="full"` and `limit=None`. Preview callers may use `depth="summary"` with a finite `limit`.

## Supported formats

| Product | Format | Status |
| --- | --- | --- |
| Analytical workbook | Native xlsx (openpyxl) or CSV-in-ZIP fallback | Implemented |
| Current-state executive report | Markdown | Implemented |
| Observatory dashboard | Static HTML | Implemented |
| PDF export | Optional reportlab product | Implemented when extra installed |
| Word export | Optional python-docx product | Implemented when extra installed |

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
python -m pytest tests/unit/test_products_excel.py tests/unit/test_products_reconciliation.py -q
```

Cross-format reconciliation tests assert identical release SHA-256 and withheld-claims language across Markdown, HTML, and PDF outputs.

## Residual limitations

- Optional Word/PDF dependencies remain outside the core install.
- Full-depth sheets only project fields present on the canonical release; missing sections are omitted rather than invented.
- HTML dashboard is static; no remote assets or telemetry are included.
