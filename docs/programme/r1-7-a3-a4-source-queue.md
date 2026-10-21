# A3/A4-sensitive R1.7 source verification queue

The frozen R1.6.1 execution checkpoint contains 171 pending
`SOURCE_SURFACE_RESOLUTION` work items (226 frozen capture references).
Of these, **18 F6 items** are capable of changing the A3 capability
increment, and **51 F8 items** are capable of changing the A4 multilingual
increment. The 69 items are selected directly from the frozen route
checkpoint and exact-joined to their original F6/F8 source-capture shards.

```bash
python -m scripts.r1_7_a3_a4_source_queue \
  --output /tmp/r1-7-a3-a4-priority-worklist.json
```

The JSON includes the work-item and candidate-cluster IDs, original capture
and observation references, query family, language/jurisdiction, source packet,
frozen original response state (64 `ABSTAIN` and five
`FAILED_INACCESSIBLE` capture outcomes), and the analytical reason for selection.
Ordering is deterministic. The script makes **no network requests**.

This is a **pending execution queue**: it assigns no new source locator, real
retrieval timestamp, offering, product status, completion decision or A3/A4
increment. A source/query abstention or inaccessible-response failure is not proof of
source absence or zero eligible products. Primary-source verification and
separate exact-capture evidence decisions must still be performed before
substantive counts change.

Priority within this queue should begin with high-impact F6 capabilities
and F8 local-language primary sources, retaining exact provenance and the
2026-09-24 world-time cutoff. Evaluate outcomes only when the
2026-10-24T23:59:59Z knowledge-time window closes.
