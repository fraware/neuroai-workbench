# R1.7 literature pilot: four distinct papers, 21 frozen capture records

The R1.6.1 route table selects 21 `LITERATURE_RECORD_EXTRACTION` work items.
Each one covers one F6 capture; their frozen `lit-<PMID>` labels refer to
**four distinct publications**. Repetitions across F6 queries and rounds are
separate retrieval provenance, not additional research publications or products.

## Bibliographic screening (public source lookups, 20 October 2026)

| Frozen PMID | Publication | Bibliographic source | Interpretation |
| --- | --- | --- | --- |
| 42505450 | *Smart Wearable EEG Devices: A Review of Lightweight, Multi-Sensor Systems for Sleep and Everyday Neurophysiology* | https://pubmed.ncbi.nlm.nih.gov/42505450/ | Review of EEG devices; possible leads require actual source extraction |
| 42645991 | *Turning Immersive Viewers into Analytical Workspaces: ASCRIBE-XR and Agent-Driven Scientific Visualization* | https://pubmed.ncbi.nlm.nih.gov/42645991/ | General XR imaging analysis; neuroscience product relevance undetermined |
| 42022893 | *ROS 4 healthcare: a framework for physiological human sensing for social, assistive, rehabilitation, and medical robotics* | https://pubmed.ncbi.nlm.nih.gov/42022893/ | Research framework; commercial offering status undetermined |
| 41939223 | *Processing and analysis of portable EEG data for cognitive load assessment in neurotypical university students* | https://pubmed.ncbi.nlm.nih.gov/41939223/ | EEG research study; product status undetermined |

This table records publication identity and a **preliminary screening description**.
It is **not** an R1.7 evidence archive. No article HTTP response bytes were
captured by this document; no offering was included, excluded or resolved.
No zero-lead conclusion follows from the paper title or abstract.

## Preliminary mentions for evidence-backed follow-up

The following names were found during public scholarly-source screening.
They are **leads to verify**, not accepted new product identities, distinct
offering counts, current-market claims, or complete article extractions:

- **PMID 42505450:** the wearable EEG review names **Muse** systems,
  **Emotiv Insight**, **OpenBCI Galea**, **OpenBCI Ultracortex**, and
  **Unicorn Hybrid Black**. See
  https://pmc.ncbi.nlm.nih.gov/articles/PMC13406779/ and
  https://www.mdpi.com/2079-6374/16/7/374.
  Precise model identity, availability at the 2026-09-24 world-time cutoff,
  duplicates against the existing registry and device/developer attribution
  remain to be checked before any ledger lead is asserted.
- **PMID 41939223:** the study describes its use of a **12-channel
  Bitbrain dry-sensor EEG headset**. See
  https://www.frontiersin.org/journals/human-neuroscience/articles/10.3389/fnhum.2026.1737723/full.
  The exact commercial offering variant and registry overlap remain open.
- **PMID 42022893:** the robotics paper introduces **ROS4HC** and discusses
  **OpenViBE** and **ROS Neuro** as research-software frameworks. See
  https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2026.1745197/full.
  A cited research framework is not automatically an eligible product.
- **PMID 42645991:** **ASCRIBE-XR** is described as an immersive scientific
  visualization platform. See https://pubmed.ncbi.nlm.nih.gov/42645991/.
  Direct relevance to the NeuroAI product population is unresolved.

These preliminary observations identify productive next retrieval and
extraction targets. All R1.7 source bytes, explicit offering claims and
per-capture extraction conclusions remain to be supplied and validated.

## Work with the repository's existing frozen population

```bash
python -m scripts.r1_7_literature_pilot catalog > /tmp/r1-7-all-literature.json
python -m scripts.r1_7_literature_pilot pilot --count 3 > /tmp/r1-7-first-three.json
```

The pilot command selects one frozen capture for each of three different PMIDs.
The catalogue enumerates all 21 captures. Neither performs a network request
nor represents a completed evidence record.

For each actual source retrieval, save the raw response bytes locally, **outside
Git**, and record the real retrieval time, locator, HTTP context and an explicit
extraction decision in a separate JSON file with exactly these fields:

```json
{
  "capture_id": "REPLACE_WITH_FROZEN_CAPTURE_ID",
  "source_locator": "https://pubmed.ncbi.nlm.nih.gov/REPLACE_WITH_PMID/",
  "knowledge_observed_at": "REPLACE_WITH_ACTUAL_UTC_OBSERVATION_TIME",
  "retrieval_request": {
    "method": "GET",
    "locator": "https://pubmed.ncbi.nlm.nih.gov/REPLACE_WITH_PMID/",
    "request_context": {"query_or_seed_id": "REPLACE_WITH_FROZEN_QUERY_ID"}
  },
  "response_context": {
    "retrieval_status": "RETRIEVED",
    "content_type": "text/html",
    "encoding": "utf-8",
    "final_locator": "https://pubmed.ncbi.nlm.nih.gov/REPLACE_WITH_PMID/",
    "response_metadata": {"status_code": 200, "raw_sha256": "REPLACE_WITH_ACTUAL_SNAPSHOT_SHA256"}
  },
  "completion_state": "RECORD_EXTRACTION_UNRESOLVED",
  "extracted_candidate_keys": []
}
```

The metadata above is **a template**, not a report that a request occurred.
In particular, replace status 200 with the actually observed response status.
Use `RECORD_EXTRACTED_ZERO_OFFERING_LEADS` only after examining enough of the
source to support that exact claim. Use `RECORD_EXTRACTED_WITH_OFFERING_LEADS`
only with explicit nonempty candidate keys. Terminal extraction also requires
operator metadata recording a successful HTTP 200 retrieval; a 404, 403,
rate-limit page or inaccessible source must remain unresolved. HTTP 200 alone
does not establish that the source body is the intended article. The unresolved
state preserves the work item as pending.

```bash
python -m scripts.r1_7_literature_pilot ingest --decision /tmp/decision.json --snapshot /tmp/raw-response.html > /tmp/record-bundle.json
python -m scripts.r1_7_literature_pilot combine /tmp/record-bundle.json > /tmp/r1-7-ledger-state.json
```

The importer encodes the exact submitted bytes, verifies their SHA-256, binds
the frozen capture/query, computes deterministic record and evidence identifiers,
and checks them through the existing R1.7 evidence-archive and aggregation code.
Source metadata, interpretation and retrieval truth remain claims supplied by
the operator; software validation does not establish their authenticity.

**Temporal scope:** world state as of 2026-09-24; evidence knowledge time no
later than 2026-10-24T23:59:59Z. The importer rejects later observations.
Research snapshots and resulting evidence archives must remain outside the
repository; the source files, normative resources, and canonical S2 data are
unchanged.
