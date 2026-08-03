# Analytical workbook generation

**Control identifier:** NEUROAI-PRODUCT-EXCEL-1.0  
**Governing issues:** [#42](https://github.com/fraware/neuroai-workbench/issues/42), epic [#34](https://github.com/fraware/neuroai-workbench/issues/34)

## Invariant

The analytical workbook is a deterministic projection of canonical JSON fixtures. Workbook generation confirms record identity and layout only; it does not establish scientific truth, regulatory authorization, or substantive assessment authority.

## Format

`openpyxl` is not a core dependency. When the optional `products` extra is installed, generators emit a **native `.xlsx`** workbook with a single merged `verification` sheet (never `verification1`). Without openpyxl, the workbook ships as a **CSV-in-ZIP xlsx stub**:

- one CSV per logical sheet under `sheets/`
- `workbook.manifest.json` with release SHA-256 and sheet inventory
- `sheets/verification.csv` with release identity and boundary statement

CI pins the product extras in `requirements/constraints.txt` and asserts the native branch via `product-native`; end-user core installs remain free of those packages.

## Usage

```powershell
python -c "from pathlib import Path; from neuroai_workbench.products.generate import generate_publication_set; print(generate_publication_set(Path('examples/observatory/canonical_successor_snapshot_v1.7.json'), Path('artifacts/products')))"
```

## Verification

```powershell
python -m pytest tests/unit/test_products_excel.py tests/unit/test_products_native.py -q
```

## Residual limitations

- Workbook rows follow the shared query depth/limit rules; publication builds use unbounded full depth.
- CSV-in-ZIP remains the offline fallback when openpyxl is absent; operators then open sheets individually or convert with approved tooling.
- No manually maintained master data is permitted; all displayed values trace to canonical JSON queries.
