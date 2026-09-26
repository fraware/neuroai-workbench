from __future__ import annotations

import hashlib
import json
from importlib.resources import files
from typing import Any, cast

from neuroai_workbench.f2_f3_bounded_universe import (
    F2_UNIVERSE_ID,
    F2_UNIVERSE_SHA256,
    F3_UNIVERSE_ID,
    F3_UNIVERSE_SHA256,
    bounded_frame_exhaustion_state,
    family_disposition_coverage,
    load_default_f3_provider_query_universe,
)
from neuroai_workbench.product_discovery_frames import (
    identity_set_digest,
    load_default_analysis_universe,
    load_default_frame_register,
    validate_capture_against_analysis_universe,
    validate_capture_against_frame,
    validate_discovery_run,
    validate_run_against_analysis_universe,
    validate_run_against_captures,
)

RESOURCE_PACKAGE = "neuroai_workbench.resources.discovery"
PACKET_RESOURCE = "RELEASE_A_A2_F3_INTERVENTION_DEVICE_EXHAUSTION_TRANCHE_3.v1.0.json"
PACKET_ID = "RELEASE_A_A2_F3_INTERVENTION_DEVICE_EXHAUSTION_TRANCHE_3_v1.0"
PACKET_SHA256 = "584ab1dae1fcf0885a51ec527bea953a2ee4ad5452c10b7bb6985ca652edb82b"
PRIOR_PACKET_ID = "RELEASE_A_A2_F2_EXHAUSTION_F3_FORMAL_RETRY_TRANCHE_2_v1.0"
PRIOR_PACKET_SHA = "d66590970362ac82b880e5fe4b9d7c66a913b6dc91618d31fbf67fa39a31c39b"
R1_PACKET_SHA = "0f5c6e9f83ca1e212d235dac82724ac146d63ed6db3b4abe6f8bd9f681595777"


def _load_packet() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(RESOURCE_PACKAGE).joinpath(PACKET_RESOURCE).read_text(encoding="utf-8")),
    )


def _packet_sha256(packet: dict[str, Any]) -> str:
    material = {key: value for key, value in packet.items() if key not in {"packet_sha256", "disposition_credits"}}
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_tranche3_binds_frozen_universes_and_immutable_predecessors() -> None:
    packet = _load_packet()
    universe = load_default_analysis_universe()
    assert packet["packet_id"] == PACKET_ID
    assert packet["packet_sha256"] == PACKET_SHA256
    assert _packet_sha256(packet) == PACKET_SHA256
    assert packet["predecessor_packet_id"] == PRIOR_PACKET_ID
    assert packet["predecessor_packet_sha256"] == PRIOR_PACKET_SHA
    assert packet["f2_provider_query_universe_id"] == F2_UNIVERSE_ID
    assert packet["f2_provider_query_universe_sha256"] == F2_UNIVERSE_SHA256
    assert packet["f3_provider_query_universe_id"] == F3_UNIVERSE_ID
    assert packet["f3_provider_query_universe_sha256"] == F3_UNIVERSE_SHA256
    assert packet["analysis_universe_id"] == universe["analysis_universe_id"]
    known = cast(list[str], packet["round_start_known_identity_ids"])
    assert identity_set_digest(known) == packet["round_start_known_identity_set_sha256"]
    assert packet["round_start_known_identity_set_sha256"] == universe["initial_known_identity_set_sha256"]

    prior = json.loads(
        files(RESOURCE_PACKAGE)
        .joinpath("RELEASE_A_A2_F2_EXHAUSTION_F3_FORMAL_RETRY_TRANCHE_2.v1.0.json")
        .read_text(encoding="utf-8")
    )
    assert prior["packet_sha256"] == PRIOR_PACKET_SHA
    r1 = json.loads(
        files(RESOURCE_PACKAGE).joinpath("RELEASE_A_A2_BOUNDED_TRANCHE_1.v1.0.json").read_text(encoding="utf-8")
    )
    assert r1["packet_sha256"] == R1_PACKET_SHA


