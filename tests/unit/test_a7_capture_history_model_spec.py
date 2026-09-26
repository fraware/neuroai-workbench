from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pytest

from neuroai_workbench.a6_saturation_analysis import A6_PREREG_SHA256, A6_STUDY_PACKET_SHA256
from neuroai_workbench.a7_population_estimation import (
    A7_CAPTURE_HISTORY_BOUNDARY,
    A7_CAPTURE_HISTORY_ID,
    A7_CAPTURE_HISTORY_SHA256,
    A7_ELIGIBLE_CAPTURE_RECORDS_SHA256,
    A7_MODEL_SPEC_BOUNDARY,
    A7_MODEL_SPEC_ID,
    A7_MODEL_SPEC_SHA256,
    A7_STUDY_ID,
    FAIL_CLOSED_REASONS,
    IDENTIFIABILITY_THRESHOLDS,
    N_OBSERVED,
    OBSERVED_OFFERING_IDS,
    VALID_NO_ESTIMATE_OUTCOME,
    a7_freeze_does_not_fit_models,
    compile_capture_history_rows_from_resources,
    content_digest,
    estimator_eligible_rows,
    evaluate_identifiability_gate,
    load_default_a7_capture_history_dataset,
    load_default_a7_population_model_specification,
    offering_binary_histories,
    records_digest,
    validate_a7_capture_history_dataset,
    validate_a7_population_model_specification,
)
from neuroai_workbench.product_discovery_frames import (
    A1_INITIAL_KNOWN_IDENTITY_SHA256,
    PRIMARY_ESTIMATION_EXCLUDED_FRAME_IDS,
    ProductDiscoveryError,
)
from neuroai_workbench.release_a_preregistration import (
    FRAME_SET_SENSITIVITIES,
    PRIMARY_ESTIMATION_FRAME_IDS,
    REQUIRED_MODEL_FAMILIES,
)


def _rehash_dataset(dataset: dict[str, Any]) -> None:
    dataset["dataset_sha256"] = content_digest(dataset, exclude="dataset_sha256")


def _rehash_spec(spec: dict[str, Any]) -> None:
    spec["specification_sha256"] = content_digest(spec, exclude="specification_sha256")


def test_a7_capture_history_and_model_spec_are_content_bound_before_fit() -> None:
    dataset = load_default_a7_capture_history_dataset()
    spec = load_default_a7_population_model_specification()

    assert dataset["dataset_id"] == A7_CAPTURE_HISTORY_ID
    assert dataset["dataset_sha256"] == A7_CAPTURE_HISTORY_SHA256
    assert content_digest(dataset, exclude="dataset_sha256") == A7_CAPTURE_HISTORY_SHA256
    assert dataset["boundary"] == A7_CAPTURE_HISTORY_BOUNDARY
    assert dataset["n_observed"] == N_OBSERVED
    assert tuple(dataset["observed_offering_ids"]) == OBSERVED_OFFERING_IDS
    assert dataset["observed_offering_set_sha256"] == A1_INITIAL_KNOWN_IDENTITY_SHA256
    assert dataset["a6_preregistration_sha256"] == A6_PREREG_SHA256
    assert dataset["a6_study_sha256"] == A6_STUDY_PACKET_SHA256

    assert spec["specification_id"] == A7_MODEL_SPEC_ID
    assert spec["specification_sha256"] == A7_MODEL_SPEC_SHA256
    assert content_digest(spec, exclude="specification_sha256") == A7_MODEL_SPEC_SHA256
    assert spec["study_id"] == A7_STUDY_ID
    assert spec["boundary"] == A7_MODEL_SPEC_BOUNDARY
    assert spec["capture_history_dataset_sha256"] == A7_CAPTURE_HISTORY_SHA256
    assert spec["estimator_eligible_capture_records_sha256"] == A7_ELIGIBLE_CAPTURE_RECORDS_SHA256
    assert a7_freeze_does_not_fit_models() == "PREREGISTERED_AWAITING_EXECUTION"
    assert spec["execution_gate"]["freeze_alone_does_not_fit_models"] is True
    assert spec["execution_gate"]["does_not_emit_a7_estimation_report"] is True
    assert spec["execution_gate"]["does_not_start_a8_or_ag"] is True


def test_capture_history_reproduces_from_source_packets_and_excludes_f7_f9_f11() -> None:
    dataset = load_default_a7_capture_history_dataset()
    sources, rows = compile_capture_history_rows_from_resources()
    assert sources == dataset["source_packet_bindings"]
    assert rows == dataset["capture_records"]
    assert records_digest(rows) == dataset["capture_records_sha256"]

    eligible = estimator_eligible_rows(rows)
    assert len(eligible) == dataset["estimator_eligible_capture_count"]
    assert records_digest(eligible) == A7_ELIGIBLE_CAPTURE_RECORDS_SHA256
    assert all(row["frame_id"] not in PRIMARY_ESTIMATION_EXCLUDED_FRAME_IDS for row in eligible)
    assert all(row["outcome"] == "INCLUDE_RESOLVED" for row in eligible)
    assert all(row["capture_estimation_eligible"] is True for row in eligible)

    histories = offering_binary_histories(eligible)
    assert histories == dataset["estimator_eligible_offering_binary_histories"]
    assert set(item["canonical_offering_id"] for item in histories) == set(OBSERVED_OFFERING_IDS)


def test_identifiability_gate_fail_closes_on_sparse_six_identity_table() -> None:
    dataset = load_default_a7_capture_history_dataset()
    gate = evaluate_identifiability_gate(dataset["estimator_eligible_offering_binary_histories"])
    assert gate["n_estimator_eligible_distinct_offerings"] == N_OBSERVED
    assert gate["identifiability_gate_passed"] is False
    assert "CAPTURE_TABLE_TOO_SPARSE" in gate["fail_closed_reasons"]
    assert gate["valid_outcome_if_failed"] == VALID_NO_ESTIMATE_OUTCOME
    assert set(IDENTIFIABILITY_THRESHOLDS) <= set(
        load_default_a7_population_model_specification()["acceptance_and_fail_closed_criteria"][
            "identifiability_thresholds"
        ]
    )


