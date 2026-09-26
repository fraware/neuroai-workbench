from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pytest

from neuroai_workbench.f8_f10_protocol import (
    F8_BOUNDARY,
    F8_PROTOCOL_ID,
    F8_PROTOCOL_SHA256,
    F8_UNIVERSE_ID,
    F8_UNIVERSE_SHA256,
    F10_BOUNDARY,
    F10_UNIVERSE_ID,
    F10_UNIVERSE_SHA256,
    LANGUAGE_SCOPE_ID,
    LANGUAGE_STRATA_ID,
    LANGUAGE_STRATA_SHA256,
    content_digest,
    f8_frame_stop_state,
    f8_freeze_does_not_imply_saturation,
    f10_frame_stop_state,
    f10_freeze_does_not_imply_exhaustion,
    id_set_digest,
    load_default_f8_query_universe,
    load_default_f8_round_protocol,
    load_default_f10_patent_assignee_universe,
    load_default_language_jurisdiction_strata,
    validate_f8_query_universe,
    validate_f8_round_protocol,
    validate_f10_patent_assignee_universe,
    validate_language_jurisdiction_strata,
)
from neuroai_workbench.product_discovery_frames import ProductDiscoveryError, load_default_frame_register


def _rehash_protocol(protocol: dict[str, Any]) -> None:
    if "protocol_sha256" in protocol:
        protocol["protocol_sha256"] = content_digest(protocol, exclude="protocol_sha256")


def _rehash_universe(universe: dict[str, Any]) -> None:
    if "universe_sha256" in universe:
        universe["universe_sha256"] = content_digest(universe, exclude="universe_sha256")


def _rehash_strata(strata: dict[str, Any]) -> None:
    if "strata_sha256" in strata:
        strata["strata_sha256"] = content_digest(strata, exclude="strata_sha256")


def test_language_strata_and_f8_f10_freezes_are_content_bound() -> None:
    strata = load_default_language_jurisdiction_strata()
    protocol = load_default_f8_round_protocol()
    f8 = load_default_f8_query_universe()
    f10 = load_default_f10_patent_assignee_universe()
    frames = {frame["frame_id"]: frame for frame in load_default_frame_register()["frames"]}

    assert strata["strata_id"] == LANGUAGE_STRATA_ID
    assert strata["strata_sha256"] == LANGUAGE_STRATA_SHA256
    assert strata["language_scope_id"] == LANGUAGE_SCOPE_ID
    assert content_digest(strata, exclude="strata_sha256") == LANGUAGE_STRATA_SHA256
    assert strata["stratum_count"] == 7

    assert protocol["protocol_id"] == F8_PROTOCOL_ID
    assert protocol["protocol_sha256"] == F8_PROTOCOL_SHA256
    assert protocol["language_jurisdiction_strata_sha256"] == LANGUAGE_STRATA_SHA256
    assert protocol["boundary"] == F8_BOUNDARY

    assert f8["universe_id"] == F8_UNIVERSE_ID
    assert f8["universe_sha256"] == F8_UNIVERSE_SHA256
    assert f8["capture_estimation_eligible"] is True is frames["F8"]["capture_estimation_eligible"]
    assert set(f8["query_families"]) == set(frames["F8"]["query_families"])
    assert set(f8["source_classes"]) == set(frames["F8"]["source_classes"])
    assert f8["query_seed_set_sha256"] == id_set_digest(seed["query_or_seed_id"] for seed in f8["query_seeds"])
    for round_id in ("R1", "R2", "R3"):
        assert f8["per_round_seed_counts"][round_id] >= 20
    assert "en" not in f8["languages"]

    assert f10["universe_id"] == F10_UNIVERSE_ID
    assert f10["universe_sha256"] == F10_UNIVERSE_SHA256
    assert f10["capture_estimation_eligible"] is True is frames["F10"]["capture_estimation_eligible"]
    assert set(f10["query_families"]) == set(frames["F10"]["query_families"])
    assert f10["patent_candidate_count"] >= 1
    assert f10["assignee_candidate_count"] >= 1
    assert f10["boundary"] == F10_BOUNDARY
    assert f10["contamination_controls"]["patent_ownership_does_not_establish_commercialization"] is True
    assert f10["contamination_controls"]["semantic_similarity_does_not_create_product_identity"] is True
    assert f10["contamination_controls"]["f7_f9_f11_remain_estimator_excluded"] is True


