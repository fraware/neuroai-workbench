# Analytical workbook generation

**Control identifier:** NEUROAI-PRODUCT-EXCEL-1.0  
**Governing issues:** [#42](https://github.com/fraware/neuroai-workbench/issues/42), epic [#34](https://github.com/fraware/neuroai-workbench/issues/34)

## Invariant

The analytical workbook is a deterministic projection of canonical JSON fixtures. Workbook generation confirms record identity and layout only; it does not establish scientific truth, regulatory authorization, or substantive assessment authority.

## Format

`openpyxl` is not a core dependency. The workbook ships as a **CSV-in-ZIP xlsx stub**:

- one CSV per logical sheet under `sheets/`
- `workbook.manifest.json` with release SHA-256 and sheet inventory
- `sheets/verification.csv` with release identity and boundary statement

Native `.xlsx` output may be added later behind an optional dependency extra.

## Usage

```powershell
python -c "from pathlib import Path; from neuroai_workbench.products.generate import generate_publication_set; print(generate_publication_set(Path('examples/observatory/canonical_successor_snapshot_v1.7.json'), Path('artifacts/products')))"
```

## Verification

```powershell
python -m pytest tests/unit/test_products_excel.py -q
```

## Residual limitations

- Workbook rows cap list projections at 50 records per sheet for compact fixtures; full releases require future pagination.
- CSV-in-ZIP is not a native Excel file; operators open sheets individually or convert with approved tooling.
- No manually maintained master data is permitted; all displayed values trace to canonical JSON queries.
