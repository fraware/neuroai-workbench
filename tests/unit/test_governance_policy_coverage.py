from __future__ import annotations

from collections import Counter
from copy import deepcopy

from neuroai_workbench.governance_opinions import OPINION_STATES, REVIEW_TRACKS
from neuroai_workbench.governance_policy import (
    POLICY_BOUNDARY,
    _active,
    _condition_metrics,
    _consensus_state,
    _disposition_by_opinion,
    _human_claim_metrics,
    _input_binding,
    _same_scope_records,
    _starts_with_marker,
    _state_subset,
    _string_list,
    _track_result,
    _validate_policy,
    load_governance_completion_policy,
)


def test_string_and_state_validation_helpers_cover_fail_closed_edges() -> None:
    assert _string_list(["A"]) is True
    assert _string_list(None) is False
    assert _string_list([]) is False
    assert _string_list([""]) is False
    assert _string_list([1]) is False

    assert _state_subset(["SUPPORT"], OPINION_STATES) is True
    assert _state_subset([], OPINION_STATES) is True
    assert _state_subset(None, OPINION_STATES) is False
    assert _state_subset(["UNKNOWN"], OPINION_STATES) is False


def test_policy_validation_rejects_each_normative_axis() -> None:
    base = load_governance_completion_policy()
    assert _validate_policy(base) == []

    mutations: list[tuple[str, object]] = [
        ("schema_version", "0"),
        ("policy_id", "LOCAL"),
        ("policy_version", ""),
        ("authority_profile", "AUTHORIZING"),
        ("boundary", "wrong"),
        ("human_accountability_states", []),
        ("no_conflict_markers", []),
        ("declared_conflict_markers", []),
    ]
    for field, value in mutations:
        policy = deepcopy(base)
        policy[field] = value
        assert _validate_policy(policy)

    policy = deepcopy(base)
    policy["tracks"] = []
    assert "tracks must be an object" in _validate_policy(policy)

    policy = deepcopy(base)
    del policy["tracks"]["SECURITY"]
    assert "policy tracks must exactly match the six governance review tracks" in _validate_policy(policy)

    policy = deepcopy(base)
    policy["tracks"]["SECURITY"] = "invalid"
    assert "track SECURITY: policy must be an object" in _validate_policy(policy)

    field_mutations: list[tuple[str, object, str]] = [
        ("applicable", False, "v1 policy requires explicit applicability"),
        ("minimum_reviewer_claims", True, "minimum_reviewer_claims must be a positive integer"),
        ("minimum_supporting_reviewer_claims", 0, "minimum_supporting_reviewer_claims must be a positive integer"),
        ("minimum_distinct_organizations", "2", "minimum_distinct_organizations must be a positive integer"),
        ("require_claimed_independence", False, "claimed independence must be required"),
        ("require_no_declared_conflict", False, "no-declared-conflict claim must be required"),
        ("blocking_opinion_states", ["INVALID"], "invalid blocking_opinion_states"),
        (
            "owner_disposition_required_for_states",
            ["INVALID"],
            "invalid owner_disposition_required_for_states",
        ),
        ("blocking_owner_disposition_states", ["INVALID"], "invalid blocking_owner_disposition_states"),
        ("unresolved_condition_policy", "IGNORE", "unsupported unresolved_condition_policy"),
    ]
    for field, value, message in field_mutations:
        policy = deepcopy(base)
        policy["tracks"]["SECURITY"][field] = value
        assert any(message in error for error in _validate_policy(policy))

    assert POLICY_BOUNDARY == base["boundary"]


def test_consensus_state_covers_all_semantic_classes() -> None:
    assert _consensus_state(Counter()) == "NO_REVIEW"
    assert _consensus_state(Counter({"SUPPORT": 1, "OBJECT": 1})) == "MIXED_WITH_BLOCKING_DISSENT"
    assert _consensus_state(Counter({"REQUEST_EVIDENCE": 1})) == "EVIDENCE_REQUESTED"
    assert _consensus_state(Counter({"OBJECT": 1})) == "OBJECTED"
    assert _consensus_state(Counter({"SUPPORT": 1, "ABSTAIN": 1})) == "SUPPORT_WITH_ABSTENTION"
    assert _consensus_state(Counter({"SUPPORT_WITH_CONDITIONS": 1})) == "CONDITIONAL_SUPPORT"
    assert _consensus_state(Counter({"SUPPORT": 1})) == "SUPPORT"
    assert _consensus_state(Counter({"ABSTAIN": 1})) == "ABSTENTION_ONLY"
    assert _consensus_state(Counter({"UNKNOWN": 1})) == "NO_SUPPORT"


