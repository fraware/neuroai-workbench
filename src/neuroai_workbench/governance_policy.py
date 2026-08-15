from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from importlib.resources import files
from typing import Any, cast

from .governance_dispositions import (
    DISPOSITION_STATES,
    load_governance_owner_dispositions,
    verify_governance_owner_dispositions,
)
from .governance_opinions import (
    OPINION_STATES,
    REVIEW_TRACKS,
    load_governance_reviewer_opinions,
    verify_governance_reviewer_opinions,
)
from .governance_scope import load_governance_scope_manifests
from .util import canonical_json_bytes, sha256_bytes
from .workspace import Workspace

OPERATIONS_RESOURCE_PACKAGE = "neuroai_workbench.resources.operations"
DEFAULT_POLICY_RESOURCE = "GOVERNANCE_COMPLETION_POLICY.v2.json"
LEGACY_POLICY_RESOURCE = "GOVERNANCE_COMPLETION_POLICY.v1.json"
POLICY_SCHEMA_VERSIONS = frozenset({"1", "2"})
SINGLE_AUTHORITY_MODEL = "SINGLE_DESIGNATED_HUMAN_AUTHORITY"
SUPPORT_STATES = frozenset({"SUPPORT", "SUPPORT_WITH_CONDITIONS"})
POLICY_BOUNDARY = (
    "Governance completion policy evaluates structurally recorded workflow claims over exact hashes. "
    "It does not authenticate reviewers, establish scientific or clinical truth, determine regulatory status "
    "or conformance, confer institutional or UNESCO endorsement, authorize a canonical successor, or authorize "
    "publication."
)
EVALUATION_BOUNDARY = (
    "Governance completion evaluation is deterministic workflow-readiness evidence over claimed identities and "
    "exact record digests. Structural sufficiency is not identity authentication, institutional delegation, "
    "scientific approval, regulatory authorization, clinical validation, conformance, UNESCO endorsement, or "
    "release authority."
)


def load_governance_completion_policy(*, version: str = "current") -> dict[str, Any]:
    """Load the active policy, or v1 explicitly for historical verification."""
    if version == "current" or version == "2":
        resource_name = DEFAULT_POLICY_RESOURCE
    elif version == "1":
        resource_name = LEGACY_POLICY_RESOURCE
    else:
        raise ValueError(f"Unsupported governance policy version {version!r}")
    resource = files(OPERATIONS_RESOURCE_PACKAGE).joinpath(resource_name)
    return cast(dict[str, Any], json.loads(resource.read_text(encoding="utf-8")))


def governance_policy_sha256(policy: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(policy))


def _string_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item for item in value)


def _state_subset(value: Any, allowed: frozenset[str]) -> bool:
    return isinstance(value, list) and set(value) <= set(allowed)


