
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
- Controlled full-baseline and compact-successor observatory import, validation, summary, and reopening queues.
- Four public reference assessments covering Brain2Qwerty, FDA adaptive DBS, BrainGate2 T15, and PRIMA.
- Loss-aware conversion from programme completed-assessment records into the native v4.2 object model.
- Deterministic human-readable Markdown assessment, evidence-gap, and review reports.
- Attributable local review assignments, immutable agreement/disagreement statements, scoped human dispositions, and tamper verification.
- Protected-evidence metadata requests and out-of-band custodian-response records with no evidence-byte transfer.
- Provider-neutral GPT assistance request, response, disposition, and integrity records with no direct model API call or automatic assessment mutation.

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

The reference server binds to localhost by default. It has no authentication, authorization, multi-tenant isolation, or TLS and must not be exposed directly to an untrusted network. Non-loopback binding is an expert escape hatch that requires both an explicit flag and `NEUROAI_ALLOW_NETWORK=1`; `/api/health` reports configuration status without returning absolute workspace paths.

## Import a completed assessment

```bash
neuroai-workbench case-import workspaces/demo \
  examples/assessments/PILOT-02_FDA_Adaptive_DBS_v4.2.json

neuroai-workbench validate \
  --workspace workspaces/demo \
  --case-id PILOT-02-FDA-ADBS-v4.1.4
```


## Adapt the PRIMA programme record

```bash
neuroai-workbench programme-adapt \
  examples/programme/PRIMA_COMPLETED_ASSESSMENT_v4.2.1.programme.json \
  artifacts/PRIMA.native.json \
  --report artifacts/PRIMA.adapter-report.json

neuroai-workbench report \
  --assessment artifacts/PRIMA.native.json \
  --output artifacts/PRIMA.md
```

## Collaborative review

The local reference workflow records claimed reviewer identities, typed roles, scoped assignments, agreement or disagreement statements, and human dispositions as separate integrity-addressed records. It does not authenticate a person or institution, and no review record edits the assessment automatically. See [collaborative review](docs/reference/review.md).

## Protected-evidence metadata exchange

The workbench can prepare a minimum-necessary custodian request and record an out-of-band response without transporting evidence bytes or local paths. A request does not create a disclosure duty or establish receipt. See [protected-evidence exchange](docs/reference/evidence-exchange.md).

## Controlled GPT assistance

The default workbench makes no external model call. It exports bounded structured requests, validates imported candidate responses, records exact provider and model identifiers, requires human disposition, and preserves assessment bytes unchanged. See [controlled model assistance](docs/reference/assistance.md).

## Observatory monitoring operations

The workbench can now operationalize the controlled v1.5 source monitor registry without crawling the network or making substantive claims automatically. It plans due source checks, records content-addressed source snapshots, compares captures, creates human-review change candidates, preserves immutable adjudications, and assembles a non-canonical refresh package with a reopening queue.

```bash
neuroai-monitor registry-validate \
  examples/operations/SOURCE_MONITOR_REGISTRY_SAMPLE.json

neuroai-monitor init workspaces/operations \
  examples/operations/SOURCE_MONITOR_REGISTRY_SAMPLE.json

neuroai-monitor plan workspaces/operations \
  --out artifacts/monitor-plan.json
```

Network acquisition remains outside the default workbench. An approved collector captures source bytes; the workbench controls identity, comparison, review, and release preparation. See [observatory automation](docs/operations/observatory-automation.md) and [static archive to operational programme](docs/architecture/static-to-operational.md).

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
- [Documentation map](docs/README.md)
- [Architecture](docs/architecture/overview.md)
- [Evidence and decision boundary](docs/governance/evidence-boundary.md)
- [Threat model](THREAT_MODEL.md)
- [Data governance](DATA_GOVERNANCE.md)
- [Contribution protocol](CONTRIBUTING.md)
- [AI-agent development](docs/operations/ai-agent-development.md)
- [Release process](docs/operations/release-process.md)
- [Observatory automation](docs/operations/observatory-automation.md)
- [Public data release](docs/operations/public-data-release.md)
- [Static archive to operational programme](docs/architecture/static-to-operational.md)

## Repository status

`main` tracks unreleased package version `0.3.0.dev0` (v0.3 foundations merged; not a tagged release). Published stabilization remains `v0.2.1`. The v4.2 normative requirement semantics remain unchanged from v0.2.0. Production security, institutional adoption, substantive evidence validity, system conformance, regulatory authorization, clinical advice, and UNESCO endorsement remain outside the software release determination.

## License

Apache License 2.0. Incorporated v4.2 resources retain their controlled provenance. See [`NOTICE`](NOTICE) and the [evidence boundary](docs/governance/evidence-boundary.md).
