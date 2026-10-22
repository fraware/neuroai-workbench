# R1.7 — remaining original source-capture evidence queue

As of the two specified saved-source archives (Europe PMC four-paper archive
`12320317652` and F8 alternative-source archive `12325963314`),
the immutable R1.6.1 refinement contains 192 governed SOURCE/LITERATURE
work items and 247 associated captures.

The bounded archive projection identifies:

- 4 directly archived literature captures;
- 17 other literature captures whose frozen PMID refers to one of those
  four acquired papers (reused **publication text**, not independent capture);
- 4 F8 original source contexts with new alternative HTTP 200 bytes;
- 1 F8 source context with two recorded 403 access failures;
- **221 source-surface captures** with **no receipt in these two archives**.

These five categories sum to 247. The 221 figure does not demonstrate that
a source is absent, no other evidence exists, or no product was returned.

Execute the reproducible and read-only source task projection:

```shell
python -m scripts.r1_7_unlinked_source_capture_queue \
  --output /tmp/r1-7-unlinked-source-captures.json
```

Each output row is joined to the exact historical frozen A2 capture with
work-item ID, frame, round, registered query-or-seed ID, query family,
language, jurisdiction, source class, original source observation and
packet IDs, candidate key and source result, plus the already-frozen A3/A4
and marginal-yield sensitivity flags.

The program reads original package resources and the SHA-digested bounded
inventory; it performs no network searches or new source acquisitions,
does not produce new query-result observations, and assigns no model,
product identity, completeness or eligibility outcomes. It refuses
missing source records, duplicate capture IDs, and changed denominators.

This is the unlinked subset of the original 226 source-surface capture
references, not the set of all remaining unresolved candidate
adjudications. It supplies stable work-item/source hooks for subsequent
attributable acquisition attempts. Every successful acquisition still needs
separate source-byte custody, world/knowledge-time boundaries, source
rights, and substantive extraction before it is eligible for an R1.7
completion decision.
