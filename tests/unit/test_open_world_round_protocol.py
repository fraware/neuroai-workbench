from __future__ import annotations

from copy import deepcopy

import pytest

from neuroai_workbench.open_world_round_protocol import (
    CHECKPOINT_SHA256,
    DIAGNOSTIC_OPEN_WORLD_FRAME_IDS,
    OPEN_WORLD_BOUNDARY,
    OPEN_WORLD_FRAME_IDS,
    PRIMARY_OPEN_WORLD_FRAME_IDS,
    PROTOCOL_ID,
    PROTOCOL_SHA256,
    UNIVERSE_IDS,
    UNIVERSE_SHA256,
    freeze_does_not_imply_saturation,
    load_all_default_open_world_query_universes,
    load_default_open_world_query_universe,
    load_default_open_world_round_protocol,
    open_world_content_digest,
    open_world_frame_stop_state,
    query_seed_set_digest,
    validate_open_world_query_universe,
    validate_open_world_round_protocol,
)
from neuroai_workbench.product_discovery_frames import (
    ProductDiscoveryError,
    load_default_analysis_universe,
    load_default_frame_register,
)


def test_open_world_protocol_and_universes_are_content_bound() -> None:
    protocol = load_default_open_world_round_protocol()
    universes = load_all_default_open_world_query_universes()
    analysis = load_default_analysis_universe()
    frames = {frame["frame_id"]: frame for frame in load_default_frame_register()["frames"]}

    assert protocol["protocol_id"] == PROTOCOL_ID
    assert protocol["protocol_sha256"] == PROTOCOL_SHA256
    assert open_world_content_digest(protocol, exclude="protocol_sha256") == PROTOCOL_SHA256
    assert tuple(protocol["frame_ids"]) == OPEN_WORLD_FRAME_IDS
    assert protocol["analysis_universe_id"] == analysis["analysis_universe_id"]
    assert protocol["a2_checkpoint_sha256"] == CHECKPOINT_SHA256
    assert protocol["boundary"] == OPEN_WORLD_BOUNDARY
    assert tuple(protocol["estimator_policy"]["primary_estimation_eligible_frames"]) == PRIMARY_OPEN_WORLD_FRAME_IDS
    assert tuple(protocol["estimator_policy"]["diagnostic_only_frames"]) == DIAGNOSTIC_OPEN_WORLD_FRAME_IDS

    for frame_id in OPEN_WORLD_FRAME_IDS:
        universe = universes[frame_id]
        assert universe["universe_id"] == UNIVERSE_IDS[frame_id]
        assert universe["universe_sha256"] == UNIVERSE_SHA256[frame_id]
        assert open_world_content_digest(universe, exclude="universe_sha256") == UNIVERSE_SHA256[frame_id]
        assert universe["open_world_round_protocol_sha256"] == PROTOCOL_SHA256
        assert universe["query_families"] == frames[frame_id]["query_families"]
        assert set(universe["source_classes"]) == set(frames[frame_id]["source_classes"])
        assert universe["capture_estimation_eligible"] is frames[frame_id]["capture_estimation_eligible"]
        assert universe["query_seed_set_sha256"] == query_seed_set_digest(
            seed["query_or_seed_id"] for seed in universe["query_seeds"]
        )
        for round_id in ("R1", "R2", "R3"):
            assert universe["per_round_seed_counts"][round_id] >= 20


def test_freeze_alone_remains_continue_and_does_not_claim_saturation() -> None:
    for frame_id in OPEN_WORLD_FRAME_IDS:
        assert freeze_does_not_imply_saturation(frame_id) == "CONTINUE"
        assert open_world_frame_stop_state(frame_id, []) == "CONTINUE"
        # One low-yield round is not enough.
        one_round = [{"raw_candidates": 30, "marginal_new_identity_yield": 0.0}]
        assert open_world_frame_stop_state(frame_id, one_round) == "CONTINUE"
        # Two low-yield rounds without a third completed round is not enough.
        two_rounds = [
            {"raw_candidates": 30, "marginal_new_identity_yield": 0.0},
            {"raw_candidates": 30, "marginal_new_identity_yield": 0.0},
        ]
        assert open_world_frame_stop_state(frame_id, two_rounds) == "CONTINUE"


