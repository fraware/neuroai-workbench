from __future__ import annotations

import hashlib
import json
from importlib.resources import files
from typing import Any, cast

from neuroai_workbench.product_discovery_frames import (
    identity_set_digest,
    load_default_analysis_universe,
    load_default_frame_register,
    summarize_discovery_round,
    validate_capture_against_analysis_universe,
    validate_capture_against_frame,
    validate_discovery_run,
    validate_run_against_analysis_universe,
    validate_run_against_captures,
)

RESOURCE_PACKAGE = "neuroai_workbench.resources.discovery"
PACKET_RESOURCE = "RELEASE_A_A2_BOUNDED_TRANCHE_1.v1.0.json"
PACKET_ID = "RELEASE_A_A2_BOUNDED_TRANCHE_1_v1.0"
PACKET_SHA256 = "bf77141a2bcff1c2a995d751ae339678517d48765e1aaf6a7e7ec927dc0176b9"


def _load_packet() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(RESOURCE_PACKAGE).joinpath(PACKET_RESOURCE).read_text(encoding="utf-8")),
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


def test_bounded_tranche_packet_is_content_bound_to_frozen_universe() -> None:
    packet = _load_packet()
    universe = load_default_analysis_universe()

    assert packet["packet_id"] == PACKET_ID
    assert packet["packet_sha256"] == PACKET_SHA256
    assert _packet_sha256(packet) == PACKET_SHA256
    assert packet["analysis_universe_id"] == universe["analysis_universe_id"]
    assert packet["world_time_cutoff"] == universe["world_time_cutoff"]
    assert packet["knowledge_time_cutoff"] == universe["knowledge_time_cutoff"]

    known_ids = cast(list[str], packet["round_start_known_identity_ids"])
    assert identity_set_digest(known_ids) == packet["round_start_known_identity_set_sha256"]
    assert packet["round_start_known_identity_set_sha256"] == universe["initial_known_identity_set_sha256"]
    assert len(known_ids) == universe["initial_known_identity_count"]

    registration = cast(dict[str, Any], packet["source_recheck_registration"])
    assert registration["repository"] == "fraware/neuroai-workbench"
    assert registration["issue_number"] == 336
    assert registration["issue_comment_id"] == 5829489285
    assert registration["registered_at"] == "2026-09-25T08:39:30Z"


def test_bounded_tranche_captures_bind_exact_queries_observations_and_frames() -> None:
    packet = _load_packet()
    universe = load_default_analysis_universe()
    frame_register = load_default_frame_register()
    frames = {frame["frame_id"]: frame for frame in frame_register["frames"]}
    queries = {query["query_or_seed_id"]: query for query in packet["queries"]}
    observations = {observation["observation_id"]: observation for observation in packet["observations"]}

    assert len(queries) == 8
    assert len(observations) == 7
    assert all(observation["content_bytes_archived"] is False for observation in observations.values())

    for capture in packet["captures"]:
        frame = frames[capture["frame_id"]]
        query = queries[capture["query_or_seed_id"]]

        validate_capture_against_analysis_universe(capture, universe)
        validate_capture_against_frame(capture, frame)

        assert query["frame_id"] == capture["frame_id"]
        assert query["round_id"] == capture["round_id"]
        assert query["query_family"] == capture["query_family"]
        assert query["source_class"] == capture["source_class"]
        assert query["candidate_key"] == capture["candidate_key"]

        source_ref = capture["source_observation_ref"]
        if source_ref is None:
            assert capture["outcome"] == "FAILED_INACCESSIBLE"
            assert query["retrieval_outcome"] == "FAILED_INACCESSIBLE"
            assert capture["world_time_alignment"] == "UNRESOLVED"
            assert capture["world_time_support_ref"] is None
            continue

        observation = observations[source_ref]
        assert query["retrieval_outcome"] == "RETRIEVED"
        assert observation["frame_id"] == capture["frame_id"]
        assert observation["candidate_key"] == capture["candidate_key"]
        assert observation["source_class"] == capture["source_class"]
        assert observation["source_url"] == query["source_url"]
        assert observation["observation_registered_at"] == capture["observed_at"]

        if capture["outcome"] == "INCLUDE_RESOLVED":
            assert capture["world_time_support_ref"] == observation["world_time_support_ref"]


def test_bounded_tranche_runs_and_round_summaries_reproduce_exactly() -> None:
    packet = _load_packet()
    universe = load_default_analysis_universe()
    frame_register = load_default_frame_register()
    frames = {frame["frame_id"]: frame for frame in frame_register["frames"]}
    captures = cast(list[dict[str, Any]], packet["captures"])
    known_ids = cast(list[str], packet["round_start_known_identity_ids"])
    summaries = {
        (summary["frame_id"], summary["round_id"]): summary for summary in packet["round_summaries"]
    }

    assert {run["frame_id"] for run in packet["runs"]} == {"F2", "F3"}
    for run in packet["runs"]:
        frame_id = run["frame_id"]
        run_captures = [
            capture
            for capture in captures
            if capture["frame_id"] == frame_id and capture["round_id"] == run["round_id"]
        ]

        validate_discovery_run(run)
        validate_run_against_analysis_universe(run, universe)
        validate_run_against_captures(run, run_captures, frames[frame_id])
        assert run["known_identity_set_sha256"] == identity_set_digest(known_ids)
        assert run["stop_state"] == "CONTINUE"

        reproduced = summarize_discovery_round(
            run_captures,
            known_identity_ids_before=known_ids,
        )
        assert reproduced == summaries[(frame_id, run["round_id"])]


def test_bounded_tranche_preserves_conservative_partial_execution_state() -> None:
    packet = _load_packet()
    captures = cast(list[dict[str, Any]], packet["captures"])
    f2 = [capture for capture in captures if capture["frame_id"] == "F2"]
    f3 = [capture for capture in captures if capture["frame_id"] == "F3"]

    assert packet["execution_state"] == "PARTIAL_BOUNDED_FRAME_EXECUTION"
    assert {capture["canonical_offering_id"] for capture in f2 if capture["outcome"] == "INCLUDE_RESOLVED"} == {
        "PRD-FLOW-FL-100",
        "PRD-MODIUS-SPERO",
    }
    assert not any(capture["outcome"] == "INCLUDE_RESOLVED" for capture in f3)
    assert {capture["candidate_key"] for capture in f3 if capture["outcome"] == "FAILED_INACCESSIBLE"} == {
        "NCT07357428"
    }
    assert all(run["stop_state"] == "CONTINUE" for run in packet["runs"])