def test_f8_freeze_alone_remains_continue_and_literal_stop_holds() -> None:
    assert f8_freeze_does_not_imply_saturation() == "CONTINUE"
    assert f8_frame_stop_state([]) == "CONTINUE"
    assert (
        f8_frame_stop_state(
            [
                {"raw_candidates": 30, "marginal_new_identity_yield": 0.0},
                {"raw_candidates": 30, "marginal_new_identity_yield": 0.0},
            ]
        )
        == "CONTINUE"
    )
    saturated = [
        {"raw_candidates": 30, "marginal_new_identity_yield": 0.20},
        {"raw_candidates": 30, "marginal_new_identity_yield": 0.04},
        {"raw_candidates": 30, "marginal_new_identity_yield": 0.03},
    ]
    assert f8_frame_stop_state(saturated) == "SATURATION_UNDER_DECLARED_PROTOCOL"
    broken = [
        {"raw_candidates": 30, "marginal_new_identity_yield": 0.20},
        {"raw_candidates": 5, "marginal_new_identity_yield": 0.01},
        {"raw_candidates": 30, "marginal_new_identity_yield": 0.01},
    ]
    assert f8_frame_stop_state(broken) == "CONTINUE"


def test_f10_freeze_alone_remains_continue_until_exhaustion_flag() -> None:
    assert f10_freeze_does_not_imply_exhaustion() == "CONTINUE"
    assert f10_frame_stop_state(source_exhausted=False) == "CONTINUE"
    assert f10_frame_stop_state(source_exhausted=True) == "BOUNDED_FRAME_EXHAUSTED"


