# Observatory successor releases

The successor package generator builds a reviewable candidate from an immutable predecessor and adjudicated delta. Publication requires explicit gate advancement by named local authority claims.

## Release gates

Gate order is strict and sequential:

1. `CANDIDATE` — reproducible package generated from predecessor and delta inputs.
2. `REVIEWED` — schema, referential, predecessor-hash, and reopening reconciliation checks recorded.
3. `AUTHORIZED` — domain, security, and data-governance review recorded.
4. `PUBLISHED` — named release-authority approval recorded.

Automatic publication is prohibited. Each gate advancement appends an immutable gate record with:

- prior and target gate;
- named authority claim (`name_or_role`, `authority_basis`, `accountability_state`);
- rationale;
- verification checks performed.

Authority claims are local workflow identities only. They do not establish authenticated institutional delegation.

## Generated candidate objects

A successor candidate includes:

- predecessor reference and SHA-256;
- adjudicated delta counts and operation inventory;
- reopening recommendation register;
- changed, unchanged, superseded, and unresolved inventories;
- data-quality report checklist;
- withheld-claims statements;
- release gate state and history.

## Verification

```bash
python -m pytest tests/unit/test_successor.py -q
```

Schemas:

- `src/neuroai_workbench/resources/operations/SUCCESSOR_CANDIDATE.schema.json`
- `src/neuroai_workbench/resources/operations/SUCCESSOR_RELEASE_GATE.schema.json`

## Boundary

Canonical publication is a programme release-control state. It does not make every underlying source claim true or establish system conformance.
