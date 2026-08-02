# Governing input migration

Governing-input migration records storage lineage, digests, and adapter outcomes for observatory and assessment inputs. Migration does not validate substantive claims, confer authorization, or establish conformance.

## Families and adapters

| Family | Adapter | Public / ops source |
| --- | --- | --- |
| `OBSERVATORY_V1_4` | `observatory-v1.4-adapter` | `examples/observatory/evidence_depth_release_v1.4.json` |
| `OBSERVATORY_V1_6` | `observatory-v1.6-adapter` | Ops: `05_RELEASES/historical/CANONICAL_LIVE_REFRESH_RELEASE_v1.6.json` and `ADJUDICATED_DELTA_v1.6.json` |
| `OBSERVATORY_V1_7` | `observatory-v1.7-adapter` | `examples/observatory/canonical_successor_snapshot_v1.7.json` |
| `ASSESSMENT_V4_2` | `assessment-v4.2-adapter` | four assessments under `examples/assessments/` |
| `SOURCE_REGISTRY` | `source-registry-adapter` | CI sample under `examples/operations/`; full 224-source registry via ops |
| `PROGRAMME_ADAPTER` | `programme-adapter-input-adapter` | `examples/programme/PRIMA_COMPLETED_ASSESSMENT_v4.2.1.programme.json` |

Each accessible adapter computes:

- `source_sha256` from fixture or ops bytes;
- `lineage_digest`, a canonical hash of family-specific governing metadata;
- mechanical validation outcome from existing observatory, assessment, or registry validators.

## Protected ops workspace

Set `NEUROAI_OPS_WORKSPACE` to the extracted Operations Starter root (the directory that contains `01_CONFIG/` and `05_RELEASES/`). Absolute paths must not be committed into inventory JSON.

When the env var is unset, CI records known digests for full registry and v1.6 objects as `DIGEST_RECORDED` / `DIGEST_VERIFIED_EXTERNAL` without loading protected bytes. When set, adapters load `ops_relpath` files, verify digests, and migrate.

Never commit the starter ZIP or full protected archive bytes into `neuroai-workbench`.

## External and residual objects

| State | Meaning |
| --- | --- |
| `DIGEST_VERIFIED_EXTERNAL` | Digest and size recorded; bytes live outside the software repo |
| `INACCESSIBLE` | Declared archive object; bytes not available |
| `NOT_RECORDED` | No digest or path recorded |
| `UNKNOWN` | Lineage digest unavailable without loaded bytes |

Residual blocker:

- Combined Excel/Word reconciliation corpus (`AMB-003`) — absent from Operations Starter v0.1.0

Resolved:

- Full registry and v1.6 digests verified from starter (`AMB-001`, `AMB-002`)
- Public data repository exists at https://github.com/fraware/neuroai-observatory-data (`AMB-004`)

## Verification document

`migration/MIGRATION_VERIFICATION.json` is generated from:

- `migration/archive_inventory.jsonl`
- `migration/unresolved_ambiguities.json`
- `migration/MIGRATION_DECISIONS.jsonl`
- public fixtures referenced by the inventory

Generate or refresh the committed CI template (ops env unset):

```powershell
Remove-Item Env:NEUROAI_OPS_WORKSPACE -ErrorAction SilentlyContinue
python scripts/generate_migration_verification.py --recorded-at 2026-08-02T18:00:00Z
```

Ops-aware verification (local only):

```powershell
$env:NEUROAI_OPS_WORKSPACE = "<extract-root>"
python scripts/generate_migration_verification.py --now --output migration/MIGRATION_VERIFICATION.ops.local.json
```

Reproduce the executable v1.4 → v1.6 → v1.7 chain from ops inputs:

```powershell
$env:NEUROAI_OPS_WORKSPACE = "<extract-root>"

# Digests must match migration/archive_inventory.jsonl
Get-FileHash "$env:NEUROAI_OPS_WORKSPACE\05_RELEASES\historical\CANONICAL_EVIDENCE_DEPTH_AND_OBSERVATORY_RELEASE_v1.4.json" -Algorithm SHA256
Get-FileHash "$env:NEUROAI_OPS_WORKSPACE\05_RELEASES\historical\CANONICAL_LIVE_REFRESH_RELEASE_v1.6.json" -Algorithm SHA256
Get-FileHash "$env:NEUROAI_OPS_WORKSPACE\05_RELEASES\historical\ADJUDICATED_DELTA_v1.6.json" -Algorithm SHA256
Get-FileHash "$env:NEUROAI_OPS_WORKSPACE\05_RELEASES\current\CANONICAL_SUCCESSOR_SNAPSHOT_v1.7.json" -Algorithm SHA256

python -m pytest tests/integration/test_ops_v16_chain.py -q
```

When `NEUROAI_OPS_WORKSPACE` is set, `observatory-v1.6-adapter` migrates both v1.6 packages and clears the inaccessible-predecessor blocker for v1.7 verification. Missing ops files fail closed to `DIGEST_RECORDED` (known digest, no invented bytes).

Or through the CLI:

```powershell
neuroai-workbench governing-inputs-verify --repo-root .
```

## Material warnings and human disposition

Named dispositions live in `migration/MIGRATION_DECISIONS.jsonl`. Allowed dispositions include:

- `PENDING_REVIEW`
- `ACKNOWLEDGED`
- `DEFERRED`
- `ACCEPTED`
- `BLOCKED_WITH_RATIONALE`
- `ACCEPTED_WITH_RESIDUALS`

Top-level verification disposition after Phase 0 ingest is `ACCEPTED_WITH_RESIDUALS` with residual `AMB-003`. Software does not auto-acknowledge material warnings without a decision row.

## Boundaries

- No protected neural, participant, clinical, regulatory, credential, or key material belongs in public migration output.
- The combined Excel workbook and Word compendium remain generated views, not master databases.
- Full archive-to-canonical reconciliation against historical workbook counts remains deferred until those bytes are located.

## Related issues

- Issue #44 — canonical observatory data repository and archive-migration boundary
- Epic #34 — observatory engineering takeover programme
