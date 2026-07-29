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
