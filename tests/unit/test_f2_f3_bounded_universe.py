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


def _reseal(universe: dict[str, Any]) -> dict[str, Any]:
    universe["universe_sha256"] = provider_query_universe_digest(universe)
    return universe


def test_validator_fail_closed_matrix() -> None:
    f2 = load_default_f2_provider_query_universe()
    f3 = load_default_f3_provider_query_universe()

    cases: list[tuple[str, dict[str, Any], str]] = []

    missing = deepcopy(f2)
    del missing["providers"]
    cases.append(("missing", missing, "missing fields"))

    for field, value, match in [
        ("status", "DRAFT", "status"),
        ("frame_id", "F9", "frame_id"),
        ("frame_version", "WRONG", "frame_version"),
        ("frame_register_version", "WRONG", "frame_register_version"),
        ("frame_register_blob_sha", "0" * 40, "frame_register_blob_sha"),
        ("analysis_universe_id", "RAU-wrong", "analysis_universe_id"),
        ("world_time_cutoff", "1999-01-01", "world_time_cutoff"),
        ("knowledge_time_cutoff", "1999-01-01T00:00:00Z", "knowledge_time_cutoff"),
        ("source_class", "WRONG", "source_class"),
        ("universe_id", "WRONG", "universe_id"),
        ("boundary", "wrong boundary", "boundary"),
    ]:
        tampered = _reseal(deepcopy(f2))
        tampered[field] = value
        tampered = _reseal(tampered)
        cases.append((field, tampered, match))

    empty_providers = _reseal(deepcopy(f2))
    empty_providers["providers"] = []
    empty_providers = _reseal(empty_providers)
    cases.append(("empty_providers", empty_providers, "providers must be non-empty"))

    providers_not_list = _reseal(deepcopy(f2))
    providers_not_list["providers"] = {"x": 1}
    providers_not_list = _reseal(providers_not_list)
    cases.append(("providers_not_list", providers_not_list, "providers must be an array"))

    bad_provider = _reseal(deepcopy(f2))
    bad_provider["providers"] = ["not-an-object"]
    bad_provider = _reseal(bad_provider)
    cases.append(("provider_type", bad_provider, "provider must be an object"))

    dup_provider = _reseal(deepcopy(f2))
    dup_provider["providers"] = [deepcopy(f2["providers"][0]), deepcopy(f2["providers"][0])]
    dup_provider = _reseal(dup_provider)
    cases.append(("dup_provider", dup_provider, "Duplicate provider_id"))

    blank_provider = _reseal(deepcopy(f2))
    blank_provider["providers"][0] = {
        "provider_id": " ",
        "base_url": "https://example.org",
        "authority": "x",
    }
    blank_provider = _reseal(blank_provider)
    cases.append(("blank_provider", blank_provider, "provider_id"))

    unknown_family = _reseal(deepcopy(f2))
    unknown_family["query_families"][0]["query_family"] = "NOT_A_FAMILY"
    unknown_family = _reseal(unknown_family)
    cases.append(("unknown_family", unknown_family, "Unknown query_family"))

    dup_family = _reseal(deepcopy(f2))
    dup_family["query_families"][1]["query_family"] = dup_family["query_families"][0]["query_family"]
    dup_family = _reseal(dup_family)
    cases.append(("dup_family", dup_family, "Duplicate query_family"))

    bad_provider_ref = _reseal(deepcopy(f2))
    bad_provider_ref["query_families"][0]["provider_id"] = "MISSING_PROVIDER"
    bad_provider_ref = _reseal(bad_provider_ref)
    cases.append(("bad_provider_ref", bad_provider_ref, "unknown provider_id"))

    empty_ids = _reseal(deepcopy(f2))
    empty_ids["query_families"][0]["frozen_record_ids"] = []
    empty_ids["query_families"][0]["frozen_record_count"] = 0
    empty_ids["query_families"][0]["frozen_record_set_sha256"] = record_id_set_digest([])
    empty_ids = _reseal(empty_ids)
    cases.append(("empty_ids", empty_ids, "must be non-empty"))

    unsorted = _reseal(deepcopy(f2))
    ids = list(reversed(unsorted["query_families"][0]["frozen_record_ids"]))
    unsorted["query_families"][0]["frozen_record_ids"] = ids
    unsorted["query_families"][0]["frozen_record_count"] = len(ids)
    unsorted["query_families"][0]["frozen_record_set_sha256"] = record_id_set_digest(ids)
    unsorted = _reseal(unsorted)
    cases.append(("unsorted", unsorted, "must be sorted"))

    dup_ids = _reseal(deepcopy(f2))
    base_ids = list(dup_ids["query_families"][0]["frozen_record_ids"])
    base_ids = sorted(base_ids + [base_ids[0]])
    # force duplicate while keeping sorted appearance attempt
    dup_ids["query_families"][0]["frozen_record_ids"] = [base_ids[0], base_ids[0]] + base_ids[2:]
    dup_ids["query_families"][0]["frozen_record_count"] = len(dup_ids["query_families"][0]["frozen_record_ids"])
    dup_ids["query_families"][0]["frozen_record_set_sha256"] = record_id_set_digest(
        dup_ids["query_families"][0]["frozen_record_ids"]
    )
    dup_ids = _reseal(dup_ids)
    cases.append(("dup_ids", dup_ids, "must be unique"))

    count_mismatch = _reseal(deepcopy(f2))
    count_mismatch["query_families"][0]["frozen_record_count"] = 1
    count_mismatch = _reseal(count_mismatch)
    cases.append(("count_mismatch", count_mismatch, "frozen_record_count mismatch"))

    digest_mismatch = _reseal(deepcopy(f2))
    digest_mismatch["query_families"][0]["frozen_record_set_sha256"] = "0" * 64
    digest_mismatch = _reseal(digest_mismatch)
    cases.append(("family_digest", digest_mismatch, "frozen_record_set_sha256 mismatch"))

    missing_family = _reseal(deepcopy(f2))
    missing_family["query_families"] = missing_family["query_families"][:2]
    missing_family = _reseal(missing_family)
    cases.append(("missing_family", missing_family, "missing query families"))

    for rule_field in [
        "requires_every_query_family_record_id_dispositioned",
        "global_completeness_claim_prohibited",
        "candidate_is_not_automatic_product_identity",
    ]:
        rule_bad = _reseal(deepcopy(f2))
        rule_bad["bounded_exhaustion_rule"][rule_field] = False
        rule_bad = _reseal(rule_bad)
        cases.append((rule_field, rule_bad, "bounded_exhaustion_rule"))

    for label, payload, match in cases:
        with pytest.raises(ProductDiscoveryError, match=match):
            validate_f2_provider_query_universe(payload)

    f3_bad_id = _reseal(deepcopy(f3))
    f3_bad_id["universe_id"] = "WRONG"
    f3_bad_id = _reseal(f3_bad_id)
    with pytest.raises(ProductDiscoveryError, match="universe_id"):
        validate_f3_provider_query_universe(f3_bad_id)

    f3_sources = _reseal(deepcopy(f3))
    f3_sources["source_classes"] = ["WRONG"]
    f3_sources = _reseal(f3_sources)
    with pytest.raises(ProductDiscoveryError, match="source_classes"):
        validate_f3_provider_query_universe(f3_sources)

    f3_union = _reseal(deepcopy(f3))
    f3_union["union_record_ids"] = list(reversed(f3_union["union_record_ids"]))
    f3_union = _reseal(f3_union)
    with pytest.raises(ProductDiscoveryError, match="union_record_ids"):
        validate_f3_provider_query_universe(f3_union)

    f3_union_count = _reseal(deepcopy(f3))
    f3_union_count["union_record_count"] = 1
    f3_union_count = _reseal(f3_union_count)
    with pytest.raises(ProductDiscoveryError, match="union_record_count"):
        validate_f3_provider_query_universe(f3_union_count)

    f3_union_digest = _reseal(deepcopy(f3))
    f3_union_digest["union_record_set_sha256"] = "0" * 64
    f3_union_digest = _reseal(f3_union_digest)
    with pytest.raises(ProductDiscoveryError, match="union_record_set_sha256"):
        validate_f3_provider_query_universe(f3_union_digest)

    f3_union_drift = _reseal(deepcopy(f3))
    f3_union_drift["union_record_ids"] = f3_union_drift["union_record_ids"][:-1]
    f3_union_drift["union_record_count"] = len(f3_union_drift["union_record_ids"])
    f3_union_drift["union_record_set_sha256"] = record_id_set_digest(f3_union_drift["union_record_ids"])
    f3_union_drift = _reseal(f3_union_drift)
    with pytest.raises(ProductDiscoveryError, match="union of family"):
        validate_f3_provider_query_universe(f3_union_drift)

    with pytest.raises(ProductDiscoveryError, match="F2 or F3"):
        family_disposition_coverage(f2, [], frame_id="F9")

    with pytest.raises(ProductDiscoveryError, match="missing fields"):
        family_disposition_coverage(
            f2,
            [{"frame_id": "F2"}],
            frame_id="F2",
        )

    with pytest.raises(ProductDiscoveryError, match="frame_id mismatch"):
        family_disposition_coverage(
            f2,
            [
                _credit(
                    frame_id="F3",
                    query_family="REGULATORY_PRODUCT_IDENTITY_SEARCH",
                    record_id="P150031",
                )
            ],
            frame_id="F2",
        )

    with pytest.raises(ProductDiscoveryError, match="capture_outcome"):
        family_disposition_coverage(
            f2,
            [
                _credit(
                    frame_id="F2",
                    query_family="REGULATORY_PRODUCT_IDENTITY_SEARCH",
                    record_id="P150031",
                    outcome="NOT_AN_OUTCOME",
                )
            ],
            frame_id="F2",
        )

    bad_prior = deepcopy(f2)
    bad_prior["query_families"][2]["prior_packet_observations"] = {"already_dispositioned_record_ids": "not-a-list"}
    # prior_packet_credit_ids path
    with pytest.raises(ProductDiscoveryError, match="already_dispositioned_record_ids"):
        prior_packet_credit_ids(bad_prior, "REGULATORY_PRODUCT_IDENTITY_SEARCH")

    drifted_prior = _reseal(deepcopy(f2))
    drifted_prior["query_families"][2]["prior_packet_observations"]["already_dispositioned_record_ids"] = [
        "NOT-IN-UNIVERSE"
    ]
    drifted_prior = _reseal(drifted_prior)
    with pytest.raises(ProductDiscoveryError, match="prior credit ids outside"):
        family_disposition_coverage(drifted_prior, [], frame_id="F2")
