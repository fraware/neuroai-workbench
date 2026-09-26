from __future__ import annotations

from copy import deepcopy

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
    f10_frame_stop_state,
    f10_freeze_does_not_imply_exhaustion,
    f8_frame_stop_state,
    f8_freeze_does_not_imply_saturation,
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
    assert f8["query_seed_set_sha256"] == id_set_digest(
        seed["query_or_seed_id"] for seed in f8["query_seeds"]
    )
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


def test_f8_protocol_fails_closed_on_strata_or_estimator_drift() -> None:
    protocol = load_default_f8_round_protocol()
    bad = deepcopy(protocol)
    bad["language_jurisdiction_strata_sha256"] = "0" * 64
    bad["protocol_sha256"] = content_digest(bad, exclude="protocol_sha256")
    with pytest.raises(ProductDiscoveryError, match="frozen language strata digest"):
        validate_f8_round_protocol(bad)

    bad_est = deepcopy(protocol)
    bad_est["estimator_policy"]["f7_f9_f11_remain_estimator_excluded"] = False
    bad_est["protocol_sha256"] = content_digest(bad_est, exclude="protocol_sha256")
    with pytest.raises(ProductDiscoveryError, match="F7/F9/F11 must remain estimator-excluded"):
        validate_f8_round_protocol(bad_est)


def test_f8_universe_rejects_english_only_or_global_seeds() -> None:
    universe = load_default_f8_query_universe()
    bad = deepcopy(universe)
    bad["query_seeds"][0]["language"] = "en"
    bad["universe_sha256"] = content_digest(bad, exclude="universe_sha256")
    with pytest.raises(ProductDiscoveryError, match="native-language"):
        validate_f8_query_universe(bad)

    bad2 = deepcopy(universe)
    bad2["query_seeds"][0]["jurisdiction"] = "GLOBAL"
    bad2["universe_sha256"] = content_digest(bad2, exclude="universe_sha256")
    with pytest.raises(ProductDiscoveryError, match="matched jurisdiction"):
        validate_f8_query_universe(bad2)


def test_f10_universe_rejects_contamination_control_or_product_identity_drift() -> None:
    universe = load_default_f10_patent_assignee_universe()
    bad = deepcopy(universe)
    bad["contamination_controls"]["patent_ownership_does_not_establish_commercialization"] = False
    bad["universe_sha256"] = content_digest(bad, exclude="universe_sha256")
    with pytest.raises(ProductDiscoveryError, match="patent_ownership_does_not_establish_commercialization"):
        validate_f10_patent_assignee_universe(bad)

    bad2 = deepcopy(universe)
    bad2["bounded_exhaustion_rule"]["semantic_similarity_does_not_create_product_link"] = False
    bad2["universe_sha256"] = content_digest(bad2, exclude="universe_sha256")
    with pytest.raises(ProductDiscoveryError, match="semantic similarity"):
        validate_f10_patent_assignee_universe(bad2)

    bad3 = deepcopy(universe)
    bad3["patent_candidates"][0]["source_class"] = "ATTRIBUTABLE_PRODUCT_EVIDENCE"
    bad3["universe_sha256"] = content_digest(bad3, exclude="universe_sha256")
    with pytest.raises(ProductDiscoveryError, match="PATENT_BIBLIOGRAPHIC"):
        validate_f10_patent_assignee_universe(bad3)


def test_language_strata_fail_closed_on_digest_drift() -> None:
    strata = load_default_language_jurisdiction_strata()
    bad = deepcopy(strata)
    bad["strata"][0]["selection_basis"] = "post-hoc after seeing yield"
    # Intentionally leave digest stale.
    with pytest.raises(ProductDiscoveryError, match="strata_sha256"):
        validate_language_jurisdiction_strata(bad)
