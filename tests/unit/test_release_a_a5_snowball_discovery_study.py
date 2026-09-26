from __future__ import annotations

from collections.abc import Callable
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
        (lambda p: p.__setitem__("knowledge_time_cutoff", "2020-01-01T00:00:00Z"), "knowledge_time_cutoff"),
        (lambda p: p.__setitem__("a2_checkpoint_id", "WRONG"), "frozen A2 checkpoint"),
        (lambda p: p.__setitem__("a2_checkpoint_sha256", "0" * 64), "frozen A2 checkpoint"),
        (lambda p: p.__setitem__("round_start_known_identity_set_sha256", "0" * 64), "A1 known-identity"),
        (lambda p: p.__setitem__("final_known_identity_set_sha256", "0" * 64), "A1 known-identity"),
        (lambda p: p.__setitem__("language_scope_id", "EN_ONLY"), "language_scope_id"),
        (lambda p: p.__setitem__("edge_taxonomy_set_id", "WRONG"), "edge_taxonomy_set_id"),
        (lambda p: p.__setitem__("open_world_round_protocol_id", "WRONG"), "open_world_round_protocol_id"),
        (lambda p: p.__setitem__("open_world_round_protocol_sha256", "0" * 64), "open_world_round_protocol_sha256"),
        (lambda p: p.__setitem__("f11_query_universe_id", "WRONG"), "f11_query_universe_id"),
        (lambda p: p.__setitem__("f11_query_universe_sha256", "0" * 64), "f11_query_universe_sha256"),
        (lambda p: p.__setitem__("f11_execution_packet_id", "WRONG"), "f11_execution_packet_id"),
        (lambda p: p.__setitem__("f11_execution_packet_sha256", "0" * 64), "f11_execution_packet_sha256"),
        (lambda p: p.__setitem__("a4_study_id", "WRONG"), "a4_study_id"),
        (lambda p: p.__setitem__("a4_study_sha256", "0" * 64), "a4_study_sha256"),
        (lambda p: p.__setitem__("boundary", "drift"), "boundary text drift"),
        (lambda p: p.__setitem__("new_canonical_allocations", 1), "new_canonical_allocations must be 0"),
        (
            lambda p: p.__setitem__("final_known_identity_ids", ["PRD-EMOTIV-EPOC-X"]),
            "final_known_identity_ids must equal",
        ),
        (
            lambda p: p["evidence_substrate_bindings"].__setitem__("controlled_snowball_frame_id", "F1"),
            "controlled_snowball_frame_id must be F11",
        ),
        (
            lambda p: p["evidence_substrate_bindings"].__setitem__("source_packets", []),
            "source_packets must bind exactly",
        ),
        (
            lambda p: p["evidence_substrate_bindings"]["source_packets"][0].__setitem__("packet_sha256", "0" * 64),
            "F11 source packet digest drift",
        ),
        (
            lambda p: p["evidence_substrate_bindings"]["source_packets"][0].__setitem__(
                "new_validated_product_count", 1
            ),
            "new_validated_product_count must be 0",
        ),
        (lambda p: p.__setitem__("round_metrics", p["round_metrics"][:1]), "round_metrics must contain exactly"),
        (lambda p: p["round_metrics"][0].__setitem__("Y_r", 1), "Y_r"),
        (lambda p: p["round_metrics"][0].__setitem__("m_r", 0.5), "m_r"),
        (
            lambda p: p["round_metrics"][0].__setitem__("known_identity_duplicate_count", 0),
            "D_r must equal",
        ),
        (lambda p: p["edge_provenance_summary"].__setitem__("edge_count", 1), "edge_count must be 120"),
        (
            lambda p: p["edge_provenance_summary"].__setitem__("edges_missing_parent_seed", 1),
            "edges_missing_parent_seed must be 0",
        ),
        (
            lambda p: p["edge_provenance_summary"].__setitem__("edges_establishing_inclusion", 1),
            "edges_establishing_inclusion must be 0",
        ),
        (
            lambda p: p["edge_provenance_summary"].__setitem__("all_parents_among_a1_known_identities", False),
            "all_parents_among_a1_known_identities must be true",
        ),
        (lambda p: p.__setitem__("edge_provenance_ledger", p["edge_provenance_ledger"][:10]), "120 edges"),
        (
            lambda p: p["edge_provenance_ledger"][0].__setitem__("parent_seed_offering_id", "PRD-FAKE"),
            "parent_seed_offering_id must be among A1",
        ),
        (
            lambda p: p["edge_provenance_ledger"][0].__setitem__("candidate_reentered", False),
            "candidate_reentered must be true",
        ),
        (
            lambda p: p["edge_provenance_ledger"][0].__setitem__("edge_establishes_inclusion", True),
            "edge_establishes_inclusion must be false",
        ),
        (
            lambda p: p["edge_provenance_ledger"][0].__setitem__("f11_query_family", "UNKNOWN"),
            "unexpected f11_query_family",
        ),
        (
            lambda p: p["marginal_yield_decomposition"]["by_source_frame"][0].__setitem__("Y_total", 1),
            "Y_total must be 0",
        ),
        (
            lambda p: p["marginal_yield_decomposition"]["by_language"][0].__setitem__("m", 0.1),
            "m must be 0.0",
        ),
        (
            lambda p: p.__setitem__(
                "marginal_yield_by_f11_query_family",
                p["marginal_yield_by_f11_query_family"][:1],
            ),
            "six F11 query families",
        ),
        (
            lambda p: p["stop_state_evidence"].__setitem__("final_stop_state", "GLOBAL_COMPLETE"),
            "final_stop_state",
        ),
        (
            lambda p: p["stop_state_evidence"].__setitem__("permitted", False),
            "permitted must be true",
        ),
        (
            lambda p: p["stop_state_evidence"].__setitem__("each_qualifying_round_raw_candidates_gte_20", False),
            "each_qualifying_round_raw_candidates_gte_20 must be true",
        ),
        (
            lambda p: p["authority_controls"].__setitem__("f7_f9_f11_estimator_excluded", False),
            "f7_f9_f11_estimator_excluded",
        ),
        (
            lambda p: p["authority_controls"].__setitem__("no_inclusion_from_edge_alone", False),
            "no_inclusion_from_edge_alone",
        ),
        (
            lambda p: p["key_result"].__setitem__("headline", "WRONG"),
            "CONTROLLED_SNOWBALL_ROUND_METRICS",
        ),
        (lambda p: p["key_result"].__setitem__("total_Y", 1), "total_Y must be 0"),
        (
            lambda p: p.__setitem__("next_required_state", "Done forever"),
            "next_required_state must gate A6",
        ),
        (
            lambda p: p.__setitem__("next_required_state", "Next is A6 only"),
            "next_required_state must keep A7",
        ),
    ],
)
def test_a5_study_rejects_binding_and_authority_drift(
    mutator: Callable[[dict[str, Any]], Any],
    match: str,
) -> None:
    packet = deepcopy(load_default_a5_snowball_discovery_study())
    mutator(packet)
    if match != "content digest":
        _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match=match):
        validate_a5_snowball_discovery_study(packet)
