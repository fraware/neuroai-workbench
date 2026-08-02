# Model assistance boundary

This document states the authority and data boundary for all language-model assistance in the workbench, including assessment assistance ([assistance.md](../reference/assistance.md)) and observatory source extraction ([extraction.md](../reference/extraction.md)).

## Governing decision

[ADR 0005](../adr/0005-controlled-language-model-assistance.md) requires that model output remain an untrusted proposal. The default workbench is local, offline-first, and performs no external model calls.

## Authority boundary

A model may produce candidate material only. It may not create a final finding or adjudication, change applicability or conformance, close an evidence gap, alter historical or canonical records, approve a release, or mutate assessment or observatory canonical state.

Human reviewers must record an explicit disposition before any derived record influences a controlled edit path.

## Data boundary

Exportable context is limited to explicitly selected public or synthetic structured summaries and source excerpts. Registered evidence bytes and protected material remain excluded by default. Credentials, secrets, and local paths are blocked by scan controls. Field-level disclosure classification is required before export.

## Withheld claims

Model-generated candidates do not establish evidence authenticity, scientific validity, legal authorization, clinical safety, deployment readiness, or system conformance.

See also `.cursor/rules/80-model-assistance.mdc`, `docs/reference/extraction.md`, and `docs/evaluation/extraction-preregistration.md`.
