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
Ordering is deterministic. The script makes **no network requests**. The
queue also binds every priority capture to its **full frozen query expression**,
confirms query round/family/source class/language/jurisdiction, and reports
raw-byte SHA-256 hashes for the routing checkpoint, F6/F8 source shards,
and their two frozen query universes. These checks protect reproducibility;
they do not establish retrieval or review completion.

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

## Five historical F8 inaccessible-source recoveries

The five frozen `FAILED_INACCESSIBLE` items are now linked to **ten
verified alternative official source/portal entry points** in the
read-only file `r1-7-five-inaccessible-f8-recovery-candidates.json`.
These entries are a **pre-acquisition candidate list**. They do **not** claim
that the original 2026-09-26 retrieval attempts succeeded. A later, separately
archived 2026-10-21 acquisition is documented in
[`r1-7-f8-five-alternative-source-probe-2026-10-21.md`](r1-7-f8-five-alternative-source-probe-2026-10-21.md).
That later probe attempted ten alternative URLs, archived eight HTTP 200
responses, recorded two 403 failures, and independently rehashed the reported
archive. It does not retroactively change the original capture outcomes,
validate a specific product or record, or establish terminal R1.7 decisions.

| F8 query | Source category | Alternative research target | Remaining gap |
| --- | --- | --- | --- |
| `F8-R2-CAP-ZH-2` | Chinese-language capability surface | 2025 MIIT multi-ministry BCI policy; NMPA UDI portal | An attributable product and exact original page |
| `F8-R3-LOC-BITBRAIN-ES` | Spanish manufacturer | Bitbrain Diadem 12-channel page and 2024 Spanish technical article | Original source URL and model/world-time status |
| `F8-R3-LOC-NMPA-ZH` | Chinese regulator | NMPA government device-registration portal and UDI database | Specific registration record and registration date |
| `F8-R3-LOC-MOH-IL` | Israeli regulator | Health Ministry's medical-device registry index and AMR notices | A specific medical-device registry entry |
| `F8-R3-LOC-NEUROELECTRICS-ES` | Spanish manufacturer | Neuroelectrics Enobio model page and historical Enobio/Starstim article | Spanish original source and model-specific status |

Most of these are **source discovery**, not direct evidence of a specific
qualifying NeuroAI product. The English Neuroelectrics pages are explicitly
identified as a *language mismatch* for the Spanish frozen query. The NMPA
and Israeli Ministry records identify **official registries**, not any
positive or negative registration result. The dated Bitbrain article is
a historical manufacturer representation rather than a conclusion about
2026-09-24 commercial availability.

For the eight archived responses, the next step is primary content-level
extraction and historically valid source assessment. For the two inaccessible
Israeli responses, the access barrier remains unresolved. Any subsequent
source-execution decision must bind the exact frozen capture/query ID and
new evidence identity while keeping historical failed captures unchanged.
The main priority queue is an unresolved-work projection and does not ingest
this later probe as successful original September execution.
