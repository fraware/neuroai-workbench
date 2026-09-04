# Online-first Phase 3: controlled live/replay runtime proof

**Status:** bounded proof architecture for issue #287  
**Baseline:** Workbench `5a7bc387d0da31d92b1bee2794eb7e270412b755`  
**Scope:** operational capture/replay equivalence and interruption evidence only  
**Runtime default:** unchanged; local/offline-first

## Objective

Phase 3 converts the Phase 2A policy-bound live path and Phase 2B replay/fallback path into auditable proof evidence for one exact structured source. It does not change the default scheduler, deploy a standing network service, mutate canonical Observatory S2, or authorize publication.

The reference source is one ClinicalTrials.gov single-study endpoint:

```text
https://clinicaltrials.gov/api/v2/studies/<NCT-ID>
```

This source is used because the existing adapter separates HTTP capture from deterministic structured normalization. The proof therefore tests a narrow software property: the same hash-verified captured JSON bytes produce the same canonical normalized projection when projected from the live-capture lineage and from the replay lineage.

The governing separation remains:

```text
acquisition permission
    != live observation
    != captured-byte identity
    != deterministic projection
    != source truth
    != evidence adjudication
    != assessment mutation
    != canonical S2 admission
    != release authorization
    != publication
```

## Proof boundary

A Phase 3 proof establishes only bounded operational properties for the exact programme, source, acquisition policy, code/configuration, run ledgers, and captured bytes named by the proof. It does not establish ClinicalTrials.gov completeness, NeuroAI relevance, clinical validity, scientific truth, G0/G1/G2 passage, legal authority, institutional identity, production readiness, release authorization, or publication authority.

The proof bundle contains no claim that an NCT record is a valid or complete representation of a clinical intervention. The fixture/live source is an execution reference, not an assessment conclusion.

## Capture-before-projection

The live path must persist the collector result record and quarantine bytes before the Phase 3 projection is calculated. The proof verifier never projects directly from a network response. It loads the durable result record, resolves the controlled quarantine path, revalidates byte size and SHA-256, decodes JSON, and only then calls the existing `ClinicalTrialsGovAdapter.normalize_study` normalizer.

This creates the required boundary:

```text
external response
    -> durable immutable collector result + quarantine bytes
    -> hash/size revalidation
    -> deterministic structured projection
```

The collector result remains `RETRIEVED_BYTES_NOT_SUBSTANTIVELY_ADJUDICATED`. Projection equality does not change that evidence state.

## Run-ledger binding

The proof verifier validates the durable run summary, manifest, and target checkpoint for both the live and replay runs. It requires:

- one exact logical source and one retrieval target;
- the exact programme ID and acquisition-policy SHA-256 in the run binding;
- a live run bound to an online acquisition mode;
- a replay run bound to `REPLAY_ONLY`;
- the summary manifest and binding digests to match the durable manifest;
- the summary semantic digest to recompute from its semantic fields;
- the target checkpoint to be hash-valid and terminal `RESULT`;
- the checkpoint result identity to equal the collector result used for projection;
- source-accountability coverage = `1.0`;
- target-execution coverage = `1.0`.

The live run must record at least one collection attempt and must not use prior-capture fallback. The replay run must record zero collection attempts, zero unique retrievals, zero retries, no per-host accounting, and an empty target-attempt list.

## Exact replay identity

The replay checkpoint must preserve the original:

- `result_id`;
- `retrieved_at`;
- content SHA-256;
- byte size and quarantine-path binding;
- source/monitor identity;
- normalized retrieval URL.

The replay target's pre-bound `prior_capture` reference is compared canonically with the current hash-verified collector result reference. A replay cannot mint a new collector result or rewrite the original capture timestamp.

## Projection equivalence

The live-capture projection and replay projection are each computed independently from the same verified durable capture. Each projection is canonical-JSON encoded and SHA-256 hashed.

Phase 3 equivalence requires:

```text
live_projection_sha256 == replay_projection_sha256
```

This equality means that the same bytes, under the same normalizer implementation, produced the same deterministic projection. It is not evidence that the source content is true, complete, clinically valid, or unchanged outside the captured observation.

## Semantic proof digest and recurrence

A proof has a `proof_semantic_sha256` over the semantic object only. The semantic object binds:

- programme/source/policy identity;
- exact capture identity and hash;
- exact normalized projection and projection digest;
- live run summary, manifest, binding, and target-checkpoint digests;
- replay run summary, manifest, binding, and target-checkpoint digests;
- route and operational accounting;
- the fixed authority boundary and bounded proof claims.

