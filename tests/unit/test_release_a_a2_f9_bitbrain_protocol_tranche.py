from __future__ import annotations

import hashlib
import json
from importlib.resources import files
from typing import Any, cast

from neuroai_workbench.f9_actor_enumeration import (
    F9_ACTOR_ENUMERATION_PROCEDURE_SHA256,
    f9_bounded_exhaustion_state,
    validate_f9_actor_completion_record,
)
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
PACKET_RESOURCE = "RELEASE_A_A2_F9_BITBRAIN_PROTOCOL_TRANCHE_5.v1.0.json"
LEDGER_RESOURCE = "RELEASE_A_F9_ACTOR_COMPLETION_LEDGER_001.v1.0.json"
PRIOR_PACKET_RESOURCE = "RELEASE_A_A2_F9_CLINICAL_PRODUCT_TRANCHE_4.v1.0.json"
TRANCHE_3_RESOURCE = "RELEASE_A_A2_F9_RESEARCH_BOUNDARY_TRANCHE_3.v1.0.json"
TRANCHE_2_RESOURCE = "RELEASE_A_A2_F9_UNALLOCATED_CANDIDATE_TRANCHE_2.v1.0.json"
TRANCHE_1_RESOURCE = "RELEASE_A_A2_F9_KNOWN_OVERLAP_TRANCHE_1.v1.0.json"
PACKET_SHA256 = "8295c6cdeb48655938c7bdb08bdfd1af66677ca4861e879ef9372b798f482ba4"
LEDGER_SHA256 = "daec7d933de5a5496c397a87c1105adca162157451c920a68ba2d4d03c958166"


def _load_json(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8")),
    )


def _content_sha256(value: dict[str, Any], digest_field: str) -> str:
    material = {key: item for key, item in value.items() if key != digest_field}
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_bitbrain_protocol_tranche_is_content_bound_and_extends_f9_accounting() -> None:
    packet = _load_json(PACKET_RESOURCE)
    prior = _load_json(PRIOR_PACKET_RESOURCE)
    tranche_3 = _load_json(TRANCHE_3_RESOURCE)
    tranche_2 = _load_json(TRANCHE_2_RESOURCE)
    tranche_1 = _load_json(TRANCHE_1_RESOURCE)
    universe = load_default_analysis_universe()
    register = load_f9_actor_seed_register()

    assert packet["packet_sha256"] == PACKET_SHA256
    assert _content_sha256(packet, "packet_sha256") == PACKET_SHA256
    assert packet["analysis_universe_id"] == universe["analysis_universe_id"]
    assert packet["f9_actor_seed_register_id"] == register["register_id"]
    assert packet["f9_actor_seed_count"] == register["actor_count"] == 37
    assert packet["f9_enumeration_procedure_sha256"] == F9_ACTOR_ENUMERATION_PROCEDURE_SHA256
    assert packet["prior_f9_packet_id"] == prior["packet_id"]
    assert packet["prior_f9_packet_sha256"] == prior["packet_sha256"]

    actor_sets = [
        set(cast(list[str], tranche["actors_accounted_in_this_tranche"]))
        for tranche in (tranche_1, tranche_2, tranche_3, prior, packet)
    ]
    for index, actor_set in enumerate(actor_sets):
        for later in actor_sets[index + 1 :]:
            assert actor_set.isdisjoint(later)

    cumulative = set().union(*actor_sets)
    assert packet["actors_accounted_in_this_tranche"] == ["ORG-0003"]
    assert len(cumulative) == packet["cumulative_actors_accounted_count"] == 24
    assert packet["actors_remaining_count"] == 13
    assert cumulative <= {str(actor["organization_id"]) for actor in register["actors"]}


def test_bitbrain_protocol_tranche_preserves_nonadmission_and_exact_capture_binding() -> None:
    packet = _load_json(PACKET_RESOURCE)
    universe = load_default_analysis_universe()
    frame_register = load_default_frame_register()
    f9_frame = next(frame for frame in frame_register["frames"] if frame["frame_id"] == "F9")

    queries = {query["query_or_seed_id"]: query for query in packet["queries"]}
    observations = {item["observation_id"]: item for item in packet["observations"]}
    captures = cast(list[dict[str, Any]], packet["captures"])

    assert len(packet["queries"]) == len(packet["observations"]) == len(captures) == 16
    assert identity_set_digest(packet["round_start_known_identity_ids"]) == packet["round_start_known_identity_set_sha256"]
    assert packet["source_recheck_registration"]["issue_number"] == 357
    assert packet["source_recheck_registration"]["issue_comment_id"] == 5837669615

    outcomes = [str(capture["outcome"]) for capture in captures]
    assert outcomes.count("UNRESOLVED_IDENTITY") == 5
    assert outcomes.count("ABSTAIN") == 11
    assert "INCLUDE_RESOLVED" not in outcomes

    for capture in captures:
        validate_capture_against_analysis_universe(capture, universe)
        validate_capture_against_frame(capture, f9_frame)
        assert capture["capture_estimation_eligible"] is False
        assert capture["canonical_offering_id"] is None
        assert capture["world_time_alignment"] == "UNRESOLVED"
        assert capture["world_time_support_ref"] is None

        query = queries[capture["query_or_seed_id"]]
        observation = observations[capture["source_observation_ref"]]
        assert query["organization_id"] == "ORG-0003"
        assert query["candidate_key"] == capture["candidate_key"]
        assert query["source_url"] == "https://www.bitbrain.com/neurotechnology-products"
        assert query["retrieval_outcome"] == "RETRIEVED"
        assert observation["candidate_key"] == capture["candidate_key"]
        assert observation["source_url"] == query["source_url"]
        assert observation["source_class"] == "MANUFACTURER_VENDOR_OFFICIAL"
        assert observation["observation_registered_at"] == capture["observed_at"]


