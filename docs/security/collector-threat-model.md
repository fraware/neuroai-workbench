# Collector threat model

## Scope

This document covers the approved external source collector that retrieves public registry targets and writes quarantined bytes plus retrieval provenance. It does not cover monitoring adjudication, change-candidate creation, assessment mutation, or canonical observatory release.

Successful retrieval establishes byte identity and provenance only. It does not establish source authenticity, claim truth, regulatory status, clinical effectiveness, conformance, or assessment effect.

## Separation from monitoring adjudication

| Concern | Collector | Monitoring workbench |
| --- | --- | --- |
| Network access | Yes, in a restricted environment | No default network acquisition |
| Writes captured bytes | Quarantine only | Immutable snapshots after approved handoff |
| Creates change candidates | No | Yes, after human-directed comparison |
| Adjudicates materiality | No | Human adjudication only |
| Mutates assessment findings | No | No automatic mutation |

The collector hands off approved quarantine records. `record_snapshot` in the monitoring pipeline remains a separate, human-gated operation that accepts bytes only after quarantine approval.

## Protected assets

- Workbench private evidence, assessment, and event directories.
- Collector credentials and secret-store material.
- Quarantined byte stores before approval.
- Registry integrity hash and source allowlist.
- Retrieval provenance records used for audit and retry visibility.

## Adversaries and failure modes

### 1. Server-side request forgery (SSRF)

An attacker manipulates a registry entry, redirect chain, or adapter override so the collector requests an internal service, metadata endpoint, or cloud control plane instead of the intended public source.

**Controls**

- Registry-driven allowlist only; no ad hoc URL parameters outside reviewed adapters.
- HTTP and HTTPS only unless a separately reviewed adapter explicitly permits another scheme.
- DNS resolution before every request and after every redirect hop.
- Reject loopback, private, link-local, reserved, multicast, and unspecified addresses after resolution.
- Revalidate redirect targets with the same SSRF checks applied to the initial URL.
- Block embedded credentials in URLs at schema and runtime validation.

**Contract mapping**

- `collection-request.schema.json` constrains `requested_url`.
- `collection-result.schema.json` constrains `requested_url`, `final_url`, and `redirect_chain`.
- `collection-failure.schema.json` records `SSRF_BLOCKED`.

### 2. DNS rebinding

An attacker serves an initial public address record, then changes DNS so a subsequent connection resolves to a private target.

**Controls**

- Resolve immediately before connect for every hop.
- Compare resolved addresses against the blocked-address policy on every request and redirect.
- Fail closed when resolution changes within a single retrieval attempt.
- Record DNS decisions in the collection result for audit.

**Contract mapping**

- `collection-result.schema.json` requires `dns_resolution.rebinding_check`.
- `collection-failure.schema.json` records `DNS_REBINDING_BLOCKED`.

### 3. Redirect abuse

An attacker uses open redirects, protocol downgrade, or long redirect chains to reach disallowed targets or exhaust retry budgets.

**Controls**

- Bounded redirect count.
- Revalidate every redirect target with SSRF and scheme checks.
- Reject redirects to non-HTTP(S) schemes unless a reviewed adapter permits otherwise.
- Record the full redirect chain in provenance.

**Contract mapping**

- `collection-result.schema.json` caps `redirect_chain` length and validates each hop.
- `collection-failure.schema.json` records `REDIRECT_BLOCKED`.

### 4. Archive and decompression bombs

An attacker serves compressed content that expands beyond policy limits or consumes excessive memory or disk during quarantine write.

**Controls**

- Maximum response bytes before and after decompression.
- Decompression-ratio limits and streaming size checks.
- Timeouts on connect, read, and total retrieval duration.
- Content-type allowlists per adapter class.
- Reject unsafe filenames and path-bearing names before quarantine write.

**Contract mapping**

- `collection-result.schema.json` caps `size_bytes` and constrains `original_filename`.
- `collection-failure.schema.json` records `DECOMPRESSION_BOMB`, `SIZE_LIMIT_EXCEEDED`, and `UNSAFE_FILENAME`.

### 5. Credential leakage

An attacker or misconfiguration causes credentials to appear in URLs, manifests, logs, or quarantine metadata.

**Controls**

- Prohibit embedded credentials in URLs at schema validation.
- Load credentials only from an approved secret store at runtime.
- Never write secrets to collection manifests, quarantine records, or logs.
- Redact or omit sensitive headers from persisted provenance.

**Contract mapping**

- URL patterns reject `@` credential forms across request, result, and failure schemas.
- `collection-failure.schema.json` records `CREDENTIAL_LEAK_PREVENTED`.

### 6. Quarantine escape

An attacker attempts to write outside the quarantine root using path traversal, absolute paths, symlinks, or unsafe archive members.

**Controls**

- Quarantine-only writes; no direct access to workbench workspace paths.
- Reject filenames containing path separators, `..`, or control characters.
- Store objects under content-addressed relative paths inside the quarantine root.
- Require human approval before any handoff to monitoring snapshot registration.

**Contract mapping**

- `collection-result.schema.json` and `quarantine-record.schema.json` constrain `original_filename` and `quarantine_path`.
- `quarantine-record.schema.json` requires explicit `approval_state` before handoff.
- `collection-failure.schema.json` records `QUARANTINE_REJECTED`.

## Authority boundary

The collector may:

- retrieve approved registry targets within reviewed adapter policy;
- record retrieval provenance, DNS decisions, redirect chains, and byte hashes;
- write captured bytes to quarantine;
- record visible failures without overwriting prior successful monitoring state.

The collector may not:

- create monitoring snapshots directly;
- create change candidates or adjudications;
- mutate assessment findings or observatory successor records;
- imply authenticity, completeness, or substantive truth from a successful retrieval;
- access workbench private evidence or assessment directories.

## Residual risks

Schema validation and this threat model do not replace independent security review, restricted-network deployment, secret-store hardening, or operational monitoring of collector behavior. A compromised collector host, secret store, or registry supply chain can still produce structurally valid but misleading provenance. Human quarantine approval is a workflow gate, not proof of substantive correctness.

## Related documents

- [ADR 0008 — Collector deployment boundary](../adr/0008-collector-deployment-boundary.md)
- [Collector contracts index](../operations/collector-contracts.md)
- [Observatory automation operating model](../operations/observatory-automation.md)
- [THREAT_MODEL.md](../../THREAT_MODEL.md)
