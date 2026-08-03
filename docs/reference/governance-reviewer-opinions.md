# Governance reviewer opinions

## Purpose

Governance reviewer opinions are append-only, content-addressed records over one exact governance scope. They preserve claimed attribution, support, conditional support, objection, abstention, requests for evidence, and later supersession without erasing the earlier record.

This layer records workflow evidence. It does not authenticate a reviewer, prove independence, establish institutional delegation, resolve substantive disagreement, or authorize a successor release.

## Prerequisite scope

Every opinion binds both:

- a `GOVSCOPE-*` identifier;
- the exact governance-scope `manifest_sha256`.

The recorder rejects an unknown scope or a mismatched scope digest. A later scope version is a different review object and requires a distinct opinion set. Opinions never float across successor candidates, deltas, reopening registers, products, or withheld-claim sets.

## Opinion states

The schema supports five explicit states:

- `SUPPORT`;
- `SUPPORT_WITH_CONDITIONS`;
- `OBJECT`;
- `ABSTAIN`;
- `REQUEST_EVIDENCE`.

Conditional support contains at least one condition. An evidence request contains at least one concrete request. Abstention remains visible and never converts into support. Objection and evidence-request states remain visible after later owner disposition; owner handling is a separate layer under issue #111.

## Claimed reviewer attribution

Each opinion records:

- a stable local `reviewer_key`;
- a claimed name or role;
- an optional organization;
- an accountability state;
- an independence statement;
- an explicit conflict-of-interest disclosure.

These fields are attributed claims. The software verifies their presence and record integrity. It does not authenticate the person, the organization, the independence claim, or any delegated authority.

## Evidence references

An opinion may bind evidence references by SHA-256. Public, generated, and archive references use normalized relative POSIX locators. Protected evidence uses an opaque `protected-ref:<identifier>` locator. Protected paths and bytes remain outside public Git.

Evidence-reference integrity establishes the declared byte identity. It does not establish provenance, authenticity, admissibility, completeness, or substantive validity.

## Supersession

A reviewer may change an opinion only by recording a new opinion that identifies the current active opinion through:

- `supersedes_opinion_id`;
- `supersedes_opinion_sha256`.

The new record must retain the same governance scope, review track, and `reviewer_key`. Supersession cannot branch, form a cycle, change the reviewed scope, or silently replace an earlier record. Prior opinion files and events remain immutable.

A second active opinion for the same scope, track, and reviewer is rejected. Summaries derive the current active view from the append-only chain and continue to expose the superseded history through the underlying records.

## Recording and event binding

`record_governance_reviewer_opinion` validates the current opinion store, verifies the bound scope identity, normalizes conditions, evidence requests, and evidence references, writes one immutable opinion record under `governance/opinions/`, and appends `GOVERNANCE_REVIEWER_OPINION_RECORDED` to the workspace event chain.

The event binds:

- opinion ID and digest;
- governance-scope ID and digest;
- review track and opinion state;
- reviewer key;
- superseded opinion ID, when present;
- `release_authorization_performed: false`.

## Verification

`verify_governance_reviewer_opinions` checks:

1. closed JSON Schema conformance;
2. canonical opinion SHA-256;
3. the fixed non-authorizing boundary;
4. exact governance-scope binding;
5. required semantics for conditional support and evidence requests;
6. evidence-reference digest and locator structure;
7. unique opinion identifiers;
8. complete, same-reviewer supersession links;
9. absence of branching and cycles;
10. one active opinion per scope, track, and reviewer;
11. one matching append-only event per opinion;
12. event-chain and trailer integrity.

The verifier reports missing review tracks as warnings. Track coverage and release readiness are evaluated later by the versioned six-track policy under issue #112.

## Summary semantics

`summarize_governance_reviewer_opinions` presents every active opinion by track and preserves:

- support states;
- conditions;
- objections;
- evidence requests;
- abstentions;
- mixed support and blocking states within a track.

A disagreement flag is descriptive workflow evidence. It does not decide the dispute. The summary always reports `release_readiness_established: false` and `release_authorization_performed: false`.

## Authority boundary

A cryptographically valid opinion means that the claimed opinion record, scope binding, and event linkage are internally consistent. It does not mean that:

- the reviewer identity is authenticated;
- the reviewer is independent;
- the organization delegated authority;
- the opinion is correct;
- scientific, clinical, regulatory, security, accessibility, domain, affected-community, or conformance requirements are satisfied;
- an institution or UNESCO endorsed the result;
- an owner accepted the opinion;
- a successor is authorized or published.