def test_marker_and_human_claim_metrics_preserve_conflict_classes() -> None:
    assert _starts_with_marker(" no_conflict_declared ", ["NO_CONFLICT_DECLARED"]) is True
    assert _starts_with_marker("NO_CONFLICT_DECLARED: detail", ["NO_CONFLICT_DECLARED"]) is True
    assert _starts_with_marker("free form", ["NO_CONFLICT_DECLARED"]) is False

    opinions = [
        {"opinion_id": "none", "opinion_state": "SUPPORT", "reviewer_claim": None},
        {
            "opinion_id": "synthetic",
            "opinion_state": "SUPPORT",
            "reviewer_claim": {"accountability_state": "SYNTHETIC_REHEARSAL_REVIEWER"},
        },
        {
            "opinion_id": "conflict",
            "opinion_state": "SUPPORT",
            "reviewer_claim": {
                "accountability_state": "CLAIMED_HUMAN_REVIEWER",
                "organization": "Org A",
                "independence_statement": "claimed",
                "conflict_of_interest_disclosure": "CONFLICT_DECLARED: fixture",
                "reviewer_key": "a",
            },
        },
        {
            "opinion_id": "clean",
            "opinion_state": "SUPPORT_WITH_CONDITIONS",
            "reviewer_claim": {
                "accountability_state": "CLAIMED_HUMAN_REVIEWER",
                "organization": "Org B",
                "independence_statement": "claimed",
                "conflict_of_interest_disclosure": "NO_CONFLICT_DECLARED",
                "reviewer_key": "b",
            },
        },
        {
            "opinion_id": "unclassified",
            "opinion_state": "ABSTAIN",
            "reviewer_claim": {
                "accountability_state": "CLAIMED_HUMAN_REVIEWER",
                "organization": "",
                "independence_statement": "",
                "conflict_of_interest_disclosure": "free form",
                "reviewer_key": "c",
            },
        },
    ]
    metrics = _human_claim_metrics(
        opinions,
        human_states={"CLAIMED_HUMAN_REVIEWER"},
        no_conflict_markers=["NO_CONFLICT_DECLARED"],
        declared_conflict_markers=["CONFLICT_DECLARED"],
    )

    assert len(metrics["human"]) == 3
    assert len(metrics["supporting"]) == 2
    assert metrics["organizations"] == {"Org A", "Org B"}
    assert metrics["independent"] == 2
    assert metrics["no_conflict"] == 1
    assert metrics["conflicts"] == ["a"]
    assert metrics["unclassified"] == ["c"]


def test_active_disposition_and_condition_helpers_cover_defensive_shapes() -> None:
    records = [
        {"id": "old", "supersedes": None},
        {"id": "new", "supersedes": "old"},
    ]
    assert _active(records, id_field="id", supersedes_field="supersedes") == [records[1]]

    disposition = {
        "disposition_id": "disp-good",
        "addressed_opinions": [None, {}, {"opinion_id": "op-1"}],
    }
    mapping = _disposition_by_opinion([disposition])
    assert mapping == {"op-1": disposition}

    opinions = [
        {"opinion_id": "missing"},
        {"opinion_id": "bad-register"},
        {"opinion_id": "conditions"},
    ]
    disposition_map = {
        "bad-register": {
            "disposition_id": "disp-blocking",
            "disposition_state": "DEFER",
            "condition_register": "invalid",
        },
        "conditions": {
            "disposition_id": "disp-conditions",
            "disposition_state": "ACCEPT_WITH_ACTION",
            "condition_register": {
                "conditions": [
                    "invalid",
                    {"condition_id": "resolved", "status": "RESOLVED", "release_effect": "BLOCKS_RELEASE"},
                    {"condition_id": "open", "status": "OPEN", "release_effect": "ADVISORY"},
                ]
            },
        },
    }
    blocking, unresolved = _condition_metrics(opinions, disposition_map, {"DEFER"})
    assert blocking == ["disp-blocking"]
    assert unresolved == [{"condition_id": "open", "status": "OPEN", "release_effect": "ADVISORY"}]


def test_scope_and_input_binding_cover_condition_register_fallback() -> None:
    records = [
        {"scope_id": "scope", "scope_sha256": "a" * 64, "id": 1},
        {"scope_id": "other", "scope_sha256": "a" * 64, "id": 2},
    ]
    assert _same_scope_records(records, scope_id="scope", scope_sha256="a" * 64) == [records[0]]

    policy = load_governance_completion_policy()
    binding = _input_binding(
        scope_id="scope",
        scope_sha256="a" * 64,
        policy=policy,
        policy_sha256="b" * 64,
        opinions=[
            {"opinion_id": "z", "opinion_sha256": "2" * 64},
            {"opinion_id": "a", "opinion_sha256": "1" * 64},
        ],
        dispositions=[
            {
                "disposition_id": "z",
                "disposition_sha256": "4" * 64,
                "condition_register": "invalid",
            },
            {
                "disposition_id": "a",
                "disposition_sha256": "3" * 64,
                "condition_register": {"register_sha256": "5" * 64},
            },
        ],
    )
    assert [item["opinion_id"] for item in binding["opinion_records"]] == ["a", "z"]
    assert [item["disposition_id"] for item in binding["owner_disposition_records"]] == ["a", "z"]
    assert binding["owner_disposition_records"][1]["condition_register_sha256"] == ""


