from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from neuroai_workbench.f2_f3_bounded_universe import (
    F2_F3_BOUNDARY,
    F2_UNIVERSE_ID,
    F2_UNIVERSE_SHA256,
    F3_UNIVERSE_ID,
    F3_UNIVERSE_SHA256,
    bounded_frame_exhaustion_state,
    family_disposition_coverage,
    load_default_f2_provider_query_universe,
    load_default_f3_provider_query_universe,
    prior_packet_credit_ids,
    provider_query_universe_digest,
    record_id_set_digest,
    validate_f2_provider_query_universe,
    validate_f3_provider_query_universe,
)
from neuroai_workbench.product_discovery_frames import (
    ProductDiscoveryError,
    load_default_analysis_universe,
    load_default_frame_register,
)


def _credit(
    *,
    frame_id: str,
    query_family: str,
    record_id: str,
    outcome: str = "ABSTAIN",
    packet_id: str = "SUCCESSOR_PACKET",
    packet_sha: str = "a" * 64,
) -> dict[str, Any]:
    return {
        "frame_id": frame_id,
        "query_family": query_family,
        "record_id": record_id,
        "capture_outcome": outcome,
        "source_packet_id": packet_id,
        "source_packet_sha256": packet_sha,
    }


def test_f2_and_f3_universes_are_content_bound_and_register_aligned() -> None:
    f2 = load_default_f2_provider_query_universe()
    f3 = load_default_f3_provider_query_universe()
    universe = load_default_analysis_universe()
    frames = {frame["frame_id"]: frame for frame in load_default_frame_register()["frames"]}

    assert f2["universe_id"] == F2_UNIVERSE_ID
    assert f2["universe_sha256"] == F2_UNIVERSE_SHA256
    assert provider_query_universe_digest(f2) == F2_UNIVERSE_SHA256
    assert f3["universe_id"] == F3_UNIVERSE_ID
    assert f3["universe_sha256"] == F3_UNIVERSE_SHA256
    assert provider_query_universe_digest(f3) == F3_UNIVERSE_SHA256

    assert f2["analysis_universe_id"] == universe["analysis_universe_id"]
    assert f3["analysis_universe_id"] == universe["analysis_universe_id"]
    assert f2["world_time_cutoff"] == universe["world_time_cutoff"]
    assert f3["knowledge_time_cutoff"] == universe["knowledge_time_cutoff"]
    assert f2["boundary"] == F2_F3_BOUNDARY
    assert f3["boundary"] == F2_F3_BOUNDARY

    assert {entry["query_family"] for entry in f2["query_families"]} == set(frames["F2"]["query_families"])
    assert {entry["query_family"] for entry in f3["query_families"]} == set(frames["F3"]["query_families"])

    for entry in f2["query_families"] + f3["query_families"]:
        assert entry["frozen_record_set_sha256"] == record_id_set_digest(entry["frozen_record_ids"])
        assert entry["frozen_record_count"] == len(entry["frozen_record_ids"])


def test_fda_examples_alone_do_not_exhaust_f2_or_f3() -> None:
    f2 = load_default_f2_provider_query_universe()
    f3 = load_default_f3_provider_query_universe()

    # R1 prior credits only — explicitly not exhaustion.
    assert bounded_frame_exhaustion_state(f2, [], frame_id="F2") == "CONTINUE"
    assert bounded_frame_exhaustion_state(f3, [], frame_id="F3") == "CONTINUE"

    f2_coverage = family_disposition_coverage(f2, [], frame_id="F2")
    assert f2_coverage["REGULATORY_PRODUCT_IDENTITY_SEARCH"]["credited_count"] == 3
    assert f2_coverage["REGULATORY_PRODUCT_IDENTITY_SEARCH"]["remaining_record_ids"] == ["P150031"]
    assert f2_coverage["DEVICE_REGISTRY_ENUMERATION"]["exhausted"] is False
    assert f2_coverage["AUTHORIZATION_CLEARANCE_SEARCH"]["exhausted"] is False

    f3_coverage = family_disposition_coverage(f3, [], frame_id="F3")
    assert f3_coverage["FORMAL_INVESTIGATIONAL_PRODUCT_SEARCH"]["credited_count"] == 4
    assert f3_coverage["FORMAL_INVESTIGATIONAL_PRODUCT_SEARCH"]["remaining_record_ids"] == ["NCT07357428"]
    assert "NCT07357428" not in prior_packet_credit_ids(f3, "FORMAL_INVESTIGATIONAL_PRODUCT_SEARCH")
    # Failed inaccessible prior credit is not treated as complete.
    assert f3_coverage["FORMAL_INVESTIGATIONAL_PRODUCT_SEARCH"]["exhausted"] is False
    assert f3_coverage["TRIAL_INTERVENTION_PRODUCT_SEARCH"]["exhausted"] is False
    assert f3_coverage["DEVICE_INTERVENTION_SEARCH"]["exhausted"] is False