def test_helpers_reject_non_objects_and_empty_strings() -> None:
    with pytest.raises(ProductDiscoveryError, match="missing fields"):
        validate_language_jurisdiction_strata({})
    with pytest.raises(ProductDiscoveryError, match="missing fields"):
        validate_f8_round_protocol({})
    with pytest.raises(ProductDiscoveryError, match="missing fields"):
        validate_f8_query_universe({})
    with pytest.raises(ProductDiscoveryError, match="missing fields"):
        validate_f10_patent_assignee_universe({})


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (lambda s: s.pop("status", None), "missing fields"),
        (lambda s: s.__setitem__("strata_id", "WRONG"), "strata_id must be"),
        (lambda s: s.__setitem__("status", "DRAFT"), "must be FROZEN_v1.0"),
        (lambda s: s.__setitem__("strata_sha256", "0" * 64), "strata_sha256"),
        (lambda s: s.__setitem__("language_scope_id", "EN_ONLY"), "language_scope_id must be"),
        (lambda s: s.__setitem__("analysis_universe_id", "RAU-" + ("0" * 64)), "frozen A2 analysis universe"),
        (lambda s: s.__setitem__("world_time_cutoff", "2020-01-01"), "world_time_cutoff"),
        (lambda s: s.__setitem__("knowledge_time_cutoff", "2020-01-01T00:00:00Z"), "knowledge_time_cutoff"),
        (lambda s: s.__setitem__("a2_checkpoint_id", "WRONG"), "frozen A2 checkpoint"),
        (lambda s: s.__setitem__("a2_checkpoint_sha256", "0" * 64), "frozen A2 checkpoint"),
        (lambda s: s.__setitem__("stratum_count", 0), "stratum_count does not match"),
        (lambda s: s.__setitem__("strata", []), "stratum_count does not match"),
        (lambda s: s.__setitem__("strata", "bad"), "must be an array"),
        (lambda s: s["strata"].__setitem__(0, "bad"), "must be an object"),
        (lambda s: s["strata"][0].__setitem__("stratum_id", ""), "non-empty string"),
        (lambda s: s["strata"].append(deepcopy(s["strata"][0])), "stratum_count does not match"),
        (
            lambda s: (
                s["strata"].append(deepcopy(s["strata"][0])),
                s.__setitem__("stratum_count", len(s["strata"])),
            ),
            "Duplicate stratum_id",
        ),
        (lambda s: s["strata"][0].__setitem__("matched_jurisdictions", []), "matched_jurisdictions must be non-empty"),
        (lambda s: s["strata"][0].__setitem__("matched_jurisdictions", "ES"), "must be an array"),
        (lambda s: s["strata"][0].__setitem__("selection_basis", ""), "non-empty string"),
        (lambda s: s["strata"][0].__setitem__("language_code", ""), "non-empty string"),
    ],
)
def test_language_strata_adversarial_field_drift(mutator: Callable[[dict[str, Any]], Any], match: str) -> None:
    strata = deepcopy(load_default_language_jurisdiction_strata())
    mutator(strata)
    if match not in {"strata_sha256", "missing fields"}:
        try:
            _rehash_strata(strata)
        except Exception:
            pass
    with pytest.raises(ProductDiscoveryError, match=match):
        validate_language_jurisdiction_strata(strata)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (lambda p: p.pop("status", None), "missing fields"),
        (lambda p: p.__setitem__("protocol_id", "WRONG"), "protocol_id must be"),
        (lambda p: p.__setitem__("status", "DRAFT"), "must be FROZEN_v1.0"),
        (lambda p: p.__setitem__("protocol_sha256", "0" * 64), "deterministic content digest"),
        (lambda p: p.__setitem__("frame_ids", ["F8", "F10"]), "exactly \\[F8\\]"),
        (lambda p: p.__setitem__("frame_version", "WRONG"), "frame_version must be"),
        (lambda p: p.__setitem__("frame_register_version", "WRONG"), "frame_register_version must be"),
        (lambda p: p.__setitem__("frame_register_blob_sha", "0" * 40), "frozen register blob"),
        (lambda p: p.__setitem__("analysis_universe_id", "RAU-" + ("0" * 64)), "frozen A2 analysis universe"),
        (lambda p: p.__setitem__("world_time_cutoff", "2020-01-01"), "world_time_cutoff"),
        (lambda p: p.__setitem__("knowledge_time_cutoff", "2020-01-01T00:00:00Z"), "knowledge_time_cutoff"),
        (lambda p: p.__setitem__("a2_checkpoint_id", "WRONG"), "frozen A2 checkpoint"),
        (lambda p: p.__setitem__("a2_checkpoint_sha256", "0" * 64), "frozen A2 checkpoint"),
        (lambda p: p.__setitem__("round_start_known_identity_set_sha256", "0" * 64), "known-identity digest"),
        (lambda p: p.__setitem__("language_scope_id", "EN_ONLY"), "language_scope_id must be"),
        (lambda p: p.__setitem__("language_jurisdiction_strata_id", "WRONG"), "frozen language strata ID"),
        (lambda p: p.__setitem__("language_jurisdiction_strata_sha256", "0" * 64), "frozen language strata digest"),
        (lambda p: p.__setitem__("boundary", "drift"), "boundary drift"),
        (lambda p: p["stopping_rule"].__setitem__("mode", "BOUNDED_SOURCE_EXHAUSTION"), "MARGINAL_YIELD"),
        (lambda p: p["stopping_rule"].__setitem__("minimum_completed_rounds", 9), "minimum_completed_rounds drift"),
        (
            lambda p: p["stopping_rule"].__setitem__("consecutive_low_yield_rounds", 9),
            "consecutive_low_yield_rounds drift",
        ),
        (
            lambda p: p["stopping_rule"].__setitem__("maximum_marginal_new_identity_yield", 0.9),
            "maximum_marginal_new_identity_yield drift",
        ),
        (
            lambda p: p["stopping_rule"].__setitem__("minimum_raw_candidates_per_round", 1),
            "minimum_raw_candidates_per_round drift",
        ),
        (lambda p: p["stopping_rule"].__setitem__("literal_tail_only", False), "literal_tail_only must be true"),
        (
            lambda p: p["estimator_policy"].__setitem__("frame_capture_estimation_eligible", False),
            "capture_estimation_eligible at frame level",
        ),
        (
            lambda p: p["estimator_policy"].__setitem__("f7_f9_f11_remain_estimator_excluded", False),
            "F7/F9/F11 must remain estimator-excluded",
        ),
        (
            lambda p: p["execution_gate"].__setitem__("language_strata_bound_before_yield_interpretation", False),
            "bind language strata before yield",
        ),
        (lambda p: p["execution_gate"].__setitem__("does_not_start_a3_or_later", False), "A3\\+ out of scope"),
    ],
)
def test_f8_protocol_adversarial_field_drift(mutator: Callable[[dict[str, Any]], Any], match: str) -> None:
    protocol = deepcopy(load_default_f8_round_protocol())
    mutator(protocol)
    if match != "deterministic content digest" and "protocol_sha256" in protocol:
        try:
            _rehash_protocol(protocol)
        except Exception:
            pass
    with pytest.raises(ProductDiscoveryError, match=match):
        validate_f8_round_protocol(protocol)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (lambda u: u.pop("status", None), "missing fields"),
        (lambda u: u.__setitem__("universe_id", "WRONG"), "universe_id must be"),
        (lambda u: u.__setitem__("status", "DRAFT"), "must be FROZEN_v1.0"),
        (lambda u: u.__setitem__("universe_sha256", "0" * 64), "deterministic content digest"),
        (lambda u: u.__setitem__("frame_id", "F10"), "frame_id mismatch"),
        (lambda u: u.__setitem__("frame_class", "WRONG"), "frame_class does not match"),
        (lambda u: u.__setitem__("capture_estimation_eligible", False), "capture_estimation_eligible must be true"),
        (lambda u: u.__setitem__("query_families", ["WRONG"]), "query_families do not match"),
        (lambda u: u.__setitem__("source_classes", ["WRONG"]), "source_classes do not match"),
        (lambda u: u.__setitem__("analysis_universe_id", "RAU-" + ("0" * 64)), "frozen A2 analysis universe"),
        (lambda u: u.__setitem__("world_time_cutoff", "2020-01-01"), "world_time_cutoff"),
        (lambda u: u.__setitem__("knowledge_time_cutoff", "2020-01-01T00:00:00Z"), "knowledge_time_cutoff"),
        (lambda u: u.__setitem__("a2_checkpoint_id", "WRONG"), "frozen A2 checkpoint"),
        (lambda u: u.__setitem__("f8_round_protocol_id", "WRONG"), "F8 round protocol ID"),
        (lambda u: u.__setitem__("f8_round_protocol_sha256", "0" * 64), "F8 round protocol digest"),
        (lambda u: u.__setitem__("language_jurisdiction_strata_sha256", "0" * 64), "frozen language strata digest"),
        (lambda u: u.__setitem__("round_start_known_identity_set_sha256", "0" * 64), "A1 known-identity digest"),
        (lambda u: u.__setitem__("boundary", "drift"), "boundary drift"),
        (lambda u: u.__setitem__("minimum_rounds", ["R1"]), "minimum_rounds must be R1/R2/R3"),
        (lambda u: u.__setitem__("query_seed_count", 0), "query_seed_count does not match"),
        (lambda u: u.__setitem__("query_seed_set_sha256", "0" * 64), "query_seed_set_sha256 does not match"),
        (
            lambda u: u["independence_rule"].__setitem__("independently_attributable_from_other_frames", False),
            "independently attributable",
        ),
        (
            lambda u: u["independence_rule"].__setitem__(
                "does_not_credit_f9_actor_enumeration_or_f2_f3_exhaustion", False
            ),
            "must not credit F9/F2/F3",
        ),
        (lambda u: u["query_seeds"][0].__setitem__("language", "en"), "native-language"),
        (lambda u: u["query_seeds"][0].__setitem__("jurisdiction", "GLOBAL"), "matched jurisdiction"),
        (lambda u: u["query_seeds"][0].__setitem__("query_family", "WRONG"), "outside declared families"),
        (lambda u: u["query_seeds"][0].__setitem__("source_class", "WRONG"), "outside declared classes"),
        (lambda u: u["query_seeds"][0].__setitem__("round_id", "R9"), "round_id must be R1/R2/R3"),
        (lambda u: u["query_seeds"].append(deepcopy(u["query_seeds"][0])), "query_seed_count does not match"),
        (
            lambda u: (
                u["query_seeds"].append(deepcopy(u["query_seeds"][0])),
                u.__setitem__("query_seed_count", len(u["query_seeds"])),
            ),
            "Duplicate F8 query_or_seed_id",
        ),
        (lambda u: u["query_seeds"].__setitem__(0, "bad"), "must be an object"),
        (lambda u: u.__setitem__("query_seeds", "bad"), "must be an array"),
        (lambda u: u["per_round_seed_counts"].__setitem__("R1", 1), "per_round_seed_counts"),
        (
            lambda u: u["round_seed_ids"].__setitem__("R1", list(u["round_seed_ids"]["R1"])[::-1]),
            "round_seed_ids\\[R1\\] does not match",
        ),
    ],
)
def test_f8_universe_adversarial_field_drift(mutator: Callable[[dict[str, Any]], Any], match: str) -> None:
    universe = deepcopy(load_default_f8_query_universe())
    mutator(universe)
    if match not in {"deterministic content digest", "missing fields"}:
        try:
            _rehash_universe(universe)
        except Exception:
            pass
    with pytest.raises(ProductDiscoveryError, match=match):
        validate_f8_query_universe(universe)


