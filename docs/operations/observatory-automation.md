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

## Commands

Validate the exact legacy registry:

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
