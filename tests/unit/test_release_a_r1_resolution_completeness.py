from __future__ import annotations

import copy

import pytest

import neuroai_workbench.release_a_r1_resolution_completeness as rc


def _reseal(value: dict[str, object], field: str) -> None:
    value[field] = rc.artifact_sha256(value, digest_field=field)


def test_default_resolution_completeness_checkpoint_reconstructs_fail_closed() -> None:
    checkpoint = rc.load_resolution_completeness_checkpoint()

    assert checkpoint["status"] == "CHECKPOINT_PENDING_KNOWLEDGE_WINDOW_CLOSE"
    assert checkpoint["temporal_finality"] == "CHECKPOINT_PENDING_KNOWLEDGE_WINDOW_CLOSE"
    assert checkpoint["aggregate_scientific_disposition"] == (
        "ALL_HISTORICAL_MARGINAL_YIELD_SATURATION_INTERPRETATIONS_RESOLUTION_CENSORED"
    )
    assert [result["frame_id"] for result in checkpoint["frame_results"]] == [
        "F1",
        "F4",
        "F5",
        "F6",
        "F8",
        "F11",
    ]

    for frame in checkpoint["frame_results"]:
        assert frame["historical_final_stop_state"] == "SATURATION_UNDER_DECLARED_PROTOCOL"
        assert frame["qualifying_tail_round_ids"] == ["R2", "R3"]
        assert frame["scientific_interpretation_state"] == "CONTINUE_RESOLUTION_CENSORED"
        tail = {
            result["round_id"]: result
            for result in frame["round_results"]
            if result["identifiability_required_for_terminal_decision"]
        }
        assert set(tail) == {"R2", "R3"}
        assert all(result["identifiability_state"] == "RESOLUTION_SOURCE_BARRIER_CENSORED" for result in tail.values())
        assert all(result["finite_upper_bound_available"] is False for result in tail.values())
        assert all(result["m_r_upper"] is None for result in tail.values())


def test_a3_a4_checkpoint_is_interval_censored_not_point_zero_claim() -> None:
    checkpoint = rc.load_resolution_completeness_checkpoint()

    a3 = checkpoint["a3_capability_increment_checkpoint"]
    assert a3["historical_delta_n_capability"] == 0
    assert a3["resolved_incremental_offering_count"] == 0
    assert a3["unresolved_expanded_arm_clusters_capable_of_changing_increment"] == 52
    assert a3["cardinality_unproven_cluster_count"] == 13
    assert a3["unbounded_source_or_abstention_barrier_cluster_count"] == 39
    assert a3["increment_lower_bound"] == 0
    assert a3["increment_upper_bound"] is None
    assert a3["successor_interpretation_state"] == "INCREMENT_RESOLUTION_CENSORED"

    a4 = checkpoint["a4_multilingual_increment_checkpoint"]
    assert a4["historical_delta_n_multilingual"] == 0
    assert a4["resolved_incremental_offering_count"] == 0
    assert a4["unresolved_expanded_arm_clusters_capable_of_changing_increment"] == 63
    assert a4["cardinality_unproven_cluster_count"] == 12
    assert a4["unbounded_source_or_abstention_barrier_cluster_count"] == 51
    assert a4["increment_lower_bound"] == 0
    assert a4["increment_upper_bound"] is None
    assert a4["successor_interpretation_state"] == "INCREMENT_RESOLUTION_CENSORED"


def test_round_identifiability_exhaustive_resolution_passes() -> None:
    result = rc.evaluate_round_identifiability(
        C_r=20,
        Y_r=0,
        one_object_upper_bound_cluster_count=0,
        cardinality_unproven_cluster_count=0,
        unbounded_source_or_abstention_barrier_cluster_count=0,
        threshold=0.05,
    )

    assert result["m_r_lower"] == 0
    assert result["m_r_upper"] == 0
    assert result["finite_upper_bound_available"] is True
    assert result["identifiability_state"] == "IDENTIFIABLE_LOW_YIELD"
    assert result["identifiability_path"] == "EXHAUSTIVE_RESOLUTION"


