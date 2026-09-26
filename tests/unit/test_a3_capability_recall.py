from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pytest

from neuroai_workbench.a3_capability_recall import (
    A3_BOUNDARY,
    A3_PREREG_ID,
    A3_PREREG_SHA256,
    A3_STUDY_ID,
    ALL_DISCOVERY_FRAME_IDS,
    CAPABILITY_FAMILY_SET_ID,
    CAPABILITY_FRAME_IDS,
    CONVENTIONAL_FAMILY_SET_ID,
    CONVENTIONAL_FRAME_IDS,
    REQUIRED_CAPABILITY_FAMILY_IDS,
    REQUIRED_COMPANION_RATES,
    REQUIRED_CONVENTIONAL_FAMILY_IDS,
    a3_freeze_does_not_compute_delta_n,
    compute_companion_rates,
    compute_delta_n_capability,
    content_digest,
    load_default_a3_capability_recall_preregistration,
    validate_a3_capability_recall_preregistration,
)
from neuroai_workbench.product_discovery_frames import ProductDiscoveryError
from neuroai_workbench.release_a_preregistration import FRAME_SET_SENSITIVITIES


def _rehash(prereg: dict[str, Any]) -> None:
    prereg["preregistration_sha256"] = content_digest(prereg, exclude="preregistration_sha256")


def test_a3_preregistration_is_content_bound_before_yield() -> None:
    prereg = load_default_a3_capability_recall_preregistration()
    validate_a3_capability_recall_preregistration(prereg)

    assert prereg["preregistration_id"] == A3_PREREG_ID
    assert prereg["preregistration_sha256"] == A3_PREREG_SHA256
    assert content_digest(prereg, exclude="preregistration_sha256") == A3_PREREG_SHA256
    assert prereg["study_id"] == A3_STUDY_ID
    assert prereg["conventional_search_family_set_id"] == CONVENTIONAL_FAMILY_SET_ID
    assert prereg["capability_search_family_set_id"] == CAPABILITY_FAMILY_SET_ID
    assert prereg["boundary"] == A3_BOUNDARY
    assert a3_freeze_does_not_compute_delta_n() == "PREREGISTERED_AWAITING_EXECUTION"

    conventional_ids = [row["family_id"] for row in prereg["conventional_search_families"]]
    capability_ids = [row["family_id"] for row in prereg["capability_search_families"]]
    assert tuple(conventional_ids) == REQUIRED_CONVENTIONAL_FAMILY_IDS
    assert tuple(capability_ids) == REQUIRED_CAPABILITY_FAMILY_IDS
    assert len(capability_ids) == 9
    assert "BEHAVIORAL_PERSONALIZATION" in capability_ids
    assert "COGNITIVE_LOAD_WORKLOAD" in capability_ids
    assert "AFFECTIVE_STRESS_STATE" in capability_ids

    substrate = prereg["evidence_substrate"]
    assert tuple(substrate["conventional_frame_ids"]) == CONVENTIONAL_FRAME_IDS
    assert tuple(substrate["capability_frame_ids"]) == CAPABILITY_FRAME_IDS
    assert tuple(substrate["all_discovery_frame_ids"]) == ALL_DISCOVERY_FRAME_IDS
    assert set(FRAME_SET_SENSITIVITIES["CONVENTIONAL_SOURCE_CORE"]) == set(CONVENTIONAL_FRAME_IDS)
    assert substrate["f8_reserved_for_a4"] is True
    assert substrate["f10_patent_leads_are_not_products"] is True
    assert substrate["f7_f9_f11_estimator_excluded"] is True

    metrics = prereg["metrics_contract"]
    assert metrics["primary_estimand_id"] == "DELTA_N_CAPABILITY"
    assert tuple(metrics["required_companion_rates"]) == REQUIRED_COMPANION_RATES
    assert metrics["denominator_rules"]["raw_search_hits_are_not_the_increment_unit"] is True


