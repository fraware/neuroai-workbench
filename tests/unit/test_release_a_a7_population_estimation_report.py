from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pytest

from neuroai_workbench.a7_population_estimation import (
    A7_CAPTURE_HISTORY_SHA256,
    A7_MODEL_SPEC_SHA256,
    A7_STUDY_BOUNDARY,
    A7_STUDY_ID,
    A7_STUDY_PACKET_ID,
    A7_STUDY_PACKET_SHA256,
    EXPECTED_FAIL_CLOSED_REASONS,
    N_OBSERVED,
    POORLY_OBSERVED_CLASS_IDS,
    VALID_NO_ESTIMATE_OUTCOME,
    content_digest,
    load_default_a7_population_estimation_report,
    validate_a7_population_estimation_report,
)
from neuroai_workbench.product_discovery_frames import ProductDiscoveryError
from neuroai_workbench.release_a_preregistration import REQUIRED_MODEL_FAMILIES


def _rehash(packet: dict[str, Any]) -> None:
    packet["packet_sha256"] = content_digest(packet, exclude="packet_sha256")


def test_a7_estimation_report_fail_closes_without_forced_estimate() -> None:
    packet = load_default_a7_population_estimation_report()
    assert packet["packet_id"] == A7_STUDY_PACKET_ID
    assert packet["packet_sha256"] == A7_STUDY_PACKET_SHA256
    assert content_digest(packet, exclude="packet_sha256") == A7_STUDY_PACKET_SHA256
    assert packet["study_id"] == A7_STUDY_ID
    assert packet["boundary"] == A7_STUDY_BOUNDARY
    assert packet["model_specification_sha256"] == A7_MODEL_SPEC_SHA256
    assert packet["capture_history_dataset_sha256"] == A7_CAPTURE_HISTORY_SHA256

    assert packet["n_observed"] == N_OBSERVED
    assert packet["n_estimated"] is None
    assert packet["n_unobserved"] is None
    assert packet["coverage_estimated"] is None
    assert packet["estimation_outcome"] == "FAIL_CLOSED"
    assert packet["fail_closed_outcome"] == VALID_NO_ESTIMATE_OUTCOME
    assert set(packet["fail_closed_reasons"]) == set(EXPECTED_FAIL_CLOSED_REASONS)
    assert packet["headline_admissible_models"] == []
    assert packet["admissible_model_envelope"] is None
    assert packet["interval_or_sensitivity"] is None
    assert packet["key_result"]["n_observed"] == N_OBSERVED
    assert packet["key_result"]["n_estimated"] is None
    assert packet["next_required_state"] == "A8_PRODUCT_POPULATION_RELEASE_PACKAGE"
    assert packet["authority_controls"]["does_not_start_a8_or_ag"] is True
    assert packet["authority_controls"]["observed_count_reported_separately_from_estimate"] is True
    assert [item["model_family"] for item in packet["model_family_results"]] == list(REQUIRED_MODEL_FAMILIES)
    assert all(item["headline_admissible"] is False for item in packet["model_family_results"])
    assert all(item["fitted_unseen_estimate"] is False for item in packet["model_family_results"])
    assert [item["class_id"] for item in packet["classes_likely_poorly_observed"]] == list(POORLY_OBSERVED_CLASS_IDS)


def test_helpers_reject_non_objects() -> None:
    with pytest.raises(ProductDiscoveryError, match="missing fields"):
        validate_a7_population_estimation_report({})


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (lambda p: p.pop("status", None), "missing fields"),
        (lambda p: p.__setitem__("packet_id", "WRONG"), "packet_id must be"),
        (lambda p: p.__setitem__("status", "DRAFT"), "CONTROLLED_RESEARCH_PACKET"),
        (lambda p: p.__setitem__("packet_sha256", "0" * 64), "content digest"),
        (lambda p: p.__setitem__("n_observed", 7), "n_observed must be"),
        (lambda p: p.__setitem__("n_estimated", 100), "must not emit n_estimated"),
        (lambda p: p.__setitem__("estimation_outcome", "POINT_ESTIMATE"), "FAIL_CLOSED"),
        (lambda p: p.__setitem__("fail_closed_outcome", "WRONG"), "fail_closed_outcome drift"),
        (lambda p: p.__setitem__("model_specification_sha256", "0" * 64), "model_specification_sha256"),
        (lambda p: p.__setitem__("capture_history_dataset_sha256", "0" * 64), "capture_history_dataset_sha256"),
        (lambda p: p.__setitem__("headline_admissible_models", ["LOG_LINEAR_INDEPENDENCE_BASELINE"]), "must be empty"),
        (lambda p: p.__setitem__("admissible_model_envelope", [6, 100]), "must be null"),
        (lambda p: p.__setitem__("boundary", "drift"), "boundary text drift"),
        (lambda p: p["authority_controls"].__setitem__("does_not_start_a8_or_ag", False), "must be true"),
        (
            lambda p: p["model_family_results"][2].__setitem__("headline_admissible", True),
            "must not be headline-admissible",
        ),
        (
            lambda p: p["model_family_results"][3].__setitem__("fitted_unseen_estimate", True),
            "must not emit a fitted unseen estimate",
        ),
        (lambda p: p["key_result"].__setitem__("n_estimated", 50), "must not emit n_estimated"),
        (lambda p: p.__setitem__("next_required_state", "A-G"), "A8_PRODUCT_POPULATION_RELEASE_PACKAGE"),
    ],
)
def test_a7_report_rejects_semantic_drift(mutator: Callable[[dict[str, Any]], Any], match: str) -> None:
    packet = deepcopy(load_default_a7_population_estimation_report())
    mutator(packet)
    if match != "content digest":
        _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match=match):
        validate_a7_population_estimation_report(packet)