def test_round_identifiability_worst_case_bound_passes_only_below_threshold() -> None:
    passing = rc.evaluate_round_identifiability(
        C_r=100,
        Y_r=0,
        one_object_upper_bound_cluster_count=4,
        cardinality_unproven_cluster_count=0,
        unbounded_source_or_abstention_barrier_cluster_count=0,
        threshold=0.05,
    )
    assert passing["m_r_upper"] == 0.04
    assert passing["identifiability_state"] == "IDENTIFIABLE_LOW_YIELD"
    assert passing["identifiability_path"] == "WORST_CASE_BOUND"

    failing = rc.evaluate_round_identifiability(
        C_r=20,
        Y_r=0,
        one_object_upper_bound_cluster_count=2,
        cardinality_unproven_cluster_count=0,
        unbounded_source_or_abstention_barrier_cluster_count=0,
        threshold=0.05,
    )
    assert failing["m_r_upper"] == 0.1
    assert failing["identifiability_state"] == "RESOLUTION_SOURCE_BARRIER_CENSORED"
    assert failing["identifiability_path"] is None


def test_large_unresolved_backlog_cannot_manufacture_zero_yield_saturation() -> None:
    result = rc.evaluate_round_identifiability(
        C_r=100,
        Y_r=0,
        one_object_upper_bound_cluster_count=0,
        cardinality_unproven_cluster_count=40,
        unbounded_source_or_abstention_barrier_cluster_count=0,
        threshold=0.05,
    )

    assert result["m_r_lower"] == 0
    assert result["m_r_upper"] is None
    assert result["finite_upper_bound_available"] is False
    assert result["identifiability_state"] == "RESOLUTION_SOURCE_BARRIER_CENSORED"


def test_inaccessible_or_abstained_source_barrier_blocks_finite_upper_bound() -> None:
    result = rc.evaluate_round_identifiability(
        C_r=100,
        Y_r=0,
        one_object_upper_bound_cluster_count=0,
        cardinality_unproven_cluster_count=0,
        unbounded_source_or_abstention_barrier_cluster_count=1,
        threshold=0.05,
    )

    assert result["U_r_star"] == 0
    assert result["m_r_upper"] is None
    assert result["finite_upper_bound_available"] is False
    assert result["identifiability_state"] == "RESOLUTION_SOURCE_BARRIER_CENSORED"


def test_reviewed_statistical_path_requires_prior_registration() -> None:
    censored = rc.evaluate_round_identifiability(
        C_r=100,
        Y_r=0,
        one_object_upper_bound_cluster_count=0,
        cardinality_unproven_cluster_count=10,
        unbounded_source_or_abstention_barrier_cluster_count=3,
        threshold=0.05,
        statistical_design_preregistered=False,
        statistical_upper_bound=0.04,
    )
    assert censored["identifiability_state"] == "RESOLUTION_SOURCE_BARRIER_CENSORED"

    reviewed = rc.evaluate_round_identifiability(
        C_r=100,
        Y_r=0,
        one_object_upper_bound_cluster_count=0,
        cardinality_unproven_cluster_count=10,
        unbounded_source_or_abstention_barrier_cluster_count=3,
        threshold=0.05,
        statistical_design_preregistered=True,
        statistical_upper_bound=0.04,
    )
    assert reviewed["identifiability_state"] == "IDENTIFIABLE_LOW_YIELD"
    assert reviewed["identifiability_path"] == "REVIEWED_STATISTICAL"


