# Adjudicated observatory delta

An adjudicated delta is a **non-canonical** package that records proposed observatory changes supported by human adjudication. It is not a canonical successor release and does not establish substantive correctness of those changes.

## Scope

This module provides:

- versioned JSON Schema for typed delta operations (no unrestricted JSON Patch);
- disposition registers for accepted, rejected, deferred, duplicate, needs-evidence, and unresolved candidates;
- a deterministic compiler from refresh packages to adjudicated deltas;
- fail-closed application onto an immutable predecessor (this module).

## Application

```python
from neuroai_workbench.delta import apply_delta

result = apply_delta(predecessor_release, adjudicated_delta, output_dir, apply_id="apply-2026-08-02")
```

Application writes:

- `candidate-successor.json` — proposed successor (NON_CANONICAL);
- `apply-manifest.json` — integrity record including delta and predecessor hashes.

The predecessor object and file are never modified. Applying the same delta twice to the same output directory is explicitly rejected.

## Operation vocabulary

Only explicit operations are permitted:

| Operation | Purpose |
| --- | --- |
| `ADD_RECORD` | Append a new record to a named section |
| `ADD_RELATIONSHIP` | Append a relationship record |
| `UPDATE_FIELD_WITH_PREDECESSOR` | Update one field with verified before-value |
| `ADD_EVENT` | Append an observatory event record |
| `SUPERSEDE_RECORD` | Replace a record via explicit tombstone and successor reference |
| `ADD_ALIAS` | Register a canonical alias |
| `RECORD_SOURCE_INACCESSIBILITY` | Record inaccessible source state |
| `QUEUE_ASSESSMENT_REVIEW` | Queue assessment reopening review without mutating findings |

Generic patch paths, free-form JSON Patch, or unrestricted field mutation are rejected.

## Package status

All adjudicated delta packages carry `metadata.status: NON_CANONICAL`. They must pass domain review and authorized release gates before any canonical successor is issued.

## Compiler

```python
from neuroai_workbench.delta import compile_adjudicated_delta

delta = compile_adjudicated_delta(
    refresh_package,
    predecessor_release,
    predecessor_release_id="v1.4-synthetic",
    operation_specs={
        "CAND-...": [
            {
                "operation_type": "UPDATE_FIELD_WITH_PREDECESSOR",
                "target_section": "sources",
                "record_id_field": "source_id",
                "record_id": "SRC-0001",
                "field": "baseline_verification_state",
                "before_value": "CURRENT_VERIFIED",
                "after_value": "CURRENT_PARTIAL",
            }
        ]
    },
)
```

Accepted candidates without explicit `operation_specs` and without a recognized `change_class` default are recorded in `blocked_operations` rather than silently compiled.

## Authority boundary

- An adjudicated delta records **proposed** changes only.
- Schema validation and hash checks do not establish scientific, regulatory, or conformance truth.
- Missing or blocked operations are not converted into automatic failure of unrelated records.

## Related issues

- Epic #34 — Operationalize the NeuroAI observatory
- Issue #39 — Apply accepted candidates into an adjudicated observatory delta
