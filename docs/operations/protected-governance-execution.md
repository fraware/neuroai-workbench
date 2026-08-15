# Protected governance execution runbook

## Purpose

This runbook is the operator procedure for issue #114. It starts **after** the engineering and synthetic-rehearsal layers are complete and ends only when the real protected workflow has produced an explicit authorization decision, an explicit withholding decision outside the release recorder, or a publication record following authorization.

The runbook does not supply reviewer judgments, protected evidence, authority evidence, or publication evidence. Those inputs must come from the real execution context. Do not substitute examples, synthetic fixtures, repository metadata, or test results for real governance inputs.

Active policy:

- policy ID: `GOVPOLICY-2.0.0`;
- authority model: `SINGLE_DESIGNATED_HUMAN_AUTHORITY`;
- designated repository authority: `fraware`;
- required tracks: `SECURITY`, `METHODOLOGY`, `DATA_GOVERNANCE`, `ACCESSIBILITY`, `DOMAIN`, `AFFECTED_COMMUNITY`.

See [governance record semantics](../reference/governance-records.md) and [single designated human authority](../architecture/governance-single-authority.md).

## Hard boundary

Real execution must occur in an operator-controlled workspace. Protected evidence bytes, credentials, licensed material, private paths, and non-public authority evidence do not belong in public Git, issue comments, pull-request text, event payloads, or public examples.

Opaque `protected-ref:` identifiers and SHA-256 digests may appear in governance records where the schema permits them. The underlying protected bytes remain outside public repository storage.

No step below establishes scientific truth, clinical safety or effectiveness, regulatory or legal authorization, conformance, institutional delegation, external endorsement, or external publication.

## Stop conditions

Stop immediately and preserve the workspace if any of the following occurs:

- an existing governance record store fails verification;
- the event chain or transaction recovery state is invalid or ambiguous;
- any governed input digest changes after scope freeze;
- the successor candidate differs from the candidate artifact bound in the scope;
- the active policy ID, version, or digest differs from the policy used for review;
- a required track lacks an active designated-authority opinion;
- an active designated-authority opinion is `OBJECT`, `REQUEST_EVIDENCE`, or `ABSTAIN` when readiness is expected;
- a required owner disposition is missing;
- an owner disposition on the active path is attributed to a key other than `fraware`;
- a blocking owner disposition remains active;
- an unresolved condition has `release_effect = BLOCKS_RELEASE`;
- the readiness package contains any blocker code;
- the final decision actor differs from `fraware`;
- the authority-evidence reference or digest is missing or cannot be verified in the protected environment;
- publication inputs differ from the exact prior authorization package.

Do not edit historical JSON records or `events.jsonl` by hand to clear a stop condition. Follow [governance transaction recovery](governance-transaction-recovery.md) for persistence faults. Resolve substantive blockers through new evidence, explicit dispositions, and/or superseding records.

## Phase 0 — freeze the execution envelope

Create an operator-controlled execution note outside public Git that identifies:

1. protected workspace root;
2. exact predecessor release file;
3. exact successor candidate file;
4. exact adjudicated delta file;
5. exact reopening-register file;
6. exact product manifest and the product files it binds;
7. exact withheld-claims file;
8. every protected evidence object required for the review;
9. boundary roots for `PUBLIC_GIT`, `GENERATED_OUTPUT`, and `ARCHIVE`;
10. opaque protected-reference bindings used only in the protected environment.

Compute and retain the SHA-256 digest of every governed input. Do not proceed if any object is still expected to change.

Load the current policy and record its identity in the execution note:

```python
from neuroai_workbench.governance_policy import (
    governance_policy_sha256,
    load_governance_completion_policy,
)

policy = load_governance_completion_policy(version="current")
assert policy["policy_id"] == "GOVPOLICY-2.0.0"
assert policy["designated_authority_key"] == "fraware"
policy_sha256 = governance_policy_sha256(policy)
```

The policy digest is part of the final exact-input binding. A later policy change requires a fresh evaluation and, where the governed decision basis changes, a new execution scope.

## Phase 1 — verify persistence integrity