def test_track_result_blocks_missing_or_blocking_owner_and_ignores_advisory_open_condition() -> None:
    policy = deepcopy(load_governance_completion_policy()["tracks"]["SECURITY"])
    opinions = [
        {
            "opinion_id": "support-a",
            "opinion_state": "SUPPORT",
            "reviewer_claim": {
                "accountability_state": "CLAIMED_HUMAN_REVIEWER",
                "organization": "Org A",
                "independence_statement": "claimed",
                "conflict_of_interest_disclosure": "NO_CONFLICT_DECLARED",
                "reviewer_key": "a",
            },
        },
        {
            "opinion_id": "support-b",
            "opinion_state": "SUPPORT",
            "reviewer_claim": {
                "accountability_state": "CLAIMED_HUMAN_REVIEWER",
                "organization": "Org B",
                "independence_statement": "claimed",
                "conflict_of_interest_disclosure": "NO_CONFLICT_DECLARED",
                "reviewer_key": "b",
            },
        },
        {
            "opinion_id": "conditional",
            "opinion_state": "SUPPORT_WITH_CONDITIONS",
            "reviewer_claim": {
                "accountability_state": "CLAIMED_HUMAN_REVIEWER",
                "organization": "Org C",
                "independence_statement": "claimed",
                "conflict_of_interest_disclosure": "NO_CONFLICT_DECLARED",
                "reviewer_key": "c",
            },
        },
    ]
    missing = _track_result(
        "SECURITY",
        policy,
        opinions,
        {},
        human_states={"CLAIMED_HUMAN_REVIEWER"},
        no_conflict_markers=["NO_CONFLICT_DECLARED"],
        declared_conflict_markers=["CONFLICT_DECLARED"],
    )
    assert missing["missing_owner_disposition_opinion_ids"] == ["conditional"]
    assert missing["release_readiness"] == "UNSATISFIED"

    blocking_map = {
        "conditional": {
            "disposition_id": "disp",
            "disposition_state": "DEFER",
            "addressed_opinions": [{"opinion_id": "conditional"}],
            "condition_register": {
                "conditions": [
                    {
                        "condition_id": "advisory-open",
                        "status": "OPEN",
                        "release_effect": "ADVISORY",
                    }
                ]
            },
        }
    }
    blocked = _track_result(
        "SECURITY",
        policy,
        opinions,
        blocking_map,
        human_states={"CLAIMED_HUMAN_REVIEWER"},
        no_conflict_markers=["NO_CONFLICT_DECLARED"],
        declared_conflict_markers=["CONFLICT_DECLARED"],
    )
    assert blocked["blocking_owner_disposition_ids"] == ["disp"]
    assert blocked["unresolved_condition_ids"] == ["advisory-open"]
    assert blocked["release_blocking_condition_ids"] == []
    assert blocked["release_readiness"] == "UNSATISFIED"

    accepted_map = deepcopy(blocking_map)
    accepted_map["conditional"]["disposition_state"] = "ACCEPT_WITH_ACTION"
    accepted = _track_result(
        "SECURITY",
        policy,
        opinions,
        accepted_map,
        human_states={"CLAIMED_HUMAN_REVIEWER"},
        no_conflict_markers=["NO_CONFLICT_DECLARED"],
        declared_conflict_markers=["CONFLICT_DECLARED"],
    )
    assert accepted["release_blocking_condition_ids"] == []
    assert accepted["release_readiness"] == "SATISFIED"


def test_track_result_reports_insufficient_independence_claims() -> None:
    policy = deepcopy(load_governance_completion_policy()["tracks"]["DOMAIN"])
    opinions = [
        {
            "opinion_id": "a",
            "opinion_state": "SUPPORT",
            "reviewer_claim": {
                "accountability_state": "CLAIMED_HUMAN_REVIEWER",
                "organization": "Org A",
                "independence_statement": "",
                "conflict_of_interest_disclosure": "NO_CONFLICT_DECLARED",
                "reviewer_key": "a",
            },
        },
        {
            "opinion_id": "b",
            "opinion_state": "SUPPORT",
            "reviewer_claim": {
                "accountability_state": "CLAIMED_HUMAN_REVIEWER",
                "organization": "Org B",
                "independence_statement": "claimed",
                "conflict_of_interest_disclosure": "NO_CONFLICT_DECLARED",
                "reviewer_key": "b",
            },
        },
    ]
    result = _track_result(
        "DOMAIN",
        policy,
        opinions,
        {},
        human_states={"CLAIMED_HUMAN_REVIEWER"},
        no_conflict_markers=["NO_CONFLICT_DECLARED"],
        declared_conflict_markers=["CONFLICT_DECLARED"],
    )
    assert result["coverage_state"] == "COMPLETE"
    assert result["claimed_independence_threshold_satisfied"] is False
    assert result["independence_state"] == "INSUFFICIENT_CLAIMS"
    assert result["release_readiness"] == "UNSATISFIED"


def test_policy_track_universe_remains_exactly_six() -> None:
    assert len(REVIEW_TRACKS) == 6
