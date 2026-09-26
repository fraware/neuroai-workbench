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


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (lambda p: p.pop("status", None), "missing fields"),
        (lambda p: p.__setitem__("protocol_id", "WRONG"), "protocol_id must be"),
        (lambda p: p.__setitem__("status", "DRAFT"), "must be FROZEN_v1.0"),
        (lambda p: p.__setitem__("protocol_sha256", "0" * 64), "deterministic content digest"),
        (lambda p: p.__setitem__("frame_ids", ["F1", "F4"]), "exactly F1/F4/F5/F6/F11"),
        (lambda p: p.__setitem__("frame_version", "WRONG"), "frame_version must be"),
        (lambda p: p.__setitem__("frame_register_version", "WRONG"), "frame_register_version must be"),
        (lambda p: p.__setitem__("frame_register_blob_sha", "0" * 40), "frozen register blob"),
        (lambda p: p.__setitem__("world_time_cutoff", "2020-01-01"), "world_time_cutoff"),
        (lambda p: p.__setitem__("knowledge_time_cutoff", "2020-01-01T00:00:00Z"), "knowledge_time_cutoff"),
        (lambda p: p.__setitem__("a2_checkpoint_id", "WRONG"), "checkpoint ID"),
        (lambda p: p.__setitem__("a2_checkpoint_sha256", "0" * 64), "checkpoint digest"),
        (lambda p: p.__setitem__("round_start_known_identity_set_sha256", "0" * 64), "known-identity digest"),
        (lambda p: p.__setitem__("boundary", "drift"), "boundary drift"),
        (lambda p: p["stopping_rule"].__setitem__("mode", "BOUNDED_SOURCE_EXHAUSTION"), "MARGINAL_YIELD"),
        (lambda p: p["stopping_rule"].__setitem__("minimum_completed_rounds", 1), "minimum_completed_rounds must be 3"),
        (
            lambda p: p["stopping_rule"].__setitem__("consecutive_low_yield_rounds", 1),
            "consecutive_low_yield_rounds must be 2",
        ),
        (lambda p: p["stopping_rule"].__setitem__("maximum_marginal_new_identity_yield", 0.5), "must be 0.05"),
        (lambda p: p["stopping_rule"].__setitem__("minimum_raw_candidates_per_round", 1), "must be 20"),
        (lambda p: p["stopping_rule"].__setitem__("literal_tail_only", False), "literal_tail_only must be true"),
        (
            lambda p: p["estimator_policy"].__setitem__("primary_estimation_eligible_frames", ["F1"]),
            "primary_estimation_eligible_frames must be F1/F4/F5/F6",
        ),
        (
            lambda p: p["estimator_policy"].__setitem__("f11_capture_estimation_eligible_must_be_false", False),
            "estimator-ineligible",
        ),
        (
            lambda p: p["independence_rule"].__setitem__("frames_independently_attributable", False),
            "independently attributable",
        ),
        (
            lambda p: p["independence_rule"].__setitem__(
                "prohibit_pooling_source_routes_merely_because_same_product_found", False
            ),
            "Pooling source routes",
        ),
        (
            lambda p: p["temporal_rule"].__setitem__(
                "resolved_post_cutoff_capture_requires_world_time_support_ref", False
            ),
            "world_time_support_ref",
        ),
        (
            lambda p: p["temporal_rule"].__setitem__("no_canonical_identity_allocation_by_implication", False),
            "Canonical identity allocation",
        ),
        (lambda p: p.__setitem__("minimum_declared_rounds", ["R1"]), "R1/R2/R3"),
        (lambda p: p["execution_gate"].__setitem__("does_not_start_f8_f10_a3_or_a7", False), "F8/F10/A3/A7"),
        (lambda p: p.__setitem__("stopping_rule", "bad"), "must be an object"),
    ],
)
def test_protocol_adversarial_field_drift(mutator, match: str) -> None:
    protocol = deepcopy(load_default_open_world_round_protocol())
    mutator(protocol)
    if "protocol_sha256" in protocol and match != "deterministic content digest":
        try:
            protocol["protocol_sha256"] = open_world_content_digest(protocol, exclude="protocol_sha256")
        except Exception:
            pass
    with pytest.raises(ProductDiscoveryError, match=match):
        validate_open_world_round_protocol(protocol)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (lambda u: None, "Unknown open-world frame_id"),
        (lambda u: u.pop("status", None), "missing fields"),
        (lambda u: u.__setitem__("universe_id", "WRONG"), "universe_id must be"),
        (lambda u: u.__setitem__("status", "DRAFT"), "must be FROZEN_v1.0"),
        (lambda u: u.__setitem__("universe_sha256", "0" * 64), "deterministic content digest"),
        (lambda u: u.__setitem__("frame_id", "F4"), "frame_id mismatch"),
        (lambda u: u.__setitem__("frame_version", "WRONG"), "frame_version must be"),
        (lambda u: u.__setitem__("frame_register_version", "WRONG"), "frame_register_version must be"),
        (lambda u: u.__setitem__("frame_register_blob_sha", "0" * 40), "frozen register blob"),
        (lambda u: u.__setitem__("analysis_universe_id", "RAU-" + ("0" * 64)), "frozen A2 analysis universe"),
        (lambda u: u.__setitem__("world_time_cutoff", "2020-01-01"), "world_time_cutoff"),
        (lambda u: u.__setitem__("knowledge_time_cutoff", "2020-01-01T00:00:00Z"), "knowledge_time_cutoff"),
        (lambda u: u.__setitem__("a2_checkpoint_id", "WRONG"), "frozen A2 checkpoint"),
        (lambda u: u.__setitem__("open_world_round_protocol_id", "WRONG"), "must bind RELEASE_A_OPEN_WORLD"),
        (lambda u: u.__setitem__("open_world_round_protocol_sha256", "0" * 64), "frozen open-world protocol digest"),
        (lambda u: u.__setitem__("round_start_known_identity_set_sha256", "0" * 64), "A1 known-identity digest"),
        (lambda u: u.__setitem__("boundary", "drift"), "boundary drift"),
        (lambda u: u.__setitem__("frame_class", "WRONG"), "frame_class does not match"),
        (lambda u: u.__setitem__("capture_estimation_eligible", False), "capture_estimation_eligible does not match"),
        (lambda u: u.__setitem__("query_families", ["WRONG"]), "query_families do not match"),
        (lambda u: u.__setitem__("source_classes", ["WRONG"]), "source_classes do not match"),
        (lambda u: u.__setitem__("minimum_rounds", ["R1"]), "minimum_rounds must be R1/R2/R3"),
        (lambda u: u["stopping_rule"].__setitem__("mode", "BOUNDED_SOURCE_EXHAUSTION"), "MARGINAL_YIELD"),
        (lambda u: u["stopping_rule"].__setitem__("minimum_completed_rounds", 9), "minimum_completed_rounds drift"),
        (
            lambda u: u["stopping_rule"].__setitem__("consecutive_low_yield_rounds", 9),
            "consecutive_low_yield_rounds drift",
        ),
        (
            lambda u: u["stopping_rule"].__setitem__("maximum_marginal_new_identity_yield", 0.9),
            "maximum_marginal_new_identity_yield drift",
        ),
        (
            lambda u: u["stopping_rule"].__setitem__("minimum_raw_candidates_per_round", 1),
            "minimum_raw_candidates_per_round drift",
        ),
        (lambda u: u.__setitem__("query_seed_count", 1), "query_seed_count does not match"),
        (lambda u: u.__setitem__("query_seed_set_sha256", "0" * 64), "query_seed_set_sha256 does not match"),
        (
            lambda u: u["independence_rule"].__setitem__("independently_attributable_from_other_frames", False),
            "independently attributable",
        ),
        (
            lambda u: u["temporal_rule"].__setitem__(
                "resolved_post_cutoff_capture_requires_world_time_support_ref", False
            ),
            "world_time_support_ref",
        ),
        (
            lambda u: u["temporal_rule"].__setitem__("no_canonical_identity_allocation_by_implication", False),
            "canonical identity allocation by implication",
        ),
        (lambda u: u["query_seeds"].__setitem__(0, "bad"), "must be an object"),
        (lambda u: u["query_seeds"][0].__setitem__("round_id", "R9"), "round_id must be R1/R2/R3"),
        (lambda u: u["query_seeds"][0].__setitem__("source_class", "WRONG"), "outside declared classes"),
        (lambda u: u["query_seeds"][0].__setitem__("query_or_seed_id", ""), "non-empty string"),
        (lambda u: u["per_round_seed_counts"].__setitem__("R1", 0), "per_round_seed_counts"),
    ],
)
def test_query_universe_adversarial_field_drift(mutator, match: str) -> None:
    if match == "Unknown open-world frame_id":
        with pytest.raises(ProductDiscoveryError, match=match):
            validate_open_world_query_universe(load_default_open_world_query_universe("F1"), frame_id="F8")
        return
    universe = deepcopy(load_default_open_world_query_universe("F1"))
    mutator(universe)
    # Keep seed/round bookkeeping coherent for mutations that do not intentionally break it.
    if match not in {
        "query_seed_count does not match",
        "query_seed_set_sha256 does not match",
        "per_round_seed_counts",
        "round_id must be R1/R2/R3",
        "outside declared classes",
        "must be an object",
        "non-empty string",
        "at least 20 query seeds",
    }:
        if isinstance(universe.get("query_seeds"), list) and all(isinstance(s, dict) for s in universe["query_seeds"]):
            seed_ids = [str(seed["query_or_seed_id"]) for seed in universe["query_seeds"]]
            if "" not in seed_ids and len(seed_ids) == len(set(seed_ids)):
                universe["query_seed_count"] = len(seed_ids)
                universe["query_seed_set_sha256"] = query_seed_set_digest(seed_ids)
                rebuilt = {"R1": [], "R2": [], "R3": []}
                valid_rounds = True
                for seed in universe["query_seeds"]:
                    round_id = str(seed.get("round_id"))
                    if round_id not in rebuilt:
                        valid_rounds = False
                        break
                    rebuilt[round_id].append(str(seed["query_or_seed_id"]))
                if valid_rounds:
                    universe["round_seed_ids"] = rebuilt
                    universe["per_round_seed_counts"] = {key: len(value) for key, value in rebuilt.items()}
    if "universe_sha256" in universe and match != "deterministic content digest":
        try:
            universe["universe_sha256"] = open_world_content_digest(universe, exclude="universe_sha256")
        except Exception:
            pass
    with pytest.raises(ProductDiscoveryError, match=match):
        validate_open_world_query_universe(universe, frame_id="F1")


