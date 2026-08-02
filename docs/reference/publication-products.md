# Publication products (narrative, dashboard, PDF stub)

**Control identifier:** NEUROAI-PRODUCT-DOCS-1.0  
**Governing issues:** [#42](https://github.com/fraware/neuroai-workbench/issues/42), epic [#34](https://github.com/fraware/neuroai-workbench/issues/34)

## Invariant

Word, PDF, and dashboard products are deterministic projections of canonical JSON through a shared query layer. Generation confirms layout and identity only; it does not establish scientific truth or institutional authority.

## Supported formats

| Product | Format | Status |
| --- | --- | --- |
| Current-state executive report | Markdown | Implemented |
| Observatory dashboard | Static HTML | Implemented |
| PDF export | Text stub | Documented limitation |
| Word export | Not implemented | Use Markdown source; optional docx extra future work |

Native Word/PDF libraries are intentionally excluded from core dependencies. Operators use Markdown/HTML outputs until optional renderers are reviewed.

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
python -m pytest tests/unit/test_products_reconciliation.py -q
```

Cross-format reconciliation tests assert identical release SHA-256 and withheld-claims language across Markdown, HTML, and PDF stub outputs.

## Residual limitations

- PDF and Word require optional dependencies not yet packaged.
- Dashboard list projections inherit query-layer caps from canonical fixtures.
- HTML dashboard is static; no remote assets or telemetry are included.