def test_delta_n_capability_uses_exact_offering_ids_not_raw_hits() -> None:
    result = compute_delta_n_capability(
        conventional_offering_ids=["PRD-A", "PRD-B", "PRD-A"],
        all_discovery_offering_ids=["PRD-A", "PRD-B", "PRD-C"],
    )
    assert result["n_conventional_terminology"] == 2
    assert result["n_all_discovery"] == 3
    assert result["delta_n_capability"] == 1
    assert result["unique_product_gain"] == 1
    assert result["unique_capability_offering_ids"] == ["PRD-C"]

    with pytest.raises(ProductDiscoveryError, match="superset"):
        compute_delta_n_capability(
            conventional_offering_ids=["PRD-A", "PRD-Z"],
            all_discovery_offering_ids=["PRD-A"],
        )


def test_companion_rates_required_alongside_unique_product_gain() -> None:
    rates = compute_companion_rates(
        raw_candidates=100,
        exclude_count=5,
        unresolved_count=20,
        known_identity_duplicate_count=4,
        within_round_duplicate_count=1,
    )
    assert rates["false_positive_rate"] == pytest.approx(0.05)
    assert rates["unresolved_rate"] == pytest.approx(0.20)
    assert rates["duplicate_rate"] == pytest.approx(0.05)

    with pytest.raises(ProductDiscoveryError, match="positive"):
        compute_companion_rates(
            raw_candidates=0,
            exclude_count=0,
            unresolved_count=0,
            known_identity_duplicate_count=0,
            within_round_duplicate_count=0,
        )


def test_helpers_reject_non_objects() -> None:
    with pytest.raises(ProductDiscoveryError, match="missing fields"):
        validate_a3_capability_recall_preregistration({})


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
        (lambda p: p.__setitem__("f6_query_universe_id", "WRONG"), "f6_query_universe_id"),
        (lambda p: p.__setitem__("f6_query_universe_sha256", "0" * 64), "f6_query_universe_sha256"),
        (lambda p: p.__setitem__("conventional_search_family_set_id", "WRONG"), "conventional_search_family_set_id"),
        (lambda p: p.__setitem__("capability_search_family_set_id", "WRONG"), "capability_search_family_set_id"),
        (lambda p: p.__setitem__("boundary", "drift"), "boundary text drift"),
        (
            lambda p: p["conventional_search_families"].pop(),
            "conventional_search_families must equal",
        ),
        (
            lambda p: p["capability_search_families"].pop(),
            "capability_search_families must equal",
        ),
        (
            lambda p: p["capability_search_families"].append(
                {
                    "family_id": "POST_HOC_FAMILY",
                    "label": "post-hoc",
                    "terminology_class": "CAPABILITY_FUNCTION",
                    "f6_query_family_binding": "ATTENTION_VIGILANCE",
                    "notes": "forbidden",
                }
            ),
            "capability_search_families must equal",
        ),
        (
            lambda p: p["conventional_search_families"][0].__setitem__("terminology_class", "CAPABILITY_FUNCTION"),
            "CATEGORY_BRANDED",
        ),
        (
            lambda p: p["capability_search_families"][0].__setitem__("terminology_class", "CATEGORY_BRANDED"),
            "CAPABILITY_FUNCTION",
        ),
        (
            lambda p: p["capability_search_families"][0].__setitem__("f6_query_family_binding", "NOT_A_F6_FAMILY"),
            "not in the frozen F6",
        ),
        (
            lambda p: p["evidence_substrate"].__setitem__("conventional_frame_ids", ["F1"]),
            "conventional_frame_ids must be F1-F5",
        ),
        (
            lambda p: p["evidence_substrate"].__setitem__("capability_frame_ids", ["F6", "F8"]),
            "capability_frame_ids must be F6 only",
        ),
        (
            lambda p: p["evidence_substrate"].__setitem__("f8_reserved_for_a4", False),
            "f8_reserved_for_a4 must be true",
        ),
        (
            lambda p: p["evidence_substrate"].__setitem__("no_identity_allocation_by_implication", False),
            "no_identity_allocation_by_implication must be true",
        ),
        (
            lambda p: p["metrics_contract"].__setitem__("primary_estimand_id", "RAW_HITS"),
            "DELTA_N_CAPABILITY",
        ),
        (
            lambda p: p["metrics_contract"].__setitem__("required_companion_rates", ["FALSE_POSITIVE_RATE"]),
            "required_companion_rates",
        ),
        (
            lambda p: p["metrics_contract"]["denominator_rules"].__setitem__(
                "raw_search_hits_are_not_the_increment_unit", False
            ),
            "raw_search_hits_are_not_the_increment_unit must be true",
        ),
        (
            lambda p: p["execution_gate"].__setitem__("post_hoc_family_edits_prohibited", False),
            "post_hoc_family_edits_prohibited must be true",
        ),
        (
            lambda p: p["execution_gate"].__setitem__("does_not_start_a4_or_later", False),
            "does_not_start_a4_or_later must be true",
        ),
        (
            lambda p: p["execution_gate"].__setitem__("freeze_alone_does_not_compute_delta_n", False),
            "freeze_alone_does_not_compute_delta_n must be true",
        ),
    ],
)
def test_a3_preregistration_rejects_post_hoc_and_binding_drift(
    mutator: Callable[[dict[str, Any]], None],
    match: str,
) -> None:
    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    mutator(prereg)
    if match not in {"content digest", "missing fields"}:
        try:
            _rehash(prereg)
        except Exception:
            pass
    with pytest.raises(ProductDiscoveryError, match=match):
        validate_a3_capability_recall_preregistration(prereg)


