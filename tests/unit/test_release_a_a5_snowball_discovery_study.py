from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from neuroai_workbench.a5_snowball_discovery import (
    A5_PREREG_SHA256,
    A5_STUDY_BOUNDARY,
    A5_STUDY_PACKET_ID,
    A5_STUDY_PACKET_SHA256,
    EXPECTED_ROUND_METRICS,
    F11_PACKET_SHA256,
    content_digest,
    load_default_a5_snowball_discovery_preregistration,
    load_default_a5_snowball_discovery_study,
    validate_a5_snowball_discovery_study,
)
from neuroai_workbench.product_discovery_frames import ProductDiscoveryError


def _rehash(packet: dict[str, Any]) -> None:
    packet["packet_sha256"] = content_digest(packet, exclude="packet_sha256")


def test_a5_study_reports_zero_yield_with_parent_seed_provenance() -> None:
    packet = load_default_a5_snowball_discovery_study()
    prereg = load_default_a5_snowball_discovery_preregistration()

    assert packet["packet_id"] == A5_STUDY_PACKET_ID
    assert packet["packet_sha256"] == A5_STUDY_PACKET_SHA256
    assert content_digest(packet, exclude="packet_sha256") == A5_STUDY_PACKET_SHA256
    assert packet["preregistration_sha256"] == A5_PREREG_SHA256 == prereg["preregistration_sha256"]
    assert packet["f11_execution_packet_sha256"] == F11_PACKET_SHA256
    assert packet["boundary"] == A5_STUDY_BOUNDARY
    assert packet["new_canonical_allocations"] == 0

    rounds = packet["round_metrics"]
    assert len(rounds) == 3
    for expected, row in zip(EXPECTED_ROUND_METRICS, rounds, strict=True):
        for key, value in expected.items():
            assert row[key] == value

    summary = packet["edge_provenance_summary"]
    assert summary["edge_count"] == 120
    assert summary["edges_with_parent_seed"] == 120
    assert summary["edges_missing_parent_seed"] == 0
    assert summary["edges_establishing_inclusion"] == 0
    assert summary["candidate_reentry_count"] == 120
    assert len(packet["edge_provenance_ledger"]) == 120
    assert all(edge["candidate_reentered"] is True for edge in packet["edge_provenance_ledger"])
    assert all(edge["edge_establishes_inclusion"] is False for edge in packet["edge_provenance_ledger"])

    stop = packet["stop_state_evidence"]
    assert stop["final_stop_state"] == "SATURATION_UNDER_DECLARED_PROTOCOL"
    assert stop["permitted"] is True
    assert packet["key_result"]["total_Y"] == 0
    assert "A6" in packet["next_required_state"]
    assert "not A7" in packet["next_required_state"] or "not A7–A8" in packet["next_required_state"]


def test_a5_study_decomposes_marginal_yield_fail_closed() -> None:
    packet = load_default_a5_snowball_discovery_study()
    decomp = packet["marginal_yield_decomposition"]
    assert decomp["by_source_frame"][0]["dimension_value"] == "F11"
    assert decomp["by_language"][0]["dimension_value"] == "en"
    assert decomp["by_jurisdiction"][0]["dimension_value"] == "GLOBAL"
    assert decomp["by_product_class"][0]["dimension_value"] == "NOT_ATTRIBUTABLE"
    assert decomp["by_capability_family"][0]["dimension_value"] == "NOT_ATTRIBUTABLE"
    assert [row["dimension_value"] for row in decomp["by_discovery_round"]] == ["R1", "R2", "R3"]
    assert all(row["Y_total"] == 0 and row["m"] == 0.0 for rows in decomp.values() for row in rows)

    families = packet["marginal_yield_by_f11_query_family"]
    assert len(families) == 6
    assert all(row["Y_total"] == 0 and row["m"] == 0.0 for row in families)


def test_a5_study_rejects_missing_fields_and_digest_drift() -> None:
    with pytest.raises(ProductDiscoveryError, match="missing fields"):
        validate_a5_snowball_discovery_study({})

    packet = deepcopy(load_default_a5_snowball_discovery_study())
    packet["packet_sha256"] = "0" * 64
    with pytest.raises(ProductDiscoveryError, match="content digest"):
        validate_a5_snowball_discovery_study(packet)


def test_a5_study_rejects_inclusion_from_edge_or_yield_inflation() -> None:
    packet = deepcopy(load_default_a5_snowball_discovery_study())
    packet["round_metrics"][0]["Y_r"] = 1
    packet["round_metrics"][0]["m_r"] = 1 / 40
    _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match="Y_r"):
        validate_a5_snowball_discovery_study(packet)

    packet = deepcopy(load_default_a5_snowball_discovery_study())
    packet["edge_provenance_ledger"][0]["edge_establishes_inclusion"] = True
    _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match="edge_establishes_inclusion"):
        validate_a5_snowball_discovery_study(packet)

    packet = deepcopy(load_default_a5_snowball_discovery_study())
    packet["stop_state_evidence"]["final_stop_state"] = "GLOBAL_COMPLETE"
    _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match="final_stop_state"):
        validate_a5_snowball_discovery_study(packet)

    packet = deepcopy(load_default_a5_snowball_discovery_study())
    packet["authority_controls"]["f7_f9_f11_estimator_excluded"] = False
    _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match="f7_f9_f11_estimator_excluded"):
        validate_a5_snowball_discovery_study(packet)
