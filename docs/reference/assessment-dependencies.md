# Assessment dependency manifests

Assessment dependency manifests declare versioned, typed links between an exact assessment boundary and observatory objects. They support reopening analysis without modifying assessments automatically.

## Dependency roles

Each dependency is typed as one of:

- `IDENTITY_DEFINING` — required to preserve the exact system, configuration, population, or endpoint boundary.
- `FINDING_SUPPORTING` — material to one or more recorded findings.
- `GAP_SUPPORTING` — linked to an open evidence gap or required action.
- `DECISION_SUPPORTING` — linked to a bounded decision object or evidence freeze.
- `CONTEXTUAL_ONLY` — contextual linkage that must not alone trigger reassessment.
- `REOPENING_TRIGGER` — a monitored object whose material change may require reopening review.

## Resolution states

- `RESOLVED` — the dependency target is identified within the declared boundary.
- `PARTIAL` — the target is partially identified; further exact-version control is required.
- `UNKNOWN` — the target is not publicly resolved; no substantive failure is inferred.
- `INACCESSIBLE` — required evidence exists but is not accessible in the public corpus.

## Reference manifests

Four reference manifests ship under `examples/assessments/dependencies/`:

| Assessment ID | Manifest file |
| --- | --- |
| `PRIMA-PUBLIC-2026-001` | `PRIMA-PUBLIC-2026-001.dependencies.json` |
| `PILOT-01-BRAINGATE2-T15-v4.1.5` | `PILOT-01-BRAINGATE2-T15-v4.1.5.dependencies.json` |
| `PILOT-02-FDA-ADBS-v4.1.4` | `PILOT-02-FDA-ADBS-v4.1.4.dependencies.json` |
| `PILOT-05-BRAIN2QWERTY-v4.1.3` | `PILOT-05-BRAIN2QWERTY-v4.1.3.dependencies.json` |

## Validation

```bash
python -c "from neuroai_workbench.assessment_dependencies import validate_manifest_file, reference_manifest_dir; \
[print(p.name, validate_manifest_file(p)['valid']) for p in sorted(reference_manifest_dir().glob('*.json'))]"
```

Schema: `src/neuroai_workbench/resources/operations/ASSESSMENT_DEPENDENCY_MANIFEST.schema.json`.

## Boundary

Manifest validation confirms structure and identifier uniqueness only. It does not establish scientific truth, regulatory authorization, deployment readiness, or conformance.
