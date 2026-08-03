# Governance scope manifests

## Purpose

A governance scope manifest defines the exact immutable object set presented to later reviewers, owners, policy evaluators, and release authorities. It is the first additive layer introduced by issue #101 after completion of the non-canonical observatory core.

The manifest provides byte-identity and storage-boundary controls. It grants no review, owner, scientific, regulatory, institutional, UNESCO, or release authority.

## Required logical roles

Each scope contains one reference for every required role:

- `PREDECESSOR_RELEASE`;
- `SUCCESSOR_CANDIDATE`;
- `DELTA`;
- `REOPENING_REGISTER`;
- `PRODUCT_MANIFEST`;
- `WITHHELD_CLAIMS`.

`CORE_CYCLE_EXECUTION` is optional for scopes that do not arise from a protected live-refresh cycle. When present, it binds the digest-level execution record or a protected operations object.

Logical roles are unique. Each role has one permitted `object_type`; changing a role label cannot substitute a release for a delta, a product manifest for a candidate, or another structurally valid JSON object for the reviewed object class.

## Storage boundaries and locators

The manifest records one of four storage boundaries for every object:

- `PUBLIC_GIT`;
- `GENERATED_OUTPUT`;
- `PROTECTED_WORKSPACE`;
- `ARCHIVE`.

Public, generated, and archive locators are normalized relative POSIX paths. Absolute paths, `..` traversal, backslashes, and protected-reference prefixes are rejected.

Protected objects use only opaque locators of the form `protected-ref:<identifier>`. The manifest never records the protected filesystem path. Verification receives a separate in-memory mapping from the opaque reference to the protected local file. That mapping is neither serialized into the manifest nor appended to the event log.

## Canonical identity

`manifest_sha256` is computed over canonical JSON with only `manifest_sha256` and private runtime keys excluded. The hash binds:

- the scope identifier and label;
- creation attribution;
- every logical role;
- every object type and label;
- every object digest;
- every storage boundary and locator;
- the non-authorizing authority profile;
- the claim boundary.

The object list is sorted by logical role before the manifest is recorded. A matching digest establishes byte identity for the acquired file. It does not establish source authenticity, truth, completeness, legal admissibility, reviewer identity, or institutional delegation.

## Recording workflow

Use `scope_object_for_path` to construct each object reference. The helper computes the file digest and enforces the declared boundary:

```python
reference = scope_object_for_path(
    role="SUCCESSOR_CANDIDATE",
    label="v2.3 successor candidate",
    object_type="SUCCESSOR_CANDIDATE",
    path=candidate_path,
    storage_boundary="GENERATED_OUTPUT",
    boundary_root=generated_root,
)
```

For a protected object, supply an opaque reference instead of a boundary root:

```python
reference = scope_object_for_path(
    role="CORE_CYCLE_EXECUTION",
    label="Protected core-cycle record",
    object_type="CORE_CYCLE_EXECUTION",
    path=protected_cycle_path,
    storage_boundary="PROTECTED_WORKSPACE",
    protected_ref="cycle-43",
)
```

`record_governance_scope_manifest` verifies every referenced object before persisting the manifest. It then writes an append-only record under `governance/scopes/` and appends `GOVERNANCE_SCOPE_RECORDED` to the workspace event chain. The event binds the scope ID, manifest digest, object count, and `release_authorization_performed: false`.

## Verification workflow

`verify_governance_scope_manifest` checks:

1. closed JSON Schema conformance;
2. canonical manifest hash;
3. required and unique logical roles;
4. exact role-to-object-type mapping;
5. normalized storage-boundary locators;
6. referenced-file presence;
7. referenced-file SHA-256;
8. the prohibition on release authorization.

`verify_governance_scope_records` additionally verifies:

- duplicate scope identifiers;
- the workspace event chain and trailer;
- one matching append-only event for every persisted scope;
- warning aggregation without converting warnings into authorization.

## Reproducibility boundary

Deterministic candidates, deltas, reopening records, manifests, claim sets, and products reproduce from identical frozen inputs and toolchain constraints. Protected or live-acquired bytes are verified against their recorded digests through local bindings. Remote resources may change, so the governance scope binds the acquired bytes presented for review rather than asserting timeless identity of a remote endpoint.

## Authority boundary

A valid governance scope means that the software verified the declared object bytes and manifest structure. It does not mean that:

- a reviewer examined the scope;
- a claimed reviewer identity is authenticated;
- conflicts of interest were resolved;
- scientific or domain claims are correct;
- clinical, regulatory, security, accessibility, or conformance requirements are satisfied;
- an institution or UNESCO endorsed the work;
- a successor is authorized or published.

Reviewer opinions, owner dispositions, policy evaluation, and release-authority decisions are separate append-only layers tracked by issues #110–#114.
