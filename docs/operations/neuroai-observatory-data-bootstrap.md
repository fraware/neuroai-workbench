# neuroai-observatory-data bootstrap

**Control identifier:** NEUROAI-DATA-BOOTSTRAP-1.0  
**Governing issues:** [#44](https://github.com/fraware/neuroai-workbench/issues/44), epic [#34](https://github.com/fraware/neuroai-workbench/issues/34)  
**Storage role:** S2 public canonical data ([ADR-0009](../adr/0009-canonical-data-and-evidence-stores.md))

## Invariant

Bootstrap establishes a separately governed public data surface with deterministic manifests and explicit withheld claims. Manifest and schema success confirm artifact identity only; they do not establish scientific truth, regulatory authorization, or substantive assessment authority.

## Repository status

| Item | Value |
| --- | --- |
| Target repository | `fraware/neuroai-observatory-data` |
| Workbench scaffold path | `templates/neuroai-observatory-data/` |
| Workbench version pin | `0.3.0.dev0` (`WORKBENCH_VERSION`) |

When the GitHub repository exists, treat the scaffold as the source of truth until the remote is initialized from it. When repository creation is blocked, operators copy the scaffold manually and follow the admin steps below.

## Admin steps — create or initialize the data repository

### 1. Create the repository (if absent)

```powershell
gh repo create fraware/neuroai-observatory-data `
  --public `
  --description "Public canonical observatory data for NeuroAI Workbench (S2 store; ADR-0009)"
```

If creation fails because of organization permissions, quotas, or naming conflicts:

1. Request org admin creation of `fraware/neuroai-observatory-data`.
2. Keep the committed scaffold under `templates/neuroai-observatory-data/` in this workbench repository.
3. Record the blocker in `migration/unresolved_ambiguities.json` under topic `neuroai-observatory-data repository creation`.

### 2. Initialize remote content from the scaffold

```powershell
$scaffold = "templates/neuroai-observatory-data"
$staging = Join-Path $env:TEMP "neuroai-observatory-data-init"
Remove-Item -Recurse -Force $staging -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $staging | Out-Null
Copy-Item -Path "$scaffold\*" -Destination $staging -Recurse -Force
Set-Location $staging
git init
git add .
git commit -m @"
Bootstrap public canonical data repository scaffold.

"@
git branch -M main
git remote add origin https://github.com/fraware/neuroai-observatory-data.git
git push -u origin main
```

Adjust the commit message and signing settings to match programme policy before pushing.

### 3. Apply GitHub governance

Follow the committed policy documents copied into the data repository:

- `docs/branch-protection-policy.md`
- `docs/signed-release-policy.md`
- `CODEOWNERS`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/ISSUE_TEMPLATE/*`

Minimum administrator actions:

1. Require pull requests and Code Owner review on `main`.
2. Protect `data-v*` tags from deletion and force update.
3. Enable secret scanning and dependency graph where available.
4. Restrict tag creation to maintainers.

### 4. Publish the bootstrap tag

After `main` contains the scaffold:

```powershell
python scripts/verify_manifest.py fixtures releases/data-v0.0.1-bootstrap/SHA256SUMS.txt
git tag -a data-v0.0.1-bootstrap -m "Synthetic bootstrap release; manifest tooling only."
git push origin data-v0.0.1-bootstrap
gh release create data-v0.0.1-bootstrap `
  --title "data-v0.0.1-bootstrap" `
  --notes "Synthetic fixtures only. No substantive observatory authority." `
  releases/data-v0.0.1-bootstrap/release-descriptor.json `
  releases/data-v0.0.1-bootstrap/SHA256SUMS.txt
```

Prefer signed tags when maintainer signing keys are configured.

## Workbench-side consumption

1. Import adapters in `neuroai-workbench` must pin releases by immutable `data-v*` tag, not branch tips.
2. Update `templates/neuroai-observatory-data/WORKBENCH_VERSION` when coupling changes.
3. Keep synthetic and explicitly public fixtures in the data repository; never migrate protected archive bytes into GitHub.

## Verification in this repository

Unit tests under `tests/unit/test_observatory_data_manifest.py` exercise the scaffold manifest scripts against temporary synthetic trees:

```powershell
python -m pytest tests/unit/test_observatory_data_manifest.py -q
```

## Residual limitations

- Bootstrap does not migrate historical archive bytes or reconcile record counts against predecessor workbooks.
- Protected evidence remains outside public GitHub regardless of manifest success.
- Branch protection and signed releases require manual GitHub administrator activation.
