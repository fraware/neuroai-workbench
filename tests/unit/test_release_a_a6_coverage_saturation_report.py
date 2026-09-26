from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pytest

from neuroai_workbench.a5_snowball_discovery import A5_PREREG_SHA256, A5_STUDY_PACKET_SHA256
from neuroai_workbench.a6_saturation_analysis import (
    A6_PREREG_SHA256,
    A6_STUDY_BOUNDARY,
    A6_STUDY_PACKET_ID,
    A6_STUDY_PACKET_SHA256,
    EXPECTED_ROUND_METRICS,
    content_digest,
    load_default_a6_coverage_saturation_preregistration,
    load_default_a6_coverage_saturation_report,
    validate_a6_coverage_saturation_report,
)
from neuroai_workbench.product_discovery_frames import ProductDiscoveryError


def _rehash(packet: dict[str, Any]) -> None:
    packet["packet_sha256"] = content_digest(packet, exclude="packet_sha256")


def test_a6_report_binds_a2_through_a5_with_permitted_stop() -> None:
    packet = load_default_a6_coverage_saturation_report()
    prereg = load_default_a6_coverage_saturation_preregistration()

    assert packet["packet_id"] == A6_STUDY_PACKET_ID
    assert packet["packet_sha256"] == A6_STUDY_PACKET_SHA256
    assert content_digest(packet, exclude="packet_sha256") == A6_STUDY_PACKET_SHA256
    assert packet["preregistration_sha256"] == A6_PREREG_SHA256 == prereg["preregistration_sha256"]
    assert packet["a5_preregistration_sha256"] == A5_PREREG_SHA256
    assert packet["a5_study_sha256"] == A5_STUDY_PACKET_SHA256
    assert packet["boundary"] == A6_STUDY_BOUNDARY
    assert packet["new_canonical_allocations"] == 0

    rounds = packet["round_metrics"]
    assert len(rounds) == 3
    for expected, row in zip(EXPECTED_ROUND_METRICS, rounds, strict=True):
        for key, value in expected.items():
            assert row[key] == value

    stop = packet["stop_state_evidence"]
    assert stop["final_stop_state"] == "SATURATION_UNDER_DECLARED_PROTOCOL"
    assert stop["permitted"] is True
    assert packet["key_result"]["total_Y"] == 0
    assert "A7" in packet["next_required_state"]
    assert "not A8" in packet["next_required_state"]


def test_a6_report_decomposes_and_inventories_frames_fail_closed() -> None:
    packet = load_default_a6_coverage_saturation_report()
    decomp = packet["marginal_yield_decomposition"]
    assert decomp["by_source_frame"][0]["dimension_value"] == "F11"
    assert decomp["by_product_class"][0]["dimension_value"] == "NOT_ATTRIBUTABLE"
    assert decomp["by_capability_family"][0]["dimension_value"] == "NOT_ATTRIBUTABLE"
    assert all(row["Y_total"] == 0 and row["m"] == 0.0 for rows in decomp.values() for row in rows)

    inventory = packet["frame_coverage_stop_inventory"]
    assert [row["frame_id"] for row in inventory] == [
        "F1",
        "F2",
        "F3",
        "F4",
        "F5",
        "F6",
        "F7",
        "F8",
        "F9",
        "F10",
        "F11",
    ]
    assert inventory[6]["frame_id"] == "F7"
    assert inventory[6]["a6_permitted_stop_description"] == "BUDGET_COVERAGE_TERMINATION"
    assert inventory[6]["estimator_excluded"] is True
    assert inventory[8]["frame_id"] == "F9"
    assert inventory[8]["estimator_excluded"] is True
    assert inventory[10]["frame_id"] == "F11"
    assert inventory[10]["estimator_excluded"] is True


