# NeuroAI Evidence and Decision Workbench

An offline-first, open-source reference implementation for the **v4.2 Pilot-Calibrated Universal NeuroAI Assessment Instrument**.

The workbench helps assessment teams preserve exact system boundaries, evidence states, requirement findings, prohibited inferences, decision authority, reopening triggers, and controlled provenance across NeuroAI cases. It is designed for research, regulatory preparation, institutional review, public-interest auditing, participant-governance workflows, and capacity building.

> **Controlled boundary**
>
> Passing schema checks, semantic checks, digest checks, event-chain checks, or software tests does **not** establish scientific truth, legal authorization, ethical acceptability, clinical safety, deployment readiness, or system conformance. Those conclusions require evidence and a competent authority.

## Why this exists

NeuroAI assessments often collapse distinct states into a single label. A system can demonstrate a bounded capability without satisfying deployment requirements. A competent authority can authorize an exact configuration without establishing every current-build, cybersecurity, participant-governance, equity, or continuity control. Public evidence can be incomplete without proving nonconformance.

The workbench preserves these distinctions in executable workflows.

## Implemented capabilities

- Full JSON Schema Draft 2020-12 validation for the v4.2 assessment model.
- Semantic checks for all 78 normative requirement IDs, cross-register references, decision separation, evidence-freeze controls, and controlled findings.
- Local workspace and multi-case management.
- Local evidence-byte preservation with SHA-256 verification.
- Hash-chained append-only event logs.
- Controlled snapshots and case ZIP bundles.
- Additive migration from v4.1.2 to v4.2.
- Cross-case comparison that preserves source findings.
- Browser interface for summaries, requirements, evidence, decisions, JSON editing, validation, snapshots, exports, and event review.
- CLI suitable for CI, reproducibility and institutional automation.
- Three migrated reference cases: Brain2Qwerty, FDA adaptive DBS, and BrainGate2 T15.

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

The server binds to localhost by default. It has no user authentication or TLS and must not be exposed directly to untrusted networks.

## Import a completed v4.2 case

```bash
neuroai-workbench case-import workspaces/demo \
  examples/PILOT-02_FDA_Adaptive_DBS_v4.2.json

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

File registration establishes byte identity and controlled custody inside the workspace. It does not establish the file’s authenticity, relevance, methodological quality, or decision weight.

## Controlled case bundle

```bash
neuroai-workbench snapshot workspaces/demo CASE-001 --label evidence-freeze
neuroai-workbench bundle workspaces/demo CASE-001 exports/CASE-001.zip
```

A bundle contains the assessment, evidence index and bytes, event log, snapshots, and a machine-generated verification manifest.

## Architecture

The workbench uses a dependency-minimal architecture:

- Python 3.10 or later.
- `jsonschema` for Draft 2020-12 validation.
- Python’s `ThreadingHTTPServer` for the local application.
- Vanilla HTML, CSS and JavaScript with no remote assets.
- Filesystem-backed controlled workspaces.

See [`docs/architecture.md`](docs/architecture.md), [`THREAT_MODEL.md`](THREAT_MODEL.md), and [`DATA_GOVERNANCE.md`](DATA_GOVERNANCE.md).

## Repository status

`v0.1.0` is a release candidate for public technical review. It is suitable for controlled local pilots and reproducible assessment workflows. It has not received UNESCO endorsement, regulator approval, clinical validation, penetration testing, or independent production-security review.

## Governance and contribution

- [Contribution guide](CONTRIBUTING.md)
- [Governance](GOVERNANCE.md)
- [Security policy](SECURITY.md)
- [Code of conduct](CODE_OF_CONDUCT.md)
- [Roadmap](ROADMAP.md)

## License

Apache License 2.0. The incorporated v4.2 assessment resources retain their controlled provenance and are distributed here as part of the reference implementation. See `NOTICE` and `docs/evidence-boundary.md`.
