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
    load_f9_actor_seed_register,
    validate_capture_against_analysis_universe,
    validate_capture_against_frame,
    validate_discovery_run,
    validate_run_against_analysis_universe,
    validate_run_against_captures,
)

RESOURCE_PACKAGE = "neuroai_workbench.resources.discovery"
PACKET_SHA256 = "ec36291d58685e30e19903a04ec83b9ba03a8cf3931f311881438eea4b3c8407"
LEDGER_SHA256 = "8ed73ad8e53c341f28a749527e5cc6e7277b5a37ba205231ed8219d24c27fc9e"
REMAINING = {
    "ORG-0011",
    "ORG-0015",
    "ORG-0016",
    "ORG-0021",
    "ORG-0022",
    "ORG-0026",
    "ORG-0028",
    "ORG-0030",
    "ORG-0031",
    "ORG-0033",
    "ORG-0042",
}


def _load(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(files(RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8")))


def _sha(value: dict[str, Any], field: str) -> str:
    material = {k: v for k, v in value.items() if k != field}
    return hashlib.sha256(
        json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def test_remaining_actors_complete_37_and_exhaust_f9_frame() -> None:
    packet = _load("RELEASE_A_A2_F9_REMAINING_ACTORS_PROTOCOL_TRANCHE_12.v1.0.json")
    ledger = _load("RELEASE_A_F9_ACTOR_COMPLETION_LEDGER_008.v1.0.json")
    predecessor = _load("RELEASE_A_F9_ACTOR_COMPLETION_LEDGER_007.v1.0.json")
    register = load_f9_actor_seed_register()
    universe = load_default_analysis_universe()
    f9 = next(f for f in load_default_frame_register()["frames"] if f["frame_id"] == "F9")
    captures = cast(list[dict[str, Any]], packet["captures"])

    assert packet["packet_sha256"] == PACKET_SHA256 == _sha(packet, "packet_sha256")
    assert packet["f9_enumeration_procedure_sha256"] == F9_ACTOR_ENUMERATION_PROCEDURE_SHA256
    assert set(packet["actors_accounted_in_this_tranche"]) == REMAINING
    assert packet["cumulative_actors_accounted_count"] == 37
    assert packet["actors_remaining_count"] == 0
    assert len(captures) == 44
    assert "INCLUDE_RESOLVED" not in [c["outcome"] for c in captures]
    for c in captures:
        validate_capture_against_analysis_universe(c, universe)
        validate_capture_against_frame(c, f9)
        assert c["canonical_offering_id"] is None
        assert c["world_time_support_ref"] is None
        assert c["capture_estimation_eligible"] is False
    validate_discovery_run(packet["run"])
    validate_run_against_analysis_universe(packet["run"], universe)
    validate_run_against_captures(packet["run"], captures, f9)
    for record in packet["actor_completion_records"]:
        validate_f9_actor_completion_record(record)
        assert record["completion_state"] == "ACTOR_ENUMERATION_COMPLETE_UNDER_PROTOCOL"

    assert ledger["ledger_sha256"] == LEDGER_SHA256 == _sha(ledger, "ledger_sha256")
    assert ledger["completion_record_count"] == 37
    assert ledger["actor_completion_records_remaining"] == 0
    assert set(ledger["completed_actor_ids"]) == {str(a["organization_id"]) for a in register["actors"]}
    validate_f9_actor_completion_ledger(ledger, predecessor=predecessor)
    assert f9_bounded_exhaustion_state(ledger["completion_records"]) == "BOUNDED_FRAME_EXHAUSTED"
    assert ledger["f9_exhaustion_state"] == "BOUNDED_FRAME_EXHAUSTED"