def test_a6_report_rejects_missing_fields_and_digest_drift() -> None:
    with pytest.raises(ProductDiscoveryError, match="missing fields"):
        validate_a6_coverage_saturation_report({})

    packet = deepcopy(load_default_a6_coverage_saturation_report())
    packet["packet_sha256"] = "0" * 64
    with pytest.raises(ProductDiscoveryError, match="content digest"):
        validate_a6_coverage_saturation_report(packet)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (lambda p: p.__setitem__("packet_id", "WRONG"), "packet_id must be"),
        (lambda p: p.__setitem__("status", "DRAFT"), "CONTROLLED_RESEARCH_PACKET"),
        (lambda p: p.__setitem__("study_id", "WRONG"), "study_id must be"),
        (lambda p: p.__setitem__("preregistration_id", "WRONG"), "preregistration_id"),
        (lambda p: p.__setitem__("preregistration_sha256", "0" * 64), "preregistration_sha256"),
        (lambda p: p.__setitem__("analysis_universe_id", "RAU-" + ("0" * 64)), "frozen A2 analysis universe"),
        (lambda p: p.__setitem__("world_time_cutoff", "2020-01-01"), "world_time_cutoff"),
        (lambda p: p.__setitem__("a2_checkpoint_sha256", "0" * 64), "frozen A2 checkpoint"),
        (lambda p: p.__setitem__("a5_study_sha256", "0" * 64), "a5_study_sha256"),
        (lambda p: p.__setitem__("boundary", "drift"), "boundary text drift"),
        (lambda p: p.__setitem__("new_canonical_allocations", 1), "new_canonical_allocations must be 0"),
        (lambda p: p.__setitem__("round_metrics", p["round_metrics"][:1]), "round_metrics must contain exactly"),
        (lambda p: p["round_metrics"][0].__setitem__("Y_r", 1), "Y_r"),
        (lambda p: p["round_metrics"][0].__setitem__("m_r", 0.5), "m_r"),
        (
            lambda p: p["marginal_yield_decomposition"]["by_source_frame"][0].__setitem__("Y_total", 1),
            "Y_total must be 0",
        ),
        (
            lambda p: p["marginal_yield_decomposition"]["by_product_class"][0].__setitem__(
                "dimension_value", "INVENTED"
            ),
            "NOT_ATTRIBUTABLE",
        ),
        (
            lambda p: p.__setitem__("frame_coverage_stop_inventory", p["frame_coverage_stop_inventory"][:3]),
            "F1–F11",
        ),
        (
            lambda p: p["frame_coverage_stop_inventory"][0].__setitem__(
                "a6_permitted_stop_description", "GLOBAL_COMPLETE"
            ),
            "a6_permitted_stop_description mismatch",
        ),
        (
            lambda p: p["frame_coverage_stop_inventory"][0].__setitem__("declared_stop_state", "GLOBAL_COMPLETE"),
            "declared_stop_state mismatch",
        ),
        (
            lambda p: p["frame_coverage_stop_inventory"][10].__setitem__("estimator_excluded", False),
            "estimator_excluded mismatch",
        ),
        (
            lambda p: p["stop_state_evidence"].__setitem__("final_stop_state", "GLOBAL_COMPLETE"),
            "final_stop_state",
        ),
        (
            lambda p: p["authority_controls"].__setitem__("protocol_saturation_is_not_global_completeness", False),
            "protocol_saturation_is_not_global_completeness",
        ),
        (
            lambda p: p["authority_controls"].__setitem__("does_not_start_a7_or_later", False),
            "does_not_start_a7_or_later",
        ),
        (lambda p: p["key_result"].__setitem__("total_Y", 1), "total_Y must be 0"),
        (
            lambda p: p.__setitem__("next_required_state", "Done forever"),
            "next_required_state must gate A7",
        ),
        (
            lambda p: p.__setitem__("next_required_state", "Next is A7 and A8 immediately"),
            "next_required_state must keep A8",
        ),
    ],
)
def test_a6_report_rejects_binding_and_authority_drift(
    mutator: Callable[[dict[str, Any]], Any],
    match: str,
) -> None:
    packet = deepcopy(load_default_a6_coverage_saturation_report())
    mutator(packet)
    if match != "content digest":
        _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match=match):
        validate_a6_coverage_saturation_report(packet)
