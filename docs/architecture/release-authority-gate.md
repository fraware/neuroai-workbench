# ADR: Governance-bound release-authority gate

**Status:** Proposed for v0.3.0-dev engineering integration  
**Issue:** #113  
**Decision scope:** successor release-state semantics, governance binding, authorization persistence, publication sequencing  
**Human-governance status:** deferred; no real reviewer, owner, institutional, or release-authority action is created by this ADR or its implementation

## Context

The original successor workflow represented release progression as a local four-state gate:

`CANDIDATE -> REVIEWED -> AUTHORIZED -> PUBLISHED`

A named local workflow claim could advance each state. That mechanism was adequate for early release-control scaffolding, but its semantics are too permissive after the introduction of the hash-bound governance stack under #109-#112. In particular, local attribution could be interpreted as release authority without requiring the exact governance scope, reviewer-opinion history, owner dispositions, policy evaluation, product set, predecessor, or withheld claims.

The observatory now has stronger invariants:

- governance scope is hash-bound;
- reviewer opinions are append-only and preserve dissent, abstention, and evidence requests;
- owner dispositions and unresolved conditions are append-only and crash-consistent;
- a versioned six-track policy evaluates workflow readiness across security, methodology, data governance, accessibility, domain, and affected-community tracks;
- governance records use the shared crash-consistent transaction kernel, with the append-only event as the durable commit witness.

The release gate must enforce the same integrity standard.

## Decision

### 1. Core successor progression stops at `REVIEWED`

The core successor API remains executable without governance activation and continues to support:

`CANDIDATE -> REVIEWED`

`REVIEWED` is a non-authorizing workflow state. New calls to the core successor API requesting `AUTHORIZED` or `PUBLISHED` fail closed and direct callers to the governance release-decision path.

The historical schema retains all four legacy state values so archived records remain readable. Existing records are never rewritten.

### 2. Legacy local authorizing states are classified explicitly

A candidate whose current gate or history contains a locally claimed `AUTHORIZED` or `PUBLISHED` state is classified as:

`LEGACY_LOCAL_AUTHORITY_CLAIM_NOT_GOVERNANCE_COMPLETE`

This classification preserves historical evidence and prevents silent promotion into the new governance-complete model. Legacy classification establishes no finding about the substantive validity of the underlying scientific work.

### 3. Readiness and authority are separate objects

The software constructs a deterministic release-readiness package from current verified inputs. The package binds:

- successor candidate ID and SHA-256;
- immutable predecessor release version and SHA-256;
- governance-scope ID and SHA-256;
- complete same-scope reviewer-opinion history by ID and SHA-256;
- complete same-scope owner-disposition history by ID, disposition SHA-256, and condition-register SHA-256;
- six-track policy evaluation ID, evaluation SHA-256, input-binding SHA-256, policy ID, policy version, and policy SHA-256;
- release product IDs and SHA-256 digests;
- withheld-claims SHA-256.

A package can reach:

`READY_FOR_REAL_AUTHORITY_REVIEW`

only when the candidate is valid, the governance input store is valid, the six-track policy is satisfied, no unresolved `BLOCKS_RELEASE` conditions remain, and no legacy local authorizing gate is present.

This state is readiness evidence. It does not authorize a canonical successor and does not authorize publication.

### 4. `AUTHORIZED` is a separate append-only governance decision

A new authorization decision requires:

- an exact readiness package in `READY_FOR_REAL_AUTHORITY_REVIEW` state;
- exact governance and release-input bindings described above;
- an explicit release-authority workflow claim;
- a digest-bound authority-evidence reference stored as `protected-ref:` metadata, never protected evidence bytes in Git.

The structural claim profile reserved for future real governance is:

- `accountability_state = CLAIMED_EXTERNAL_RELEASE_AUTHORITY`;
- `execution_mode = PROTECTED_REAL_GOVERNANCE`.

Local and synthetic execution modes are rejected by the authorization recorder.

The record also fixes:

`external_authority_authenticated = false`

This is deliberate. Cryptographic integrity of a record does not authenticate the claimant, prove institutional delegation, or establish legal authority. Those properties depend on external evidence and real governance execution.

### 5. `PUBLISHED` requires the exact prior authorization

Publication is a second append-only decision. It requires:

- one exact prior `AUTHORIZED` decision by ID and SHA-256;
- the same candidate and readiness package as the authorization;
- explicit publication evidence by digest;
- a release-authority workflow claim satisfying the same protected real-governance structural profile.

Publication never follows automatically from authorization. Every publication decision records:

`automatic_publication_performed = false`

### 6. Release decisions use the governance transaction kernel

Authorization and publication records are committed through the shared #127 governance transaction primitive.

The persistence invariant is:

- a prepared journal exists first;
- the immutable decision record is written next;
- the append-only event is the durable commit witness;
- interruption prior to durable event append rolls back the new uncommitted record;
- interruption after durable event append recovers the exact decision as committed;
- ambiguous or corrupt states fail closed;
- the governance-wide write lock serializes semantic validation and commit, preventing duplicate concurrent authorizations or publications.

Decision transactions bind secondary digests for the candidate, readiness package, policy evaluation, authority evidence, prior authorization, and publication evidence as applicable.

### 7. Verification is recomputational

A stored release decision is not accepted solely on its stored hashes. Verification recomputes the current readiness package against the supplied candidate, scope, products, and current governance store and detects:

- substituted or altered candidates;
- stale governance scopes;
- reviewer-opinion or owner-disposition drift;
- policy-evaluation drift;
- altered product digests;
- changed withheld claims;
- missing or divergent prior authorization;
- duplicate authorization or publication decisions;
- record or event tampering.

A governance change after authorization therefore produces binding drift until a new valid release process is executed under the applicable policy and authority model.

## Synthetic and test execution

Unit and adversarial tests can exercise the structural serialization and verification paths using records explicitly labeled `TEST FIXTURE ONLY`. Such fixtures can contain the reserved structural constants required to reach code branches, but they remain temporary test data and are never representations of real reviewers, owners, institutions, or release authorities.

The operational rehearsal under #114 must use a separate `SYNTHETIC_REHEARSAL` execution mode. That mode must fail if it attempts to create `AUTHORIZED` or `PUBLISHED` decisions. A successful rehearsal therefore demonstrates that the software refuses synthetic authority escalation.

## Authority boundary

The new release model proves workflow integrity and exact input binding. It does not establish:

- authenticated human identity;
- reviewer independence as a real-world fact;
- institutional delegation;
- legal release authority;
- scientific truth;
- clinical effectiveness;
- regulatory authorization or designation;
- system conformance;
- UNESCO attribution or endorsement;
- canonical publication without a separate valid release-authority decision.

Real-human governance, protected authority evidence, and institutional release execution are intentionally deferred.

## Consequences

The engineering stack can now prepare a candidate all the way to a cryptographically exact `READY_FOR_REAL_AUTHORITY_REVIEW` package without inventing authority. Future real governance can operate on that exact package through the protected authority path. Historical local gate records remain interpretable and auditable, but they cannot satisfy the new release semantics.
