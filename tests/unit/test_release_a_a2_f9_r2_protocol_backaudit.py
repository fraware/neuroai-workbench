from __future__ import annotations

import hashlib
import json
from importlib.resources import files
from typing import Any, cast

from neuroai_workbench.f9_actor_enumeration import (
    F9_ACTOR_ENUMERATION_PROCEDURE_SHA256,
    f9_bounded_exhaustion_state,
    validate_f9_actor_completion_ledger,
    validate_f9_actor_completion_record,
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

RESOURCE_PACKAGE = "neuroai_workbench.resources.discovery"
PACKET_RESOURCE = "RELEASE_A_A2_F9_R2_PROTOCOL_BACKAUDIT_TRANCHE_7.v1.0.json"
LEDGER_RESOURCE = "RELEASE_A_F9_ACTOR_COMPLETION_LEDGER_003.v1.0.json"
PREDECESSOR_LEDGER_RESOURCE = "RELEASE_A_F9_ACTOR_COMPLETION_LEDGER_002.v1.0.json"
SUCCEEDED_PACKET_RESOURCE = "RELEASE_A_A2_F9_UNALLOCATED_CANDIDATE_TRANCHE_2.v1.0.json"
PACKET_SHA256 = "375d28b1e8f4af1df8910310de420427151bd904196da2893e8791d2915833f9"
LEDGER_SHA256 = "8684e12c8a891bf2d1d11970ad5a915bb5dec3a5e67c2e494777ff1513215820"
R2_ACTORS = {
    "ORG-0001",
    "ORG-0002",
    "ORG-0012",
    "ORG-0023",
    "ORG-0025",
    "ORG-0027",
    "ORG-0041",
}


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


def test_r2_protocol_backaudit_is_content_bound_successor() -> None:
    packet = _load_json(PACKET_RESOURCE)
    succeeded = _load_json(SUCCEEDED_PACKET_RESOURCE)
    assert packet["packet_sha256"] == PACKET_SHA256
    assert _content_sha256(packet, "packet_sha256") == PACKET_SHA256
    assert packet["f9_enumeration_procedure_sha256"] == F9_ACTOR_ENUMERATION_PROCEDURE_SHA256
    assert packet["succeeded_f9_packet_id"] == succeeded["packet_id"]
    assert packet["succeeded_f9_packet_sha256"] == succeeded["packet_sha256"]
    assert set(packet["actors_protocol_completed_in_this_tranche"]) == R2_ACTORS
    assert packet["actors_accounted_in_this_tranche"] == []
    assert packet["cumulative_actors_accounted_count"] == 24
    assert set(succeeded["actors_accounted_in_this_tranche"]) == R2_ACTORS


def test_r2_protocol_backaudit_preserves_nonadmission() -> None:
    packet = _load_json(PACKET_RESOURCE)
    universe = load_default_analysis_universe()
    f9_frame = next(frame for frame in load_default_frame_register()["frames"] if frame["frame_id"] == "F9")
    captures = cast(list[dict[str, Any]], packet["captures"])
    assert len(captures) == 19
    assert (
        identity_set_digest(packet["round_start_known_identity_ids"]) == packet["round_start_known_identity_set_sha256"]
    )
    assert "INCLUDE_RESOLVED" not in [capture["outcome"] for capture in captures]
    for capture in captures:
        validate_capture_against_analysis_universe(capture, universe)
        validate_capture_against_frame(capture, f9_frame)
        assert capture["capture_estimation_eligible"] is False
        assert capture["canonical_offering_id"] is None
        assert capture["world_time_alignment"] == "UNRESOLVED"
        assert capture["world_time_support_ref"] is None


def test_r2_protocol_backaudit_run_and_completions() -> None:
    packet = _load_json(PACKET_RESOURCE)
    universe = load_default_analysis_universe()
    f9_frame = next(frame for frame in load_default_frame_register()["frames"] if frame["frame_id"] == "F9")
    captures = cast(list[dict[str, Any]], packet["captures"])
    run = cast(dict[str, Any], packet["run"])
    completions = cast(list[dict[str, Any]], packet["actor_completion_records"])
    validate_discovery_run(run)
    validate_run_against_analysis_universe(run, universe)
    validate_run_against_captures(run, captures, f9_frame)
    assert run["round_id"] == "R7"
    assert {record["actor_organization_id"] for record in completions} == R2_ACTORS
    for record in completions:
        validate_f9_actor_completion_record(record)
        assert record["completion_state"] == "ACTOR_ENUMERATION_COMPLETE_UNDER_PROTOCOL"
    assert (
        summarize_discovery_round(captures, known_identity_ids_before=packet["round_start_known_identity_ids"])
        == packet["round_summary"]
    )


def test_r2_successor_ledger_binds_predecessor() -> None:
    packet = _load_json(PACKET_RESOURCE)
    ledger = _load_json(LEDGER_RESOURCE)
    predecessor = _load_json(PREDECESSOR_LEDGER_RESOURCE)
    assert ledger["ledger_sha256"] == LEDGER_SHA256
    assert _content_sha256(ledger, "ledger_sha256") == LEDGER_SHA256
    assert ledger["ledger_sequence"] == 3
    assert ledger["predecessor_ledger_sha256"] == predecessor["ledger_sha256"]
    assert ledger["source_packet_sha256"] == packet["packet_sha256"]
    assert ledger["completion_record_count"] == 14
    assert R2_ACTORS <= set(ledger["completed_actor_ids"])
    validate_f9_actor_completion_ledger(ledger, predecessor=predecessor)
    assert f9_bounded_exhaustion_state(ledger["completion_records"]) == "CONTINUE"