def test_f3_failed_inaccessible_requires_successor_not_prior_credit() -> None:
    f3 = load_default_f3_provider_query_universe()
    prior_only = [
        _credit(
            frame_id="F3",
            query_family="FORMAL_INVESTIGATIONAL_PRODUCT_SEARCH",
            record_id="NCT07357428",
            outcome="FAILED_INACCESSIBLE",
            packet_id="RELEASE_A_A2_BOUNDED_TRANCHE_1_v1.0",
            packet_sha="0f5c6e9f83ca1e212d235dac82724ac146d63ed6db3b4abe6f8bd9f681595777",
        )
    ]
    coverage = family_disposition_coverage(f3, prior_only, frame_id="F3")
    assert coverage["FORMAL_INVESTIGATIONAL_PRODUCT_SEARCH"]["remaining_record_ids"] == ["NCT07357428"]

    successor = [
        _credit(
            frame_id="F3",
            query_family="FORMAL_INVESTIGATIONAL_PRODUCT_SEARCH",
            record_id="NCT07357428",
            outcome="UNRESOLVED_IDENTITY",
            packet_id="RELEASE_A_A2_F3_FORMAL_RETRY_TRANCHE",
            packet_sha="b" * 64,
        )
    ]
    coverage2 = family_disposition_coverage(f3, successor, frame_id="F3")
    assert coverage2["FORMAL_INVESTIGATIONAL_PRODUCT_SEARCH"]["exhausted"] is True


def test_full_credit_exhausts_each_frame() -> None:
    f2 = load_default_f2_provider_query_universe()
    f3 = load_default_f3_provider_query_universe()

    f2_credits: list[dict[str, Any]] = []
    for family in f2["query_families"]:
        prior = prior_packet_credit_ids(f2, family["query_family"])
        for record_id in family["frozen_record_ids"]:
            if record_id in prior:
                continue
            f2_credits.append(
                _credit(
                    frame_id="F2",
                    query_family=family["query_family"],
                    record_id=record_id,
                )
            )
    assert bounded_frame_exhaustion_state(f2, f2_credits, frame_id="F2") == "BOUNDED_FRAME_EXHAUSTED"

    f3_credits: list[dict[str, Any]] = []
    for family in f3["query_families"]:
        prior = prior_packet_credit_ids(f3, family["query_family"])
        failed = set(family.get("prior_packet_observations", {}).get("failed_inaccessible_record_ids", []))
        for record_id in family["frozen_record_ids"]:
            if record_id in prior and record_id not in failed:
                continue
            f3_credits.append(
                _credit(
                    frame_id="F3",
                    query_family=family["query_family"],
                    record_id=record_id,
                )
            )
    assert bounded_frame_exhaustion_state(f3, f3_credits, frame_id="F3") == "BOUNDED_FRAME_EXHAUSTED"
    assert (
        bounded_frame_exhaustion_state(f3, f3_credits, frame_id="F3", unresolved_source_barrier=True)
        == "UNRESOLVED_SOURCE_BARRIER"
    )


def test_credit_outside_frozen_universe_fails_closed() -> None:
    f2 = load_default_f2_provider_query_universe()
    with pytest.raises(ProductDiscoveryError, match="outside frozen"):
        family_disposition_coverage(
            f2,
            [
                _credit(
                    frame_id="F2",
                    query_family="REGULATORY_PRODUCT_IDENTITY_SEARCH",
                    record_id="NOT-A-FROZEN-ID",
                )
            ],
            frame_id="F2",
        )


def test_digest_tamper_fails_closed() -> None:
    f2 = load_default_f2_provider_query_universe()
    tampered = deepcopy(f2)
    tampered["query_families"][0]["frozen_record_ids"] = list(tampered["query_families"][0]["frozen_record_ids"]) + [
        "ZZZ"
    ]
    with pytest.raises(ProductDiscoveryError):
        validate_f2_provider_query_universe(tampered)

    f3 = load_default_f3_provider_query_universe()
    tampered3 = deepcopy(f3)
    tampered3["universe_sha256"] = "0" * 64
    with pytest.raises(ProductDiscoveryError, match="digest mismatch"):
        validate_f3_provider_query_universe(tampered3)