def test_tranche3_captures_validate_without_product_allocation() -> None:
    packet = _load_packet()
    universe = load_default_analysis_universe()
    frames = {frame["frame_id"]: frame for frame in load_default_frame_register()["frames"]}
    queries = {query["query_or_seed_id"]: query for query in packet["queries"]}
    f3_universe = load_default_f3_provider_query_universe()
    families = {entry["query_family"]: entry for entry in f3_universe["query_families"]}

    assert len(packet["captures"]) == 324
    assert sum(1 for c in packet["captures"] if c["query_family"] == "TRIAL_INTERVENTION_PRODUCT_SEARCH") == 228
    assert sum(1 for c in packet["captures"] if c["query_family"] == "DEVICE_INTERVENTION_SEARCH") == 96
    assert all(c["frame_id"] == "F3" for c in packet["captures"])

    for capture in packet["captures"]:
        validate_capture_against_analysis_universe(capture, universe)
        validate_capture_against_frame(capture, frames[capture["frame_id"]])
        assert capture["canonical_offering_id"] is None
        assert capture["capture_estimation_eligible"] is False
        assert capture["outcome"] != "INCLUDE_RESOLVED"
        assert capture["outcome"] == "UNRESOLVED_IDENTITY"
        query = queries[capture["query_or_seed_id"]]
        assert query["candidate_key"] == capture["candidate_key"]
        assert query["query_family"] == capture["query_family"]
        assert query["retrieval_outcome"] == "RETRIEVED"
        frozen = set(families[capture["query_family"]]["frozen_record_ids"])
        assert capture["candidate_key"] in frozen

    bindings = packet["frozen_query_bindings"]
    for family in ("TRIAL_INTERVENTION_PRODUCT_SEARCH", "DEVICE_INTERVENTION_SEARCH"):
        assert bindings[family]["query_parameters"] == families[family]["query_parameters"]
        assert bindings[family]["pagination"] == families[family]["pagination"]
        assert bindings[family]["frozen_record_set_sha256"] == families[family]["frozen_record_set_sha256"]


def test_tranche3_exhausts_f3_and_preserves_f2_terminal() -> None:
    packet = _load_packet()
    universe = load_default_analysis_universe()
    frames = {frame["frame_id"]: frame for frame in load_default_frame_register()["frames"]}
    f3_universe = load_default_f3_provider_query_universe()
    captures_by_id = {c["capture_id"]: c for c in packet["captures"]}

    assert len(packet["runs"]) == 1
    run = packet["runs"][0]
    validate_discovery_run(run)
    validate_run_against_analysis_universe(run, universe)
    run_captures = [captures_by_id[cid] for cid in run["capture_ids"]]
    validate_run_against_captures(run, run_captures, frames["F3"])
    assert run["stop_state"] == "BOUNDED_FRAME_EXHAUSTED"
    assert packet["f2_exhaustion_state"] == "BOUNDED_FRAME_EXHAUSTED"
    assert packet["f3_exhaustion_state"] == "BOUNDED_FRAME_EXHAUSTED"
    assert packet["execution_state"] == "F2_BOUNDED_FRAME_EXHAUSTED_F3_BOUNDED_FRAME_EXHAUSTED"

    credits = cast(list[dict[str, Any]], packet["disposition_credits"])
    assert bounded_frame_exhaustion_state(f3_universe, credits, frame_id="F3") == "BOUNDED_FRAME_EXHAUSTED"
    coverage = family_disposition_coverage(f3_universe, credits, frame_id="F3")
    assert coverage["TRIAL_INTERVENTION_PRODUCT_SEARCH"]["exhausted"] is True
    assert coverage["DEVICE_INTERVENTION_SEARCH"]["exhausted"] is True
    assert coverage["FORMAL_INVESTIGATIONAL_PRODUCT_SEARCH"]["exhausted"] is True
    assert coverage["TRIAL_INTERVENTION_PRODUCT_SEARCH"]["remaining_count"] == 0
    assert coverage["DEVICE_INTERVENTION_SEARCH"]["remaining_count"] == 0

    formal_credit = next(
        credit
        for credit in credits
        if credit["query_family"] == "FORMAL_INVESTIGATIONAL_PRODUCT_SEARCH" and credit["record_id"] == "NCT07357428"
    )
    assert formal_credit["source_packet_id"] == PRIOR_PACKET_ID
    assert formal_credit["source_packet_sha256"] == PRIOR_PACKET_SHA
    assert formal_credit["capture_outcome"] == "UNRESOLVED_IDENTITY"
