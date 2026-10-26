# Release-A R1.7: original temporal/public source acquisition (nonterminal)

An isolated GitHub Actions acquisition for [run 39553726368](https://github.com/fraware/neuroai-workbench/actions/runs/39553726368)
completed on 2026-10-21 UTC. The bounded public-source collector retrieved
six responses as actual raw HTML bytes, retaining real final URL, HTTP status,
response timestamp, content type, raw SHA-256 and an explicit extraction boundary.
[Artifact 12323904364](https://github.com/fraware/neuroai-workbench/actions/runs/39553726368/artifacts/12323904364)
contains the saved original responses and `capture-report.json`.

| Source | Bytes | Original response SHA-256 |
| --- | ---: | --- |
| FDA PMA, Flow FL-100 | 39,336 | `398d6e3dd7bd1fee79460de54afa293d8578fbeb8920fa895ca850469138ea4d` |
| Flow Neuroscience 2026-09-16 launch statement | 72,973 | `2fdcf54c247b5c5a4232c6a5ea8beda8f38bcbc7c6197d18f44580e83193ff75` |
| FDA De Novo, Modius Spero | 38,624 | `d1f91d82897269ab1e17c93f4fc034152743a16792287c9e48706189587f80a4` |
| NeU 2025-06-04 Japanese discontinued models | 40,603 | `f02c9da3d76d8ca3951365c2af879d369d1b3821a3f26e7dcccf6130e4b506cb` |
| Bitbrain Spanish Diadem page | 315,389 | `a380a3afb55c8f333dfb2c54e828380a204077d370f081b592844d88f62190f4` |
| Bitbrain English Diadem page | 314,024 | `84616c2bfa9e8553597a040dd365894304eb3466f93e83a6684de98b769c4242` |

The saved HTML bodies were independently downloaded and rehashed after
acquisition. The dated manufacturer announcement (2026-09-16) explicitly
states that Flow FL-100 was **available by US prescription starting 2026-09-01**,
preceding the frozen world cutoff **2026-09-24**. [FDA P230024](https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpma/pma.cfm?id=P230024)
lists FL-100 approval **2025-12-08**. These are stronger temporal and
prescription-access evidence for the existing `PRD-FLOW-FL-100` registry entry,
subject to final entity/configuration reconciliation.

[FDA DEN250013](https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/denovo.cfm?id=DEN250013)
documents **Modius Spero authorization 2026-05-08**, but does **not**
document product distribution by 2026-09-24. Its frozen currentness and
access remain unresolved.

The exact 2025-06-04 [NeU Japanese notice](https://neu-brains.co.jp/information/press/2025/06/04/4258.html)
names **HOT-2000-BIOSIGNALS, NX Ver.1.0, SP-POST01, WOT-VC1**
as discontinued, with maintenance ending 2026-06. That specific variant
notice must not be broadened to every HOT-2000 product.

The Spanish and English [Bitbrain Diadem](https://www.bitbrain.com/es/productos-neurotecnologia/dry-eeg/diadem)
manufacturer pages both identify **Diadem 12ch EEG**. They provide a
cross-language candidate identity reconciliation, not two offerings.
Those undated page bodies do not independently establish pre-cutoff
availability.

## Reproduction

```bash
python -m scripts.r1_7_capture_temporal_sources \
  --output-dir /tmp/r1-7-temporal-sources --allow-network
```

Only six named public HTTPS targets are allowed; same-host HTTPS redirects,
a bounded response size, and source-identifying markers are enforced.
A new retrieval produces a **different observation** and likely different
HTML hashes, even for the same source. This independent acquisition does
not retroactively change the recorded 2026-10-21 source bytes.

**Scientific boundary:** raw-byte capture and content markers are not
product identity adjudication, regulatory interpretation, proof of
dispensing, or a terminal R1.7 temporal/source review. No canonical
Product Registry rows, frozen v4.2 results, A3/A4 increment, or
Release-A product-population counts were changed.
