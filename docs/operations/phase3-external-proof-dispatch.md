# Phase 3 controlled external proof dispatch

## Purpose

`.github/workflows/phase3-external-proof.yml` is the controlled execution surface for the external reference-source proof required by issue #287. It exists because ordinary pull-request, push, and scheduled workflows must never create live-acquisition authority implicitly.

The workflow has one trigger: `workflow_dispatch`. It also fails closed unless the authenticated dispatch targets `main` and the operator supplies the exact confirmation token `AUTHORIZE_ONE_CT_GOV_PHASE3_LIVE_REQUEST`.

Merging this workflow establishes execution readiness only. It does not execute the external proof, complete Phase 3, authorize Phase 4, pass G0/G2, establish source or clinical truth, mutate canonical S2, authorize publication, or alter assessment authority.

## Fixed reference-source identity

The first controlled proof is deliberately fixed to the already governed ClinicalTrials.gov continuity anchor:

- source: `SRC-PR-002`;
- study: `NCT04676854`;
- origin: `https://clinicaltrials.gov`;
- programme: `PHASE3-CTGOV-EXTERNAL-PROOF-V1`.

The dispatch does not accept an arbitrary NCT identifier. Changing this identity requires a reviewed code change instead of an operator-time substitution.

## Authorization boundary

At run time, the workflow derives two short-lived, digest-bound operational objects from the authenticated GitHub actor, exact Actions run ID, and run attempt:

1. an acquisition policy scoped to `SRC-PR-002`, `ONLINE_REQUIRED` plus `REPLAY_ONLY`, the exact ClinicalTrials.gov origin, and `FALLBACK_FORBID`;
2. an `AUTHORIZED_NETWORK` local collection-authorization packet.

The existing `NEUROAI_LIVE_COLLECTION=1` gate remains independently required. These objects record claimed local operational permission only. They do not establish institutional delegation, legal authorization, source authenticity, evidence truth, S2 admission, release authorization, or publication authority.

## Execution sequence

The controlled run installs the exact dispatched Workbench tree from the hash-locked dependency constraints, creates all state under `RUNNER_TEMP`, then executes the existing Phase 3 runner. The live command must durably persist one exact ClinicalTrials.gov result before projection. The subsequent `REPLAY_ONLY` command names that exact `result_id` and must report zero collection attempts. The runtime-proof builder/verifier then revalidates the capture and run-ledger identities and requires live/replay deterministic projection equivalence.

The workflow additionally re-runs `tests/unit/test_online_first_runtime_proof.py` on the exact dispatched code so the durable-result crash window, fallback-pending recovery, replay and integrity adversarial controls remain executable in the same runtime used for the external proof.

## Custody and retained evidence

Captured response bytes and quarantine records remain under the ephemeral `RUNNER_TEMP` quarantine directory. They are not copied into the retained artifact.

The uploaded proof bundle is restricted to operational metadata:

- digest-bound acquisition policy and local authorization packet;
- bounded registry and collector-configuration identity records;
- live and replay run references;
- the verified runtime proof;
- an execution attestation binding GitHub actor/run/SHA/ref and explicit non-authority state;
- SHA-256 checksums over the bundle.

The workflow checks that the repository working tree remains clean and that the upload path is the proof-bundle directory, not quarantine.

## Operator procedure after merge

A human operator must use the GitHub Actions interface for `fraware/neuroai-workbench`, select **Phase 3 external proof**, choose the `main` branch, enter `AUTHORIZE_ONE_CT_GOV_PHASE3_LIVE_REQUEST`, and run the workflow. No other trigger is accepted.

After the run completes, issue #287 remains open until the resulting Actions run and retained proof artifact are reviewed against the exact Phase 3 acceptance criteria. A green workflow is operational evidence; the governance disposition remains separate.

## Failure handling

Any failed live request, authorization/policy mismatch, identity mismatch, nonzero replay collection count, projection mismatch, coverage shortfall, recovery-test failure, repository mutation, or artifact-boundary violation leaves Phase 3 incomplete. The failure must be preserved and diagnosed. It must not be converted into a passing result by weakening a check, changing the reference identity during the same run, substituting a fake transport, or uploading the raw quarantine material.