def test_literal_stop_requires_three_rounds_and_qualifying_tail() -> None:
    saturated = [
        {"raw_candidates": 30, "marginal_new_identity_yield": 0.20},
        {"raw_candidates": 30, "marginal_new_identity_yield": 0.04},
        {"raw_candidates": 30, "marginal_new_identity_yield": 0.03},
    ]
    assert open_world_frame_stop_state("F1", saturated) == "SATURATION_UNDER_DECLARED_PROTOCOL"

    high_tail = saturated[:-1] + [{"raw_candidates": 30, "marginal_new_identity_yield": 0.10}]
    assert open_world_frame_stop_state("F1", high_tail) == "CONTINUE"

    broken_tail = [
        {"raw_candidates": 30, "marginal_new_identity_yield": 0.20},
        {"raw_candidates": 5, "marginal_new_identity_yield": 0.01},
        {"raw_candidates": 30, "marginal_new_identity_yield": 0.01},
    ]
    assert open_world_frame_stop_state("F4", broken_tail) == "CONTINUE"


def test_f11_remains_estimator_excluded_in_frozen_universe() -> None:
    f11 = load_default_open_world_query_universe("F11")
    assert f11["capture_estimation_eligible"] is False
    assert f11["frame_class"] == "SNOWBALL_EXPANSION"
    assert all(seed["source_class"] == "SNOWBALL_EDGE_ATTRIBUTABLE" for seed in f11["query_seeds"])


def test_protocol_fails_closed_on_universe_or_estimator_drift() -> None:
    protocol = load_default_open_world_round_protocol()

    bad_universe = deepcopy(protocol)
    bad_universe["analysis_universe_id"] = "RAU-" + ("0" * 64)
    bad_universe["protocol_sha256"] = open_world_content_digest(bad_universe, exclude="protocol_sha256")
    with pytest.raises(ProductDiscoveryError, match="frozen A2 analysis universe"):
        validate_open_world_round_protocol(bad_universe)

    bad_estimator = deepcopy(protocol)
    bad_estimator["estimator_policy"]["diagnostic_only_frames"] = ["F7", "F11"]
    bad_estimator["protocol_sha256"] = open_world_content_digest(bad_estimator, exclude="protocol_sha256")
    with pytest.raises(ProductDiscoveryError, match="diagnostic_only_frames must be exactly F11"):
        validate_open_world_round_protocol(bad_estimator)

    f1 = load_default_open_world_query_universe("F1")
    pooled = deepcopy(f1)
    pooled["independence_rule"]["does_not_credit_f9_actor_enumeration_or_f2_f3_exhaustion"] = False
    pooled["universe_sha256"] = open_world_content_digest(pooled, exclude="universe_sha256")
    with pytest.raises(ProductDiscoveryError, match="must not credit F9/F2/F3"):
        validate_open_world_query_universe(pooled, frame_id="F1")


def test_query_universe_fails_closed_on_family_or_seed_floor_drift() -> None:
    f1 = load_default_open_world_query_universe("F1")
    bad_family = deepcopy(f1)
    bad_family["query_seeds"][0]["query_family"] = "DEVICE_REGISTRY_ENUMERATION"
    bad_family["universe_sha256"] = open_world_content_digest(bad_family, exclude="universe_sha256")
    with pytest.raises(ProductDiscoveryError, match="outside declared families"):
        validate_open_world_query_universe(bad_family, frame_id="F1")

    thin = deepcopy(f1)
    thin["query_seeds"] = [seed for seed in thin["query_seeds"] if seed["round_id"] != "R1"][:19] + [
        seed for seed in thin["query_seeds"] if seed["round_id"] != "R1"
    ]
    # Rebuild with only 19 R1 seeds.
    r1_seeds = [seed for seed in f1["query_seeds"] if seed["round_id"] == "R1"][:19]
    other = [seed for seed in f1["query_seeds"] if seed["round_id"] != "R1"]
    thin["query_seeds"] = r1_seeds + other
    thin["query_seed_count"] = len(thin["query_seeds"])
    thin["round_seed_ids"] = {
        "R1": [seed["query_or_seed_id"] for seed in r1_seeds],
        "R2": f1["round_seed_ids"]["R2"],
        "R3": f1["round_seed_ids"]["R3"],
    }
    thin["per_round_seed_counts"] = {
        "R1": 19,
        "R2": f1["per_round_seed_counts"]["R2"],
        "R3": f1["per_round_seed_counts"]["R3"],
    }
    thin["query_seed_set_sha256"] = query_seed_set_digest(seed["query_or_seed_id"] for seed in thin["query_seeds"])
    thin["universe_sha256"] = open_world_content_digest(thin, exclude="universe_sha256")
    with pytest.raises(ProductDiscoveryError, match="at least 20 query seeds"):
        validate_open_world_query_universe(thin, frame_id="F1")