Initialize or open the protected workspace using the ordinary `Workspace` API. Before recording real governance material, verify the existing event chain, governance transaction state, and any existing governance stores.

A clean public repository does not imply a clean protected runtime workspace. Verification must target the actual workspace used for #114.

If the workspace contains interrupted governance transactions, resolve them through the recovery protocol before any new write.

## Phase 2 — record the exact governance scope

Construct one scope object for each mandatory logical role using `scope_object_for_path()`:

- `PREDECESSOR_RELEASE` / object type `RELEASE`;
- `SUCCESSOR_CANDIDATE` / object type `SUCCESSOR_CANDIDATE`;
- `DELTA` / object type `DELTA`;
- `REOPENING_REGISTER` / object type `REOPENING_REGISTER`;
- `PRODUCT_MANIFEST` / object type `PRODUCT_MANIFEST`;
- `WITHHELD_CLAIMS` / object type `CLAIM_SET`.

Use `CORE_CYCLE_EXECUTION` only if a distinct execution artifact is intentionally part of the governed scope.

For `PROTECTED_WORKSPACE` objects, pass a private file path only to the local function call and expose it in the record through an opaque protected reference. Never encode the private path itself in the scope locator.

Record the scope once with `record_governance_scope_manifest()`. Retain:

- `scope_id`;
- `manifest_sha256`;
- the exact list of object roles and digests;
- the matching `GOVERNANCE_SCOPE_RECORDED` event witness.

Then run `verify_governance_scope_records()` with the same boundary roots and protected bindings. Do not start human review until the scope verifies successfully.

### Scope-freeze rule

After the first real opinion is recorded, any change to a governed input is a new decision basis. Do not silently update the existing scope. Freeze a new scope and repeat the review when the bytes under decision have changed.

## Phase 3 — perform the six real reviews

Record one separate real opinion for each mandatory track with `record_governance_reviewer_opinion()`.

Every designated-authority opinion must use:

```text
reviewer_key = fraware
accountability_state = CLAIMED_HUMAN_REVIEWER
```

The remaining reviewer-claim fields must contain truthful real statements for the execution context:

- `name_or_role`;
- `organization` if applicable;
- `independence_statement`;
- `conflict_of_interest_disclosure`.

Role consolidation is explicit under v2, so independence and no-conflict claims are not threshold gates. They remain auditable statements and must not be fabricated.

### Track questions

Use these questions as the minimum review frame.

**SECURITY**

- Are security assumptions, attack surfaces, privileged transitions, and unresolved security conditions explicit?
- Do release controls fail closed under tampering, concurrency, interruption, and stale-input substitution?

**METHODOLOGY**

- Are assessment methods, evidence dependencies, uncertainty states, and reopening semantics inspectable?
- Do reported conclusions remain within the evidential scope of the reviewed artifacts?

**DATA_GOVERNANCE**

- Are provenance, licensing, protected/public boundaries, retention, and disclosure constraints explicit?
- Can every release input be traced to an exact digest without exposing protected evidence?

**ACCESSIBILITY**

- Are public products usable and interpretable across the programme's intended accessibility requirements?
- Are known accessibility gaps recorded as explicit conditions instead of being omitted?

**DOMAIN**

- Do domain-specific interpretations preserve distinctions among research, regulatory, clinical, and deployment states?
- Are unresolved domain questions and evidence gaps visible to the release decision?

**AFFECTED_COMMUNITY**

- Are affected-community perspectives represented as an explicit governance track with visible gaps and dissent?
- Can abstention, objection, requested evidence, and minority positions remain visible without being converted to support?

### Judgment rule

Choose the opinion state that matches the actual review:

- `SUPPORT`;
- `SUPPORT_WITH_CONDITIONS`;
- `OBJECT`;
- `ABSTAIN`;
- `REQUEST_EVIDENCE`.

Do not pre-fill six `SUPPORT` records to satisfy the policy. Each rationale must identify the reviewed evidence and explain the track-specific judgment.

