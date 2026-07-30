# ADR 0005 — Controlled language-model assistance boundary

## Status

Accepted for the v0.3.0 foundation. The implemented workbench uses offline request export and response import. No direct language-model API integration is enabled.

## Context

Language models can help assessment teams extract candidate facts, draft structured records, identify unresolved references, and prepare review text. They can also introduce unsupported claims, collapse evidence states, expose protected information, obscure authorship, and create false authority through fluent output.

The workbench therefore needs an explicit boundary before any model-assisted capability is implemented.

## Decision

Any language-model capability must be implemented as an optional, review-gated assistant operating on an explicit input package. The default workbench remains local, offline-first, and free of external model calls.

A model may produce candidate material only. It may not independently create a final finding, change applicability, assign conformance, determine legal or clinical status, close an evidence gap, alter a historical record, or approve a release.

Every model-assisted operation must record:

- the workbench and adapter version;
- the model provider and exact model identifier when available;
- the prompt-template identifier and digest;
- the input-object identifiers and content digests;
- whether protected or restricted information was excluded;
- the raw model response or a controlled digest and retention reference;
- the human reviewer and disposition;
- accepted, modified, and rejected candidate fields;
- the event-chain entry linking the assistance record to the resulting edit.

External-provider adapters require a separate data-flow review covering consent, authorization, minimization, retention, provider terms, training use, jurisdiction, deletion, incident handling, prompt injection, and an offline fallback. Protected neural, clinical, participant, regulator, credential, or security material must remain excluded unless a separately approved institutional deployment profile establishes lawful and technically enforced handling.

## Initial implementation shape

The first implementation uses deterministic prompt-package export and response import instead of direct model API calls. The workbench now:

1. exports a bounded JSON request containing selected structured context;
2. includes explicit prohibited inferences and a machine-readable output contract;
3. accepts a structured candidate-response file;
4. validates evidence references, confidence labels, target paths, and limitations;
5. requires an explicit human disposition record;
6. appends attributable request, response, and disposition events;
7. preserves the original assessment and all assistance artifacts;
8. performs no assessment mutation and no external network call.

Field-level application of accepted drafts remains a separate future workflow and must use the ordinary controlled assessment-edit path.

## Consequences

This design adds friction, although it preserves reproducibility, reviewability, offline operation, and decision authority. Direct chat convenience is deferred until the institutional security and data-governance architecture can support it.

## Withheld claims

A model-generated candidate does not establish evidence authenticity, scientific validity, legal authorization, clinical safety, ethical acceptability, deployment readiness, or system conformance.
