# ADR 0008 — Collector deployment boundary

## Status

Accepted for Wave 0 contract definition. Implementation remains a separately reviewed increment.

## Context

Issue #35 requires an approved external source collector that retrieves public registry targets and hands immutable bytes plus retrieval provenance to the monitoring pipeline introduced in PR #32. The workbench must remain offline-first and must not perform default network acquisition.

Monitoring operations already record immutable snapshots, change candidates, and human adjudications. Mixing network retrieval into `monitoring.py` would blur capability boundaries, complicate security review, and increase the risk that retrieved bytes bypass quarantine or appear authoritative before human review.

## Decision

1. Implement the collector as a dedicated package and deployment boundary, not as code inside `monitoring.py` or the default workbench CLI.
2. Define versioned collector contracts under `src/neuroai_workbench/resources/collector/` for collection requests, results, failures, and quarantine records.
3. Restrict collector writes to quarantine storage only. The collector must not write into workbench assessment, evidence, event, or monitoring snapshot directories.
4. Require explicit quarantine approval before any call to `record_snapshot` or equivalent monitoring handoff. Retrieval success alone does not authorize snapshot registration.
5. Treat collector output as untrusted provenance plus byte identity. Schema validity and hash agreement do not establish authenticity, claim truth, regulatory status, or assessment effect.
6. Keep HTTP client, scheduler, adapter, and secret-store integration outside this repository increment until a follow-on implementation issue is approved.

## Consequences

- Monitoring and collector responsibilities remain separately testable and separately deployable.
- Security review can focus network exposure, SSRF, DNS rebinding, redirect handling, and quarantine isolation without re-reviewing adjudication semantics on every collector change.
- The workbench continues to receive bytes through an explicit, auditable handoff path rather than implicit crawl behavior.
- Additional implementation work is required for adapters, scheduling, secret management, and operational deployment.

## Non-goals

- No automatic change-candidate or adjudication creation from collector output.
- No canonical observatory successor publication from collector output.
- No inference of substantive truth from retrieval success, HTTP 200 responses, or digest matches alone.

## Follow-on

Implement the collector service, restricted-network deployment profile, adversarial runtime tests, and operational runbooks in bounded follow-on issues under epic #34. Update `THREAT_MODEL.md` when runtime controls land.

Continuous discovery query streams (candidate sources before registry succession) are specified in [ADR 0010](0010-discovery-query-streams.md) and reuse this boundary's offline-first, SSRF, and human-gate posture without relocating quarantine writes into discovery.
