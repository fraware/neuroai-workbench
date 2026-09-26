from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from importlib.resources import files
from typing import Any, cast

from neuroai_workbench.f8_f10_protocol import (
    F8_PROTOCOL_ID,
    F8_PROTOCOL_SHA256,
    F8_UNIVERSE_ID,
    F8_UNIVERSE_SHA256,
    LANGUAGE_STRATA_SHA256,
    f8_frame_stop_state,
    load_default_f8_query_universe,
)
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

DISCOVERY_RESOURCE_PACKAGE = "neuroai_workbench.resources.discovery"
PACKET_RESOURCE = "RELEASE_A_A2_F8_OPEN_WORLD_ROUNDS_1_3_TRANCHE_1.v1.0.json"
PACKET_SHA256 = "07e79f2ba1501379315850d3756cb4758f632b5f337e47a140fe50c861e2043f"
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


def test_f8_open_world_packet_is_content_bound_and_protocol_saturated() -> None:
    packet = _load_packet()
    universe = load_default_analysis_universe()
    f8_universe = load_default_f8_query_universe()

    assert packet["packet_sha256"] == PACKET_SHA256
    assert _packet_sha256(packet) == PACKET_SHA256
    assert packet["analysis_universe_id"] == universe["analysis_universe_id"]
    assert packet["frame_id"] == "F8"
    assert packet["f8_round_protocol_id"] == F8_PROTOCOL_ID
    assert packet["f8_round_protocol_sha256"] == F8_PROTOCOL_SHA256
    assert packet["f8_query_universe_id"] == F8_UNIVERSE_ID == f8_universe["universe_id"]
    assert packet["f8_query_universe_sha256"] == F8_UNIVERSE_SHA256
    assert packet["language_jurisdiction_strata_sha256"] == LANGUAGE_STRATA_SHA256
    assert packet["round_start_known_identity_set_sha256"] == identity_set_digest(KNOWN_IDS)
    assert packet["new_canonical_identity_count"] == 0
    assert packet["frame_stop_state"] == "SATURATION_UNDER_DECLARED_PROTOCOL"
    assert packet["capture_estimation_eligible_frame"] is True
    assert packet["include_resolved_canonical_ids"] == []

    summaries = packet["round_summaries"]
    assert len(summaries) == 3
    assert [row["round_id"] for row in summaries] == ["R1", "R2", "R3"]
    assert all(int(row["raw_candidates"]) >= 20 for row in summaries)
    assert all(float(row["marginal_new_identity_yield"]) == 0.0 for row in summaries)
    assert f8_frame_stop_state(summaries) == "SATURATION_UNDER_DECLARED_PROTOCOL"


def test_f8_open_world_captures_and_runs_validate_under_frozen_contracts() -> None:
    packet = _load_packet()
    analysis = load_default_analysis_universe()
    frame = next(frame for frame in load_default_frame_register()["frames"] if frame["frame_id"] == "F8")
    f8_universe = load_default_f8_query_universe()
    allowed_seeds = {str(seed["query_or_seed_id"]) for seed in f8_universe["query_seeds"]}

    captures = cast(list[dict[str, Any]], packet["captures"])
    observations = {obs["observation_id"]: obs for obs in packet["observations"]}
    assert len(captures) == 63

    for capture in captures:
        validate_capture_against_analysis_universe(capture, analysis)
        validate_capture_against_frame(capture, frame)
        assert capture["query_or_seed_id"] in allowed_seeds
        assert capture["source_observation_ref"] in observations
        assert capture["language"] != "en"
        assert capture["jurisdiction"] != "GLOBAL"
        if capture["outcome"] == "INCLUDE_RESOLVED":
            assert capture["canonical_offering_id"] in KNOWN_IDS
            assert capture["capture_estimation_eligible"] is True
            assert capture["world_time_support_ref"]
            assert str(capture["world_time_support_ref"]).startswith("OBS-A1-")
        else:
            assert capture["canonical_offering_id"] is None
            assert capture["capture_estimation_eligible"] is False

    include_ids = {
        str(capture["canonical_offering_id"]) for capture in captures if capture["outcome"] == "INCLUDE_RESOLVED"
    }
    assert include_ids <= set(KNOWN_IDS)
    assert include_ids == set()

    for run in packet["runs"]:
        round_captures = [capture for capture in captures if capture["round_id"] == run["round_id"]]
        validate_discovery_run(run)
        validate_run_against_analysis_universe(run, analysis)
        validate_run_against_captures(run, round_captures, frame)
        assert run["known_identity_set_sha256"] == identity_set_digest(KNOWN_IDS)

    assert packet["runs"][0]["stop_state"] == "CONTINUE"
    assert packet["runs"][1]["stop_state"] == "CONTINUE"
    assert packet["runs"][2]["stop_state"] == "SATURATION_UNDER_DECLARED_PROTOCOL"


def test_f8_open_world_round_accounting_matches_captures() -> None:
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


def test_f8_open_world_packet_fails_closed_on_digest_or_estimator_drift() -> None:
    packet = _load_packet()
    bad = dict(packet)
    bad["packet_sha256"] = "0" * 64
    assert _packet_sha256(bad) != bad["packet_sha256"]

    drifted = deepcopy(packet)
    drifted["frame_stop_state"] = "CONTINUE"
    drifted["packet_sha256"] = _packet_sha256(drifted)
    assert drifted["packet_sha256"] != PACKET_SHA256

    assert f8_frame_stop_state(packet["round_summaries"][:1]) == "CONTINUE"

    # Estimator contamination control: F8 remains eligible only via INCLUDE_RESOLVED.
    assert all(
        capture["capture_estimation_eligible"] is False
        for capture in packet["captures"]
        if capture["outcome"] != "INCLUDE_RESOLVED"
    )