For `SUPPORT_WITH_CONDITIONS`, supply explicit conditions. For `REQUEST_EVIDENCE`, supply explicit evidence requests. Evidence references should use exact digests and the narrowest valid storage boundary.

After recording all available opinions, run `verify_governance_reviewer_opinions()`.

## Phase 4 — disposition states that require owner action

The active v2 policy requires an owner disposition for each designated-authority opinion in any of these states:

- `SUPPORT_WITH_CONDITIONS`;
- `OBJECT`;
- `REQUEST_EVIDENCE`.

Record dispositions with `record_governance_owner_disposition()` and owner key `fraware`.

An owner disposition preserves the response to an opinion; it does not erase the opinion. In particular:

- `OBJECT` remains an active blocking opinion until that same track's designated opinion is explicitly superseded;
- `REQUEST_EVIDENCE` remains an active blocking opinion until explicitly superseded after the evidence question is resolved;
- `SUPPORT_WITH_CONDITIONS` can satisfy the support threshold, but any unresolved `BLOCKS_RELEASE` condition still prevents readiness.

Blocking disposition states are `REJECT`, `DEFER`, and `REQUEST_FURTHER_REVIEW`.

If a condition is later resolved, record a superseding disposition preserving the exact predecessor opinion set and immutable condition fields. A resolved condition requires closure evidence. Never mutate the earlier condition register.

Run `verify_governance_owner_dispositions()` after each disposition sequence.

## Phase 5 — supersede changed judgments explicitly

When review, evidence, or remediation changes the designated authority's opinion, call `record_governance_reviewer_opinion()` again with `supersedes_opinion_id` pointing to the current active opinion for the same scope and track.

Supersession must not change:

- scope ID;
- scope digest;
- review track;
- reviewer identity.

The new opinion becomes active; the predecessor remains part of the audit history. A changed governed artifact requires a new scope instead of opinion supersession on the old scope.

## Phase 6 — compute policy completion

Run:

```python
from neuroai_workbench.governance_policy import evaluate_governance_completion

evaluation = evaluate_governance_completion(
    workspace,
    scope_id=scope_id,
    scope_sha256=scope_sha256,
)
```

Require all of the following before continuing:

```text
integrity_valid = true
track_coverage_complete = true
release_readiness = SATISFIED
```

Inspect every `track_results` entry, not only the top-level readiness string. Confirm:

- one designated-authority supporting opinion on all six tracks;
- no active designated blocking opinions;
- no missing required owner dispositions;
- no non-designated owner disposition on the active decision path;
- no blocking owner dispositions;
- no unresolved release-blocking conditions.

Visible non-designated objections or evidence requests remain part of the record and may appear in `non_designated_blocking_opinion_ids`; they do not acquire v2 veto authority.

Archive the evaluation ID, evaluation digest, input-binding digest, policy digest, and track-result summary in the protected execution note. The evaluation is derived readiness evidence, not a release decision.

## Phase 7 — build the exact release-readiness package

Call `build_release_readiness_package()` using the exact candidate object, scope ID/digest, and product ID/digest list intended for release.

Proceed only when:

```text
readiness_state = READY_FOR_REAL_AUTHORITY_REVIEW
blocker_codes = []
release_blocking_condition_ids = []
```

Confirm that:

- `candidate_artifact_sha256` equals `scope_artifact_sha256`;
- the predecessor reference matches the frozen predecessor;
- the policy reference is the current v2 policy;
- reviewer and disposition references match the verified stores;
- product digests match the frozen products;
- `withheld_claims_sha256` matches the frozen withheld-claims set.

The readiness package is deterministic and will be recomputed by the final decision functions. Any drift after this point is expected to stop the final action.

## Phase 8 — prepare protected authority evidence

Before any authorization call, prepare real authority evidence in the protected environment. The software requires an authority claim containing truthful values for:

- `name_or_role`;
- `organization`;
- `authority_basis`;
- `accountability_state = CLAIMED_EXTERNAL_RELEASE_AUTHORITY`;
- `execution_mode = PROTECTED_REAL_GOVERNANCE`;
- `authority_evidence_reference = protected-ref:<opaque-identifier>`;
- `authority_evidence_sha256 = <sha256-of-the-protected-authority-evidence>`.