def test_loaded_digest_constant_is_bound() -> None:
    prereg = load_default_a3_capability_recall_preregistration()
    assert prereg["preregistration_sha256"] == A3_PREREG_SHA256


def test_compute_helpers_reject_negative_inputs() -> None:
    with pytest.raises(ProductDiscoveryError, match="raw_candidates cannot be negative"):
        compute_companion_rates(
            raw_candidates=-1,
            exclude_count=0,
            unresolved_count=0,
            known_identity_duplicate_count=0,
            within_round_duplicate_count=0,
        )
    with pytest.raises(ProductDiscoveryError, match="exclude_count cannot be negative"):
        compute_companion_rates(
            raw_candidates=1,
            exclude_count=-1,
            unresolved_count=0,
            known_identity_duplicate_count=0,
            within_round_duplicate_count=0,
        )


def test_validate_rejects_type_and_empty_value_drift() -> None:
    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    prereg["conventional_search_families"][0] = "bad"
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="must be an object"):
        validate_a3_capability_recall_preregistration(prereg)

    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    prereg["conventional_search_families"][0]["example_terms"] = []
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="example_terms cannot be empty"):
        validate_a3_capability_recall_preregistration(prereg)

    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    prereg["conventional_search_families"] = "bad"
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="must be an array"):
        validate_a3_capability_recall_preregistration(prereg)

    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    prereg["evidence_substrate"] = "bad"
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="must be an object"):
        validate_a3_capability_recall_preregistration(prereg)

    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    prereg["metrics_contract"] = "bad"
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="must be an object"):
        validate_a3_capability_recall_preregistration(prereg)

    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    prereg["execution_gate"] = "bad"
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="must be an object"):
        validate_a3_capability_recall_preregistration(prereg)

    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    prereg["metrics_contract"]["stratification_policy"] = "bad"
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="must be an object"):
        validate_a3_capability_recall_preregistration(prereg)

    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    prereg["metrics_contract"]["denominator_rules"] = "bad"
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="must be an object"):
        validate_a3_capability_recall_preregistration(prereg)

    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    prereg["conventional_search_families"][0]["family_id"] = ""
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="non-empty string"):
        validate_a3_capability_recall_preregistration(prereg)

    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    prereg["evidence_substrate"]["identity_unit"] = "RAW_HIT"
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="CANONICAL_PRODUCT_OFFERING"):
        validate_a3_capability_recall_preregistration(prereg)

    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    prereg["evidence_substrate"]["all_discovery_frame_ids"] = ["F1"]
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="all_discovery_frame_ids must be F1-F6"):
        validate_a3_capability_recall_preregistration(prereg)

    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    prereg["evidence_substrate"]["conventional_frame_set_alignment"] = "WRONG"
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="CONVENTIONAL_SOURCE_CORE"):
        validate_a3_capability_recall_preregistration(prereg)

    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    prereg["metrics_contract"]["formula"] = "WRONG"
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="metrics formula drift"):
        validate_a3_capability_recall_preregistration(prereg)

    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    prereg["metrics_contract"]["stratification_policy"]["no_post_hoc_stratum_invention"] = False
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="no_post_hoc_stratum_invention must be true"):
        validate_a3_capability_recall_preregistration(prereg)

    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    prereg["frame_register_version"] = "WRONG"
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="frame_register_version mismatch"):
        validate_a3_capability_recall_preregistration(prereg)

    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    prereg["frame_register_blob_sha"] = "0" * 40
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="frame_register_blob_sha mismatch"):
        validate_a3_capability_recall_preregistration(prereg)

    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    prereg["evidence_substrate"]["increment_requires_exact_offering_id"] = "yes"
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="must be a boolean"):
        validate_a3_capability_recall_preregistration(prereg)

    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    prereg["capability_search_families"][0]["f6_query_family_binding"] = 123
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="non-empty string"):
        validate_a3_capability_recall_preregistration(prereg)

    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    prereg["conventional_search_families"][0]["example_terms"] = [""]
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="non-empty string"):
        validate_a3_capability_recall_preregistration(prereg)

    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    prereg["evidence_substrate"]["f7_f9_f11_estimator_excluded"] = False
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="f7_f9_f11_estimator_excluded must be true"):
        validate_a3_capability_recall_preregistration(prereg)

    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    prereg["execution_gate"]["does_not_mutate_rau"] = False
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="does_not_mutate_rau must be true"):
        validate_a3_capability_recall_preregistration(prereg)

    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    prereg["execution_gate"]["does_not_allocate_canonical_identity"] = False
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="does_not_allocate_canonical_identity must be true"):
        validate_a3_capability_recall_preregistration(prereg)

    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    prereg["metrics_contract"]["denominator_rules"]["only_include_resolved_exact_offering_ids_enter_n_counts"] = False
    _rehash(prereg)
    with pytest.raises(
        ProductDiscoveryError,
        match="only_include_resolved_exact_offering_ids_enter_n_counts must be true",
    ):
        validate_a3_capability_recall_preregistration(prereg)