def test_round_above_threshold_is_not_low_yield() -> None:
    result = rc.evaluate_round_identifiability(
        C_r=20,
        Y_r=2,
        one_object_upper_bound_cluster_count=0,
        cardinality_unproven_cluster_count=0,
        unbounded_source_or_abstention_barrier_cluster_count=0,
        threshold=0.05,
    )
    assert result["m_r_lower"] == 0.1
    assert result["identifiability_state"] == "NOT_LOW_YIELD"
    assert result["identifiability_path"] is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"C_r": 0},
        {"Y_r": -1},
        {"one_object_upper_bound_cluster_count": -1},
        {"cardinality_unproven_cluster_count": -1},
        {"unbounded_source_or_abstention_barrier_cluster_count": -1},
    ],
)
def test_round_identifiability_rejects_invalid_counts(kwargs: dict[str, int]) -> None:
    values = {
        "C_r": 20,
        "Y_r": 0,
        "one_object_upper_bound_cluster_count": 0,
        "cardinality_unproven_cluster_count": 0,
        "unbounded_source_or_abstention_barrier_cluster_count": 0,
        "threshold": 0.05,
    }
    values.update(kwargs)
    with pytest.raises(rc.ProductDiscoveryError, match="counts"):
        rc.evaluate_round_identifiability(**values)


def test_round_identifiability_rejects_invalid_thresholds_and_statistical_bound() -> None:
    with pytest.raises(rc.ProductDiscoveryError, match="threshold"):
        rc.evaluate_round_identifiability(
            C_r=20,
            Y_r=0,
            one_object_upper_bound_cluster_count=0,
            cardinality_unproven_cluster_count=0,
            unbounded_source_or_abstention_barrier_cluster_count=0,
            threshold=1.1,
        )

    with pytest.raises(rc.ProductDiscoveryError, match="statistical upper bound"):
        rc.evaluate_round_identifiability(
            C_r=20,
            Y_r=0,
            one_object_upper_bound_cluster_count=0,
            cardinality_unproven_cluster_count=1,
            unbounded_source_or_abstention_barrier_cluster_count=0,
            threshold=0.05,
            statistical_design_preregistered=True,
            statistical_upper_bound=-0.1,
        )


def test_round_cluster_accounting_deduplicates_cross_record_cluster_and_preserves_exclusion() -> None:
    records = [
        {"candidate_cluster_id": "C-1", "frame_id": "F1", "round_id": "R2"},
        {"candidate_cluster_id": "C-1", "frame_id": "F1", "round_id": "R2"},
        {"candidate_cluster_id": "C-2", "frame_id": "F1", "round_id": "R2"},
    ]
    lookup = {
        "C-1": {"uncertainty_cardinality_class": rc.CARDINALITY_UNPROVEN},
        "C-2": {"uncertainty_cardinality_class": rc.TERMINAL},
    }

    counts = rc._round_cluster_counts(
        records=records,
        cluster_lookup=lookup,
        frame_id="F1",
        round_id="R2",
    )

    assert counts[rc.CARDINALITY_UNPROVEN] == 1
    assert counts[rc.TERMINAL] == 1
    assert sum(counts.values()) == 2


def test_tail_round_selector_requires_frozen_mechanical_conditions() -> None:
    summaries = [
        {"round_id": "R1", "raw_candidates": 25, "marginal_new_identity_yield": 0.2},
        {"round_id": "R2", "raw_candidates": 25, "marginal_new_identity_yield": 0.0},
        {"round_id": "R3", "raw_candidates": 25, "marginal_new_identity_yield": 0.0},
    ]
    assert rc._tail_round_ids(
        round_summaries=summaries,
        minimum_completed_rounds=3,
        consecutive_low_yield_rounds=2,
        threshold=0.05,
        minimum_raw_candidates_per_round=20,
    ) == ["R2", "R3"]

    assert rc._tail_round_ids(
        round_summaries=summaries[:2],
        minimum_completed_rounds=3,
        consecutive_low_yield_rounds=2,
        threshold=0.05,
        minimum_raw_candidates_per_round=20,
    ) == []

    too_small = copy.deepcopy(summaries)
    too_small[-1]["raw_candidates"] = 19
    assert rc._tail_round_ids(
        round_summaries=too_small,
        minimum_completed_rounds=3,
        consecutive_low_yield_rounds=2,
        threshold=0.05,
        minimum_raw_candidates_per_round=20,
    ) == []

    high_yield = copy.deepcopy(summaries)
    high_yield[-1]["marginal_new_identity_yield"] = 0.06
    assert rc._tail_round_ids(
        round_summaries=high_yield,
        minimum_completed_rounds=3,
        consecutive_low_yield_rounds=2,
        threshold=0.05,
        minimum_raw_candidates_per_round=20,
    ) == []


