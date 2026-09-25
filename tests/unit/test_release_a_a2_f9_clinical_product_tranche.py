from __future__ import annotations

import hashlib
import json
from importlib.resources import files
from typing import Any, cast

from neuroai_workbench.product_discovery_frames import (
    identity_set_digest,
    load_default_analysis_universe,
    load_default_frame_register,
    load_f9_actor_seed_register,
    summarize_discovery_round,
    validate_capture_against_analysis_universe,
    validate_capture_against_frame,
    validate_discovery_run,
    validate_run_against_analysis_universe,
    validate_run_against_captures,
)

RESOURCE_PACKAGE = "neuroai_workbench.resources.discovery"
PACKET_RESOURCE = "RELEASE_A_A2_F9_CLINICAL_PRODUCT_TRANCHE_4.v1.0.json"
PRIOR_PACKET_RESOURCE = "RELEASE_A_A2_F9_RESEARCH_BOUNDARY_TRANCHE_3.v1.0.json"
TRANCHE_2_RESOURCE = "RELEASE_A_A2_F9_UNALLOCATED_CANDIDATE_TRANCHE_2.v1.0.json"
TRANCHE_1_RESOURCE = "RELEASE_A_A2_F9_KNOWN_OVERLAP_TRANCHE_1.v1.0.json"
PACKET_SHA256 = "102dad6f17c8c9a7d8f856513e81e786f359f604a48a5917a568aa323c21e5ca"


def _load_json(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8")),
    )


def _packet_sha256(packet: dict[str, Any]) -> str:
    material = {key: value for key, value in packet.items() if key != "packet_sha256"}
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_f9_fourth_tranche_is_content_bound_and_extends_actor_accounting() -> None:
    packet = _load_json(PACKET_RESOURCE)
    prior = _load_json(PRIOR_PACKET_RESOURCE)
    tranche_2 = _load_json(TRANCHE_2_RESOURCE)
    tranche_1 = _load_json(TRANCHE_1_RESOURCE)
    universe = load_default_analysis_universe()
    register = load_f9_actor_seed_register()

    assert packet["packet_sha256"] == PACKET_SHA256
    assert _packet_sha256(packet) == PACKET_SHA256
    assert packet["analysis_universe_id"] == universe["analysis_universe_id"]
    assert packet["f9_actor_seed_register_id"] == register["register_id"]
    assert packet["f9_actor_seed_count"] == register["actor_count"] == 37
    assert packet["prior_f9_packet_id"] == prior["packet_id"]
    assert packet["prior_f9_packet_sha256"] == prior["packet_sha256"]

    actor_sets = [
        set(cast(list[str], tranche["actors_accounted_in_this_tranche"]))
        for tranche in (tranche_1, tranche_2, prior, packet)
    ]
    for index, actor_set in enumerate(actor_sets):
        for later in actor_sets[index + 1 :]:
            assert actor_set.isdisjoint(later)

    cumulative = set().union(*actor_sets)
    frozen_actors = {str(actor["organization_id"]) for actor in register["actors"]}
    assert cumulative <= frozen_actors
    assert len(actor_sets[-1]) == packet["actors_accounted_count"] == 5
    assert len(cumulative) == packet["cumulative_actors_accounted_count"] == 23
    assert packet["actors_remaining_count"] == 14
    assert packet["execution_state"] == "PARTIAL_F9_EXECUTION"


def test_f9_fourth_tranche_preserves_identity_and_temporal_nonadmission() -> None:
    packet = _load_json(PACKET_RESOURCE)
    universe = load_default_analysis_universe()
    frame_register = load_default_frame_register()
    f9_frame = next(frame for frame in frame_register["frames"] if frame["frame_id"] == "F9")

    queries = {query["query_or_seed_id"]: query for query in packet["queries"]}
    observations = {item["observation_id"]: item for item in packet["observations"]}
    known_ids = set(cast(list[str], packet["round_start_known_identity_ids"]))

    assert identity_set_digest(known_ids) == packet["round_start_known_identity_set_sha256"]
    assert packet["round_start_known_identity_set_sha256"] == universe["initial_known_identity_set_sha256"]
    assert len(packet["queries"]) == len(packet["observations"]) == len(packet["captures"]) == 8

    outcomes = [str(capture["outcome"]) for capture in packet["captures"]]
    assert outcomes.count("UNRESOLVED_IDENTITY") == 7
    assert outcomes.count("ABSTAIN") == 1
    assert "INCLUDE_RESOLVED" not in outcomes

    for capture in packet["captures"]:
        validate_capture_against_analysis_universe(capture, universe)
        validate_capture_against_frame(capture, f9_frame)

        assert capture["capture_estimation_eligible"] is False
        assert capture["canonical_offering_id"] is None
        assert capture["world_time_alignment"] == "UNRESOLVED"
        assert capture["world_time_support_ref"] is None

        query = queries[capture["query_or_seed_id"]]
        observation = observations[capture["source_observation_ref"]]

        assert query["organization_id"] in packet["actors_accounted_in_this_tranche"]
        assert query["candidate_key"] == capture["candidate_key"]
        assert query["query_family"] == capture["query_family"]
        assert query["source_class"] == capture["source_class"]
        assert query["retrieval_outcome"] == "RETRIEVED"

        assert observation["candidate_key"] == capture["candidate_key"]
        assert observation["source_url"] == query["source_url"]
        assert observation["source_class"] == "MANUFACTURER_VENDOR_OFFICIAL"
        assert observation["content_bytes_archived"] is False
        assert observation["observation_registered_at"] == capture["observed_at"]
        assert observation["world_time_support_ref"] is None


def test_f9_fourth_tranche_run_and_summary_reproduce_without_identity_admission() -> None:
    packet = _load_json(PACKET_RESOURCE)
    universe = load_default_analysis_universe()
    frame_register = load_default_frame_register()
    f9_frame = next(frame for frame in frame_register["frames"] if frame["frame_id"] == "F9")
    captures = cast(list[dict[str, Any]], packet["captures"])
    run = cast(dict[str, Any], packet["run"])
    known_ids = cast(list[str], packet["round_start_known_identity_ids"])

    validate_discovery_run(run)
    validate_run_against_analysis_universe(run, universe)
    validate_run_against_captures(run, captures, f9_frame)

    assert run["round_id"] == "R4"
    assert run["known_identity_set_sha256"] == identity_set_digest(known_ids)
    assert run["stop_state"] == "CONTINUE"
    assert run["capture_count"] == 8

    reproduced = summarize_discovery_round(
        captures,
        known_identity_ids_before=known_ids,
    )
    assert reproduced == packet["round_summary"]
    assert reproduced["unique_resolved_include_identities"] == 0
    assert reproduced["new_resolved_include_identities"] == 0
    assert reproduced["outcome_counts"]["UNRESOLVED_IDENTITY"] == 7
    assert reproduced["outcome_counts"]["ABSTAIN"] == 1
