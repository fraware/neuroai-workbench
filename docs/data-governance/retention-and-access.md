# Retention and access (observatory stores)

## Scope

Retention and access rules for the five stores defined in [data-storage-boundaries.md](../architecture/data-storage-boundaries.md) and [ADR-0009](../adr/0009-canonical-data-and-evidence-stores.md).

This policy does not authorize redistribution of protected materials or establish legal hold procedures for a specific institution. Institutional deployments must adopt their own schedules, legal-hold, backup, participant-withdrawal, and destruction verification processes (see root `DATA_GOVERNANCE.md`).

## Store rules

| Store | Access | Retention baseline |
|-------|--------|--------------------|
| Software (S1) | Public Git history | Git retention; tagged releases retained indefinitely while programme active |
| Public canonical (S2) | Public releases | Immutable release tags; predecessors retained for reconstruction |
| Protected evidence (S3) | Need-to-know custodians | Custodian schedule; workbench retains digests/metadata per case policy |
| Generated artifacts (S4) | Reconstructible | Disposable if regenerable; release-attached products follow S2 tag retention |
| Immutable archive (S5) | Read-only reference | Preserve while any successor release cites inventory digests |

## Access prohibitions

- No credentials, access tokens, or decryption material in S1/S2 records.
- No absolute workstation paths in public inventory (use relative archive keys or `INACCESSIBLE`).
- No private neural/participant bytes in public GitHub.
- Reviewer names in operational records remain claimed local workflow identities unless an authenticated deployment establishes otherwise.

## Deletion

Deletion of S3/S5 material is an administrative operation outside the workbench. Secure erasure depends on medium, filesystem, and backups. The workbench records digests; digests do not prove destruction.
