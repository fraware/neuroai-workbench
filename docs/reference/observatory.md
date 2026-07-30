# Observatory mode

Version 0.2.0 adds a local, offline-first observatory release workflow.

```bash
neuroai-workbench observatory-verify examples/observatory/evidence_depth_release_v1.4.json
neuroai-workbench observatory-summary --release examples/observatory/evidence_depth_release_v1.4.json
neuroai-workbench observatory-queue --release examples/observatory/evidence_depth_release_v1.4.json
neuroai-workbench observatory-import ./workspace examples/observatory/evidence_depth_release_v1.4.json
neuroai-workbench observatory-summary --workspace ./workspace --version v1.4
```

The commands validate identifiers, source references, organization references and declared verification-rate arithmetic. They do not establish the truth, adequacy or authority of substantive evidence.

## Compact successor snapshots

Version 0.3 foundations also recognize compact successor snapshots such as `v1.7`. These records preserve an immutable baseline reference, effective successor counts, a bounded delta, and reopening decisions without duplicating the full detailed baseline.

```bash
neuroai-workbench observatory-verify examples/observatory/canonical_successor_snapshot_v1.7.json
neuroai-workbench observatory-summary --release examples/observatory/canonical_successor_snapshot_v1.7.json
neuroai-workbench observatory-queue --release examples/observatory/canonical_successor_snapshot_v1.7.json
```

A compact successor does not replace the detailed v1.4 baseline. It records lineage and changed state.
