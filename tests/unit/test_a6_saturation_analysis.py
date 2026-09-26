from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pytest

from neuroai_workbench.a5_snowball_discovery import A5_PREREG_SHA256, A5_STUDY_PACKET_SHA256
from neuroai_workbench.a6_saturation_analysis import (
    A6_BOUNDARY,
    A6_PREREG_ID,
    A6_PREREG_SHA256,
    A6_STUDY_ID,
    COVERAGE_INVENTORY_FRAMES,
    FRAME_STOP_MAPPING,
    PERMITTED_STOP_DESCRIPTIONS,
    REQUIRED_DECOMPOSITION_DIMENSIONS,
    REQUIRED_REPORT_SECTIONS,
    REQUIRED_ROUND_METRICS,
    a6_freeze_does_not_emit_coverage_report,
    content_digest,
    load_default_a6_coverage_saturation_preregistration,
    map_frame_stop_to_permitted,
    validate_a6_coverage_saturation_preregistration,
)
from neuroai_workbench.product_discovery_frames import ProductDiscoveryError


def _rehash(prereg: dict[str, Any]) -> None:
    prereg["preregistration_sha256"] = content_digest(prereg, exclude="preregistration_sha256")


def test_a6_preregistration_is_content_bound_before_report() -> None:
    prereg = load_default_a6_coverage_saturation_preregistration()
    validate_a6_coverage_saturation_preregistration(prereg)

    assert prereg["preregistration_id"] == A6_PREREG_ID
    assert prereg["preregistration_sha256"] == A6_PREREG_SHA256
    assert content_digest(prereg, exclude="preregistration_sha256") == A6_PREREG_SHA256
    assert prereg["study_id"] == A6_STUDY_ID
    assert prereg["boundary"] == A6_BOUNDARY
    assert a6_freeze_does_not_emit_coverage_report() == "PREREGISTERED_AWAITING_EXECUTION"

    assert prereg["a5_preregistration_sha256"] == A5_PREREG_SHA256
    assert prereg["a5_study_sha256"] == A5_STUDY_PACKET_SHA256
    assert tuple(prereg["required_report_sections"]) == REQUIRED_REPORT_SECTIONS
    assert tuple(prereg["metrics_contract"]["primary_round_metrics"]) == REQUIRED_ROUND_METRICS
    assert tuple(prereg["metrics_contract"]["decomposition_dimensions"]) == REQUIRED_DECOMPOSITION_DIMENSIONS
    assert tuple(prereg["permitted_stop_descriptions"]) == PERMITTED_STOP_DESCRIPTIONS
    assert tuple(prereg["evidence_substrate"]["coverage_inventory_frames"]) == COVERAGE_INVENTORY_FRAMES
    assert prereg["execution_gate"]["does_not_start_a7_or_later"] is True
    assert prereg["execution_gate"]["protocol_saturation_never_means_global_completeness"] is True


def test_frame_stop_mapping_is_fail_closed() -> None:
    assert map_frame_stop_to_permitted("SATURATION_UNDER_DECLARED_PROTOCOL") == "SATURATION_UNDER_DECLARED_PROTOCOL"
    assert map_frame_stop_to_permitted("BOUNDED_FRAME_EXHAUSTED") == "BOUNDED_SOURCE_EXHAUSTION"
    assert map_frame_stop_to_permitted("MANUAL_DECLARED_LIMIT") == "BUDGET_COVERAGE_TERMINATION"
    assert dict(FRAME_STOP_MAPPING)["UNRESOLVED_SOURCE_BARRIER"] == "UNRESOLVED_SOURCE_BARRIER"
    with pytest.raises(ProductDiscoveryError, match="undeclared frame stop"):
        map_frame_stop_to_permitted("GLOBAL_COMPLETE")


