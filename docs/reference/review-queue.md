# Observatory monitoring review queue

The review queue is an append-only workflow layer over observatory monitoring records. It projects change candidates and adjudications into reviewer-facing queue items, records local named profiles, exclusive leases, and multiple immutable opinions.

## Boundary

Review queue records use `authority_profile: LOCAL_UNAUTHENTICATED_ATTRIBUTION`. They attribute a claimed local profile identifier and role; they do not authenticate a person, verify an institutional appointment, or confer legal or scientific decision authority. Authentication belongs to a separate institutional deployment architecture.

Queue items are projections derived from monitoring workspace state. They are not a separate source of truth. Rebuilding projections never mutates canonical observatory, monitoring candidate, adjudication, snapshot, or assessment records.

Leases coordinate local review workflow. They do not lock or modify monitoring records. Opinions are append-only workflow statements. They do not perform adjudication and do not mutate observatory or assessment data.

## Roles

Supported local named profile roles:

- `MONITORING_REVIEWER`
- `ADJUDICATION_REVIEWER`
- `LEAD_MONITORING_REVIEWER`
- `OBSERVER`

Each profile is registered once under `observatory/review_queue/profiles/`. Duplicate registration with different content is refused.

## Queue items

Queue items are rebuilt from monitoring candidates and adjudications. Each pending or adjudicated candidate becomes one `CHANGE_CANDIDATE` item with:

- a stable `item_id` derived from the candidate identifier;
- the current monitoring record hash;
- queue status (`OPEN`, `ADJUDICATED`, or `STALE`);
- linked snapshot identifiers when present.

Projections can be persisted as optional snapshots under `observatory/review_queue/projections/` for inspection, but the authoritative monitoring records remain under `observatory/monitoring/`.

## Leases

A reviewer profile claims an exclusive lease on a queue item for a bounded TTL (default one hour, maximum twenty-four hours). While active, another profile cannot claim the same item. A profile may release its own lease; releasing another profile's lease is refused.

Lease claim and release records are append-only. Expired leases are ignored by active-lease resolution without rewriting history.

## Opinions

Multiple opinions may exist for the same queue item. Each opinion records role, position, rationale, monitoring record hash, and lease linkage. Opinions are immutable; overwriting an existing opinion file is refused.

Positions include support, oppose, defer, abstain, and needs evidence. Disagreement remains visible across concurrent opinions.

Submitting an opinion requires an active lease held by the same profile. Stale opinions are detected when the underlying monitoring record hash no longer matches the projection.

## Integrity

Profiles, leases, lease releases, and opinions are individually hashed and linked to the review-queue event chain. Verification detects altered records, unknown queue items, duplicate releases, stale opinions, and invalid authority profiles.

Hash validity proves record consistency only. It does not prove that a reviewer is who they claim to be or that their reasoning is correct.

## Python API

```python
from pathlib import Path

from neuroai_workbench.review_queue import (
    claim_lease,
    initialize_review_queue,
    list_queue_items,
    register_reviewer_profile,
    release_lease,
    render_queue_markdown,
    submit_opinion,
    verify_review_queue,
)

workspace = Path("path/to/workbench")
initialize_review_queue(workspace)
register_reviewer_profile(
    workspace,
    "reviewer-a",
    "Reviewer A",
    ["MONITORING_REVIEWER"],
)
items = list_queue_items(workspace, persist_projection=True)
lease = claim_lease(workspace, items[0]["item_id"], "reviewer-a")
submit_opinion(
    workspace,
    items[0]["item_id"],
    "reviewer-a",
    "NEEDS_EVIDENCE",
    "Capture provenance should be checked against the registry entry.",
)
release_lease(workspace, lease["lease"]["lease_id"], "reviewer-a")
report = verify_review_queue(workspace)
markdown = render_queue_markdown(workspace)
```
