from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pytest

from neuroai_workbench.a4_multilingual_sensitivity import A4_PREREG_SHA256, A4_STUDY_PACKET_SHA256
from neuroai_workbench.a5_snowball_discovery import (
    A5_BOUNDARY,
    A5_PREREG_ID,
    A5_PREREG_SHA256,
    A5_STUDY_ID,
    EDGE_TAXONOMY_SET_ID,
    F11_PACKET_SHA256,
    F11_QUERY_FAMILY_BINDINGS,
    PERMITTED_STOP_DESCRIPTIONS,
    REQUIRED_DECOMPOSITION_DIMENSIONS,
    REQUIRED_EDGE_TYPE_IDS,
    REQUIRED_ROUND_METRICS,
    a5_freeze_does_not_compute_round_metrics,
    compute_round_metrics,
    content_digest,
    load_default_a5_snowball_discovery_preregistration,
    validate_a5_snowball_discovery_preregistration,
)
from neuroai_workbench.open_world_round_protocol import PROTOCOL_SHA256, UNIVERSE_SHA256
from neuroai_workbench.product_discovery_frames import ProductDiscoveryError


def _rehash(prereg: dict[str, Any]) -> None:
    prereg["preregistration_sha256"] = content_digest(prereg, exclude="preregistration_sha256")


def test_a5_preregistration_is_content_bound_before_yield() -> None:
    prereg = load_default_a5_snowball_discovery_preregistration()
    validate_a5_snowball_discovery_preregistration(prereg)

    assert prereg["preregistration_id"] == A5_PREREG_ID
    assert prereg["preregistration_sha256"] == A5_PREREG_SHA256
    assert content_digest(prereg, exclude="preregistration_sha256") == A5_PREREG_SHA256
    assert prereg["study_id"] == A5_STUDY_ID
    assert prereg["edge_taxonomy_set_id"] == EDGE_TAXONOMY_SET_ID
    assert prereg["boundary"] == A5_BOUNDARY
    assert a5_freeze_does_not_compute_round_metrics() == "PREREGISTERED_AWAITING_EXECUTION"

    assert prereg["open_world_round_protocol_sha256"] == PROTOCOL_SHA256
    assert prereg["f11_query_universe_sha256"] == UNIVERSE_SHA256["F11"]
    assert prereg["f11_execution_packet_sha256"] == F11_PACKET_SHA256
    assert prereg["a4_preregistration_sha256"] == A4_PREREG_SHA256
    assert prereg["a4_study_sha256"] == A4_STUDY_PACKET_SHA256

    edge_ids = [row["edge_type_id"] for row in prereg["edge_types"]]
    assert tuple(edge_ids) == REQUIRED_EDGE_TYPE_IDS
    for row in prereg["edge_types"]:
        assert row["f11_query_family_binding"] == F11_QUERY_FAMILY_BINDINGS[row["edge_type_id"]]

    parent = prereg["parent_seed_rules"]
    assert parent["snowball_edge_never_establishes_inclusion"] is True
    assert parent["generated_object_reenters_as_candidate"] is True
    assert parent["no_inclusion_from_edge_alone"] is True

    metrics = prereg["metrics_contract"]
    assert tuple(metrics["primary_round_metrics"]) == REQUIRED_ROUND_METRICS
    assert tuple(metrics["decomposition_dimensions"]) == REQUIRED_DECOMPOSITION_DIMENSIONS
    assert metrics["formula_m_r"] == "m_r = Y_r / Candidates_r"

    assert tuple(prereg["permitted_stop_descriptions"]) == PERMITTED_STOP_DESCRIPTIONS
    gate = prereg["execution_gate"]
    assert gate["freeze_alone_does_not_compute_round_metrics"] is True
    assert gate["does_not_start_a6_or_later"] is True
    assert gate["f7_f9_f11_remain_estimator_excluded"] is True


def test_round_metrics_use_exact_y_over_candidates() -> None:
    result = compute_round_metrics(y_r=0, d_r=15, x_r=0, u_r=4, candidates_r=40)
    assert result["Y_r"] == 0
    assert result["D_r"] == 15
    assert result["X_r"] == 0
    assert result["U_r"] == 4
    assert result["Candidates_r"] == 40
    assert result["m_r"] == 0.0

    result = compute_round_metrics(y_r=2, d_r=1, x_r=0, u_r=1, candidates_r=20)
    assert result["m_r"] == pytest.approx(0.1)

    with pytest.raises(ProductDiscoveryError, match="positive"):
        compute_round_metrics(y_r=0, d_r=0, x_r=0, u_r=0, candidates_r=0)

    with pytest.raises(ProductDiscoveryError, match="negative"):
        compute_round_metrics(y_r=-1, d_r=0, x_r=0, u_r=0, candidates_r=10)


