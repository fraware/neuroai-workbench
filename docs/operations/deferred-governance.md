# Deferred human governance overlay

## Status

The software, policy, synthetic-rehearsal, and documentation layers are complete. The remaining programme step is the real protected execution tracked by [#114](https://github.com/fraware/neuroai-workbench/issues/114).

The active completion policy is `GOVPOLICY-2.0.0` with authority model `SINGLE_DESIGNATED_HUMAN_AUTHORITY`. The designated repository authority is `fraware`. The same designated human may fulfill reviewer, owner-disposition, authorization, and publication roles, but every action remains a separate attributable, append-only, hash-bound record.

Historical v1 records remain verifiable under their original multi-person policy semantics. Those historical independence thresholds do not define current v2 completion.

| Layer | State |
| --- | --- |
| Non-canonical core cycle (#43) | Complete |
| Governance schemas, stores, transactions, and verification | Complete |
| Synthetic governance rehearsal and protected handoff | Complete; explicitly non-authoritative |
| Active single-designated-authority policy | Complete and verified |
| Real exact-scope review across six mandatory tracks | Not executed in public repository state |
| Real protected authority evidence | Not supplied in public repository state |
| Canonical authorization / publication decision | Not executed in public repository state |

## What #114 requires

The real protected workflow must bind one exact decision scope containing the predecessor release, successor candidate, delta, reopening register, product manifest, and withheld-claims set.

The designated authority must then record separate real opinions across all six tracks:

- `SECURITY`;
- `METHODOLOGY`;
- `DATA_GOVERNANCE`;
- `ACCESSIBILITY`;
- `DOMAIN`;
- `AFFECTED_COMMUNITY`.

Any designated-authority `SUPPORT_WITH_CONDITIONS`, `OBJECT`, or `REQUEST_EVIDENCE` requires an owner disposition. An active designated-authority `OBJECT` or `REQUEST_EVIDENCE` remains blocking until explicitly superseded; owner disposition alone does not convert it to support. Unresolved conditions with `release_effect = BLOCKS_RELEASE` also prevent readiness.

Only after policy evaluation is satisfied and the deterministic release-readiness package is blocker-free may the final designated actor record an authorization decision. Publication, if chosen, is a distinct subsequent decision bound to the exact prior authorization and publication evidence.

The operator procedure is [protected governance execution](protected-governance-execution.md). Record-level semantics are defined in [governance records and release-control semantics](../reference/governance-records.md).

## Protected-data boundary

Protected evidence bytes, credentials, licensed evidence, private paths, real authority evidence, and private execution notes remain outside public Git.

Governance records may bind protected material through an opaque `protected-ref:` and an exact SHA-256 digest where the schema permits it. The public reference alone does not establish authenticity, custody, relevance, or authority.

Synthetic fixtures and public examples must remain unmistakably non-authoritative. Do not promote a synthetic record, placeholder identity, or test fixture into the protected execution path.

## Fail-closed rules

The real execution must stop on:

- stale or changed governed inputs;
- invalid event chain or governance transaction state;
- invalid scope, opinion, disposition, or release-decision store;
- missing mandatory track coverage;
- wrong designated reviewer or owner key on the active path;
- active designated blocking opinions;
- missing required dispositions;
- blocking owner dispositions;
- unresolved release-blocking conditions;
- stale policy binding;
- candidate/scope artifact mismatch;
- changed product or withheld-claims digest;
- missing protected authority evidence;
- final actor other than `fraware`;
- publication that does not bind the exact prior authorization.

Do not repair a blocked state by editing governance history. Record new evidence, dispositions, conditions, or superseding opinions as appropriate. Persistence faults use the [governance transaction recovery](governance-transaction-recovery.md) procedure.

## Legacy candidate gate

The successor candidate's historical/local `release_gate` remains a compatibility mechanism. It is not the active canonical authorization path.

A candidate whose current gate or gate history contains local `AUTHORIZED` or `PUBLISHED` state is classified as a legacy authority claim and blocked by the current governance readiness builder. Canonical v2 authorization and publication are represented by governance release-decision records.

See [observatory successor releases](../reference/successor-releases.md).

## Boundaries retained

- predecessor and historical objects remain immutable;
- protected evidence remains outside public Git;
- retrieval failures remain typed operational outcomes and do not become substantive findings automatically;
- shadow evaluation does not mutate assessments;
- policy completion does not authenticate a person or institution;
- readiness does not authorize a release;
- authorization does not perform publication automatically;
- publication workflow state does not establish scientific truth, clinical safety or effectiveness, regulatory or legal authorization, conformance, institutional endorsement, external adoption, or endorsement by any external body.

## Completion rule

The existence of policy v2, synthetic rehearsal artifacts, this documentation, or passing software tests is insufficient to close #114.

#114 closes only when real protected/runtime records exist for the selected exact scope and the issue's remaining acceptance criteria are supported by those records.