`created_at` and the output filesystem path are deliberately excluded from the semantic digest. Rebuilding the proof over the same durable capture and same run-ledger state therefore produces the same proof ID and semantic digest even when the proof file is emitted later or at another controlled path.

Any semantic provenance, capture, projection, run-binding, route, or accounting change changes the semantic digest or fails verification.

## Interruption proof

Phase 3 reuses the existing run-ledger recovery semantics instead of adding a second recovery state machine.

The deterministic test seam exercises two crash windows:

1. **Durable result before checkpoint commit.** The collector result is persisted, execution is interrupted before the scheduler applies it to the target checkpoint, and resume recovers the deterministic request ID from durable collector records. The resumed run performs zero duplicate HTTP sends for the committed retrieval.
2. **Fallback pending before terminalization.** A Phase 2B scheduler reaches terminal retryable live failure, persists the `fallback_pending` checkpoint containing the pre-bound prior capture, and is interrupted before fallback terminalization. Resume applies that exact bound capture even if a newer eligible capture appears afterward; no new live request is required for that checkpoint transition.

These are recovery proofs, not availability guarantees.

## Controlled proof runner

`scripts/run_online_first_phase3_proof.py` provides four explicit commands:

- `live` — one single-source live collection run;
- `replay` — a zero-network replay run;
- `build` — build and immediately verify the semantic proof from durable run IDs;
- `verify` — re-verify an existing proof against durable controlled records.

The script performs no network operation by default. Live mode requires all of the following before a `PinnedSocketHttpTransport` is constructed:

1. the explicit `live` command;
2. `--execute-live`;
3. an active acquisition policy authorizing the exact programme/source/origin in `ONLINE_REQUIRED` mode;
4. the existing digest-bound live-authorization packet in `NEUROAI_LIVE_COLLECTION_AUTHORIZATION_JSON`;
5. `NEUROAI_LIVE_COLLECTION=1`;
6. an explicit operator-controlled quarantine root;
7. an explicit proof-output directory plus `--confirm-noncanonical-output`.

The confirmation flag records an operator assertion that the proof-output directory is outside canonical S2. It is not a substitute for deployment-level path policy. The script does not know the location of an independently governed Observatory repository and does not attempt to mutate it.

Replay mode constructs `ReplayOnlyCollectionScheduler` only; it does not construct the pinned transport or a DNS path.

## CI versus external live proof

Normal CI uses injected transport/DNS and public synthetic ClinicalTrials.gov-shaped JSON. CI proves software behavior without contacting the Internet. It must remain deterministic and offline-capable.

An actual external Phase 3 proof is a separate manually authorized operation. It is acceptable only when the exact active policy and existing live-authorization gate both permit the request at execution time. The external proof must retain the live capture in controlled quarantine and must not commit captured response bodies to public Git.

The external proof requires all of the following evidence:

- durable live capture before projection;
- exact replay of that capture with zero external I/O;
- equal live/replay projection semantic digests;
- source-accountability coverage = `1.0`;
- target-execution coverage = `1.0`;
- no prior-capture substitution for the live equivalence run;
- interruption evidence showing no duplicate committed retrieval;
- no canonical S2/release/publication mutation.

If the available execution environment cannot perform the authorized external request, the Phase 3 implementation may be reviewed as a proof harness only. Phase 3 remains incomplete and Phase 4 remains blocked until the external proof is actually executed and reviewed.

## Data handling

Live response bodies remain under the collector quarantine root and inherit collector rights, scanning, retention, access-control, and incident-response requirements. The proof bundle stores only the minimum result/run identities, hashes, structured projection, operational accounting, and authority boundary needed for audit.

A structured normalized projection may itself contain public source fields. Its inclusion in a proof bundle does not authorize redistribution of underlying captured bytes or override source terms. Operators remain responsible for the classification and retention of proof outputs.

## Non-claims

Phase 3 does not change the Workbench default from local/offline-first, deploy a production scheduler, create a standing network permission, replace the existing live authorization gate, add browser/open-world discovery, mutate canonical S2, modify assessments, authorize a release, publish an Observatory product, or establish G0/G1/G2 passage.

Phase 4 remains a separate governance and architecture decision. An online-first production/default transition may be considered only after the actual external Phase 3 proof evidence is complete, reviewed, and explicitly accepted under the applicable control process.
