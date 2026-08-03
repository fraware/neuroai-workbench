# ADR 0010 — Discovery query streams (extends collector deployment boundary)

## Status

Accepted for Wave 5 continuous discovery layer.

## Context

ADR 0008 isolates network retrieval behind a collector quarantine and human handoff boundary. The observatory still lacks the first half of `discovery → candidate sources → controlled registry → monitoring`: fixed registries and non-authoritative cohort helpers do not record continuous discovery queries, result tallies, or human-gated source proposals.

Adding discovery HTTP clients inside `monitoring.py` or silently appending to the live monitor registry would collapse capability boundaries and risk treating search hits as authorized sources.

## Decision

1. Introduce a dedicated `discovery` package and versioned schemas under `resources/discovery/` for `DISCOVERY_QUERY`, `DISCOVERY_RUN`, `CANDIDATE_SOURCE_PROPOSAL`, `DISCOVERY_ADJUDICATION`, and `REGISTRY_SUCCESSOR_PROPOSAL`.
2. Keep discovery offline-first by default. Opt-in network execution requires `NEUROAI_LIVE_DISCOVERY=1` and reuses the collector public-URL / SSRF checks (`collector.url_policy`). Live HTTP transport remains the collector's responsibility; discovery accepts caller-supplied network result records under that gate.
3. Execution produces candidate source proposals only. Human acceptance is required before any registry succession. Successors are append-only draft versions (`overwrite_refused: true`); in-place silent overwrite is refused.
4. Treat discovery counts and proposals as mechanical, untrusted workflow artifacts. Schema validity and digests do not establish authenticity, completeness, regulatory coverage, or assessment effect.
5. Store discovery runs under the ops/discovery workspace; commit only public synthetic fixtures and summaries to the software repository.

## Consequences

- Discovery, collector retrieval, monitoring adjudication, and canonical registry publication remain separately reviewable.
- Security review can focus discovery egress on the same SSRF/quarantine/handoff model as ADR 0008 without reopening assessment authority.
- Registry growth becomes an explicit human-gated succession path rather than crawl-driven mutation.

## Non-goals

- No automatic assessment findings or reopening from discovery hits.
- No claim of global NeuroAI source completeness.
- No authentication of reviewer identities beyond claimed local workflow attribution.
- No embedding of live HTTP clients inside the discovery package in this increment.

## Relationship to ADR 0008

This ADR extends the collector deployment boundary: discovery streams are an additional opt-in network-facing surface that must obey the same offline-first default, SSRF policy, quarantine/handoff discipline for retrieved bytes, and human gate before workbench authority changes. It does not relocate collector quarantine writes into discovery.
