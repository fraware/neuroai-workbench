# PR #229 / #231 / #233 local integration

Status: working-tree integration note. Hosted GitHub Actions has not executed workflow steps for these pull requests (`steps: []`). This note does not claim hosted CI success, merge, publication, or a `v0.3.0` tag.

## Baseline

Local `main` at integration start: `cbd756bd3a5be21e697605be01ab95d5392e3281`. Package identity: `0.3.0.dev0`.

PRs were applied onto this working tree with `git checkout <pull-head> -- <files>`. They were **not** merged with `gh pr merge`, not pushed, and not committed by this integration.

## What was integrated

### PR #229 (`feat/observatory-v2-foundation`) — documentation

Landed the Observatory v2 architecture documents and ADR 0014:

- `docs/architecture/vision-and-target-architecture.md`
- `docs/architecture/observatory-v2-ontology.md`
- `docs/architecture/temporal-model.md`
- `docs/architecture/entity-identity-model.md`
- `docs/architecture/s2-s3-evidence-contract.md`
- `docs/architecture/release-model-v2.md`
- `docs/architecture/observatory-v2-migration-boundary.md`
- `docs/adr/0014-observatory-v2-temporal-assertion-model.md`
- documentation index updates

Overlap with the engineering handoff is resolved by **preserving the stronger semantics**:

- every increase in authority remains explicit, reviewable, attributable, and reversible;
- mechanical PASS is not release authorization;
- Source versus Observation versus capture custody remain distinct;
- connected-IP provenance is required of the production transport (PR #233 remainder), not deferred behind mutable `last_connected_address`;
- source-universe programmes report denominator and pagination separately; cursor completion is not recall;
- typed delta vocabulary expansion remains M2 and is not silently introduced here;
- existing methodology identity `SU-TRIAL` is kept (documentation may alias `SU-TRIALS`; the id is not renamed).

ADR 0014 is accepted as the temporal implementation ADR for Workbench types. ADR 0015 (provenance) and ADR 0016 (identifier versus unresolved literal) are implementation ADRs and do not restate the #229 architecture essays.

### PR #231 (`feat/clinicaltrials-discovery-projection`) — applied onto main

Landed independently of #233:

- `src/neuroai_workbench/discovery/clinicaltrials.py` and exports
- ClinicalTrials.gov search-page projection, exact NCT identity, known-index duplicate protection
- `OFFLINE_REPLAY` execution mode
- study-type retention and post-retrieval filter accounting
- associated tests

This is the reference implementation for the reusable source-universe programme (`SU-TRIAL`), not a silent rename to `SU-TRIALS`.

### PR #233 (`feat/pinned-dns-http-transport`) — applied onto main, unstacked

#233 was stacked on #231 on GitHub. Transport security must not depend on discovery projection. Unique #233 files were checked out from `pull/233/head` onto this tree **without** keeping that stack.

Landed:

- `PinnedSocketHttpTransport`
- `HttpRequest.validated_addresses`
- collection-outcome quarantine-record exposure
- collection-request onboarding-manifest XOR registry binding
- dedicated pinned-transport tests

Not landed from #233:

- `.github/workflows/pinned-dns-http-transport.yml` — a new unaudited workflow would expand the GitHub workflow surface during CI rehabilitation. Existing `CI / tests-python-*` already executes the pytest modules. The dedicated workflow is deferred, not rejected on security grounds.

The remainder of E2 (authorization packet, immutable quarantine successors, connected-IP provenance, rights/retention and scan hooks) is implemented in this same working tree on top of the #233 transport.

## Hosted CI

See [hosted-ci-empty-steps.md](hosted-ci-empty-steps.md). Empty `steps: []` is infrastructure failure. Issue #4 (missing hosted `CI / pip-audit` and `CI / product-native` on ruleset `20116255`) is a separate ruleset-parity gap. The `v0.2.1` tag peel is historical and not M0-blocking.

## Explicitly not done by this integration

- `gh pr merge` / push / commit
- git tag `v0.3.0` or `v1.0`
- `release_authorized=true`
- Hosted CI rehabilitation (org runner assignment remains infrastructure-only; see [hosted-ci-empty-steps.md](hosted-ci-empty-steps.md))

Subsequent handoff milestones M2–M6 (additional programmes, living observatory `/v1`, validation/institutional hooks, v1.0 readiness gate doc) are implemented in the same working tree and remain uncommitted unless separately requested.