def test_helpers_reject_non_objects() -> None:
    with pytest.raises(ProductDiscoveryError, match="missing fields"):
        validate_a5_snowball_discovery_preregistration({})


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (lambda p: p.pop("status", None), "missing fields"),
        (lambda p: p.__setitem__("preregistration_id", "WRONG"), "preregistration_id must be"),
        (lambda p: p.__setitem__("status", "DRAFT"), "must be FROZEN_v1.0"),
        (lambda p: p.__setitem__("study_id", "WRONG"), "study_id must be"),
        (lambda p: p.__setitem__("preregistration_sha256", "0" * 64), "content digest"),
        (lambda p: p.__setitem__("analysis_universe_id", "RAU-" + ("0" * 64)), "frozen A2 analysis universe"),
        (lambda p: p.__setitem__("world_time_cutoff", "2020-01-01"), "world_time_cutoff"),
        (lambda p: p.__setitem__("knowledge_time_cutoff", "2020-01-01T00:00:00Z"), "knowledge_time_cutoff"),
        (lambda p: p.__setitem__("a2_checkpoint_id", "WRONG"), "frozen A2 checkpoint"),
        (lambda p: p.__setitem__("a2_checkpoint_sha256", "0" * 64), "frozen A2 checkpoint"),
        (lambda p: p.__setitem__("round_start_known_identity_set_sha256", "0" * 64), "A1 known-identity"),
        (lambda p: p.__setitem__("language_scope_id", "EN_ONLY"), "language_scope_id"),
        (lambda p: p.__setitem__("frame_register_version", "WRONG"), "frame_register_version"),
        (lambda p: p.__setitem__("frame_register_blob_sha", "0" * 40), "frame_register_blob_sha"),
        (lambda p: p.__setitem__("open_world_round_protocol_id", "WRONG"), "open_world_round_protocol_id"),
        (lambda p: p.__setitem__("open_world_round_protocol_sha256", "0" * 64), "open_world_round_protocol_sha256"),
        (lambda p: p.__setitem__("f11_query_universe_id", "WRONG"), "f11_query_universe_id"),
        (lambda p: p.__setitem__("f11_query_universe_sha256", "0" * 64), "f11_query_universe_sha256"),
        (lambda p: p.__setitem__("f11_execution_packet_id", "WRONG"), "f11_execution_packet_id"),
        (lambda p: p.__setitem__("f11_execution_packet_sha256", "0" * 64), "f11_execution_packet_sha256"),
        (lambda p: p.__setitem__("a3_preregistration_id", "WRONG"), "a3_preregistration_id"),
        (lambda p: p.__setitem__("a3_preregistration_sha256", "0" * 64), "a3_preregistration_sha256"),
        (lambda p: p.__setitem__("a3_study_id", "WRONG"), "a3_study_id"),
        (lambda p: p.__setitem__("a3_study_sha256", "0" * 64), "a3_study_sha256"),
        (lambda p: p.__setitem__("a4_preregistration_id", "WRONG"), "a4_preregistration_id"),
        (lambda p: p.__setitem__("a4_preregistration_sha256", "0" * 64), "a4_preregistration_sha256"),
        (lambda p: p.__setitem__("a4_study_id", "WRONG"), "a4_study_id"),
        (lambda p: p.__setitem__("a4_study_sha256", "0" * 64), "a4_study_sha256"),
        (lambda p: p.__setitem__("edge_taxonomy_set_id", "WRONG"), "edge_taxonomy_set_id"),
        (lambda p: p.__setitem__("boundary", "drift"), "boundary text drift"),
        (lambda p: p.__setitem__("edge_types", p["edge_types"][:-1]), "edge_types"),
        (
            lambda p: p["edge_types"][0].__setitem__("f11_query_family_binding", "WRONG"),
            "f11_query_family_binding",
        ),
        (
            lambda p: p["parent_seed_rules"].__setitem__("snowball_edge_never_establishes_inclusion", False),
            "snowball_edge_never_establishes_inclusion",
        ),
        (
            lambda p: p["parent_seed_rules"].__setitem__("generated_object_reenters_as_candidate", False),
            "generated_object_reenters_as_candidate",
        ),
        (
            lambda p: p["parent_seed_rules"].__setitem__("no_inclusion_from_edge_alone", False),
            "no_inclusion_from_edge_alone",
        ),
        (
            lambda p: p["evidence_substrate"].__setitem__("controlled_snowball_frame_id", "F1"),
            "controlled_snowball_frame_id must be F11",
        ),
        (
            lambda p: p["evidence_substrate"].__setitem__("f7_f9_f11_estimator_excluded", False),
            "f7_f9_f11_estimator_excluded must be true",
        ),
        (
            lambda p: p["evidence_substrate"].__setitem__("capture_estimation_eligible", True),
            "capture_estimation_eligible must be false",
        ),
        (
            lambda p: p["evidence_substrate"].__setitem__("no_identity_allocation_by_implication", False),
            "no_identity_allocation_by_implication must be true",
        ),
        (
            lambda p: p["evidence_substrate"].__setitem__("post_cutoff_include_requires_world_time_support_ref", False),
            "post_cutoff_include_requires_world_time_support_ref must be true",
        ),
        (
            lambda p: p["evidence_substrate"].__setitem__("minimum_rounds", ["R1"]),
            "minimum_rounds must be R1",
        ),
        (
            lambda p: p["metrics_contract"].__setitem__("primary_round_metrics", ["Y_r"]),
            "primary_round_metrics must be",
        ),
        (
            lambda p: p["metrics_contract"].__setitem__("formula_m_r", "m_r = D_r / Candidates_r"),
            "formula_m_r",
        ),
        (
            lambda p: p["metrics_contract"].__setitem__("decomposition_dimensions", ["SOURCE_FRAME"]),
            "decomposition_dimensions",
        ),
        (
            lambda p: p["metrics_contract"]["decomposition_policy"].__setitem__(
                "no_post_hoc_dimension_invention", False
            ),
            "no_post_hoc_dimension_invention must be true",
        ),
        (
            lambda p: p["metrics_contract"]["denominator_rules"].__setitem__(
                "raw_edges_are_not_validated_products", False
            ),
            "raw_edges_are_not_validated_products must be true",
        ),
        (
            lambda p: p["metrics_contract"]["denominator_rules"].__setitem__(
                "only_include_resolved_exact_offering_ids_enter_y_r", False
            ),
            "only_include_resolved_exact_offering_ids_enter_y_r must be true",
        ),
        (
            lambda p: p.__setitem__(
                "permitted_stop_descriptions",
                list(PERMITTED_STOP_DESCRIPTIONS) + ["GLOBAL_COMPLETE"],
            ),
            "permitted_stop_descriptions",
        ),
        (
            lambda p: p["stop_semantics"].__setitem__("stop_never_means_global_completeness", False),
            "stop_never_means_global_completeness must be true",
        ),
        (
            lambda p: p["stop_semantics"].__setitem__("minimum_completed_rounds", 1),
            "minimum_completed_rounds must be 3",
        ),
        (
            lambda p: p["stop_semantics"].__setitem__("consecutive_low_yield_rounds", 1),
            "consecutive_low_yield_rounds must be 2",
        ),
        (
            lambda p: p["stop_semantics"].__setitem__("maximum_marginal_new_identity_yield", 0.5),
            "maximum_marginal_new_identity_yield must be 0.05",
        ),
        (
            lambda p: p["stop_semantics"].__setitem__("minimum_raw_candidates_per_round", 1),
            "minimum_raw_candidates_per_round must be 20",
        ),
        (
            lambda p: p["execution_gate"].__setitem__("does_not_start_a6_or_later", False),
            "does_not_start_a6_or_later must be true",
        ),
        (
            lambda p: p["execution_gate"].__setitem__("snowball_edge_never_establishes_inclusion", False),
            "snowball_edge_never_establishes_inclusion must be true",
        ),
        (
            lambda p: p["execution_gate"].__setitem__("f7_f9_f11_remain_estimator_excluded", False),
            "f7_f9_f11_remain_estimator_excluded must be true",
        ),
        (
            lambda p: p.__setitem__("predeclaration_rule", "choose edges freely after yield"),
            "predeclaration_rule must forbid",
        ),
        (
            lambda p: p.__setitem__(
                "predeclaration_rule",
                "Post-hoc edge edits are prohibited but edges may establish inclusion.",
            ),
            "never establishes inclusion",
        ),
    ],
)
def test_a5_preregistration_rejects_post_hoc_and_binding_drift(
    mutator: Callable[[dict[str, Any]], Any],
    match: str,
) -> None:
    prereg = deepcopy(load_default_a5_snowball_discovery_preregistration())
    mutator(prereg)
    if match != "content digest":
        _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match=match):
        validate_a5_snowball_discovery_preregistration(prereg)
