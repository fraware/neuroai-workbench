
## Controlled change

Describe the exact problem, affected controlled objects, user impact, and root cause.

Closes #

## AI provenance

- [ ] No AI coding agent materially authored or edited this change.
- [ ] An AI coding agent assisted; human reviewer remains accountable for semantics, security, and release decisions.
- Agent / tool (if any):
- Human disposition of agent output:

AI assistance does not confer scientific, regulatory, security-acceptance, or release authority.

## Semantic impact

- [ ] No normative requirement meaning changed.
- [ ] No historical finding was overwritten.
- [ ] Capability, authorization, deployment, commercial, and conformance states remain separate.
- [ ] Missing evidence is not converted into automatic failure.
- [ ] Schema or migration effects are documented below.

## Security and data boundary

- [ ] No protected neural, participant, clinical, regulatory, security, credential, or key material is included.
- [ ] The threat model and data-governance documents are updated when required.
- [ ] No remote analytics, telemetry, external model calls, or third-party UI assets were added.

## Verification

- [ ] Tests were added or updated.
- [ ] `make quality` passes.
- [ ] `make test` passes with the coverage gate.
- [ ] `make verify` passes.
- [ ] `python scripts/agent_eval_harness.py` passes when agent-facing controls changed.
- [ ] Packaging or migration checks were run when applicable.

## Residual limitations

State what this change does not establish and any follow-up work.
