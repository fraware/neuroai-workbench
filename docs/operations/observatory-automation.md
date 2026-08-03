# Observatory automation operating model

## Purpose

The monitoring pipeline converts a static source registry and immutable source captures into reviewable change candidates. It does not make substantive NeuroAI findings automatically. Human adjudication controls whether a detected change enters an observatory delta or triggers assessment review.

## Controlled flow

```text
source registry
  -> due-source plan
  -> approved collector
  -> immutable content-addressed snapshot
  -> mechanical comparison
  -> change candidate
  -> human adjudication
  -> non-canonical refresh package
  -> domain review
  -> canonical observatory successor release
```

The current implementation covers the first seven stages. Canonical successor generation remains a separately authorized release operation.

## Capture and content identity

A source capture and its downloaded bytes are separate integrity objects. Each retrieval receives an immutable timestamped capture identifier. The downloaded content is stored by SHA-256, so unchanged bytes retrieved on different dates are deduplicated while both retrieval events remain visible. This permits the system to record a successful no-change check without inventing a substantive update or overwriting prior monitoring history.

Operational ingestion requires an explicit timezone, rejects path-bearing filenames and literal private-network targets, and enforces the controlled maximum object size. Redirect resolution, DNS rebinding protection, rate limits, robots and terms-of-use checks remain responsibilities of the separately approved collector.

## Canonical inputs

The initial operational state is seeded from the programme's controlled assets:

- `SOURCE_MONITOR_REGISTRY_v1.5.json`: 224 monitored source records;
- the immutable v1.4 detailed observatory baseline;
- the v1.6 live-refresh record and adjudicated delta;
- the compact v1.7 successor snapshot;
- the current v4.2 assessment resources and completed assessment records.

The source registry may retain legacy `CONTROLLED_LOCAL_INPUT` paths as provenance. Those paths are reported as non-portable and should be migrated to content-addressed workspace objects before operational reuse.

`CONTROLLED_LOCAL_INPUT` sources and any source with `network_access_required: false` are routed to the planner **manual** queue with reason `CONTROLLED_LOCAL_OR_NO_NETWORK`. They never appear in the HTTP collector `due` list, even when cadence would otherwise mark them due. Optional ingest uses `LocalContentAddressedAdapter` against an explicit allowlisted root to write quarantine objects by content hash; the workbench then records a monitoring snapshot separately. The collector package never calls monitoring write APIs. The scheduler also records a per-source `POLICY_BLOCK` outcome for any non-`http(s)` URL that reaches `run_plan`, without aborting the rest of the plan.

## Ops workspace (full 224-source registry)

Set `NEUROAI_OPS_WORKSPACE` to the extracted Operations Starter root (directory containing `01_CONFIG/` and `05_RELEASES/`). The full registry is never committed to this software repository.

```bash
export NEUROAI_OPS_WORKSPACE=/path/to/NeuroAI_Operations_Starter_v0.1.0

neuroai-monitor registry-validate \
  "$NEUROAI_OPS_WORKSPACE/01_CONFIG/source_monitor_registry_v1.5.json"

neuroai-monitor init "$NEUROAI_OPS_WORKSPACE/03_WORKBENCH" \
  "$NEUROAI_OPS_WORKSPACE/01_CONFIG/source_monitor_registry_v1.5.json"

neuroai-monitor plan "$NEUROAI_OPS_WORKSPACE/03_WORKBENCH" \
  --as-of 2026-08-02 \
  --out "$NEUROAI_OPS_WORKSPACE/04_REVIEW_QUEUE/ops-monitor-plan.json"

neuroai-monitor source-health "$NEUROAI_OPS_WORKSPACE/03_WORKBENCH" \
  --as-of 2026-08-02 \
  --out "$NEUROAI_OPS_WORKSPACE/04_REVIEW_QUEUE/source-health.json"
```

Integration tests under `tests/integration/` skip unless `NEUROAI_OPS_WORKSPACE` is set. CI continues to use the three-record synthetic sample below.

## Commands

Validate the CI sample registry:

```bash
neuroai-monitor registry-validate \
  examples/operations/SOURCE_MONITOR_REGISTRY_SAMPLE.json
```

Initialize monitoring state inside a workbench workspace:

```bash
neuroai-monitor init workspaces/operations \
  examples/operations/SOURCE_MONITOR_REGISTRY_SAMPLE.json
```

Generate the due-source plan without making network requests:

```bash
neuroai-monitor plan workspaces/operations \
  --as-of 2026-08-02 \
  --out artifacts/monitor-plan.json
```

Emit a structured source-health report (due/overdue/manual, failure class, obsolete/controlled-local flags):

