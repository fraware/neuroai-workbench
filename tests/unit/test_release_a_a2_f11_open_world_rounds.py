from __future__ import annotations

import hashlib
import json
from importlib.resources import files
from typing import Any, cast

import pytest

from neuroai_workbench.open_world_round_protocol import (
    PROTOCOL_ID,
    PROTOCOL_SHA256,
    UNIVERSE_IDS,
    UNIVERSE_SHA256,
    load_default_open_world_query_universe,
    open_world_frame_stop_state,
)
from neuroai_workbench.product_discovery_frames import (
    ProductDiscoveryError,
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

DISCOVERY_RESOURCE_PACKAGE = "neuroai_workbench.resources.discovery"
PACKET_RESOURCE = "RELEASE_A_A2_F11_OPEN_WORLD_ROUNDS_1_3_TRANCHE_1.v1.0.json"
PACKET_SHA256 = "e6da0402653a89bb1c55e61b630864271f80daa7d0a1f11cc38d451917d3e88a"
KNOWN_IDS = [
    "PRD-EMOTIV-EPOC-X",
    "PRD-FLOW-FL-100",
    "PRD-MODIUS-SPERO",
    "PRD-MUSE-S-ATHENA",
    "PRD-NEXTSENSE-SMARTBUDS",
    "PRD-SYNCHRON-STENTRODE",
]


def _load_packet() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(DISCOVERY_RESOURCE_PACKAGE).joinpath(PACKET_RESOURCE).read_text(encoding="utf-8")),
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


def test_f11_open_world_packet_is_content_bound_and_protocol_saturated() -> None:
    packet = _load_packet()
    universe = load_default_analysis_universe()
    f11_universe = load_default_open_world_query_universe("F11")

    assert packet["packet_sha256"] == PACKET_SHA256
    assert _packet_sha256(packet) == PACKET_SHA256
    assert packet["analysis_universe_id"] == universe["analysis_universe_id"]
    assert packet["frame_id"] == "F11"
    assert packet["open_world_round_protocol_id"] == PROTOCOL_ID
    assert packet["open_world_round_protocol_sha256"] == PROTOCOL_SHA256
    assert packet["f11_query_universe_id"] == UNIVERSE_IDS["F11"] == f11_universe["universe_id"]
    assert packet["f11_query_universe_sha256"] == UNIVERSE_SHA256["F11"]
    assert packet["round_start_known_identity_set_sha256"] == identity_set_digest(KNOWN_IDS)
    assert packet["new_canonical_allocations"] == 0
    assert packet["final_stop_state"] == "SATURATION_UNDER_DECLARED_PROTOCOL"
    assert packet["final_known_identity_set_sha256"] == identity_set_digest(KNOWN_IDS)

    summaries = packet["round_summaries"]
    assert len(summaries) == 3
    assert [row["round_id"] for row in summaries] == ["R1", "R2", "R3"]
    assert all(int(row["raw_candidates"]) >= 20 for row in summaries)
    assert all(float(row["marginal_new_identity_yield"]) == 0.0 for row in summaries)
    assert open_world_frame_stop_state("F11", summaries) == "SATURATION_UNDER_DECLARED_PROTOCOL"


def test_f11_open_world_captures_and_runs_validate_under_frozen_contracts() -> None:
    packet = _load_packet()
    analysis = load_default_analysis_universe()
    frame = next(frame for frame in load_default_frame_register()["frames"] if frame["frame_id"] == "F11")
    f11_universe = load_default_open_world_query_universe("F11")
    allowed_seeds = {str(seed["query_or_seed_id"]) for seed in f11_universe["query_seeds"]}

    captures = cast(list[dict[str, Any]], packet["captures"])
    observations = {obs["observation_id"]: obs for obs in packet["observations"]}
    assert len(captures) == 120

    for capture in captures:
        validate_capture_against_analysis_universe(capture, analysis)
        validate_capture_against_frame(capture, frame)
        assert capture["query_or_seed_id"] in allowed_seeds
        assert capture["source_observation_ref"] in observations
        assert capture["capture_estimation_eligible"] is False
        if capture["outcome"] == "INCLUDE_RESOLVED":
            assert capture["canonical_offering_id"] in KNOWN_IDS
            assert capture["world_time_support_ref"]
            assert str(capture["world_time_support_ref"]).startswith("OBS-A1-")
        else:
            assert capture["canonical_offering_id"] is None

    include_ids = {
        str(capture["canonical_offering_id"]) for capture in captures if capture["outcome"] == "INCLUDE_RESOLVED"
    }
    assert include_ids <= set(KNOWN_IDS)
    assert include_ids

    for run in packet["runs"]:
        round_captures = [capture for capture in captures if capture["round_id"] == run["round_id"]]
        validate_discovery_run(run)
        validate_run_against_analysis_universe(run, analysis)
        validate_run_against_captures(run, round_captures, frame)
        assert run["known_identity_set_sha256"] == identity_set_digest(KNOWN_IDS)

    assert packet["runs"][0]["stop_state"] == "CONTINUE"
    assert packet["runs"][1]["stop_state"] == "CONTINUE"
    assert packet["runs"][2]["stop_state"] == "SATURATION_UNDER_DECLARED_PROTOCOL"


def test_f11_open_world_round_accounting_matches_captures() -> None:
    packet = _load_packet()
    captures = cast(list[dict[str, Any]], packet["captures"])
    for summary in packet["round_summaries"]:
        round_captures = [capture for capture in captures if capture["round_id"] == summary["round_id"]]
        recomputed = summarize_discovery_round(round_captures, known_identity_ids_before=KNOWN_IDS)
        assert recomputed["raw_candidates"] == summary["raw_candidates"]
        assert recomputed["new_resolved_include_identities"] == summary["new_resolved_include_identities"]
        assert recomputed["known_identity_duplicate_count"] == summary["known_identity_duplicate_count"]
        assert recomputed["marginal_new_identity_yield"] == summary["marginal_new_identity_yield"]
        assert recomputed["outcome_counts"] == summary["outcome_counts"]


def test_f11_open_world_packet_fails_closed_on_digest_or_estimator_drift() -> None:
    packet = _load_packet()
    bad = dict(packet)
    bad["packet_sha256"] = "0" * 64
    assert _packet_sha256(bad) != bad["packet_sha256"]

    drifted = dict(packet)
    drifted["final_stop_state"] = "CONTINUE"
    drifted["packet_sha256"] = _packet_sha256(drifted)
    assert drifted["packet_sha256"] != PACKET_SHA256

    assert open_world_frame_stop_state("F11", packet["round_summaries"][:1]) == "CONTINUE"

    with pytest.raises(ProductDiscoveryError, match="Unknown open-world frame_id"):
        open_world_frame_stop_state("F9", packet["round_summaries"])