def test_rule_validation_rejects_integrity_and_contract_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rule = rc.load_resolution_completeness_rule()

    broken_digest = copy.deepcopy(rule)
    broken_digest["status"] = "CHANGED"
    with pytest.raises(rc.ProductDiscoveryError, match="digest mismatch"):
        rc.validate_resolution_completeness_rule(broken_digest)

    wrong_status = copy.deepcopy(rule)
    wrong_status["status"] = "DRAFT"
    _reseal(wrong_status, "rule_sha256")
    monkeypatch.setattr(rc, "RULE_SHA256", wrong_status["rule_sha256"])
    with pytest.raises(rc.ProductDiscoveryError, match="must be FROZEN"):
        rc.validate_resolution_completeness_rule(wrong_status)
    monkeypatch.setattr(rc, "RULE_SHA256", rule["rule_sha256"])

    wrong_statistical = copy.deepcopy(rule)
    wrong_statistical["low_yield_identifiability_paths"]["reviewed_statistical"]["current_checkpoint_state"] = (
        "POST_HOC_ENABLED"
    )
    _reseal(wrong_statistical, "rule_sha256")
    monkeypatch.setattr(rc, "RULE_SHA256", wrong_statistical["rule_sha256"])
    with pytest.raises(rc.ProductDiscoveryError, match="post-hoc statistical"):
        rc.validate_resolution_completeness_rule(wrong_statistical)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("analysis_universe_id", "RAU-WRONG", "analysis universe drift"),
        ("population_view_id", "A-P6", "population view drift"),
        ("candidate_resolution_ledger_manifest_sha256", "0" * 64, "ledger manifest binding drift"),
        ("candidate_resolution_cluster_ledger_sha256", "0" * 64, "cluster ledger binding drift"),
        ("marginal_yield_frames", ["F1"], "marginal frame set drift"),
        (
            "mechanical_rule",
            {
                "minimum_completed_rounds": 3,
                "consecutive_low_yield_rounds": 2,
                "maximum_marginal_new_identity_yield": 0.10,
                "minimum_raw_candidates_per_round": 20,
            },
            "mechanical rule drift",
        ),
    ],
)
def test_rule_validation_rejects_semantic_drift(
    field: str,
    value: object,
    message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rule = rc.load_resolution_completeness_rule()
    changed = copy.deepcopy(rule)
    changed[field] = value
    _reseal(changed, "rule_sha256")
    monkeypatch.setattr(rc, "RULE_SHA256", changed["rule_sha256"])

    with pytest.raises(rc.ProductDiscoveryError, match=message):
        rc.validate_resolution_completeness_rule(changed)


def test_checkpoint_validation_rejects_digest_and_reconstruction_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkpoint = rc.load_resolution_completeness_checkpoint()

    broken = copy.deepcopy(checkpoint)
    broken["temporal_finality"] = "FINAL"
    with pytest.raises(rc.ProductDiscoveryError, match="digest mismatch"):
        rc.validate_resolution_completeness_checkpoint(broken)

    changed = copy.deepcopy(checkpoint)
    changed["temporal_finality"] = "FINAL"
    _reseal(changed, "packet_sha256")
    monkeypatch.setattr(rc, "CHECKPOINT_SHA256", changed["packet_sha256"])
    with pytest.raises(rc.ProductDiscoveryError, match="does not reproduce"):
        rc.validate_resolution_completeness_checkpoint(changed)