The protected reference is an opaque locator; it is not proof by itself. Verify the underlying protected bytes and digest locally.

The software does not authenticate the external authority claim. The repository policy only controls which repository actor may record the final decision.

## Phase 9 — make an explicit authorization decision

### Typed withholding limitation

The current `GOVERNANCE_RELEASE_DECISION` schema admits only:

- `decision_type = AUTHORIZATION`, `decision_state = AUTHORIZED`;
- `decision_type = PUBLICATION`, `decision_state = PUBLISHED`.

There is no repository-native `WITHHELD` decision type or recorder in the current implementation.

Therefore, if authorization is **not** granted:

1. do **not** call `record_release_authorization()`;
2. do **not** fabricate a `GOVERNANCE_RELEASE_DECISION` JSON record;
3. preserve an explicit protected programme decision note that binds the scope ID/digest, readiness-package ID/digest, real authority-evidence reference/digest, decision maker, time, and rationale;
4. verify that no authorization decision exists for the candidate;
5. keep the canonical successor unauthorized and unpublished.

If #114 completion is intended to require a repository-native typed withholding record, that capability must be implemented and reviewed **before** executing the negative-decision path. Documentation must not pretend the current positive-only schema already provides it.

If authorization is granted, call `record_release_authorization()` with:

- the exact candidate;
- exact scope ID and digest;
- exact product list;
- verified real authority claim;
- `actor = "fraware"`.

The function recomputes readiness, validates the current policy binding, requires the designated actor, validates the release-decision store, and rejects duplicate authorization for the same candidate before appending the record.

Immediately run `verify_governance_release_decisions()` and `verify_release_decision_binding()` for the new authorization. Preserve the decision ID and digest in the protected execution note.

An authorization record does not publish anything automatically.

## Phase 10 — publication, only if separately chosen

Publication is a separate deliberate decision. Do not infer it from authorization.

If publication is chosen, first confirm that the exact authorized candidate and readiness package remain current. Prepare publication evidence with:

- `reference = public-ref:<identifier>` or `protected-ref:<identifier>`;
- `sha256 = <digest-of-the-publication-evidence>`.

Call `record_release_publication()` with the exact prior authorization decision ID, the same candidate/scope/products, a valid real authority claim, the publication evidence, and `actor = "fraware"`.

The publication recorder rejects:

- missing or non-authorization predecessor decisions;
- a changed readiness package;
- a changed candidate;
- a second publication for the same authorization;
- a stale current-policy binding;
- a final actor other than `fraware`.

Run `verify_governance_release_decisions()` and `verify_release_decision_binding()` again after publication.

The record sets workflow state to `PUBLISHED` but `automatic_publication_performed` remains `false`. The actual publication mechanism and its evidence remain a separate operational action.

## Phase 11 — final verification package

A completed protected execution should retain, outside public Git unless each item is deliberately safe to publish:

- execution-note identifier and date;
- exact policy ID/version/digest;
- scope ID/digest;
- governed object role/digest inventory;
- six active designated-authority opinion IDs/digests;
- all superseded opinion IDs/digests;
- required owner-disposition IDs/digests;
- condition-register IDs/digests and closure evidence references;
- evaluation ID/digest and input-binding digest;
- readiness package ID/digest;
- authorization decision ID/digest, or the explicit protected withholding note described above;
- publication decision ID/digest if publication occurred;
- final event-chain verification result;
- final governance-store verification results;
- exact candidate and product digests;
- protected authority-evidence reference/digest;
- publication-evidence reference/digest if applicable.

The public repository may receive safe metadata only through a deliberate later publication decision. Do not copy protected evidence or private execution notes into Git to demonstrate completion.

## Completion criterion for #114

Issue #114 is complete only when the actual selected release scope has been executed through this procedure and its acceptance criteria are supported by real protected/runtime records.

The presence of this runbook, passing tests, synthetic rehearsal artifacts, policy v2, or the designated-authority configuration is **not** evidence that #114 has been executed.