def test_f8_universe_rejects_thin_round_seed_floor() -> None:
    f8 = load_default_f8_query_universe()
    r1 = [seed for seed in f8["query_seeds"] if seed["round_id"] == "R1"][:19]
    other = [seed for seed in f8["query_seeds"] if seed["round_id"] != "R1"]
    thin = deepcopy(f8)
    thin["query_seeds"] = r1 + other
    thin["query_seed_count"] = len(thin["query_seeds"])
    thin["round_seed_ids"] = {
        "R1": [seed["query_or_seed_id"] for seed in r1],
        "R2": f8["round_seed_ids"]["R2"],
        "R3": f8["round_seed_ids"]["R3"],
    }
    thin["per_round_seed_counts"] = {
        "R1": 19,
        "R2": f8["per_round_seed_counts"]["R2"],
        "R3": f8["per_round_seed_counts"]["R3"],
    }
    thin["query_seed_set_sha256"] = id_set_digest(seed["query_or_seed_id"] for seed in thin["query_seeds"])
    thin["universe_sha256"] = content_digest(thin, exclude="universe_sha256")
    with pytest.raises(ProductDiscoveryError, match="at least 20 query seeds"):
        validate_f8_query_universe(thin)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (lambda u: u.pop("status", None), "missing fields"),
        (lambda u: u.__setitem__("universe_id", "WRONG"), "universe_id must be"),
        (lambda u: u.__setitem__("status", "DRAFT"), "must be FROZEN_v1.0"),
        (lambda u: u.__setitem__("universe_sha256", "0" * 64), "deterministic content digest"),
        (lambda u: u.__setitem__("frame_id", "F8"), "frame_id mismatch"),
        (lambda u: u.__setitem__("frame_class", "WRONG"), "frame_class does not match"),
        (lambda u: u.__setitem__("capture_estimation_eligible", False), "capture_estimation_eligible must be true"),
        (lambda u: u.__setitem__("query_families", ["WRONG"]), "query_families do not match"),
        (lambda u: u.__setitem__("source_classes", ["WRONG"]), "source_classes do not match"),
        (lambda u: u.__setitem__("analysis_universe_id", "RAU-" + ("0" * 64)), "frozen A2 analysis universe"),
        (lambda u: u.__setitem__("world_time_cutoff", "2020-01-01"), "world_time_cutoff"),
        (lambda u: u.__setitem__("knowledge_time_cutoff", "2020-01-01T00:00:00Z"), "knowledge_time_cutoff"),
        (lambda u: u.__setitem__("a2_checkpoint_id", "WRONG"), "frozen A2 checkpoint"),
        (lambda u: u.__setitem__("round_start_known_identity_set_sha256", "0" * 64), "A1 known-identity digest"),
        (lambda u: u.__setitem__("boundary", "drift"), "boundary drift"),
        (lambda u: u.__setitem__("patent_candidate_count", 0), "patent_candidate_count does not match"),
        (lambda u: u.__setitem__("patent_candidates", []), "patent_candidate_count does not match"),
        (lambda u: u.__setitem__("patent_publication_set_sha256", "0" * 64), "patent_publication_set_sha256"),
        (lambda u: u.__setitem__("assignee_candidate_count", 0), "assignee_candidate_count does not match"),
        (lambda u: u.__setitem__("assignee_candidates", []), "assignee_candidate_count does not match"),
        (lambda u: u.__setitem__("assignee_candidate_set_sha256", "0" * 64), "assignee_candidate_set_sha256"),
        (lambda u: u["bounded_exhaustion_rule"].__setitem__("mode", "MARGINAL_YIELD"), "BOUNDED_SOURCE_EXHAUSTION"),
        (
            lambda u: u["bounded_exhaustion_rule"].__setitem__("patent_match_is_retrieval_lead_only", False),
            "patent matches as retrieval leads",
        ),
        (
            lambda u: u["bounded_exhaustion_rule"].__setitem__("assignee_match_is_retrieval_lead_only", False),
            "assignee matches as retrieval leads",
        ),
        (
            lambda u: u["bounded_exhaustion_rule"].__setitem__(
                "product_identity_requires_separate_attributable_product_evidence", False
            ),
            "separate attributable product evidence",
        ),
        (
            lambda u: u["bounded_exhaustion_rule"].__setitem__(
                "commercialization_not_inferred_from_patent_ownership", False
            ),
            "commercialization from patent ownership",
        ),
        (
            lambda u: u["bounded_exhaustion_rule"].__setitem__(
                "semantic_similarity_does_not_create_product_link", False
            ),
            "semantic similarity",
        ),
        (
            lambda u: u["contamination_controls"].__setitem__("patent_or_assignee_match_is_retrieval_lead_only", False),
            "patent_or_assignee_match_is_retrieval_lead_only",
        ),
        (
            lambda u: u["contamination_controls"].__setitem__(
                "no_canonical_offering_allocation_from_patent_freeze", False
            ),
            "no_canonical_offering_allocation_from_patent_freeze",
        ),
        (
            lambda u: u["contamination_controls"].__setitem__(
                "estimator_eligible_only_for_include_resolved_with_attributable_product_evidence", False
            ),
            "estimator_eligible_only_for_include_resolved_with_attributable_product_evidence",
        ),
        (
            lambda u: u["contamination_controls"].__setitem__("f7_f9_f11_remain_estimator_excluded", False),
            "f7_f9_f11_remain_estimator_excluded",
        ),
        (
            lambda u: u["patent_candidates"][0].__setitem__("source_class", "ATTRIBUTABLE_PRODUCT_EVIDENCE"),
            "PATENT_BIBLIOGRAPHIC",
        ),
        (lambda u: u["patent_candidates"][0].__setitem__("publication_number", ""), "non-empty string"),
        (
            lambda u: u["patent_candidates"].append(deepcopy(u["patent_candidates"][0])),
            "patent_candidate_count does not match",
        ),
        (
            lambda u: (
                u["patent_candidates"].append(deepcopy(u["patent_candidates"][0])),
                u.__setitem__("patent_candidate_count", len(u["patent_candidates"])),
            ),
            "Duplicate F10 publication_number",
        ),
        (
            lambda u: u["assignee_candidates"][0].__setitem__("patent_publication_numbers", []),
            "at least one patent publication",
        ),
        (
            lambda u: u["assignee_candidates"].append(deepcopy(u["assignee_candidates"][0])),
            "assignee_candidate_count does not match",
        ),
        (
            lambda u: (
                u["assignee_candidates"].append(deepcopy(u["assignee_candidates"][0])),
                u.__setitem__("assignee_candidate_count", len(u["assignee_candidates"])),
            ),
            "Duplicate F10 assignee_candidate_id",
        ),
        (lambda u: u["patent_candidates"].__setitem__(0, "bad"), "must be an object"),
        (lambda u: u.__setitem__("patent_candidates", "bad"), "must be an array"),
        (lambda u: u["patent_candidates"][0].__setitem__("query_family", "WRONG"), "outside declared families"),
    ],
)
def test_f10_universe_adversarial_field_drift(mutator: Callable[[dict[str, Any]], Any], match: str) -> None:
    universe = deepcopy(load_default_f10_patent_assignee_universe())
    mutator(universe)
    if match not in {"deterministic content digest", "missing fields"}:
        try:
            _rehash_universe(universe)
        except Exception:
            pass
    with pytest.raises(ProductDiscoveryError, match=match):
        validate_f10_patent_assignee_universe(universe)
