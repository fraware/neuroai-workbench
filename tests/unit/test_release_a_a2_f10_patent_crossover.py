from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from importlib.resources import files
from typing import Any, cast

from neuroai_workbench.f8_f10_protocol import (
    F10_UNIVERSE_ID,
    F10_UNIVERSE_SHA256,
    f10_frame_stop_state,
    load_default_f10_patent_assignee_universe,
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
PACKET_RESOURCE = "RELEASE_A_A2_F10_PATENT_CROSSOVER_EXHAUSTION_TRANCHE_1.v1.0.json"
PACKET_SHA256 = "2fb9cfddb9c49c97114127fb8fc5f14a0dcbb724195c6f7cd95b5ae7599b862c"
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


def test_f10_exhaustion_packet_is_content_bound_and_source_exhausted() -> None:
    packet = _load_packet()
    universe = load_default_f10_patent_assignee_universe()
    analysis = load_default_analysis_universe()

    assert packet["packet_sha256"] == PACKET_SHA256
    assert _packet_sha256(packet) == PACKET_SHA256
    assert packet["frame_id"] == "F10"
    assert packet["analysis_universe_id"] == analysis["analysis_universe_id"]
    assert packet["f10_patent_assignee_universe_id"] == F10_UNIVERSE_ID == universe["universe_id"]
    assert packet["f10_patent_assignee_universe_sha256"] == F10_UNIVERSE_SHA256
    assert packet["round_start_known_identity_set_sha256"] == identity_set_digest(KNOWN_IDS)
    assert packet["frame_stop_state"] == "BOUNDED_FRAME_EXHAUSTED"
    assert f10_frame_stop_state(source_exhausted=True) == "BOUNDED_FRAME_EXHAUSTED"
    assert packet["exhaustion_accounting"]["source_exhausted"] is True
    assert packet["exhaustion_accounting"]["credited_patent_publication_count"] == universe["patent_candidate_count"]
    assert packet["exhaustion_accounting"]["credited_assignee_candidate_count"] == universe["assignee_candidate_count"]
    assert packet["new_canonical_identity_count"] == 0
    assert packet["contamination_controls"]["patent_ownership_does_not_establish_commercialization"] is True
    assert packet["contamination_controls"]["semantic_similarity_does_not_create_product_identity"] is True
    assert packet["contamination_controls"]["f7_f9_f11_remain_estimator_excluded"] is True


def test_f10_captures_credit_every_frozen_patent_and_assignee() -> None:
    packet = _load_packet()
    universe = load_default_f10_patent_assignee_universe()
    analysis = load_default_analysis_universe()
    frame = next(frame for frame in load_default_frame_register()["frames"] if frame["frame_id"] == "F10")

    captures = cast(list[dict[str, Any]], packet["captures"])
    observations = {obs["observation_id"]: obs for obs in packet["observations"]}
    assert len(captures) == universe["patent_candidate_count"] + universe["assignee_candidate_count"]

    patent_keys = {f"PATENT::{p['publication_number']}" for p in universe["patent_candidates"]}
    capture_keys = {str(c["candidate_key"]) for c in captures}
    assert patent_keys <= capture_keys

    assignee_ids = {str(a["assignee_candidate_id"]) for a in universe["assignee_candidates"]}
    credited_assignees = {
        str(obs["assignee_candidate_id"]) for obs in packet["observations"] if obs.get("assignee_candidate_id")
    }
    assert credited_assignees == assignee_ids

    for capture in captures:
        validate_capture_against_analysis_universe(capture, analysis)
        validate_capture_against_frame(capture, frame)
        assert capture["source_observation_ref"] in observations
        if capture["outcome"] == "INCLUDE_RESOLVED":
            assert capture["canonical_offering_id"] in KNOWN_IDS
            assert capture["capture_estimation_eligible"] is True
            assert capture["source_class"] == "ATTRIBUTABLE_PRODUCT_EVIDENCE"
            assert capture["world_time_support_ref"]
        else:
            assert capture["canonical_offering_id"] is None
            assert capture["capture_estimation_eligible"] is False
            # Bibliographic patent leads never become estimator-eligible by themselves.
            if str(capture["candidate_key"]).startswith("PATENT::"):
                assert capture["outcome"] == "ABSTAIN"
                assert capture["source_class"] == "PATENT_BIBLIOGRAPHIC"

    for run in packet["runs"]:
        validate_discovery_run(run)
        validate_run_against_analysis_universe(run, analysis)
        validate_run_against_captures(run, captures, frame)
        assert run["stop_state"] == "BOUNDED_FRAME_EXHAUSTED"


def test_f10_round_accounting_and_fail_closed_digest() -> None:
    packet = _load_packet()
    captures = cast(list[dict[str, Any]], packet["captures"])
    summary = packet["round_summaries"][0]
    recomputed = summarize_discovery_round(captures, known_identity_ids_before=KNOWN_IDS)
    assert recomputed["raw_candidates"] == summary["raw_candidates"] == len(captures)
    assert recomputed["new_resolved_include_identities"] == 0
    assert recomputed["marginal_new_identity_yield"] == 0.0

    bad = dict(packet)
    bad["packet_sha256"] = "0" * 64
    assert _packet_sha256(bad) != bad["packet_sha256"]

    drifted = deepcopy(packet)
    drifted["frame_stop_state"] = "CONTINUE"
    drifted["packet_sha256"] = _packet_sha256(drifted)
    assert drifted["packet_sha256"] != PACKET_SHA256
    assert f10_frame_stop_state(source_exhausted=False) == "CONTINUE"
