# Governance owner dispositions and unresolved conditions

## Purpose

Owner dispositions are an append-only governance layer over exact reviewer-opinion records. They record how a claimed local owner handles one or more current reviewer opinions without erasing dissent, treating missing evidence as an assessment failure, mutating the reviewed governance scope, or granting release authority.

This layer follows governance-scope manifests and reviewer opinions. It is an input to the six-track policy evaluator under issue #112; it does not determine release readiness itself.

## Exact scope and opinion binding

Every disposition binds:

- one `GOVSCOPE-*` identifier and exact scope SHA-256;
- one or more current active `GOVOP-*` identifiers;
- the exact SHA-256 of each addressed opinion;
- each opinion's review track, opinion state, and reviewer key.

A disposition cannot target a superseded reviewer opinion, float across governance scopes, or use a stale opinion digest. The reviewer-opinion store must verify successfully before a new owner disposition is recorded.

Partial disposition is allowed. Any active reviewer opinion not addressed by an active owner disposition remains explicitly visible in verification warnings and summaries. In particular, unaddressed `OBJECT`, `ABSTAIN`, and `REQUEST_EVIDENCE` states remain distinct; none is silently converted to support or failure.

## Disposition states

The owner-disposition schema supports:

- `ACCEPT`;
- `ACCEPT_WITH_ACTION`;
- `REJECT`;
- `DEFER`;
- `REQUEST_FURTHER_REVIEW`.

`ACCEPT_WITH_ACTION` requires at least one condition. A disposition state records workflow handling only. `ACCEPT` does not prove that the reviewer was correct, establish scientific validity, resolve a regulatory question, or authorize a successor.

## Claimed owner attribution

Each record contains a stable local `owner_key`, claimed name or role, optional organization, and accountability state. These fields are attributable workflow claims. The workbench does not authenticate the owner, verify institutional delegation, or infer legal, scientific, clinical, regulatory, UNESCO, publication, or canonical-release authority from the record.

## Condition register

Each owner disposition contains one independently hashed condition-register snapshot. The register is nested in the append-only disposition record so the disposition and condition state are persisted as one immutable object, while the event chain binds both the disposition digest and the independent condition-register digest.

Every condition has:

- a stable `GOVCOND-*` identifier;
- a description;
- a claimed owner;
- priority: `CRITICAL`, `HIGH`, `MEDIUM`, or `LOW`;
- status: `OPEN`, `IN_PROGRESS`, or `RESOLVED`;
- release effect: `BLOCKS_RELEASE` or `NON_BLOCKING`;
- a closure-evidence reference, which is `null` until resolution.

A `RESOLVED` condition requires a closure-evidence reference. An unresolved condition cannot contain closure evidence. Public, generated, and archive evidence references use normalized relative POSIX locators. Protected closure evidence uses an opaque `protected-ref:<identifier>` locator; protected paths and bytes stay outside public Git.

The closure-evidence reference binds declared bytes by SHA-256. Its presence does not establish substantive closure. Later policy evaluation and human governance remain responsible for deciding whether a closure is adequate.

## Supersession and lineage

Changing an owner disposition creates a new record. The successor binds the prior disposition ID and digest; the prior file and event remain immutable.

A successor must retain the exact governance scope and exact addressed reviewer-opinion set. Its condition register binds the predecessor register ID and digest. Existing condition IDs are carried forward automatically and cannot silently disappear. For an existing condition, description, owner, priority, and release effect are immutable across the lineage; status and closure evidence may change through a successor record.

Supersession is fail-closed against missing predecessors, stale hashes, branching, cycles, changed scope, changed opinion bindings, broken register lineage, or removed conditions.

## Active-disposition uniqueness

An active reviewer opinion may be addressed by at most one active owner disposition. A second overlapping disposition is refused unless it explicitly supersedes the current disposition and retains the exact opinion set. Verification independently detects overlapping active records if files are introduced or altered outside the recorder.

## Event binding

Recording a disposition appends `GOVERNANCE_OWNER_DISPOSITION_RECORDED`. The event binds:

- disposition ID and SHA-256;
- condition-register ID and SHA-256;
- governance-scope ID and SHA-256;
- addressed opinion IDs;
- disposition state;
- claimed owner key;
- predecessor disposition ID when present;
- `release_authorization_performed: false`.

The verifier requires a unique matching event and a valid event chain and trailer.

## Verification

`verify_governance_owner_dispositions` checks:

1. the underlying reviewer-opinion store;
2. closed JSON Schema conformance;
3. canonical disposition and condition-register hashes;
4. fixed non-authorizing boundaries;
5. exact scope and opinion bindings;
6. disposition-state semantics;
7. condition identifiers, statuses, priorities, release effects, and closure-evidence locators;
8. append-only disposition and condition-register supersession;
9. condition preservation and immutable condition fields;
10. active-disposition overlap;
11. one matching append-only event per disposition;
12. event-chain and trailer integrity.

Unaddressed active reviewer opinions are warnings rather than integrity errors. A partial owner process may be internally valid and still governance-incomplete.

## Summary semantics

`summarize_governance_owner_dispositions` exposes:

- active owner-disposition states;
- every unaddressed active reviewer opinion;
- explicit flags for unaddressed objection, abstention, and evidence requests;
- every unresolved condition;
- the subset of unresolved conditions marked `BLOCKS_RELEASE`;
- whether all active opinions have an owner disposition.

`owner_disposition_complete` means only that the active reviewer-opinion set is fully dispositioned. The summary always reports `release_readiness_established: false` and `release_authorization_performed: false`. Six-track policy evaluation under #112 determines whether the governance record set satisfies a versioned readiness policy.

## Authority boundary

Cryptographic integrity proves internal consistency of the recorded local workflow claims and bindings. It does not authenticate reviewer or owner identities, establish independence, resolve substantive disagreement, establish scientific truth, demonstrate clinical benefit, prove regulatory authorization or conformance, establish institutional or UNESCO endorsement, or authorize canonical publication.
