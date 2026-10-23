# R1.7: independent four-literature-bundle replay (nonterminal)

**Scope:** [issue #424](https://github.com/fraware/neuroai-workbench/issues/424), the four primary public-literature XML receipts acquired in GitHub Actions run `39543302737`, artifact `12320317652`. This is a **read-only verification of evidence already acquired**. It does not perform another web request or an extraction/adjudication decision.

Run from a Workbench checkout with its Python dependencies installed and an independently retained copy of the original ZIP **outside Git**:

```sh
python -m scripts.r1_7_replay_literature_archive \
  --archive /controlled/evidence/neuroai-evidence-12320317652.zip \
  --output /controlled/analysis/r1-7-four-bundle-replay.json
```

The original ZIP is frozen to SHA-256 `fed125c0f7d727c9fab5188ecc68914b2a7e18a04765d15697f33b6cb6bc6945`. Its four XMLs correspond to PMIDs `41939223`, `42022893`, `42505450`, `42645991`, originally captured on 2026-10-21. The script checks the entire ZIP byte digest and CRCs, exact file inventory, acquisition results, saved XML lengths/hashes, capture/work-item/seed bindings, original request/response metadata, embedded base64 source bytes, evidence-artifact canonical digests, and ledger-entry IDs. It then combines the four records and calls the **frozen R1.7 `derive_ledger_state` validator** to check them against the full R1.6.1 population and its conflict/completion semantics. The JSON output preserves only metadata, IDs, source checksums and the nonterminal state; it excludes XML payload bytes.

A successful replay establishes precisely **four machine-provisional `RECORD_EXTRACTION_UNRESOLVED` ledger entries**, **four distinct direct acquisition receipts**, **zero completed work items**, **zero active extracted offering leads**, and **192 pending source/record work items**. The 21 literature-record work items include 17 other historical capture contexts that were **not directly acquired as separate receipts in this archive**. The same four article bytes may be available for those contexts, but source-byte reuse is not proof that their original frozen queries were rerun or their extraction tasks are complete. Other evidence archives are governed separately.

This operation does not establish paper-level commercial objecthood, literature-review saturation, product identity, commercial availability, A3/A4 increments, canonical S2 changes, or Release-A finality. There is no claim of independent publisher-origin authentication or redistributed publication rights. The original ZIP must remain under the project's permitted controlled-evidence custody.

The synthetic regression suite covers deterministic results, archive mutation, terminal-state forgery, route substitution, seed provenance drift, and forged completion. These tests complement the existing R1.7 ledger module's conflict/supersession and per-capture completion tests. The real archive is excluded from Git and CI fixtures; its exact-byte integration replay needs the preserved off-Git archive.