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

DISCOVERY_RESOURCE_PACKAGE = "neuroai_workbench.resources.discovery"
PRODUCT_RESOURCE_PACKAGE = "neuroai_workbench.resources.product_registry"
PACKET_RESOURCE = "RELEASE_A_A2_F9_KNOWN_OVERLAP_TRANCHE_1.v1.0.json"
A1_PACKET_RESOURCE = "RELEASE_A_SEED_EVIDENCE_PACKET.v1.0.json"
PACKET_SHA256 = "f36ee027d4f3c5474cef8ea89a63f867f5ba6e77772d885c6c5d4f2fd21ba62f"


def _load_json(package: str, resource: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(package).joinpath(resource).read_text(encoding="utf-8")),
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


def test_f9_known_overlap_packet_is_content_bound_and_partial() -> None:
    packet = _load_json(DISCOVERY_RESOURCE_PACKAGE, PACKET_RESOURCE)
    universe = load_default_analysis_universe()
    f9_register = load_f9_actor_seed_register()

    assert packet["packet_sha256"] == PACKET_SHA256
    assert _packet_sha256(packet) == PACKET_SHA256
    assert packet["analysis_universe_id"] == universe["analysis_universe_id"]
    assert packet["frame_id"] == "F9"
    assert packet["f9_actor_seed_register_id"] == f9_register["register_id"]
    assert packet["f9_actor_seed_count"] == f9_register["actor_count"] == 37

    accounted = set(cast(list[str], packet["actors_accounted_in_this_tranche"]))
    frozen_actors = {actor["organization_id"] for actor in f9_register["actors"]}
    assert accounted <= frozen_actors
    assert len(accounted) == packet["actors_accounted_count"] == 6
    assert packet["actors_remaining_count"] == 31
    assert packet["actors_accounted_count"] + packet["actors_remaining_count"] == f9_register["actor_count"]
    assert packet["execution_state"] == "PARTIAL_F9_EXECUTION"


def test_f9_known_overlap_captures_bind_first_party_observations_and_a1_world_time_support() -> None:
    packet = _load_json(DISCOVERY_RESOURCE_PACKAGE, PACKET_RESOURCE)
    a1_packet = _load_json(PRODUCT_RESOURCE_PACKAGE, A1_PACKET_RESOURCE)
    universe = load_default_analysis_universe()
    frame_register = load_default_frame_register()
    f9_frame = next(frame for frame in frame_register["frames"] if frame["frame_id"] == "F9")

    queries = {query["query_or_seed_id"]: query for query in packet["queries"]}
    observations = {observation["observation_id"]: observation for observation in packet["observations"]}
    a1_observation_ids = {observation["observation_id"] for observation in a1_packet["observations"]}
    support_to_entities: dict[str, set[str]] = {}
    for assertion in a1_packet["assertions"]:
        for source_ref in assertion["source_observation_refs"]:
            support_to_entities.setdefault(source_ref, set()).add(assertion["canonical_entity_id"])

    known_ids = set(cast(list[str], packet["round_start_known_identity_ids"]))
    assert identity_set_digest(known_ids) == packet["round_start_known_identity_set_sha256"]
    assert packet["round_start_known_identity_set_sha256"] == universe["initial_known_identity_set_sha256"]
    assert len(packet["captures"]) == len(packet["observations"]) == len(packet["queries"]) == 6

    for capture in packet["captures"]:
        validate_capture_against_analysis_universe(capture, universe)
        validate_capture_against_frame(capture, f9_frame)

        assert capture["outcome"] == "INCLUDE_RESOLVED"
        assert capture["capture_estimation_eligible"] is False
        assert capture["canonical_offering_id"] in known_ids

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

        support_ref = capture["world_time_support_ref"]
        assert support_ref == observation["world_time_support_ref"]
        assert support_ref in a1_observation_ids
        assert capture["canonical_offering_id"] in support_to_entities[support_ref]


def test_f9_known_overlap_run_and_summary_reproduce_exactly() -> None:
    packet = _load_json(DISCOVERY_RESOURCE_PACKAGE, PACKET_RESOURCE)
    universe = load_default_analysis_universe()
    frame_register = load_default_frame_register()
    f9_frame = next(frame for frame in frame_register["frames"] if frame["frame_id"] == "F9")
    captures = cast(list[dict[str, Any]], packet["captures"])
    run = cast(dict[str, Any], packet["run"])
    known_ids = cast(list[str], packet["round_start_known_identity_ids"])

    validate_discovery_run(run)
    validate_run_against_analysis_universe(run, universe)
    validate_run_against_captures(run, captures, f9_frame)

    assert run["known_identity_set_sha256"] == identity_set_digest(known_ids)
    assert run["stop_state"] == "CONTINUE"
    assert run["capture_count"] == 6

    reproduced = summarize_discovery_round(
        captures,
        known_identity_ids_before=known_ids,
    )
    assert reproduced == packet["round_summary"]
    assert reproduced["new_resolved_include_identities"] == 0
    assert reproduced["known_identity_duplicate_count"] == 6
    assert reproduced["duplicate_yield"] == 1
