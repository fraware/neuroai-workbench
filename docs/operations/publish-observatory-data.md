# Publish observatory data to neuroai-observatory-data

**Control identifier:** NEUROAI-DATA-PUBLISH-1.0  
**Governing issues:** [#41](https://github.com/fraware/neuroai-workbench/issues/41), [#44](https://github.com/fraware/neuroai-workbench/issues/44), epic [#34](https://github.com/fraware/neuroai-workbench/issues/34)

## Invariant

The publish pipeline copies only approved synthetic public records into the separately governed `neuroai-observatory-data` surface. Manifest verification confirms artifact identity only; it does not establish scientific truth, regulatory authorization, clinical value, or substantive release authority.

## Scope

- Approved synthetic fixtures under `templates/neuroai-observatory-data/fixtures/`
- Deterministic SHA-256 manifest generation and verification via the data-repo scripts
- Dry-run planning without writing staging output
- Clean-checkout verification steps before any remote push

This pipeline does **not** migrate historical archive bytes, upload protected evidence, or replace human signing and tag protection.

## Prerequisites

1. Workbench checkout on a clean commit with passing `make test`.
2. Data repository scaffold present at `templates/neuroai-observatory-data/` or an initialized remote clone.
3. Named release-authority decision recorded outside software (issue, ADR, or programme record).
4. Maintainer signing keys configured locally when signed tags are required.

## Signed and attested release checklist

Complete every item before pushing a `data-v*` tag or GitHub release.

| Step | Control | Operator attestation |
| --- | --- | --- |
| 1 | Clean workbench checkout (`git status --porcelain` empty) | Initials / date |
| 2 | `make quality` and `make test` pass on the publishing commit | Initials / date |
| 3 | Only approved synthetic fixtures selected; no protected bytes | Initials / date |
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

Run from a fresh clone before any publication:

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

## Residual limitations

- Human maintainer signing keys and GitHub tag protection require manual administrator activation.
- Bootstrap publishes synthetic fixtures only; predecessor archive reconciliation remains out of scope.
- Manifest success does not attest to completeness of protected or licensed evidence held outside public GitHub.