def test_helpers_reject_non_objects() -> None:
    with pytest.raises(ProductDiscoveryError, match="missing fields"):
        validate_a6_coverage_saturation_preregistration({})


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
        (lambda p: p.__setitem__("a3_preregistration_id", "WRONG"), "a3_preregistration_id"),
        (lambda p: p.__setitem__("a3_preregistration_sha256", "0" * 64), "a3_preregistration_sha256"),
        (lambda p: p.__setitem__("a3_study_id", "WRONG"), "a3_study_id"),
        (lambda p: p.__setitem__("a3_study_sha256", "0" * 64), "a3_study_sha256"),
        (lambda p: p.__setitem__("a4_preregistration_id", "WRONG"), "a4_preregistration_id"),
        (lambda p: p.__setitem__("a4_preregistration_sha256", "0" * 64), "a4_preregistration_sha256"),
        (lambda p: p.__setitem__("a4_study_id", "WRONG"), "a4_study_id"),
        (lambda p: p.__setitem__("a4_study_sha256", "0" * 64), "a4_study_sha256"),
        (lambda p: p.__setitem__("a5_preregistration_id", "WRONG"), "a5_preregistration_id"),
        (lambda p: p.__setitem__("a5_preregistration_sha256", "0" * 64), "a5_preregistration_sha256"),
        (lambda p: p.__setitem__("a5_study_id", "WRONG"), "a5_study_id"),
        (lambda p: p.__setitem__("a5_study_sha256", "0" * 64), "a5_study_sha256"),
        (lambda p: p.__setitem__("report_contract_id", "WRONG"), "report_contract_id"),
        (lambda p: p.__setitem__("boundary", "drift"), "boundary text drift"),
        (lambda p: p.__setitem__("required_report_sections", ["UPSTREAM_DIGEST_BINDINGS"]), "required_report_sections"),
        (
            lambda p: p["metrics_contract"].__setitem__("primary_round_metrics", ["Y_r"]),
            "primary_round_metrics must be",
        ),
        (
            lambda p: p["metrics_contract"].__setitem__("formula_m_r", "m_r = D_r / Candidates_r"),
            "formula_m_r",
        ),
        (
            lambda p: p["metrics_contract"].__setitem__("primary_metrics_source", "WRONG"),
            "primary_metrics_source",
        ),
        (
            lambda p: p["metrics_contract"].__setitem__("decomposition_dimensions", ["SOURCE_FRAME"]),
            "decomposition_dimensions",
        ),
        (
            lambda p: p["metrics_contract"]["decomposition_policy"].__setitem__(
                "reuse_a5_declared_decompositions", False
            ),
            "reuse_a5_declared_decompositions must be true",
        ),
        (
            lambda p: p["metrics_contract"]["decomposition_policy"].__setitem__(
                "fail_closed_missing_dimension", "INVENT"
            ),
            "fail_closed_missing_dimension must be NOT_ATTRIBUTABLE",
        ),
        (
            lambda p: p["metrics_contract"]["denominator_rules"].__setitem__(
                "protocol_saturation_is_not_global_completeness", False
            ),
            "protocol_saturation_is_not_global_completeness must be true",
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
            lambda p: p["stop_semantics"].__setitem__("frame_stop_mapping", {"X": "Y"}),
            "frame_stop_mapping must equal",
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
            lambda p: p["evidence_substrate"].__setitem__("coverage_inventory_frames", ["F1"]),
            "coverage_inventory_frames must be F1",
        ),
        (
            lambda p: p["execution_gate"].__setitem__("does_not_start_a7_or_later", False),
            "does_not_start_a7_or_later must be true",
        ),
        (
            lambda p: p["execution_gate"].__setitem__("protocol_saturation_never_means_global_completeness", False),
            "protocol_saturation_never_means_global_completeness must be true",
        ),
        (
            lambda p: p.__setitem__("predeclaration_rule", "choose stops freely after yield"),
            "predeclaration_rule must forbid",
        ),
        (
            lambda p: p.__setitem__(
                "predeclaration_rule",
                "Post-hoc edits are prohibited and worldwide completeness is allowed.",
            ),
            "refuse global-completeness",
        ),
    ],
)
def test_a6_preregistration_rejects_post_hoc_and_binding_drift(
    mutator: Callable[[dict[str, Any]], Any],
    match: str,
) -> None:
    prereg = deepcopy(load_default_a6_coverage_saturation_preregistration())
    mutator(prereg)
    if match != "content digest":
        _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match=match):
        validate_a6_coverage_saturation_preregistration(prereg)