def test_post_hoc_family_reorder_or_relabel_is_rejected() -> None:
    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    families = prereg["capability_search_families"]
    families[0], families[1] = families[1], families[0]
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="capability_search_families must equal"):
        validate_a3_capability_recall_preregistration(prereg)

    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    prereg["capability_search_families"][0]["family_id"] = "ATTENTION_ONLY_RELABEL"
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="capability_search_families must equal"):
        validate_a3_capability_recall_preregistration(prereg)


def test_deepcopy_round_trip_still_validates() -> None:
    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    validate_a3_capability_recall_preregistration(prereg)


def test_load_rejects_digest_constant_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "neuroai_workbench.a3_capability_recall.A3_PREREG_SHA256",
        "0" * 64,
    )
    with pytest.raises(ProductDiscoveryError, match="A3_PREREG_SHA256"):
        load_default_a3_capability_recall_preregistration()


def test_capability_family_row_must_be_object() -> None:
    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    prereg["capability_search_families"][0] = "bad"
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="must be an object"):
        validate_a3_capability_recall_preregistration(prereg)


def test_example_terms_must_be_array() -> None:
    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    prereg["conventional_search_families"][0]["example_terms"] = "bci"
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="must be an array"):
        validate_a3_capability_recall_preregistration(prereg)


def test_required_companion_rates_must_be_array() -> None:
    prereg = deepcopy(load_default_a3_capability_recall_preregistration())
    prereg["metrics_contract"]["required_companion_rates"] = "FALSE_POSITIVE_RATE"
    _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match="must be an array"):
        validate_a3_capability_recall_preregistration(prereg)


def test_zero_delta_n_when_capability_adds_no_exact_offerings() -> None:
    result = compute_delta_n_capability(
        conventional_offering_ids=["PRD-A", "PRD-B"],
        all_discovery_offering_ids=["PRD-A", "PRD-B"],
    )
    assert result["delta_n_capability"] == 0
    assert result["unique_capability_offering_ids"] == []
    assert result["unique_product_gain"] == 0
