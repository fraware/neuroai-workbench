from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from neuroai_workbench.governance_dispositions import record_governance_owner_disposition
from neuroai_workbench.governance_opinions import REVIEW_TRACKS, record_governance_reviewer_opinion
from neuroai_workbench.governance_policy import (
    SINGLE_AUTHORITY_MODEL,
    _validate_policy,
    evaluate_governance_completion,
    governance_policy_sha256,
    load_governance_completion_policy,
)
from neuroai_workbench.governance_scope import record_governance_scope_manifest, scope_object_for_path
from neuroai_workbench.util import atomic_write_json
from neuroai_workbench.workspace import Workspace


def _workspace_and_scope(tmp_path: Path) -> tuple[Workspace, dict[str, Any]]:
    workspace = Workspace.initialize(tmp_path / "workspace")
    public = tmp_path / "public"
    generated = tmp_path / "generated"
    archive = tmp_path / "archive"
    for root in (public, generated, archive):
        root.mkdir()
    paths = {
        "predecessor": archive / "predecessor.json",
        "candidate": generated / "candidate.json",
        "delta": generated / "delta.json",
        "reopening": generated / "reopening.json",
        "products": generated / "products.json",
        "claims": public / "claims.json",
    }
    for label, path in paths.items():
        atomic_write_json(path, {"fixture": label})
    objects = [
        scope_object_for_path(role="PREDECESSOR_RELEASE", label="Predecessor", object_type="RELEASE", path=paths["predecessor"], storage_boundary="ARCHIVE", boundary_root=archive),
        scope_object_for_path(role="SUCCESSOR_CANDIDATE", label="Candidate", object_type="SUCCESSOR_CANDIDATE", path=paths["candidate"], storage_boundary="GENERATED_OUTPUT", boundary_root=generated),
        scope_object_for_path(role="DELTA", label="Delta", object_type="DELTA", path=paths["delta"], storage_boundary="GENERATED_OUTPUT", boundary_root=generated),
        scope_object_for_path(role="REOPENING_REGISTER", label="Reopening", object_type="REOPENING_REGISTER", path=paths["reopening"], storage_boundary="GENERATED_OUTPUT", boundary_root=generated),
        scope_object_for_path(role="PRODUCT_MANIFEST", label="Products", object_type="PRODUCT_MANIFEST", path=paths["products"], storage_boundary="GENERATED_OUTPUT", boundary_root=generated),
        scope_object_for_path(role="WITHHELD_CLAIMS", label="Withheld claims", object_type="CLAIM_SET", path=paths["claims"], storage_boundary="PUBLIC_GIT", boundary_root=public),
    ]
    scope = record_governance_scope_manifest(
        workspace,
        scope_label="Synthetic six-track policy fixture",
        objects=objects,
        boundary_roots={"PUBLIC_GIT": public, "GENERATED_OUTPUT": generated, "ARCHIVE": archive},
    )["manifest"]
    return workspace, scope


def _reviewer_claim(
    key: str,
    organization: str,
    *,
    conflict: str = "NO_CONFLICT_DECLARED: synthetic fixture",
    accountability: str = "CLAIMED_HUMAN_REVIEWER",
    independence: str = "Synthetic claimed independence; not authenticated.",
) -> dict[str, str]:
    return {
        "reviewer_key": key,
        "name_or_role": f"Synthetic reviewer {key}",
        "organization": organization,
        "accountability_state": accountability,
        "independence_statement": independence,
        "conflict_of_interest_disclosure": conflict,
    }


def _opinion(
    workspace: Workspace,
    scope: dict[str, Any],
    *,
    track: str,
    key: str,
    organization: str,
    state: str = "SUPPORT",
    conflict: str = "NO_CONFLICT_DECLARED: synthetic fixture",
    accountability: str = "CLAIMED_HUMAN_REVIEWER",
    supersedes: str | None = None,
) -> dict[str, Any]:
    conditions = ["Synthetic reviewer condition"] if state == "SUPPORT_WITH_CONDITIONS" else None
    requests = ["Synthetic evidence request"] if state == "REQUEST_EVIDENCE" else None
    return record_governance_reviewer_opinion(
        workspace,
        scope_id=scope["scope_id"],
        scope_sha256=scope["manifest_sha256"],
        review_track=track,
        opinion_state=state,
        reviewer_claim=_reviewer_claim(key, organization, conflict=conflict, accountability=accountability),
        rationale=f"Synthetic {state} opinion for policy testing.",
        conditions=conditions,
        evidence_requests=requests,
        supersedes_opinion_id=supersedes,
    )["opinion"]


