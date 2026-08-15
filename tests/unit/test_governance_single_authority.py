from __future__ import annotations

from copy import deepcopy

from neuroai_workbench.governance_policy import (
    SINGLE_AUTHORITY_MODEL,
    _track_result,
    _validate_policy,
    governance_policy_sha256,
    load_governance_completion_policy,
)


def _reviewer(key: str, state: str = "SUPPORT") -> dict[str, object]:
    return {
        "opinion_id": f"opinion-{key}",
        "opinion_state": state,
        "reviewer_claim": {
            "reviewer_key": key,
            "accountability_state": "CLAIMED_HUMAN_REVIEWER",
            "organization": "Repository governance",
            "independence_statement": "Role consolidation is explicit under governance policy v2.",
            "conflict_of_interest_disclosure": "CONFLICT_DECLARED: explicit role consolidation under policy v2",
        },
    }


def _result(
    opinions: list[dict[str, object]],
    dispositions: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    current = load_governance_completion_policy(version="current")
    return _track_result(
        "SECURITY",
        current["tracks"]["SECURITY"],
        opinions,
        dispositions or {},
        human_states=set(current["human_accountability_states"]),
        no_conflict_markers=list(current["no_conflict_markers"]),
        declared_conflict_markers=list(current["declared_conflict_markers"]),
        authority_model=str(current["authority_model"]),
        designated_authority_key=str(current["designated_authority_key"]),
    )


def test_v2_is_hash_distinct_single_designated_authority_policy() -> None:
    legacy = load_governance_completion_policy(version="1")
    current = load_governance_completion_policy(version="current")

    assert _validate_policy(legacy) == []
    assert _validate_policy(current) == []
    assert current["schema_version"] == "2"
    assert current["policy_id"] == "GOVPOLICY-2.0.0"
    assert current["authority_model"] == SINGLE_AUTHORITY_MODEL
    assert current["designated_authority_key"] == "fraware"
    assert current["allow_role_consolidation"] is True
    assert governance_policy_sha256(current) != governance_policy_sha256(legacy)
    assert governance_policy_sha256(current) == governance_policy_sha256(deepcopy(current))


def test_one_designated_human_satisfies_track_and_other_human_does_not() -> None:
    designated = _result([_reviewer("fraware")])
    assert designated["claimed_human_reviewer_count"] == 1
    assert designated["supporting_claimed_human_reviewer_count"] == 1
    assert designated["authority_state"] == "DESIGNATED_AUTHORITY_SATISFIED"
    assert designated["independence_state"] == "ROLE_CONSOLIDATION_ALLOWED"
    assert designated["designated_authority_threshold_satisfied"] is True
    assert designated["release_readiness"] == "SATISFIED"

    other = _result([_reviewer("other-human")])
    assert other["coverage_state"] == "INCOMPLETE"
    assert other["non_designated_reviewer_keys"] == ["other-human"]
    assert other["designated_authority_threshold_satisfied"] is False
    assert other["release_readiness"] == "UNSATISFIED"


def test_owner_disposition_must_use_same_designated_human() -> None:
    opinion = _reviewer("fraware", state="SUPPORT_WITH_CONDITIONS")
    opinion_id = str(opinion["opinion_id"])
    wrong_owner = {
        opinion_id: {
            "disposition_id": "disp-wrong-owner",
            "disposition_state": "ACCEPT",
            "owner_claim": {"owner_key": "other-human"},
            "condition_register": {"conditions": []},
        }
    }
    blocked = _result([opinion], wrong_owner)
    assert blocked["non_designated_owner_disposition_ids"] == ["disp-wrong-owner"]
    assert blocked["owner_authority_threshold_satisfied"] is False
    assert blocked["release_readiness"] == "UNSATISFIED"

    correct_owner = deepcopy(wrong_owner)
    correct_owner[opinion_id]["disposition_id"] = "disp-designated-owner"
    correct_owner[opinion_id]["owner_claim"] = {"owner_key": "fraware"}
    allowed = _result([opinion], correct_owner)
    assert allowed["non_designated_owner_disposition_ids"] == []
    assert allowed["owner_authority_threshold_satisfied"] is True
    assert allowed["release_readiness"] == "SATISFIED"


def test_non_designated_objection_is_visible_without_acquiring_veto_power() -> None:
    designated = _reviewer("fraware")
    other = _reviewer("other-human", state="OBJECT")
    result = _result([designated, other])

    assert result["consensus_state"] == "MIXED_WITH_BLOCKING_DISSENT"
    assert result["decision_consensus_state"] == "SUPPORT"
    assert result["objection_opinion_ids"] == ["opinion-other-human"]
    assert result["blocking_opinion_ids"] == []
    assert result["non_designated_blocking_opinion_ids"] == ["opinion-other-human"]
    assert result["release_readiness"] == "SATISFIED"