def _validate_policy(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schema_version = str(policy.get("schema_version", ""))
    if schema_version not in POLICY_SCHEMA_VERSIONS:
        errors.append("unsupported policy schema_version")
    if not str(policy.get("policy_id", "")).startswith("GOVPOLICY-"):
        errors.append("policy_id must use the GOVPOLICY- prefix")
    if not str(policy.get("policy_version", "")).strip():
        errors.append("policy_version is required")
    if policy.get("authority_profile") != "WORKFLOW_COMPLETION_POLICY_ONLY":
        errors.append("policy authority_profile is invalid")
    if policy.get("boundary") != POLICY_BOUNDARY:
        errors.append("policy authority boundary is invalid")
    if not _string_list(policy.get("human_accountability_states")):
        errors.append("human_accountability_states must be a non-empty string list")
    for field in ("no_conflict_markers", "declared_conflict_markers"):
        if not _string_list(policy.get(field)):
            errors.append(f"{field} must be a non-empty string list")

    single_authority = schema_version == "2"
    if single_authority:
        if policy.get("authority_model") != SINGLE_AUTHORITY_MODEL:
            errors.append("v2 policy authority_model is invalid")
        designated = str(policy.get("designated_authority_key", "")).strip()
        if not designated:
            errors.append("v2 policy designated_authority_key is required")
        if policy.get("allow_role_consolidation") is not True:
            errors.append("v2 policy must explicitly allow role consolidation")

    tracks = policy.get("tracks")
    if not isinstance(tracks, dict):
        return errors + ["tracks must be an object"]
    if set(tracks) != set(REVIEW_TRACKS):
        errors.append("policy tracks must exactly match the six governance review tracks")
    for track, raw in tracks.items():
        if not isinstance(raw, dict):
            errors.append(f"track {track}: policy must be an object")
            continue
        if raw.get("applicable") is not True:
            errors.append(f"track {track}: {'v2' if single_authority else 'v1'} policy requires explicit applicability")
        for field in ("minimum_reviewer_claims", "minimum_supporting_reviewer_claims"):
            value = raw.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                errors.append(f"track {track}: {field} must be a positive integer")
        organization_minimum = raw.get("minimum_distinct_organizations")
        minimum_allowed = 0 if single_authority else 1
        if (
            not isinstance(organization_minimum, int)
            or isinstance(organization_minimum, bool)
            or organization_minimum < minimum_allowed
        ):
            qualifier = "non-negative" if single_authority else "positive"
            errors.append(f"track {track}: minimum_distinct_organizations must be a {qualifier} integer")
        if single_authority:
            if raw.get("require_claimed_independence") is not False:
                errors.append(f"track {track}: v2 role consolidation must not require claimed independence")
            if raw.get("require_no_declared_conflict") is not False:
                errors.append(f"track {track}: v2 role consolidation must not require no-conflict status")
        else:
            if raw.get("require_claimed_independence") is not True:
                errors.append(f"track {track}: claimed independence must be required")
            if raw.get("require_no_declared_conflict") is not True:
                errors.append(f"track {track}: no-declared-conflict claim must be required")
        if not _state_subset(raw.get("blocking_opinion_states"), OPINION_STATES):
            errors.append(f"track {track}: invalid blocking_opinion_states")
        if not _state_subset(raw.get("owner_disposition_required_for_states"), OPINION_STATES):
            errors.append(f"track {track}: invalid owner_disposition_required_for_states")
        if not _state_subset(raw.get("blocking_owner_disposition_states"), DISPOSITION_STATES):
            errors.append(f"track {track}: invalid blocking_owner_disposition_states")
        if raw.get("unresolved_condition_policy") != "BLOCK_EXPLICIT_RELEASE_BLOCKERS":
            errors.append(f"track {track}: unsupported unresolved_condition_policy")
    return errors


def _active(
    records: list[dict[str, Any]],
    *,
    id_field: str,
    supersedes_field: str,
) -> list[dict[str, Any]]:
    superseded = {str(record.get(supersedes_field)) for record in records if record.get(supersedes_field)}
    return [record for record in records if str(record.get(id_field)) not in superseded]


def _starts_with_marker(value: str, markers: list[str]) -> bool:
    normalized = value.strip().upper()
    return any(normalized == marker.upper() or normalized.startswith(f"{marker.upper()}:") for marker in markers)


def _consensus_state(counts: Counter[str]) -> str:
    if not counts:
        return "NO_REVIEW"
    support = counts["SUPPORT"] + counts["SUPPORT_WITH_CONDITIONS"]
    blocking = counts["OBJECT"] + counts["REQUEST_EVIDENCE"]
    if blocking and support:
        return "MIXED_WITH_BLOCKING_DISSENT"
    if counts["REQUEST_EVIDENCE"]:
        return "EVIDENCE_REQUESTED"
    if counts["OBJECT"]:
        return "OBJECTED"
    if support and counts["ABSTAIN"]:
        return "SUPPORT_WITH_ABSTENTION"
    if counts["SUPPORT_WITH_CONDITIONS"]:
        return "CONDITIONAL_SUPPORT"
    if counts["SUPPORT"]:
        return "SUPPORT"
    if counts["ABSTAIN"]:
        return "ABSTENTION_ONLY"
    return "NO_SUPPORT"


def _disposition_by_opinion(dispositions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for disposition in dispositions:
        for ref in disposition.get("addressed_opinions", []):
            if isinstance(ref, dict) and ref.get("opinion_id"):
                result[str(ref["opinion_id"])] = disposition
    return result


def _human_claim_metrics(
    opinions: list[dict[str, Any]],
    *,
    human_states: set[str],
    no_conflict_markers: list[str],
    declared_conflict_markers: list[str],
    designated_authority_key: str | None = None,
) -> dict[str, Any]:
    human: list[dict[str, Any]] = []
    supporting: list[dict[str, Any]] = []
    organizations: set[str] = set()
    independent = 0
    no_conflict = 0
    conflicts: list[str] = []
    unclassified: list[str] = []
    wrong_authority: list[str] = []
    for opinion in opinions:
        claim = opinion.get("reviewer_claim")
        if not isinstance(claim, dict):
            continue
        if str(claim.get("accountability_state", "")) not in human_states:
            continue
        reviewer_key = str(claim.get("reviewer_key", ""))
        if designated_authority_key is not None and reviewer_key != designated_authority_key:
            wrong_authority.append(reviewer_key)
            continue
        human.append(opinion)
        if str(opinion.get("opinion_state", "")) in SUPPORT_STATES:
            supporting.append(opinion)
        organization = str(claim.get("organization", "")).strip()
        if organization:
            organizations.add(organization)
        if str(claim.get("independence_statement", "")).strip():
            independent += 1
        disclosure = str(claim.get("conflict_of_interest_disclosure", ""))
        if _starts_with_marker(disclosure, declared_conflict_markers):
            conflicts.append(reviewer_key)
        elif _starts_with_marker(disclosure, no_conflict_markers):
            no_conflict += 1
        else:
            unclassified.append(reviewer_key)
    return {
        "human": human,
        "supporting": supporting,
        "organizations": organizations,
        "independent": independent,
        "no_conflict": no_conflict,
        "conflicts": conflicts,
        "unclassified": unclassified,
        "wrong_authority": wrong_authority,
    }


def _condition_metrics(
    opinions: list[dict[str, Any]],
    disposition_map: dict[str, dict[str, Any]],
    blocking_owner_states: set[str],
) -> tuple[list[str], list[dict[str, Any]]]:
    blocking_dispositions: list[str] = []
    conditions: dict[str, dict[str, Any]] = {}
    for opinion in opinions:
        disposition = disposition_map.get(str(opinion.get("opinion_id", "")))
        if disposition is None:
            continue
        if disposition.get("disposition_state") in blocking_owner_states:
            blocking_dispositions.append(str(disposition.get("disposition_id", "")))
        register = disposition.get("condition_register")
        if not isinstance(register, dict):
            continue
        for condition in register.get("conditions", []):
            if isinstance(condition, dict):
                conditions[str(condition.get("condition_id", ""))] = condition
    unresolved = [item for item in conditions.values() if item.get("status") != "RESOLVED"]
    return sorted(set(blocking_dispositions)), unresolved


def _track_result(
    track: str,
    policy: dict[str, Any],
    opinions: list[dict[str, Any]],
    disposition_map: dict[str, dict[str, Any]],
    *,
    human_states: set[str],
    no_conflict_markers: list[str],
    declared_conflict_markers: list[str],
    authority_model: str | None = None,
    designated_authority_key: str | None = None,
) -> dict[str, Any]:
    counts = Counter(str(opinion.get("opinion_state", "")) for opinion in opinions)
    single_authority = authority_model == SINGLE_AUTHORITY_MODEL
    metrics = _human_claim_metrics(
        opinions,
        human_states=human_states,
        no_conflict_markers=no_conflict_markers,
        declared_conflict_markers=declared_conflict_markers,
        designated_authority_key=designated_authority_key if single_authority else None,
    )
    human = cast(list[dict[str, Any]], metrics["human"])
    supporting = cast(list[dict[str, Any]], metrics["supporting"])
    organizations = cast(set[str], metrics["organizations"])
    conflicts = cast(list[str], metrics["conflicts"])
    unclassified = cast(list[str], metrics["unclassified"])
    wrong_authority = cast(list[str], metrics["wrong_authority"])

    reviewer_ok = len(human) >= int(policy["minimum_reviewer_claims"])
    support_ok = len(supporting) >= int(policy["minimum_supporting_reviewer_claims"])
    organization_ok = len(organizations) >= int(policy["minimum_distinct_organizations"])
    if single_authority:
        independence_ok = True
        conflict_ok = True
        authority_ok = reviewer_ok and support_ok
        independence_state = "ROLE_CONSOLIDATION_ALLOWED"
        authority_state = "DESIGNATED_AUTHORITY_SATISFIED" if authority_ok else "DESIGNATED_AUTHORITY_MISSING"
    else:
        independence_ok = int(metrics["independent"]) == len(human) and reviewer_ok
        conflict_ok = not conflicts and not unclassified and int(metrics["no_conflict"]) == len(human) and reviewer_ok
        authority_ok = reviewer_ok
        if conflicts:
            independence_state = "DECLARED_CONFLICT"
        elif unclassified:
            independence_state = "UNVERIFIED_CONFLICT_DISCLOSURE"
        elif reviewer_ok and organization_ok and independence_ok and conflict_ok:
            independence_state = "STRUCTURALLY_SUFFICIENT_CLAIMS"
        else:
            independence_state = "INSUFFICIENT_CLAIMS"
        authority_state = "MULTI_PARTY_POLICY_SATISFIED" if authority_ok else "MULTI_PARTY_POLICY_INCOMPLETE"

    blocking_states = set(policy["blocking_opinion_states"])
    blocking = [
        str(item.get("opinion_id", "")) for item in opinions if str(item.get("opinion_state", "")) in blocking_states
    ]
    objections = [str(item.get("opinion_id", "")) for item in opinions if item.get("opinion_state") == "OBJECT"]
    requests = [str(item.get("opinion_id", "")) for item in opinions if item.get("opinion_state") == "REQUEST_EVIDENCE"]
    abstentions = [str(item.get("opinion_id", "")) for item in opinions if item.get("opinion_state") == "ABSTAIN"]

    owner_required = set(policy["owner_disposition_required_for_states"])
    required_owner = [
        str(item.get("opinion_id", "")) for item in opinions if str(item.get("opinion_state", "")) in owner_required
    ]
    missing_owner = sorted(item for item in required_owner if item not in disposition_map)
    blocking_owner, unresolved = _condition_metrics(
        opinions,
        disposition_map,
        set(policy["blocking_owner_disposition_states"]),
    )
    release_blockers = sorted(
        str(item.get("condition_id", "")) for item in unresolved if item.get("release_effect") == "BLOCKS_RELEASE"
    )

    ready = all(
        (
            reviewer_ok,
            support_ok,
            organization_ok,
            independence_ok,
            conflict_ok,
            authority_ok,
            not blocking,
            not missing_owner,
            not blocking_owner,
            not release_blockers,
        )
    )
    return {
        "track": track,
        "applicable": True,
        "coverage_state": "COMPLETE" if reviewer_ok else "INCOMPLETE",
        "consensus_state": _consensus_state(counts),
        "independence_state": independence_state,
        "authority_state": authority_state,
        "active_opinion_count": len(opinions),
        "claimed_human_reviewer_count": len(human),
        "supporting_claimed_human_reviewer_count": len(supporting),
        "distinct_claimed_organizations": len(organizations),
        "active_state_counts": dict(sorted(counts.items())),
        "blocking_opinion_ids": sorted(blocking),
        "objection_opinion_ids": sorted(objections),
        "evidence_request_opinion_ids": sorted(requests),
        "abstention_opinion_ids": sorted(abstentions),
        "required_owner_disposition_opinion_ids": sorted(required_owner),
        "missing_owner_disposition_opinion_ids": missing_owner,
        "blocking_owner_disposition_ids": blocking_owner,
        "unresolved_condition_ids": sorted(str(item.get("condition_id", "")) for item in unresolved),
        "release_blocking_condition_ids": release_blockers,
        "declared_conflict_reviewer_keys": sorted(conflicts),
        "unclassified_conflict_reviewer_keys": sorted(unclassified),
        "non_designated_reviewer_keys": sorted(set(wrong_authority)),
        "support_threshold_satisfied": support_ok,
        "organization_threshold_satisfied": organization_ok,
        "claimed_independence_threshold_satisfied": independence_ok,
        "claimed_conflict_threshold_satisfied": conflict_ok,
        "designated_authority_threshold_satisfied": authority_ok,
        "release_readiness": "SATISFIED" if ready else "UNSATISFIED",
    }


def _same_scope_records(
    records: list[dict[str, Any]],
    *,
    scope_id: str,
    scope_sha256: str,
) -> list[dict[str, Any]]:
    return [item for item in records if item.get("scope_id") == scope_id and item.get("scope_sha256") == scope_sha256]


def _input_binding(
    *,
    scope_id: str,
    scope_sha256: str,
    policy: dict[str, Any],
    policy_sha256: str,
    opinions: list[dict[str, Any]],
    dispositions: list[dict[str, Any]],
) -> dict[str, Any]:
    opinion_records = sorted(
        (
            {"opinion_id": str(item.get("opinion_id", "")), "opinion_sha256": str(item.get("opinion_sha256", ""))}
            for item in opinions
        ),
        key=lambda item: item["opinion_id"],
    )
    disposition_records = sorted(
        (
            {
                "disposition_id": str(item.get("disposition_id", "")),
                "disposition_sha256": str(item.get("disposition_sha256", "")),
                "condition_register_sha256": str(
                    item.get("condition_register", {}).get("register_sha256", "")
                    if isinstance(item.get("condition_register"), dict)
                    else ""
                ),
            }
            for item in dispositions
        ),
        key=lambda item: item["disposition_id"],
    )
    return {
        "scope_id": scope_id,
        "scope_sha256": scope_sha256,
        "policy_id": policy.get("policy_id"),
        "policy_version": policy.get("policy_version"),
        "policy_sha256": policy_sha256,
        "opinion_records": opinion_records,
        "owner_disposition_records": disposition_records,
    }


def evaluate_governance_completion(
    workspace: Workspace,
    *,
    scope_id: str,
    scope_sha256: str,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate workflow readiness without performing or implying release authorization."""
    selected = deepcopy(policy if policy is not None else load_governance_completion_policy())
    policy_errors = _validate_policy(selected)
    policy_sha256 = governance_policy_sha256(selected)

    opinion_verification = verify_governance_reviewer_opinions(workspace)
    disposition_verification = verify_governance_owner_dispositions(workspace)
    scopes = [item for item in load_governance_scope_manifests(workspace) if item.get("scope_id") == scope_id]
    scope_valid = len(scopes) == 1 and scopes[0].get("manifest_sha256") == scope_sha256

    opinions = _same_scope_records(
        load_governance_reviewer_opinions(workspace), scope_id=scope_id, scope_sha256=scope_sha256
    )
    dispositions = _same_scope_records(
        load_governance_owner_dispositions(workspace), scope_id=scope_id, scope_sha256=scope_sha256
    )
    active_opinions = _active(opinions, id_field="opinion_id", supersedes_field="supersedes_opinion_id")
    active_dispositions = _active(
        dispositions, id_field="disposition_id", supersedes_field="supersedes_disposition_id"
    )
    disposition_map = _disposition_by_opinion(active_dispositions)
    binding = _input_binding(
        scope_id=scope_id,
        scope_sha256=scope_sha256,
        policy=selected,
        policy_sha256=policy_sha256,
        opinions=opinions,
        dispositions=dispositions,
    )

    tracks: dict[str, dict[str, Any]] = {}
    if not policy_errors:
        policy_tracks = cast(dict[str, dict[str, Any]], selected["tracks"])
        human_states = set(str(item) for item in selected["human_accountability_states"])
        no_conflict = [str(item) for item in selected["no_conflict_markers"]]
        declared_conflict = [str(item) for item in selected["declared_conflict_markers"]]
        authority_model = str(selected.get("authority_model", "")) or None
        designated_authority_key = str(selected.get("designated_authority_key", "")) or None
        for track in sorted(REVIEW_TRACKS):
            track_opinions = [item for item in active_opinions if item.get("review_track") == track]
            tracks[track] = _track_result(
                track,
                policy_tracks[track],
                track_opinions,
                disposition_map,
                human_states=human_states,
                no_conflict_markers=no_conflict,
                declared_conflict_markers=declared_conflict,
                authority_model=authority_model,
                designated_authority_key=designated_authority_key,
            )

    integrity_valid = all(
        (
            not policy_errors,
            scope_valid,
            opinion_verification.get("valid") is True,
            disposition_verification.get("valid") is True,
        )
    )
    coverage_complete = bool(tracks) and all(result["coverage_state"] == "COMPLETE" for result in tracks.values())
    disagreement = any(result["objection_opinion_ids"] for result in tracks.values())
    evidence_requests = any(result["evidence_request_opinion_ids"] for result in tracks.values())
    affected_gap = "AFFECTED_COMMUNITY" not in tracks or tracks["AFFECTED_COMMUNITY"]["coverage_state"] != "COMPLETE"
    ready = integrity_valid and bool(tracks) and all(
        result["release_readiness"] == "SATISFIED" for result in tracks.values()
    )
    evaluation: dict[str, Any] = {
        "schema_version": "2" if selected.get("schema_version") == "2" else "1",
        "policy_id": selected.get("policy_id"),
        "policy_version": selected.get("policy_version"),
        "policy_sha256": policy_sha256,
        "authority_model": selected.get("authority_model", "MULTI_PARTY_STRUCTURAL_REVIEW"),
        "designated_authority_key": selected.get("designated_authority_key"),
        "role_consolidation_allowed": selected.get("allow_role_consolidation") is True,
        "scope_id": scope_id,
        "scope_sha256": scope_sha256,
        "input_binding": binding,
        "input_binding_sha256": sha256_bytes(canonical_json_bytes(binding)),
        "integrity_valid": integrity_valid,
        "policy_errors": policy_errors,
        "scope_binding_valid": scope_valid,
        "opinion_store_valid": opinion_verification.get("valid") is True,
        "owner_disposition_store_valid": disposition_verification.get("valid") is True,
        "track_coverage_complete": coverage_complete,
        "track_results": tracks,
        "unresolved_disagreement": disagreement,
        "unresolved_evidence_requests": evidence_requests,
        "affected_community_gap": affected_gap,
        "release_readiness": "SATISFIED" if ready else "UNSATISFIED",
        "release_authorization_performed": False,
        "canonical_successor_authorized": False,
        "publication_authorized": False,
        "authority_profile": "WORKFLOW_READINESS_EVALUATION_ONLY",
        "boundary": EVALUATION_BOUNDARY,
    }
    evaluation["evaluation_sha256"] = sha256_bytes(canonical_json_bytes(evaluation))
    evaluation["evaluation_id"] = f"GOVEVAL-{evaluation['evaluation_sha256'][:24]}"
    return evaluation