def _populate_support(
    workspace: Workspace,
    scope: dict[str, Any],
    *,
    omit: set[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for track in sorted(REVIEW_TRACKS - (omit or set())):
        result[track] = [
            _opinion(workspace, scope, track=track, key=f"{track.lower()}-reviewer-a", organization=f"Synthetic {track} Organization A"),
            _opinion(workspace, scope, track=track, key=f"{track.lower()}-reviewer-b", organization=f"Synthetic {track} Organization B"),
        ]
    return result


def _populate_designated_support(workspace: Workspace, scope: dict[str, Any]) -> None:
    for track in sorted(REVIEW_TRACKS):
        _opinion(
            workspace,
            scope,
            track=track,
            key="fraware",
            organization="Repository governance",
            conflict="CONFLICT_DECLARED: role consolidation is explicit under policy v2",
        )


def _evaluate(workspace: Workspace, scope: dict[str, Any], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    return evaluate_governance_completion(
        workspace,
        scope_id=scope["scope_id"],
        scope_sha256=scope["manifest_sha256"],
        policy=policy if policy is not None else load_governance_completion_policy(version="1"),
    )


def test_default_policy_is_versioned_and_hash_stable() -> None:
    policy = load_governance_completion_policy()
    assert policy["policy_id"] == "GOVPOLICY-1.0.0"
    assert policy["policy_version"] == "1.0.0"
    assert set(policy["tracks"]) == set(REVIEW_TRACKS)
    assert governance_policy_sha256(policy) == governance_policy_sha256(deepcopy(policy))


def test_current_policy_is_single_designated_authority_and_v1_is_unchanged() -> None:
    legacy = load_governance_completion_policy(version="1")
    current = load_governance_completion_policy(version="2")
    assert legacy["policy_id"] == "GOVPOLICY-1.0.0"
    assert current["policy_id"] == "GOVPOLICY-2.0.0"
    assert current["schema_version"] == "2"
    assert current["authority_model"] == SINGLE_AUTHORITY_MODEL
    assert current["designated_authority_key"] == "fraware"
    assert current["allow_role_consolidation"] is True
    assert _validate_policy(legacy) == []
    assert _validate_policy(current) == []
    assert governance_policy_sha256(legacy) != governance_policy_sha256(current)


def test_single_designated_authority_can_cover_all_six_tracks(tmp_path: Path) -> None:
    workspace, scope = _workspace_and_scope(tmp_path)
    _populate_designated_support(workspace, scope)
    evaluation = evaluate_governance_completion(
        workspace,
        scope_id=scope["scope_id"],
        scope_sha256=scope["manifest_sha256"],
    )
    assert evaluation["schema_version"] == "2"
    assert evaluation["authority_model"] == SINGLE_AUTHORITY_MODEL
    assert evaluation["designated_authority_key"] == "fraware"
    assert evaluation["role_consolidation_allowed"] is True
    assert evaluation["release_readiness"] == "SATISFIED"
    assert evaluation["track_coverage_complete"] is True
    for result in evaluation["track_results"].values():
        assert result["claimed_human_reviewer_count"] == 1
        assert result["supporting_claimed_human_reviewer_count"] == 1
        assert result["authority_state"] == "DESIGNATED_AUTHORITY_SATISFIED"
        assert result["independence_state"] == "ROLE_CONSOLIDATION_ALLOWED"
        assert result["designated_authority_threshold_satisfied"] is True
        assert result["release_readiness"] == "SATISFIED"


def test_non_designated_human_cannot_satisfy_v2_authority(tmp_path: Path) -> None:
    workspace, scope = _workspace_and_scope(tmp_path)
    for track in sorted(REVIEW_TRACKS):
        _opinion(workspace, scope, track=track, key="other-human", organization="Other organization")
    evaluation = evaluate_governance_completion(
        workspace,
        scope_id=scope["scope_id"],
        scope_sha256=scope["manifest_sha256"],
    )
    assert evaluation["release_readiness"] == "UNSATISFIED"
    for result in evaluation["track_results"].values():
        assert result["coverage_state"] == "INCOMPLETE"
        assert result["non_designated_reviewer_keys"] == ["other-human"]
        assert result["designated_authority_threshold_satisfied"] is False


def test_synthetic_structurally_complete_six_track_set_is_readiness_satisfied_only(tmp_path: Path) -> None:
    workspace, scope = _workspace_and_scope(tmp_path)
    _populate_support(workspace, scope)
    first = _evaluate(workspace, scope)
    second = _evaluate(workspace, scope)
    assert first == second
    assert first["integrity_valid"] is True
    assert first["track_coverage_complete"] is True
    assert first["release_readiness"] == "SATISFIED"
    assert first["affected_community_gap"] is False
    assert first["unresolved_disagreement"] is False
    assert first["unresolved_evidence_requests"] is False
    assert first["release_authorization_performed"] is False
    assert first["canonical_successor_authorized"] is False
    assert first["publication_authorized"] is False
    assert first["evaluation_id"].startswith("GOVEVAL-")
    for result in first["track_results"].values():
        assert result["coverage_state"] == "COMPLETE"
        assert result["consensus_state"] == "SUPPORT"
        assert result["independence_state"] == "STRUCTURALLY_SUFFICIENT_CLAIMS"
        assert result["release_readiness"] == "SATISFIED"


def test_missing_affected_community_review_is_explicit(tmp_path: Path) -> None:
    workspace, scope = _workspace_and_scope(tmp_path)
    _populate_support(workspace, scope, omit={"AFFECTED_COMMUNITY"})
    evaluation = _evaluate(workspace, scope)
    affected = evaluation["track_results"]["AFFECTED_COMMUNITY"]
    assert affected["coverage_state"] == "INCOMPLETE"
    assert affected["consensus_state"] == "NO_REVIEW"
    assert evaluation["affected_community_gap"] is True
    assert evaluation["track_coverage_complete"] is False
    assert evaluation["release_readiness"] == "UNSATISFIED"


def test_abstention_never_counts_as_support(tmp_path: Path) -> None:
    workspace, scope = _workspace_and_scope(tmp_path)
    _populate_support(workspace, scope, omit={"ACCESSIBILITY"})
    for suffix, organization in (("a", "Synthetic Abstain A"), ("b", "Synthetic Abstain B")):
        _opinion(workspace, scope, track="ACCESSIBILITY", key=f"accessibility-{suffix}", organization=organization, state="ABSTAIN")
    evaluation = _evaluate(workspace, scope)
    track = evaluation["track_results"]["ACCESSIBILITY"]
    assert track["claimed_human_reviewer_count"] == 2
    assert track["supporting_claimed_human_reviewer_count"] == 0
    assert track["support_threshold_satisfied"] is False
    assert track["consensus_state"] == "ABSTENTION_ONLY"
    assert len(track["abstention_opinion_ids"]) == 2
    assert evaluation["release_readiness"] == "UNSATISFIED"


def test_minority_objection_remains_blocking_after_owner_disposition(tmp_path: Path) -> None:
    workspace, scope = _workspace_and_scope(tmp_path)
    opinions = _populate_support(workspace, scope)
    objection = _opinion(workspace, scope, track="SECURITY", key="security-minority-objector", organization="Synthetic Security Organization C", state="OBJECT")
    record_governance_owner_disposition(
        workspace,
        scope_id=scope["scope_id"],
        scope_sha256=scope["manifest_sha256"],
        opinion_ids=[objection["opinion_id"]],
        disposition_state="ACCEPT",
        owner_claim={"owner_key": "synthetic-owner", "name_or_role": "Synthetic local owner", "accountability_state": "CLAIMED_LOCAL_OWNER"},
        rationale="Synthetic workflow handling of a minority objection.",
    )
    evaluation = _evaluate(workspace, scope)
    security = evaluation["track_results"]["SECURITY"]
    assert len(opinions["SECURITY"]) == 2
    assert objection["opinion_id"] in security["objection_opinion_ids"]
    assert objection["opinion_id"] in security["blocking_opinion_ids"]
    assert security["missing_owner_disposition_opinion_ids"] == []
    assert security["consensus_state"] == "MIXED_WITH_BLOCKING_DISSENT"
    assert evaluation["unresolved_disagreement"] is True
    assert evaluation["release_readiness"] == "UNSATISFIED"


def test_evidence_request_is_visible_and_blocking(tmp_path: Path) -> None:
    workspace, scope = _workspace_and_scope(tmp_path)
    _populate_support(workspace, scope)
    request = _opinion(workspace, scope, track="DOMAIN", key="domain-evidence-requester", organization="Synthetic Domain Organization C", state="REQUEST_EVIDENCE")
    record_governance_owner_disposition(
        workspace,
        scope_id=scope["scope_id"],
        scope_sha256=scope["manifest_sha256"],
        opinion_ids=[request["opinion_id"]],
        disposition_state="ACCEPT",
        owner_claim={"owner_key": "synthetic-owner", "name_or_role": "Synthetic local owner", "accountability_state": "CLAIMED_LOCAL_OWNER"},
        rationale="Synthetic handling; evidence request remains visible.",
    )
    evaluation = _evaluate(workspace, scope)
    domain = evaluation["track_results"]["DOMAIN"]
    assert request["opinion_id"] in domain["evidence_request_opinion_ids"]
    assert request["opinion_id"] in domain["blocking_opinion_ids"]
    assert evaluation["unresolved_evidence_requests"] is True
    assert evaluation["release_readiness"] == "UNSATISFIED"


def test_unresolved_explicit_release_blocker_blocks_readiness(tmp_path: Path) -> None:
    workspace, scope = _workspace_and_scope(tmp_path)
    _populate_support(workspace, scope)
    conditional = _opinion(workspace, scope, track="METHODOLOGY", key="methodology-conditional", organization="Synthetic Methodology Organization C", state="SUPPORT_WITH_CONDITIONS")
    disposition = record_governance_owner_disposition(
        workspace,
        scope_id=scope["scope_id"],
        scope_sha256=scope["manifest_sha256"],
        opinion_ids=[conditional["opinion_id"]],
        disposition_state="ACCEPT_WITH_ACTION",
        owner_claim={"owner_key": "synthetic-owner", "name_or_role": "Synthetic local owner", "accountability_state": "CLAIMED_LOCAL_OWNER"},
        rationale="Synthetic conditional handling.",
        conditions=[{"description": "Synthetic blocking condition.", "owner": "synthetic-owner", "priority": "HIGH", "status": "OPEN", "release_effect": "BLOCKS_RELEASE"}],
    )["disposition"]
    evaluation = _evaluate(workspace, scope)
    methodology = evaluation["track_results"]["METHODOLOGY"]
    condition_id = disposition["condition_register"]["conditions"][0]["condition_id"]
    assert condition_id in methodology["release_blocking_condition_ids"]
    assert methodology["release_readiness"] == "UNSATISFIED"
    assert evaluation["release_readiness"] == "UNSATISFIED"


def test_declared_conflict_and_same_organization_fail_structural_independence(tmp_path: Path) -> None:
    workspace, scope = _workspace_and_scope(tmp_path)
    _populate_support(workspace, scope, omit={"DATA_GOVERNANCE"})
    _opinion(workspace, scope, track="DATA_GOVERNANCE", key="data-a", organization="Synthetic Shared Organization")
    _opinion(workspace, scope, track="DATA_GOVERNANCE", key="data-b", organization="Synthetic Shared Organization", conflict="CONFLICT_DECLARED: synthetic adversarial fixture")
    evaluation = _evaluate(workspace, scope)
    result = evaluation["track_results"]["DATA_GOVERNANCE"]
    assert result["organization_threshold_satisfied"] is False
    assert result["claimed_conflict_threshold_satisfied"] is False
    assert result["independence_state"] == "DECLARED_CONFLICT"
    assert result["declared_conflict_reviewer_keys"] == ["data-b"]
    assert evaluation["release_readiness"] == "UNSATISFIED"


def test_unclassified_conflict_disclosure_does_not_satisfy_policy(tmp_path: Path) -> None:
    workspace, scope = _workspace_and_scope(tmp_path)
    _populate_support(workspace, scope, omit={"DOMAIN"})
    _opinion(workspace, scope, track="DOMAIN", key="domain-a", organization="Synthetic Domain A")
    _opinion(workspace, scope, track="DOMAIN", key="domain-b", organization="Synthetic Domain B", conflict="Free-form disclosure without the v1 machine marker")
    evaluation = _evaluate(workspace, scope)
    domain = evaluation["track_results"]["DOMAIN"]
    assert domain["independence_state"] == "UNVERIFIED_CONFLICT_DISCLOSURE"
    assert domain["unclassified_conflict_reviewer_keys"] == ["domain-b"]
    assert domain["release_readiness"] == "UNSATISFIED"


def test_non_human_accountability_claim_does_not_satisfy_human_reviewer_threshold(tmp_path: Path) -> None:
    workspace, scope = _workspace_and_scope(tmp_path)
    _populate_support(workspace, scope, omit={"SECURITY"})
    for suffix, organization in (("a", "Synthetic Security A"), ("b", "Synthetic Security B")):
        _opinion(workspace, scope, track="SECURITY", key=f"security-{suffix}", organization=organization, accountability="SYNTHETIC_REHEARSAL_REVIEWER")
    evaluation = _evaluate(workspace, scope)
    security = evaluation["track_results"]["SECURITY"]
    assert security["active_opinion_count"] == 2
    assert security["claimed_human_reviewer_count"] == 0
    assert security["coverage_state"] == "INCOMPLETE"
    assert evaluation["release_readiness"] == "UNSATISFIED"


def test_policy_version_change_is_new_hash_and_does_not_rewrite_prior_evaluation(tmp_path: Path) -> None:
    workspace, scope = _workspace_and_scope(tmp_path)
    _populate_support(workspace, scope)
    policy_v1 = load_governance_completion_policy()
    first = _evaluate(workspace, scope, policy_v1)
    preserved = deepcopy(first)
    policy_v2 = deepcopy(policy_v1)
    policy_v2["policy_id"] = "GOVPOLICY-1.0.1"
    policy_v2["policy_version"] = "1.0.1"
    second = _evaluate(workspace, scope, policy_v2)
    assert first == preserved
    assert second["policy_sha256"] != first["policy_sha256"]
    assert second["evaluation_sha256"] != first["evaluation_sha256"]
    assert second["evaluation_id"] != first["evaluation_id"]


def test_invalid_policy_fails_closed_without_track_results(tmp_path: Path) -> None:
    workspace, scope = _workspace_and_scope(tmp_path)
    _populate_support(workspace, scope)
    policy = load_governance_completion_policy()
    del policy["tracks"]["AFFECTED_COMMUNITY"]
    evaluation = _evaluate(workspace, scope, policy)
    assert evaluation["integrity_valid"] is False
    assert evaluation["track_results"] == {}
    assert evaluation["policy_errors"]
    assert evaluation["affected_community_gap"] is True
    assert evaluation["release_readiness"] == "UNSATISFIED"


def test_wrong_scope_hash_fails_integrity_and_binds_requested_hash(tmp_path: Path) -> None:
    workspace, scope = _workspace_and_scope(tmp_path)
    _populate_support(workspace, scope)
    evaluation = evaluate_governance_completion(
        workspace,
        scope_id=scope["scope_id"],
        scope_sha256="f" * 64,
        policy=load_governance_completion_policy(version="1"),
    )
    assert evaluation["scope_binding_valid"] is False
    assert evaluation["integrity_valid"] is False
    assert evaluation["input_binding"]["scope_sha256"] == "f" * 64
    assert evaluation["release_readiness"] == "UNSATISFIED"


def test_superseded_opinion_history_remains_bound_but_only_active_state_is_evaluated(tmp_path: Path) -> None:
    workspace, scope = _workspace_and_scope(tmp_path)
    opinions = _populate_support(workspace, scope)
    prior = opinions["ACCESSIBILITY"][0]
    successor = _opinion(
        workspace,
        scope,
        track="ACCESSIBILITY",
        key=prior["reviewer_claim"]["reviewer_key"],
        organization=prior["reviewer_claim"]["organization"],
        state="ABSTAIN",
        supersedes=prior["opinion_id"],
    )
    evaluation = _evaluate(workspace, scope)
    bound_ids = {item["opinion_id"] for item in evaluation["input_binding"]["opinion_records"]}
    accessibility = evaluation["track_results"]["ACCESSIBILITY"]
    assert prior["opinion_id"] in bound_ids
    assert successor["opinion_id"] in bound_ids
    assert accessibility["active_opinion_count"] == 2
    assert successor["opinion_id"] in accessibility["abstention_opinion_ids"]
    assert accessibility["supporting_claimed_human_reviewer_count"] == 1
    assert evaluation["release_readiness"] == "UNSATISFIED"