def test_model_spec_binds_preregistered_families_and_sensitivities() -> None:
    spec = load_default_a7_population_model_specification()
    assert set(spec["model_families"]) == set(REQUIRED_MODEL_FAMILIES)
    assert spec["model_family_specifications"]["PAIRWISE_CAPTURE_RECAPTURE_DIAGNOSTIC"]["headline_admissible"] is False
    assert spec["model_family_specifications"]["OBSERVED_ONLY_BASELINE"]["fits_unseen_population"] is False
    assert set(spec["frame_set_sensitivities"]) == set(FRAME_SET_SENSITIVITIES)
    assert set(spec["acceptance_and_fail_closed_criteria"]["sparseness_fail_closed_reasons"]) == set(
        FAIL_CLOSED_REASONS
    )
    assert tuple(spec["estimation_universe"]["capture_frame_ids"]) == PRIMARY_ESTIMATION_FRAME_IDS


def test_helpers_reject_non_objects() -> None:
    with pytest.raises(ProductDiscoveryError, match="missing fields"):
        validate_a7_capture_history_dataset({})
    with pytest.raises(ProductDiscoveryError, match="missing fields"):
        validate_a7_population_model_specification({})


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (lambda d: d.pop("status", None), "missing fields"),
        (lambda d: d.__setitem__("dataset_id", "WRONG"), "dataset_id must be"),
        (lambda d: d.__setitem__("status", "DRAFT"), "must be FROZEN_v1.0"),
        (lambda d: d.__setitem__("dataset_sha256", "0" * 64), "content digest"),
        (lambda d: d.__setitem__("analysis_universe_id", "RAU-" + ("0" * 64)), "frozen A2 analysis universe"),
        (lambda d: d.__setitem__("n_observed", 7), "n_observed must be"),
        (lambda d: d.__setitem__("observed_offering_set_sha256", "0" * 64), "digest mismatch"),
        (lambda d: d.__setitem__("mixed_universe_policy", "ALLOW"), "REJECT"),
        (lambda d: d.__setitem__("boundary", "drift"), "boundary text drift"),
        (lambda d: d["execution_gate"].__setitem__("freeze_alone_does_not_fit_models", False), "must be true"),
        (
            lambda d: d.__setitem__("estimator_excluded_frame_ids", ["F7", "F9"]),
            "estimator_excluded_frame_ids",
        ),
        (
            lambda d: d["capture_records"].append(deepcopy(d["capture_records"][0])),
            "capture_record_count",
        ),
    ],
)
def test_capture_history_rejects_semantic_drift(mutator: Callable[[dict[str, Any]], Any], match: str) -> None:
    dataset = deepcopy(load_default_a7_capture_history_dataset())
    mutator(dataset)
    if "dataset_sha256" not in match and match != "content digest":
        _rehash_dataset(dataset)
    with pytest.raises(ProductDiscoveryError, match=match):
        validate_a7_capture_history_dataset(dataset)


def test_capture_history_rejects_eligible_row_from_excluded_frame() -> None:
    dataset = deepcopy(load_default_a7_capture_history_dataset())
    poison = deepcopy(dataset["capture_records"][0])
    poison["frame_id"] = "F9"
    poison["capture_estimation_eligible"] = True
    poison["outcome"] = "INCLUDE_RESOLVED"
    poison["capture_id"] = "PDC-" + ("a" * 64)
    dataset["capture_records"].append(poison)
    dataset["capture_record_count"] = len(dataset["capture_records"])
    dataset["capture_records_sha256"] = records_digest(dataset["capture_records"])
    _rehash_dataset(dataset)
    with pytest.raises(ProductDiscoveryError, match="excluded frame"):
        validate_a7_capture_history_dataset(dataset)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (lambda s: s.pop("status", None), "missing fields"),
        (lambda s: s.__setitem__("specification_id", "WRONG"), "specification_id must be"),
        (lambda s: s.__setitem__("status", "DRAFT"), "must be FROZEN_v1.0"),
        (lambda s: s.__setitem__("specification_sha256", "0" * 64), "content digest"),
        (lambda s: s.__setitem__("capture_history_dataset_sha256", "0" * 64), "capture_history_dataset_sha256"),
        (lambda s: s.__setitem__("n_observed_declared", 99), "n_observed_declared must be"),
        (lambda s: s.__setitem__("boundary", "drift"), "boundary text drift"),
        (lambda s: s["execution_gate"].__setitem__("does_not_start_a8_or_ag", False), "must be true"),
        (
            lambda s: s["model_family_specifications"]["PAIRWISE_CAPTURE_RECAPTURE_DIAGNOSTIC"].__setitem__(
                "headline_admissible", True
            ),
            "diagnostic-only",
        ),
        (
            lambda s: s["acceptance_and_fail_closed_criteria"].__setitem__(
                "no_forced_point_estimate_when_inadmissible", False
            ),
            "must be true",
        ),
        (lambda s: s.__setitem__("n_estimated", 100), "fitted estimate fields"),
    ],
)
def test_model_spec_rejects_semantic_drift(mutator: Callable[[dict[str, Any]], Any], match: str) -> None:
    spec = deepcopy(load_default_a7_population_model_specification())
    mutator(spec)
    if match != "content digest":
        _rehash_spec(spec)
    with pytest.raises(ProductDiscoveryError, match=match):
        validate_a7_population_model_specification(spec)
