# Public data releases

Authorized public machine-readable observatory records are published to [fraware/neuroai-observatory-data](https://github.com/fraware/neuroai-observatory-data).

## data-v0.1.0-public-governing

First authorized public governing set (public-governing-v1):

- source monitor registry v1.5 (224 sources)
- observatory v1.4 baseline
- observatory v1.6 live refresh + adjudicated delta
- observatory v1.7 successor snapshot
- public disposition summary (ACCEPTED_WITH_RESIDUALS, residual AMB-003)

Publish from workbench (ops extract required; bytes are not committed here):

```powershell
$env:NEUROAI_OPS_WORKSPACE = "<extract-root>"
python scripts/publish_observatory_data.py `
  --staging <data-repo-checkout> `
  --target <data-repo-checkout> `
  --release-tag data-v0.1.0-public-governing `
  --release-set public-governing-v1
```

Checksum verification confirms artifact identity only. It does not establish scientific truth, regulatory authorization, clinical value, conformance, or UNESCO endorsement.
