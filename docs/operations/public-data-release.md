# Public observatory data release

**Control identifiers:** NEUROAI-DATA-BOOTSTRAP-1.0, NEUROAI-DATA-PUBLISH-1.0  
**Governing issues:** [#41](https://github.com/fraware/neuroai-workbench/issues/41), [#44](https://github.com/fraware/neuroai-workbench/issues/44), epic [#34](https://github.com/fraware/neuroai-workbench/issues/34)  
**Storage role:** S2 public canonical data ([ADR-0009](../adr/0009-canonical-data-and-evidence-stores.md))

## Invariant

Bootstrap and publish establish a separately governed public data surface with deterministic manifests and explicit withheld claims. Manifest verification confirms artifact identity only; it does not establish scientific truth, regulatory authorization, clinical value, substantive release authority, conformance, or UNESCO endorsement.

The publish pipeline copies only approved synthetic or explicitly public records into [fraware/neuroai-observatory-data](https://github.com/fraware/neuroai-observatory-data). It does not migrate historical archive bytes, upload protected evidence, or replace human signing and tag protection.

## Repository and scaffold

| Item | Value |
| --- | --- |
| Target repository | `fraware/neuroai-observatory-data` |
| Workbench scaffold path | `templates/neuroai-observatory-data/` |
| Workbench version pin | see `templates/neuroai-observatory-data/WORKBENCH_VERSION` |

When the GitHub repository exists, treat the scaffold as the source of truth until the remote is initialized from it. When repository creation is blocked, operators copy the scaffold manually and record the blocker in `migration/unresolved_ambiguities.json`.

## Bootstrap the data repository

### 1. Create the repository (if absent)

```powershell
gh repo create fraware/neuroai-observatory-data `
  --public `
  --description "Public canonical observatory data for NeuroAI Workbench (S2 store; ADR-0009)"
```

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
git commit -m "Bootstrap public canonical data repository scaffold."
git branch -M main
git remote add origin https://github.com/fraware/neuroai-observatory-data.git
git push -u origin main
```

Adjust commit message and signing settings to match programme policy before pushing.

### 3. Apply GitHub governance

Follow the policy documents copied into the data repository:

- `docs/branch-protection-policy.md`
- `docs/signed-release-policy.md`
- `CODEOWNERS`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/ISSUE_TEMPLATE/*`

Minimum administrator actions: require pull requests and Code Owner review on `main`; protect `data-v*` tags from deletion and force update; enable secret scanning and dependency graph where available; restrict tag creation to maintainers.

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

## Signed and attested release checklist

Complete every item before pushing a `data-v*` tag or GitHub release.

| Step | Control | Operator attestation |
| --- | --- | --- |
| 1 | Clean workbench checkout (`git status --porcelain` empty) | Initials / date |
| 2 | `make quality` and `make test` pass on the publishing commit | Initials / date |
| 3 | Only approved synthetic or public fixtures selected; no protected bytes | Initials / date |
| 4 | Dry-run publish verifies manifest (`--dry-run`) | Initials / date |
| 5 | Staging publish writes fixtures, manifest, and descriptor | Initials / date |
| 6 | `verify_manifest.py` passes on staging fixtures | Initials / date |
| 7 | Descriptor `manifest_sha256` matches manifest file | Initials / date |
| 8 | Domain and data-governance review for outward language | Initials / date |
| 9 | Named release-authority approval recorded | Initials / date |
| 10 | Signed annotated tag created (`git tag -s data-vX.Y.Z`) when keys available | Initials / date |
| 11 | Tag protection rules prevent deletion and force update | Admin confirmation |
| 12 | GitHub release notes restate withheld claims | Initials / date |

## Publish workflow

### Prerequisites

1. Workbench checkout on a clean commit with passing `make test`.
2. Data repository scaffold present at `templates/neuroai-observatory-data/` or an initialized remote clone.
3. Named release-authority decision recorded outside software (issue, ADR, or programme record).
4. Maintainer signing keys configured locally when signed tags are required.

### 1. Dry-run verify integration

```powershell
python scripts/publish_observatory_data.py `
  --staging $env:TEMP\neuroai-data-staging `
  --release-tag data-v0.0.1-bootstrap `
  --dry-run
```

Expect `"manifest_verified": true` and a descriptor preview with explicit `withheld_claims`.

### 2. Write staging output

```powershell
$staging = Join-Path $env:TEMP "neuroai-data-staging"
Remove-Item -Recurse -Force $staging -ErrorAction SilentlyContinue
python scripts/publish_observatory_data.py `
  --staging $staging `
  --release-tag data-v0.0.1-bootstrap
```

### 3. Verify staging before remote push

```powershell
python scripts/publish_observatory_data.py `
  --staging $staging `
  --release-tag data-v0.0.1-bootstrap `
  --verify-only

python templates/neuroai-observatory-data/scripts/verify_manifest.py `
  "$staging\fixtures" `
  "$staging\releases\data-v0.0.1-bootstrap\SHA256SUMS.txt"
```

### 4. Copy into remote data repository (when initialized)

Copy `fixtures/` and `releases/<tag>/` into the `neuroai-observatory-data` checkout, commit on a pull request, and obtain Code Owner review before merge.

## Clean-checkout verification

```powershell
git clone https://github.com/fraware/neuroai-workbench.git neuroai-workbench-verify
Set-Location neuroai-workbench-verify
git checkout <publish-commit-sha>
python -m pip install -e .[dev]
make quality
make test
python scripts/publish_observatory_data.py --staging .\artifacts\data-staging --release-tag data-v0.0.1-bootstrap --dry-run
python -m pytest tests/unit/test_publish_observatory_data.py -q
```

Record the publish commit SHA in the data release descriptor notes or programme release record.

## Authorized public governing set

### data-v0.1.0-public-governing

First authorized public governing set (`public-governing-v1`):

- source monitor registry v1.5 (224 sources)
- observatory v1.4 baseline
- observatory v1.6 live refresh + adjudicated delta
- observatory v1.7 successor snapshot
- public disposition summary (`ACCEPTED_WITH_RESIDUALS`, residual AMB-003)

Publish from workbench (ops extract required; bytes are not committed here):

```powershell
$env:NEUROAI_OPS_WORKSPACE = "<extract-root>"
python scripts/publish_observatory_data.py `
  --staging <data-repo-checkout> `
  --target <data-repo-checkout> `
  --release-tag data-v0.1.0-public-governing `
  --release-set public-governing-v1
```

## Workbench-side consumption

1. Import adapters must pin releases by immutable `data-v*` tag, not branch tips.
2. Update `templates/neuroai-observatory-data/WORKBENCH_VERSION` when coupling changes.
3. Keep synthetic and explicitly public fixtures in the data repository; never migrate protected archive bytes into GitHub.

## Verification in this repository

```powershell
python -m pytest tests/unit/test_observatory_data_manifest.py tests/unit/test_publish_observatory_data.py -q
```

## Residual limitations

- Human maintainer signing keys and GitHub tag protection require manual administrator activation.
- Bootstrap publishes synthetic fixtures only unless a named release-authority decision authorizes a public governing set.
- Predecessor archive reconciliation and protected evidence remain outside public GitHub regardless of manifest success.
- Manifest success does not attest to completeness of protected or licensed evidence held outside public GitHub.
