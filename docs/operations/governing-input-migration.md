# Governing input migration

Phase C migrates **governing** observatory and assessment inputs from the software repository and declared archive inventory into typed migration records. Migration establishes storage lineage and adapter outcomes only. It does not validate substantive claims, confer authorization, or establish conformance.

## Families and adapters

| Family | Adapter | Public fixture |
| --- | --- | --- |
| `OBSERVATORY_V1_4` | `observatory-v1.4-adapter` | `examples/observatory/evidence_depth_release_v1.4.json` |
| `OBSERVATORY_V1_7` | `observatory-v1.7-adapter` | `examples/observatory/canonical_successor_snapshot_v1.7.json` |
| `ASSESSMENT_V4_2` | `assessment-v4.2-adapter` | four assessments under `examples/assessments/` |
| `SOURCE_REGISTRY` | `source-registry-adapter` | `examples/operations/SOURCE_MONITOR_REGISTRY_SAMPLE.json` |
| `PROGRAMME_ADAPTER` | `programme-adapter-input-adapter` | `examples/programme/PRIMA_COMPLETED_ASSESSMENT_v4.2.1.programme.json` |

Each accessible adapter computes:

- `source_sha256` from fixture bytes;
- `lineage_digest`, a canonical hash of family-specific governing metadata;
- mechanical validation outcome from existing observatory, assessment, or registry validators.

## Inaccessible objects

Inventory entries for external archive objects that are not present in the public software repository emit typed states instead of invented values:

| State | Meaning |
| --- | --- |
| `INACCESSIBLE` | Declared archive object; bytes not available locally |
| `NOT_RECORDED` | No digest or path recorded |
| `UNKNOWN` | Lineage digest unavailable |

Blocked governing objects include:

- `external/archive/observatory_v1.6_live_refresh_delta.json`
- `external/archive/SOURCE_MONITOR_REGISTRY_v1.5.json`

Missing archive bytes are recorded as migration blockers. They do not convert into automatic substantive failure for assessments or authorization.

## Verification document

`migration/MIGRATION_VERIFICATION.json` is generated from:

- `migration/archive_inventory.jsonl`
- `migration/unresolved_ambiguities.json`
- public fixtures referenced by the inventory

Generate or refresh the template:

```powershell
python scripts/generate_migration_verification.py
```

Or through the CLI:

```powershell
neuroai-workbench governing-inputs-verify --repo-root .
```

Use `--now` only for operational reruns. The committed template uses fixed `recorded_at` for deterministic verification.

## Material warnings and human disposition

Material warnings appear on individual migration records and in the top-level `material_warnings` array. Each warning and the verification document include `human_disposition`, defaulting to `PENDING_REVIEW`. A human reviewer must disposition warnings before treating migration as operationally closed.

Allowed dispositions:

- `PENDING_REVIEW`
- `ACKNOWLEDGED`
- `DEFERRED`

Software does not auto-acknowledge material warnings.

## Boundaries

- No protected neural, participant, clinical, regulatory, credential, or key material belongs in public migration output.
- The combined Excel workbook and Word compendium remain generated views, not master databases.
- Full archive-to-canonical reconciliation against historical workbook counts remains deferred until the immutable archive is verified locally.

## Related issues

- Issue #44 — canonical observatory data repository and archive-migration boundary
- Epic #34 — observatory engineering takeover programme
