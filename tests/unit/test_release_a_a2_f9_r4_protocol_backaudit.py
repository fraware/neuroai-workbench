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
    load_default_analysis_universe,
    load_default_frame_register,
    validate_capture_against_analysis_universe,
    validate_capture_against_frame,
    validate_discovery_run,
    validate_run_against_analysis_universe,
    validate_run_against_captures,
)

RESOURCE_PACKAGE = "neuroai_workbench.resources.discovery"
PACKET_RESOURCE = "RELEASE_A_A2_F9_R4_PROTOCOL_BACKAUDIT_TRANCHE_9.v1.0.json"
LEDGER_RESOURCE = "RELEASE_A_F9_ACTOR_COMPLETION_LEDGER_005.v1.0.json"
PREDECESSOR_LEDGER_RESOURCE = "RELEASE_A_F9_ACTOR_COMPLETION_LEDGER_004.v1.0.json"
SUCCEEDED_PACKET_RESOURCE = "RELEASE_A_A2_F9_CLINICAL_PRODUCT_TRANCHE_4.v1.0.json"
PACKET_SHA256 = "b7298c9928937ccf16ee3996c5beab3dbf82a249853e22af85e35242bd1b2560"
LEDGER_SHA256 = "fd8a013758c88516c798ffe7a7ff3f787fe8d99f763738852666e9f9d26209f8"
R4_ACTORS = {"ORG-0018", "ORG-0019", "ORG-0032", "ORG-0034", "ORG-0036"}


def _load_json(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(files(RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8")))


def _content_sha256(value: dict[str, Any], digest_field: str) -> str:
    material = {key: item for key, item in value.items() if key != digest_field}
    return hashlib.sha256(
        json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def test_r4_protocol_backaudit_packet_and_ledger() -> None:
    packet = _load_json(PACKET_RESOURCE)
    succeeded = _load_json(SUCCEEDED_PACKET_RESOURCE)
    ledger = _load_json(LEDGER_RESOURCE)
    predecessor = _load_json(PREDECESSOR_LEDGER_RESOURCE)
    universe = load_default_analysis_universe()
    f9_frame = next(frame for frame in load_default_frame_register()["frames"] if frame["frame_id"] == "F9")
    captures = cast(list[dict[str, Any]], packet["captures"])
    run = cast(dict[str, Any], packet["run"])
    completions = cast(list[dict[str, Any]], packet["actor_completion_records"])

    assert packet["packet_sha256"] == PACKET_SHA256 == _content_sha256(packet, "packet_sha256")
    assert packet["f9_enumeration_procedure_sha256"] == F9_ACTOR_ENUMERATION_PROCEDURE_SHA256
    assert packet["succeeded_f9_packet_sha256"] == succeeded["packet_sha256"]
    assert set(packet["actors_protocol_completed_in_this_tranche"]) == R4_ACTORS
    assert packet["cumulative_actors_accounted_count"] == 24
    assert set(succeeded["actors_accounted_in_this_tranche"]) == R4_ACTORS
    assert "INCLUDE_RESOLVED" not in [c["outcome"] for c in captures]
    for capture in captures:
        validate_capture_against_analysis_universe(capture, universe)
        validate_capture_against_frame(capture, f9_frame)
        assert capture["canonical_offering_id"] is None
        assert capture["world_time_support_ref"] is None
    validate_discovery_run(run)
    validate_run_against_analysis_universe(run, universe)
    validate_run_against_captures(run, captures, f9_frame)
    for record in completions:
        validate_f9_actor_completion_record(record)
    assert ledger["ledger_sha256"] == LEDGER_SHA256 == _content_sha256(ledger, "ledger_sha256")
    assert ledger["completion_record_count"] == 24
    assert ledger["actor_completion_records_remaining"] == 13
    validate_f9_actor_completion_ledger(ledger, predecessor=predecessor)
    assert f9_bounded_exhaustion_state(ledger["completion_records"]) == "CONTINUE"