def test_duplicate_seed_id_and_unknown_frame_helpers_fail_closed() -> None:
    f1 = deepcopy(load_default_open_world_query_universe("F1"))
    f1["query_seeds"][1]["query_or_seed_id"] = f1["query_seeds"][0]["query_or_seed_id"]
    f1["query_seed_count"] = len(f1["query_seeds"])
    f1["query_seed_set_sha256"] = query_seed_set_digest(seed["query_or_seed_id"] for seed in f1["query_seeds"])
    f1["universe_sha256"] = open_world_content_digest(f1, exclude="universe_sha256")
    with pytest.raises(ProductDiscoveryError, match="Duplicate open-world query_or_seed_id"):
        validate_open_world_query_universe(f1, frame_id="F1")

    with pytest.raises(ProductDiscoveryError, match="Unknown open-world frame_id"):
        load_default_open_world_query_universe("F8")
    with pytest.raises(ProductDiscoveryError, match="Unknown open-world frame_id"):
        open_world_frame_stop_state("F8", [])


def test_query_universe_fails_closed_on_family_or_seed_floor_drift() -> None:
    f1 = load_default_open_world_query_universe("F1")
    bad_family = deepcopy(f1)
    bad_family["query_seeds"][0]["query_family"] = "DEVICE_REGISTRY_ENUMERATION"
    bad_family["universe_sha256"] = open_world_content_digest(bad_family, exclude="universe_sha256")
    with pytest.raises(ProductDiscoveryError, match="outside declared families"):
        validate_open_world_query_universe(bad_family, frame_id="F1")

    # Rebuild with only 19 R1 seeds.
    r1_seeds = [seed for seed in f1["query_seeds"] if seed["round_id"] == "R1"][:19]
    other = [seed for seed in f1["query_seeds"] if seed["round_id"] != "R1"]
    thin = deepcopy(f1)
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

    mismatched_rounds = deepcopy(f1)
    mismatched_rounds["round_seed_ids"] = {
        "R1": list(f1["round_seed_ids"]["R1"])[::-1],
        "R2": f1["round_seed_ids"]["R2"],
        "R3": f1["round_seed_ids"]["R3"],
    }
    mismatched_rounds["universe_sha256"] = open_world_content_digest(mismatched_rounds, exclude="universe_sha256")
    with pytest.raises(ProductDiscoveryError, match="round_seed_ids\\[R1\\] does not match"):
        validate_open_world_query_universe(mismatched_rounds, frame_id="F1")