def test_bitbrain_protocol_tranche_run_summary_and_completion_reproduce() -> None:
    packet = _load_json(PACKET_RESOURCE)
    universe = load_default_analysis_universe()
    frame_register = load_default_frame_register()
    f9_frame = next(frame for frame in frame_register["frames"] if frame["frame_id"] == "F9")
    captures = cast(list[dict[str, Any]], packet["captures"])
    run = cast(dict[str, Any], packet["run"])
    completion = cast(dict[str, Any], packet["actor_completion_record"])

    validate_discovery_run(run)
    validate_run_against_analysis_universe(run, universe)
    validate_run_against_captures(run, captures, f9_frame)
    validate_f9_actor_completion_record(completion)

    assert run["round_id"] == "R5"
    assert run["capture_count"] == 16
    assert run["stop_state"] == "CONTINUE"
    assert set(item["capture_id"] for item in completion["candidate_manifest"]) == set(run["capture_ids"])
    assert completion["actor_organization_id"] == "ORG-0003"
    assert completion["completion_state"] == "ACTOR_ENUMERATION_COMPLETE_UNDER_PROTOCOL"

    reproduced = summarize_discovery_round(
        captures,
        known_identity_ids_before=packet["round_start_known_identity_ids"],
    )
    assert reproduced == packet["round_summary"]
    assert reproduced["outcome_counts"]["UNRESOLVED_IDENTITY"] == 5
    assert reproduced["outcome_counts"]["ABSTAIN"] == 11


def test_bitbrain_candidate_manifest_retains_identity_scope_and_service_boundaries() -> None:
    packet = _load_json(PACKET_RESOURCE)
    completion = cast(dict[str, Any], packet["actor_completion_record"])
    by_key = {item["candidate_key"]: item for item in completion["candidate_manifest"]}

    assert by_key["ORG-0003::Diadem EEG 12ch"]["object_class"] == "PLAUSIBLE_PRODUCT_OFFERING"
    assert by_key["ORG-0003::Versatile EEG"]["object_class"] == "SYSTEM_OR_CONFIGURATION_BOUNDARY"
    assert by_key["ORG-0003::Versatile Bio Amplifier"]["object_class"] == "OTHER_SCOPE_BOUNDARY"
    assert by_key["ORG-0003::SennsMetrics Software"]["object_class"] == "SERVICE_OR_SOFTWARE_BOUNDARY"
    assert by_key["ORG-0003::Bitbrain Human Behaviour Research Labs"]["capture_outcome"] == "ABSTAIN"

    keys = set(by_key)
    assert not any("Tobii" in key for key in keys)
    assert not any("Cortivision" in key for key in keys)


def test_first_f9_completion_ledger_is_immutable_content_bound_and_nonexhaustive() -> None:
    packet = _load_json(PACKET_RESOURCE)
    ledger = _load_json(LEDGER_RESOURCE)

    assert ledger["ledger_sha256"] == LEDGER_SHA256
    assert _content_sha256(ledger, "ledger_sha256") == LEDGER_SHA256
    assert ledger["ledger_sequence"] == 1
    assert ledger["predecessor_ledger_id"] is None
    assert ledger["source_packet_id"] == packet["packet_id"]
    assert ledger["source_packet_sha256"] == packet["packet_sha256"]
    assert ledger["completion_record_count"] == 1
    assert ledger["completed_actor_ids"] == ["ORG-0003"]
    assert ledger["actor_completion_records_remaining"] == 36

    records = cast(list[dict[str, Any]], ledger["completion_records"])
    for record in records:
        validate_f9_actor_completion_record(record)
    assert f9_bounded_exhaustion_state(records) == "CONTINUE"
    assert ledger["f9_exhaustion_state"] == "CONTINUE"
