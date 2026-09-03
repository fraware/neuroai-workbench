# Observatory S1 pin handoff (Workbench prerequisite)

Status: **S1 Workbench prerequisite handoff only**. This note does not pass G0, approve G1, freeze G2, authorize Observatory S2 mutation, authorize publication, or establish scientific validity.

## Exact pin identity

| Field | Value |
| --- | --- |
| Observatory pin target SHA | `685f1597a2a63f2e2217f65f115a67ac3e35cc55` |
| Pin source PR | [#267](https://github.com/fraware/neuroai-workbench/pull/267) (`MERGED_TRANSPORT_WORKBENCH_SHA`) |
| Workbench green base (pre-transport repair) | `b4374fe8ecca69fae1f19f55dfda31a9d9df8387` ([#274](https://github.com/fraware/neuroai-workbench/pull/274)) |
| Package version at handoff | `0.3.0.dev0` |
| Hosted live-collection proof run | `33781523925` |
| Hosted proof job | `100736091926` |
| Hosted proof route outcomes | `200` / `200` / `200` |

The pin SHA is the merged transport/workbench commit that Observatory operators should treat as the reusable S1 software identity for subsequent S2 ledger work. Package-version equality alone is not execution evidence. Schema validation, CI green, and route HTTP 200 responses do not authorize canonical S2 release.

## What this handoff establishes

1. Workbench transport framing required for hosted live collection was repaired and merged at `685f1597a2a63f2e2217f65f115a67ac3e35cc55`.
2. A hosted proof run (`33781523925` / job `100736091926`) completed with route outcomes `200/200/200` against that transport lineage.
3. PRE-G2 held-out benchmark software lineage on Workbench is the keyed-HMAC stack selected by ADR 0019 (`#272` then `#275`), with deferred packaging ported additively afterward. Control flags remain fail-closed (`g2_passed=false` and equivalent non-authority fields).

## What this handoff does not establish

- G0 passage
- G1 approval or disposition authenticity
- G2 freeze or held-out label construction
- Real held-out membership, labels, adjudication packets, licensed bytes, or commitment secrets in the public repository
- Observatory S2 ledger mutation or canonical publication
- v4.2 assessment effect or scientific truth

## Operator stop condition

A true Observatory pin (S2 ledger binding, programme release attestation, or external gate record) cannot be completed inside this Workbench repository alone. Operators must take the exact SHA and proof IDs above into the Observatory S2 process and produce a separate governed S2 record. Until that external step exists, treat this document as the Workbench-side prerequisite artifact only.

## Related Workbench references

- ADR 0019: `docs/adr/0019-pre-g2-heldout-benchmark-lineage.md`
- Held-out boundary: `docs/methodology/held-out-benchmark-boundary.md`
- Pinned DNS transport: `docs/collector/pinned-dns-transport.md`
- Compatibility identity: `docs/architecture/compatibility-identity.md`
