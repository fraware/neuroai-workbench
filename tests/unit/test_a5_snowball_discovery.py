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


def test_a5_preregistration_rejects_digest_drift_and_post_hoc_edge_edits() -> None:
    with pytest.raises(ProductDiscoveryError, match="missing fields"):
        validate_a5_snowball_discovery_preregistration({})

    prereg = deepcopy(load_default_a5_snowball_discovery_preregistration())
    prereg["preregistration_sha256"] = "0" * 64
    with pytest.raises(ProductDiscoveryError, match="content digest"):
        validate_a5_snowball_discovery_preregistration(prereg)

    prereg = deepcopy(load_default_a5_snowball_discovery_preregistration())
    prereg["edge_types"] = prereg["edge_types"][:-1]
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="edge_types"):
        validate_a5_snowball_discovery_preregistration(prereg)

    prereg = deepcopy(load_default_a5_snowball_discovery_preregistration())
    prereg["parent_seed_rules"]["snowball_edge_never_establishes_inclusion"] = False
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="snowball_edge_never_establishes_inclusion"):
        validate_a5_snowball_discovery_preregistration(prereg)

    prereg = deepcopy(load_default_a5_snowball_discovery_preregistration())
    prereg["permitted_stop_descriptions"] = list(PERMITTED_STOP_DESCRIPTIONS) + ["GLOBAL_COMPLETE"]
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="permitted_stop_descriptions"):
        validate_a5_snowball_discovery_preregistration(prereg)

    prereg = deepcopy(load_default_a5_snowball_discovery_preregistration())
    prereg["evidence_substrate"]["capture_estimation_eligible"] = True
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="capture_estimation_eligible"):
        validate_a5_snowball_discovery_preregistration(prereg)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda p: p.__setitem__("a4_study_sha256", "0" * 64),
            "a4_study_sha256",
        ),
        (
            lambda p: p["execution_gate"].__setitem__("does_not_start_a6_or_later", False),
            "does_not_start_a6_or_later",
        ),
        (
            lambda p: p["metrics_contract"].__setitem__("formula_m_r", "m_r = D_r / Candidates_r"),
            "formula_m_r",
        ),
    ],
)
def test_a5_preregistration_fail_closed_mutations(
    mutator: Callable[[dict[str, Any]], None],
    match: str,
) -> None:
    prereg = deepcopy(load_default_a5_snowball_discovery_preregistration())
    mutator(prereg)
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match=match):
        validate_a5_snowball_discovery_preregistration(prereg)
