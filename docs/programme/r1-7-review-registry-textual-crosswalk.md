### Frozen registry textual crosswalk (nonterminal)

The independent public-source replay established 57 raw device-comparison
rows in PMID 42505450. The six-entry Release-A R1 Product Registry contains
existing canonical identifiers for Emotiv EPOC X, Muse S ATHENA, and NextSense
Smartbuds, alongside three other registered products.

To regenerate a **nonterminal textual** crosswalk from the original raw
Europe PMC XML saved in the evidence artifact:

```bash
python -m scripts.r1_7_compare_review_registry \
  --source-xml /path/to/pmid-42505450-fulltext.xml \
  --output /path/to/r1-7-review-registry-crosswalk.json
```

The command re-extracts all 57 seven-column device-table rows from the
**exact SHA-256-pinned source XML**, loads the unchanged six-entry Product
Registry, and compares literal device designations to two explicit expanded
registry entity IDs. The generic label *Smartbuds* receives a partial/ambiguous
name match only. The frozen comparison results are **2 exact textual matches,
1 ambiguous name overlap, and 54 unmatched designations**, including six
slash-joined multi-model designations. All 57 require independently supported
identity and 2026-09-24 market/currentness evaluation before any population
effect is inferred. A textual nonmatch is **not** proof of a new offering.

No registry identities, eligibility, commercial-status or R1.7 terminal
literature conclusions are created by this command.
