from __future__ import annotations

import hashlib
import json
from importlib.resources import files
from typing import Any, cast

from neuroai_workbench.f9_actor_enumeration import (
    F9_ACTOR_ENUMERATION_PROCEDURE_SHA256,
    f9_bounded_exhaustion_state,
    f9_sole_product_detail_catalogue_risk,
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
PACKET_SHA256 = "c17567c3ec47875a4e0305bfcb46d4b3b6e15adc3fd5e2128ed0a73226ae5350"
LEDGER_SHA256 = "7af9f8324852dc300c586594095ff180bb668e401d6569e74884a5eb5e8ac833"


def _load(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(files(RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8")))


def _sha(value: dict[str, Any], field: str) -> str:
    material = {k: v for k, v in value.items() if k != field}
    return hashlib.sha256(
        json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def test_openbci_protocol_tranche_and_ledger() -> None:
    packet = _load("RELEASE_A_A2_F9_OPENBCI_PROTOCOL_TRANCHE_11.v1.0.json")
    ledger = _load("RELEASE_A_F9_ACTOR_COMPLETION_LEDGER_007.v1.0.json")
    predecessor = _load("RELEASE_A_F9_ACTOR_COMPLETION_LEDGER_006.v1.0.json")
    universe = load_default_analysis_universe()
    f9 = next(f for f in load_default_frame_register()["frames"] if f["frame_id"] == "F9")
    captures = cast(list[dict[str, Any]], packet["captures"])
    assert packet["packet_sha256"] == PACKET_SHA256 == _sha(packet, "packet_sha256")
    assert packet["f9_enumeration_procedure_sha256"] == F9_ACTOR_ENUMERATION_PROCEDURE_SHA256
    assert packet["actors_accounted_in_this_tranche"] == ["ORG-0017"]
    assert packet["cumulative_actors_accounted_count"] == 26
    assert len(captures) == 24
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
        assert f9_sole_product_detail_catalogue_risk(record) is None
    assert ledger["ledger_sha256"] == LEDGER_SHA256 == _sha(ledger, "ledger_sha256")
    assert ledger["completion_record_count"] == 26
    validate_f9_actor_completion_ledger(ledger, predecessor=predecessor)
    assert f9_bounded_exhaustion_state(ledger["completion_records"]) == "CONTINUE"
