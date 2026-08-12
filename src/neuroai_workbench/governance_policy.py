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
DEFAULT_POLICY_RESOURCE = "GOVERNANCE_COMPLETION_POLICY.v1.json"
POLICY_SCHEMA_VERSION = "1"
SUPPORT_STATES = frozenset({"SUPPORT", "SUPPORT_WITH_CONDITIONS"})
POLICY_BOUNDARY = (
    "Governance completion policy evaluates structurally recorded workflow claims over exact hashes. "
    "It does not authenticate reviewers, establish scientific or clinical truth, determine regulatory status "
    "or conformance, confer institutional or UNESCO endorsement, authorize a canonical successor, or authorize publication."
)
EVALUATION_BOUNDARY = (
    "Governance completion evaluation is deterministic workflow-readiness evidence over claimed identities and exact "
    "record digests. Structural sufficiency is not identity authentication, institutional delegation, scientific approval, "
    "regulatory authorization, clinical validation, conformance, UNESCO endorsement, or release authority."
)


def load_governance_completion_policy() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(
            files(OPERATIONS_RESOURCE_PACKAGE).joinpath(DEFAULT_POLICY_RESOURCE).read_text(encoding="utf-8")
        ),
    )


def governance_policy_sha256(policy: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(policy))


def _validate_policy(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if policy.get("schema_version") != POLICY_SCHEMA_VERSION:
        errors.append("unsupported policy schema_version")
    if not str(policy.get("policy_id", "")).startswith("GOVPOLICY-"):
        errors.append("policy_id must use the GOVPOLICY- prefix")
    if not str(policy.get("policy_version", "")).strip():
        errors.append("policy_version is required")
    if policy.get("authority_profile") != "WORKFLOW_COMPLETION_POLICY_ONLY":
        errors.append("policy authority_profile is invalid")
    if policy.get("boundary") != POLICY_BOUNDARY:
        errors.append("policy authority boundary is invalid")

    human_states = policy.get("human_accountability_states")
    if not isinstance(human_states, list) or not human_states or any(not isinstance(item, str) or not item for item in human_states):
        errors.append("human_accountability_states must be a non-empty string list")
    for field in ("no_conflict_markers", "declared_conflict_markers"):
        values = policy.get(field)
        if not isinstance(values, list) or not values or any(not isinstance(item, str) or not item for item in values):
            errors.append(f"{field} must be a non-empty string list")

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
            errors.append(f"track {track}: v1 policy requires explicit applicability")
        for field in (
            "minimum_reviewer_claims",
            "minimum_supporting_reviewer_claims",
            "minimum_distinct_organizations",
        ):
            value = raw.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                errors.append(f"track {track}: {field} must be a positive integer")
        if raw.get("require_claimed_independence") is not True:
            errors.append(f"track {track}: claimed independence must be required")
        if raw.get("require_no_declared_conflict") is not True:
            errors.append(f"track {track}: no-declared-conflict claim must be required")
        blocking = raw.get("blocking_opinion_states")
        if not isinstance(blocking, list) or not set(blocking) <= set(OPINION_STATES):
            errors.append(f"track {track}: invalid blocking_opinion_states")
        owner_required = raw.get("owner_disposition_required_for_states")
        if not isinstance(owner_required, list) or not set(owner_required) <= set(OPINION_STATES):
            errors.append(f"track {track}: invalid owner_disposition_required_for_states")
        owner_blocking = raw.get("blocking_owner_disposition_states")
        if not isinstance(owner_blocking, list) or not set(owner_blocking) <= set(DISPOSITION_STATES):
            errors.append(f"track {track}: invalid blocking_owner_disposition_states")
        if raw.get("unresolved_condition_policy") != "BLOCK_EXPLICIT_RELEASE_BLOCKERS":
            errors.append(f"track {track}: unsupported unresolved_condition_policy")
    return errors


def _active(records: list[dict[str, Any]], *, id_field: str, supersedes_field: str) -> list[dict[str, Any]]:
    superseded = {str(record.get(supersedes_field)) for record in records if record.get(supersedes_field)}
    return [record for record in records if str(record.get(id_field)) not in superseded]


def _starts_with_marker(value: str, markers: list[str]) -> bool:
    normalized = value.strip().upper()
    return any(normalized == marker.upper() or normalized.startswith(f"{marker.upper()}:") for marker in markers)


def _consensus_state(state_counts: Counter[str]) -> str:
    if not state_counts:
        return "NO_REVIEW"
    support = state_counts["SUPPORT"] + state_counts["SUPPORT_WITH_CONDITIONS"]
    blocking = state_counts["OBJECT"] + state_counts["REQUEST_EVIDENCE"]
    if blocking and support:
        return "MIXED_WITH_BLOCKING_DISSENT"
    if state_counts["REQUEST_EVIDENCE"]:
        return "EVIDENCE_REQUESTED"
    if state_counts["OBJECT"]:
        return "OBJECTED"
    if support and state_counts["ABSTAIN"]:
        return "SUPPORT_WITH_ABSTENTION"
    if state_counts["SUPPORT_WITH_CONDITIONS"]:
        return "CONDITIONAL_SUPPORT"
    if state_counts["SUPPORT"]:
        return "SUPPORT"
    if state_counts["ABSTAIN"]:
        return "ABSTENTION_ONLY"
    return "NO_SUPPORT"


def _disposition_by_opinion(active_dispositions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for disposition in active_dispositions:
        for ref in disposition.get("addressed_opinions", []):
            if isinstance(ref, dict):
                opinion_id = str(ref.get("opinion_id", ""))
                if opinion_id:
                    result[opinion_id] = disposition
    return result


def _track_result(
    track: str,
    track_policy: dict[str, Any],
    opinions: list[dict[str, Any]],
    disposition_map: dict[str, dict[str, Any]],
    *,
    human_states: set[str],
    no_conflict_markers: list[str],
    declared_conflict_markers: list[str],
) -> dict[str, Any]:
    state_counts = Counter(str(opinion.get("opinion_state", "")) for opinion in opinions)
    human_claims: list[dict[str, Any]] = []
    supporting_human_claims: list[dict[str, Any]] = []
    organizations: set[str] = set()
    claimed_independence = 0
    claimed_no_conflict = 0
    declared_conflicts: list[str] = []
    unclassified_conflicts: list[str] = []

    for opinion in opinions:
        claim = opinion.get("reviewer_claim")
        if not isinstance(claim, dict):
            continue
        if str(claim.get("accountability_state", "")) not in human_states:
            continue
        human_claims.append(opinion)
        if str(opinion.get("opinion_state", "")) in SUPPORT_STATES:
            supporting_human_claims.append(opinion)
        organization = str(claim.get("organization", "")).strip()
        if organization:
            organizations.add(organization)
        if str(claim.get("independence_statement", "")).strip():
            claimed_independence += 1
        disclosure = str(claim.get("conflict_of_interest_disclosure", ""))
        reviewer_key = str(claim.get("reviewer_key", ""))
        if _starts_with_marker(disclosure, declared_conflict_markers):
            declared_conflicts.append(reviewer_key)
        elif _starts_with_marker(disclosure, no_conflict_markers):
            claimed_no_conflict += 1
        else:
            unclassified_conflicts.append(reviewer_key)

    reviewer_count_ok = len(human_claims) >= int(track_policy["minimum_reviewer_claims"])
    supporting_count_ok = len(supporting_human_claims) >= int(track_policy["minimum_supporting_reviewer_claims"])
    organizations_ok = len(organizations) >= int(track_policy["minimum_distinct_organizations"])
    independence_ok = claimed_independence == len(human_claims) and reviewer_count_ok
    conflicts_ok = (
        not declared_conflicts
        and not unclassified_conflicts
        and claimed_no_conflict == len(human_claims)
        and reviewer_count_ok
    )

    blocking_states = set(track_policy["blocking_opinion_states"])
    blocking_opinions = [
        str(opinion.get("opinion_id"))
        for opinion in opinions
        if str(opinion.get("opinion_state")) in blocking_states
    ]
    evidence_requests = [
        str(opinion.get("opinion_id"))
        for opinion in opinions
        if opinion.get("opinion_state") == "REQUEST_EVIDENCE"
    ]
    objections = [
        str(opinion.get("opinion_id")) for opinion in opinions if opinion.get("opinion_state") == "OBJECT"
    ]
    abstentions = [
        str(opinion.get("opinion_id")) for opinion in opinions if opinion.get("opinion_state") == "ABSTAIN"
    ]

    owner_required_states = set(track_policy["owner_disposition_required_for_states"])
    required_owner_opinions = [
        str(opinion.get("opinion_id"))
        for opinion in opinions
        if str(opinion.get("opinion_state")) in owner_required_states
    ]
    missing_owner_dispositions = sorted(
        opinion_id for opinion_id in required_owner_opinions if opinion_id not in disposition_map
    )
    blocking_owner_states = set(track_policy["blocking_owner_disposition_states"])
    blocking_owner_dispositions: list[str] = []
    condition_by_id: dict[str, dict[str, Any]] = {}
    for opinion in opinions:
        opinion_id = str(opinion.get("opinion_id", ""))
        disposition = disposition_map.get(opinion_id)
        if disposition is None:
            continue
        if disposition.get("disposition_state") in blocking_owner_states:
            blocking_owner_dispositions.append(str(disposition.get("disposition_id")))
        register = disposition.get("condition_register")
        if not isinstance(register, dict):
            continue
        for condition in register.get("conditions", []):
            if isinstance(condition, dict):
                condition_by_id[str(condition.get("condition_id", ""))] = condition
    unresolved_conditions = [
        condition for condition in condition_by_id.values() if condition.get("status") != "RESOLVED"
    ]
    release_blocking_conditions = sorted(
        str(condition.get("condition_id"))
        for condition in unresolved_conditions
        if condition.get("release_effect") == "BLOCKS_RELEASE"
    )

    coverage_state = "COMPLETE" if reviewer_count_ok else "INCOMPLETE"
    if declared_conflicts:
        independence_state = "DECLARED_CONFLICT"
    elif unclassified_conflicts:
        independence_state = "UNVERIFIED_CONFLICT_DISCLOSURE"
    elif reviewer_count_ok and organizations_ok and independence_ok and conflicts_ok:
        independence_state = "STRUCTURALLY_SUFFICIENT_CLAIMS"
    else:
        independence_state = "INSUFFICIENT_CLAIMS"

    readiness = (
        reviewer_count_ok
        and supporting_count_ok
        and organizations_ok
        and independence_ok
        and conflicts_ok
        and not blocking_opinions
        and not missing_owner_dispositions
        and not blocking_owner_dispositions
        and not release_blocking_conditions
    )
    return {
        "track": track,
        "applicable": True,
        "coverage_state": coverage_state,
        "consensus_state": _consensus_state(state_counts),
        "independence_state": independence_state,
        "active_opinion_count": len(opinions),
        "claimed_human_reviewer_count": len(human_claims),
        "supporting_claimed_human_reviewer_count": len(supporting_human_claims),
        "distinct_claimed_organizations": len(organizations),
        "active_state_counts": dict(sorted(state_counts.items())),
        "blocking_opinion_ids": sorted(blocking_opinions),
        "objection_opinion_ids": sorted(objections),
        "evidence_request_opinion_ids": sorted(evidence_requests),
        "abstention_opinion_ids": sorted(abstentions),
        "required_owner_disposition_opinion_ids": sorted(required_owner_opinions),
        "missing_owner_disposition_opinion_ids": missing_owner_dispositions,
        "blocking_owner_disposition_ids": sorted(set(blocking_owner_dispositions)),
        "unresolved_condition_ids": sorted(str(item.get("condition_id")) for item in unresolved_conditions),
        "release_blocking_condition_ids": release_blocking_conditions,
        "declared_conflict_reviewer_keys": sorted(declared_conflicts),
        "unclassified_conflict_reviewer_keys": sorted(unclassified_conflicts),
        "support_threshold_satisfied": supporting_count_ok,
        "organization_threshold_satisfied": organizations_ok,
        "claimed_independence_threshold_satisfied": independence_ok,
        "claimed_conflict_threshold_satisfied": conflicts_ok,
        "release_readiness": "SATISFIED" if readiness else "UNSATISFIED",
    }


def evaluate_governance_completion(
    workspace: Workspace,
    *,
    scope_id: str,
    scope_sha256: str,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate six-track workflow readiness without performing or implying release authorization."""
    policy = deepcopy(policy if policy is not None else load_governance_completion_policy())
    policy_errors = _validate_policy(policy)
    policy_sha256 = governance_policy_sha256(policy)

    opinion_verification = verify_governance_reviewer_opinions(workspace)
    disposition_verification = verify_governance_owner_dispositions(workspace)
    scopes = [scope for scope in load_governance_scope_manifests(workspace) if scope.get("scope_id") == scope_id]
    scope_valid = len(scopes) == 1 and scopes[0].get("manifest_sha256") == scope_sha256

    opinions_all = [
        opinion
        for opinion in load_governance_reviewer_opinions(workspace)
        if opinion.get("scope_id") == scope_id and opinion.get("scope_sha256") == scope_sha256
    ]
    dispositions_all = [
        disposition
        for disposition in load_governance_owner_dispositions(workspace)
        if disposition.get("scope_id") == scope_id and disposition.get("scope_sha256") == scope_sha256
    ]
    active_opinions = _active(opinions_all, id_field="opinion_id", supersedes_field="supersedes_opinion_id")
    active_dispositions = _active(
        dispositions_all,
        id_field="disposition_id",
        supersedes_field="supersedes_disposition_id",
    )
    disposition_map = _disposition_by_opinion(active_dispositions)

    input_opinions = sorted(
        (
            {"opinion_id": str(item.get("opinion_id")), "opinion_sha256": str(item.get("opinion_sha256"))}
            for item in opinions_all
        ),
        key=lambda item: item["opinion_id"],
    )
    input_dispositions = sorted(
        (
            {
                "disposition_id": str(item.get("disposition_id")),
                "disposition_sha256": str(item.get("disposition_sha256")),
                "condition_register_sha256": str(
                    item.get("condition_register", {}).get("register_sha256", "")
                    if isinstance(item.get("condition_register"), dict)
                    else ""
                ),
            }
            for item in dispositions_all
        ),
        key=lambda item: item["disposition_id"],
    )
    input_binding = {
        "scope_id": scope_id,
        "scope_sha256": scope_sha256,
        "policy_id": policy.get("policy_id"),
        "policy_version": policy.get("policy_version"),
        "policy_sha256": policy_sha256,
        "opinion_records": input_opinions,
        "owner_disposition_records": input_dispositions,
    }
    input_binding_sha256 = sha256_bytes(canonical_json_bytes(input_binding))

    human_states = set(str(item) for item in policy.get("human_accountability_states", []))
    no_conflict_markers = [str(item) for item in policy.get("no_conflict_markers", [])]
    declared_conflict_markers = [str(item) for item in policy.get("declared_conflict_markers", [])]
    track_results: dict[str, dict[str, Any]] = {}
    if not policy_errors:
        policy_tracks = cast(dict[str, dict[str, Any]], policy["tracks"])
        for track in sorted(REVIEW_TRACKS):
            track_opinions = [opinion for opinion in active_opinions if opinion.get("review_track") == track]
            track_results[track] = _track_result(
                track,
                policy_tracks[track],
                track_opinions,
                disposition_map,
                human_states=human_states,
                no_conflict_markers=no_conflict_markers,
                declared_conflict_markers=declared_conflict_markers,
            )

    integrity_valid = (
        not policy_errors
        and scope_valid
        and opinion_verification.get("valid") is True
        and disposition_verification.get("valid") is True
    )
    track_coverage_complete = bool(track_results) and all(
        result["coverage_state"] == "COMPLETE" for result in track_results.values()
    )
    unresolved_disagreement = any(result["objection_opinion_ids"] for result in track_results.values())
    unresolved_evidence_requests = any(
        result["evidence_request_opinion_ids"] for result in track_results.values()
    )
    affected_community_gap = (
        "AFFECTED_COMMUNITY" not in track_results
        or track_results["AFFECTED_COMMUNITY"]["coverage_state"] != "COMPLETE"
    )
    release_ready = integrity_valid and bool(track_results) and all(
        result["release_readiness"] == "SATISFIED" for result in track_results.values()
    )

    evaluation: dict[str, Any] = {
        "schema_version": "1",
        "policy_id": policy.get("policy_id"),
        "policy_version": policy.get("policy_version"),
        "policy_sha256": policy_sha256,
        "scope_id": scope_id,
        "scope_sha256": scope_sha256,
        "input_binding": input_binding,
        "input_binding_sha256": input_binding_sha256,
        "integrity_valid": integrity_valid,
        "policy_errors": policy_errors,
        "scope_binding_valid": scope_valid,
        "opinion_store_valid": opinion_verification.get("valid") is True,
        "owner_disposition_store_valid": disposition_verification.get("valid") is True,
        "track_coverage_complete": track_coverage_complete,
        "track_results": track_results,
        "unresolved_disagreement": unresolved_disagreement,
        "unresolved_evidence_requests": unresolved_evidence_requests,
        "affected_community_gap": affected_community_gap,
        "release_readiness": "SATISFIED" if release_ready else "UNSATISFIED",
        "release_authorization_performed": False,
        "canonical_successor_authorized": False,
        "publication_authorized": False,
        "authority_profile": "WORKFLOW_READINESS_EVALUATION_ONLY",
        "boundary": EVALUATION_BOUNDARY,
    }
    evaluation["evaluation_sha256"] = sha256_bytes(canonical_json_bytes(evaluation))
    evaluation["evaluation_id"] = f"GOVEVAL-{evaluation['evaluation_sha256'][:24]}"
    return evaluation
