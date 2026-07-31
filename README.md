
# NeuroAI Evidence and Decision Workbench

An offline-first, open-source reference implementation for the **v4.2 Pilot-Calibrated Universal NeuroAI Assessment Instrument** and its controlled observatory workflow.

The workbench preserves exact system boundaries, typed evidence states, requirement findings, prohibited inferences, decision authority, reopening triggers, and controlled provenance across NeuroAI cases. It is intended for public-interest assessment, research review, regulatory preparation, institutional pilots, participant-governance workflows, and reproducible evidence operations.

> **Controlled boundary**
>
> Schema validity, semantic validity, file-digest integrity, event-chain integrity, or passing software tests do not establish scientific truth, legal authorization, ethical acceptability, clinical safety, deployment readiness, or system conformance. Those conclusions require substantive evidence and a named competent authority.

## Capabilities

- JSON Schema Draft 2020-12 and semantic validation for the v4.2 assessment model.
- Exact coverage of all 78 normative requirement identifiers.
- Local multi-case workspaces with atomic JSON writes.
- Content-addressed evidence preservation and SHA-256 verification.
- Append-only hash-chained event records.
- Controlled snapshots and case bundles.
- Additive v4.1.2-to-v4.2 migration that preserves historical findings.
- Cross-case comparison without generating new substantive findings.
- Offline browser interface with no remote assets or analytics.
- CLI workflows suitable for CI and institutional automation.
- Controlled landscape-release import, validation, summary, and unresolved queues.
- Three public reference assessments covering Brain2Qwerty, FDA adaptive DBS, and BrainGate2 T15.

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e .

neuroai-workbench init workspaces/demo
neuroai-workbench case-create workspaces/demo CASE-001 \
  --title "Controlled NeuroAI assessment"
neuroai-workbench serve workspaces/demo
```

Open `http://127.0.0.1:8765`.

The reference server binds to localhost by default. It has no authentication, authorization, multi-tenant isolation, or TLS and must not be exposed directly to an untrusted network.

## Import a completed assessment

```bash
neuroai-workbench case-import workspaces/demo \
  examples/assessments/PILOT-02_FDA_Adaptive_DBS_v4.2.json

neuroai-workbench validate \
  --workspace workspaces/demo \
  --case-id PILOT-02-FDA-ADBS-v4.1.4
```

## Register evidence bytes

```bash
neuroai-workbench evidence-add workspaces/demo CASE-001 report.pdf \
  --title "Controlled technical report" \
  --type "METHOD OR TECHNICAL DOCUMENT" \
  --source "Local authorized copy"

neuroai-workbench evidence-verify workspaces/demo CASE-001
```

Byte registration establishes local identity and custody. It does not establish authenticity, relevance, methodological adequacy, or decision weight.

## Controlled bundle

```bash
neuroai-workbench snapshot workspaces/demo CASE-001 --label evidence-freeze
neuroai-workbench bundle workspaces/demo CASE-001 artifacts/CASE-001.zip
```

## Engineering entry points

- [`AGENTS.md`](AGENTS.md) defines mandatory invariants for humans and coding agents.
- [Architecture](docs/architecture/overview.md)
- [Evidence and decision boundary](docs/governance/evidence-boundary.md)
- [Threat model](THREAT_MODEL.md)
- [Data governance](DATA_GOVERNANCE.md)
- [Contribution protocol](CONTRIBUTING.md)
- [Release process](docs/operations/release-process.md)

## Repository status

`v0.2.1` is the repository-stabilization candidate for controlled local technical pilots. The v4.2 normative requirement semantics remain unchanged from v0.2.0. Production security, institutional adoption, substantive evidence validity, system conformance, regulatory authorization, clinical advice, and UNESCO endorsement remain outside the software release determination.

## License

Apache License 2.0. Incorporated v4.2 resources retain their controlled provenance. See [`NOTICE`](NOTICE) and the [evidence boundary](docs/governance/evidence-boundary.md).