```bash
neuroai-monitor source-health workspaces/operations \
  --as-of 2026-08-02 \
  --out artifacts/source-health.json
```

Register bytes captured by an approved external collector:

```bash
neuroai-monitor snapshot workspaces/operations SRC-0004 \
  incoming/SRC-0004.html \
  --media-type text/html \
  --retrieved-at 2026-08-02T08:00:00Z
```

Compare two immutable captures:

```bash
neuroai-monitor diff workspaces/operations SRC-0004 \
  SNAP-SRC-0004-OLD SNAP-SRC-0004-NEW
```

Create a candidate only when the comparison requires review:

```bash
neuroai-monitor candidate workspaces/operations SRC-0004 \
  SNAP-SRC-0004-NEW \
  --previous-snapshot-id SNAP-SRC-0004-OLD
```

Record the human decision:

```bash
neuroai-monitor adjudicate workspaces/operations CAND-... ACCEPT \
  --change-class REGULATORY_OR_MARKET_EVENT \
  --materiality MATERIAL \
  --reopening-effect REVIEW_REQUIRED \
  --rationale "The controlling regulatory record changed; exact-system review is required."
```

Build a review candidate package:

```bash
neuroai-monitor package workspaces/operations refresh-2026-08 \
  --evidence-cutoff 2026-08-02 \
  --out artifacts/refresh-package-result.json
```

## Programme control

**Control identifier:** NEUROAI-ENG-TAKEOVER-1.0  
**Governing epic:** [#34](https://github.com/fraware/neuroai-workbench/issues/34)

Named humans retain substantive classification, entity-resolution approval, assessment reopening, and canonical release authority. Automation may schedule, retrieve, preserve, compare, propose, validate, and render only.

Locked decisions:

1. CodeQL Option A: Default Setup disabled; Advanced `.github/workflows/codeql.yml` retained; required check context `codeql`.
2. Public data repository name: `neuroai-observatory-data` ([ADR-0009](../adr/0009-canonical-data-and-evidence-stores.md)).
3. One capability per PR; see [public-data-release.md](public-data-release.md) for S2 publication.

Authority exclusions (always stated): no UNESCO endorsement; no regulatory, clinical, or conformance claim from software gates; generated Excel/Word/PDF/dashboard products are views never canonical inputs; absence of evidence is not automatic FAIL.

## Verification gates

### Software gates

- Source-registry schema and semantic validation pass.
- Capture identifiers remain distinct from content hashes.
- Repeated unchanged retrievals preserve both capture events and deduplicate bytes.
- Snapshot manifests and content digests verify.
- Change candidates never mutate canonical observatory or assessment state.
- Accepted candidates require explicit human change class, materiality, reopening effect, and rationale.
- Adjudications and refresh packages are immutable and content-addressed.
- The monitoring core satisfies its dedicated module coverage floor.
- Ruff, mypy, Python 3.10–3.14 tests, package verification, release verification, container checks, CodeQL, and dependency controls pass.

### Substantive gates

Software verification does not establish source authenticity, claim truth, scientific validity, regulatory status, clinical safety, conformance, or UNESCO endorsement. A canonical observatory successor still requires reconciliation against the predecessor release and an authorized release decision with named release-authority approval. Issue #10 independent-review tracks remain optional recommended follow-up and do not block AUTHORIZED or PUBLISHED.

## Authority boundary

Automation may:

- schedule checks;
- preserve bytes and hashes;
- detect content differences;
- propose a change candidate;
- validate identifiers and records;
- assemble accepted candidate records for release review.

Automation may not:

- establish a regulatory event from a company claim;
- determine clinical effectiveness or safety;
- change PASS, PARTIAL, FAIL, or NOT ASSESSED findings;
- reopen or close an assessment automatically;
- issue a canonical observatory successor release;
- imply UNESCO endorsement or institutional adoption.

## Collection boundary

The workbench intentionally does not crawl all registered URLs from GitHub Actions. Acquisition requires a separately approved collector with rate limits, robots and terms-of-use review, redirect and SSRF controls, source-specific authentication policy, maximum-byte limits, and a protected storage design. The workbench receives captured bytes and records their identity and provenance.

## Operational cadence

- Regulatory, safety, and trial sources: daily or weekly planning.
- Company and institutional sources: weekly or monthly planning.
- Patent and broad landscape sources: monthly or quarterly planning.
- Human candidate triage: weekly.
- Successor release decision: monthly when material accepted changes exist.
- Full source-health and unresolved-evidence review: quarterly.

A period with no material change should create a monitoring record, not an artificial substantive release.
