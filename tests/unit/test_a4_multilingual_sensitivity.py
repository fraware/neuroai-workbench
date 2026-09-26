from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pytest

from neuroai_workbench.a4_multilingual_sensitivity import (
    A4_BOUNDARY,
    A4_PREREG_ID,
    A4_PREREG_SHA256,
    A4_STUDY_ID,
    ENGLISH_FRAME_IDS,
    ENGLISH_PLUS_NATIVE_FRAME_IDS,
    MATCHED_PROTOCOL_SET_ID,
    NATIVE_FRAME_IDS,
    REQUIRED_COMPANION_METRICS,
    REQUIRED_STRATUM_IDS,
    a4_freeze_does_not_compute_delta_n,
    compute_companion_rates,
    compute_delta_n_multilingual,
    content_digest,
    load_default_a4_multilingual_sensitivity_preregistration,
    validate_a4_multilingual_sensitivity_preregistration,
)
from neuroai_workbench.f8_f10_protocol import LANGUAGE_STRATA_SHA256
from neuroai_workbench.product_discovery_frames import ProductDiscoveryError


def _rehash(prereg: dict[str, Any]) -> None:
    prereg["preregistration_sha256"] = content_digest(prereg, exclude="preregistration_sha256")


def test_a4_preregistration_is_content_bound_before_yield() -> None:
    prereg = load_default_a4_multilingual_sensitivity_preregistration()
    validate_a4_multilingual_sensitivity_preregistration(prereg)

    assert prereg["preregistration_id"] == A4_PREREG_ID
    assert prereg["preregistration_sha256"] == A4_PREREG_SHA256
    assert content_digest(prereg, exclude="preregistration_sha256") == A4_PREREG_SHA256
    assert prereg["study_id"] == A4_STUDY_ID
    assert prereg["matched_protocol_set_id"] == MATCHED_PROTOCOL_SET_ID
    assert prereg["language_jurisdiction_strata_sha256"] == LANGUAGE_STRATA_SHA256
    assert prereg["boundary"] == A4_BOUNDARY
    assert a4_freeze_does_not_compute_delta_n() == "PREREGISTERED_AWAITING_EXECUTION"

    assert tuple(prereg["bound_stratum_ids"]) == REQUIRED_STRATUM_IDS
    assert len(REQUIRED_STRATUM_IDS) == 7

    substrate = prereg["evidence_substrate"]
    assert tuple(substrate["english_frame_ids"]) == ENGLISH_FRAME_IDS
    assert tuple(substrate["native_frame_ids"]) == NATIVE_FRAME_IDS
    assert tuple(substrate["english_plus_native_frame_ids"]) == ENGLISH_PLUS_NATIVE_FRAME_IDS
    assert substrate["f8_is_controlled_local_language_frame"] is True
    assert substrate["no_post_hoc_language_selection"] is True

    metrics = prereg["metrics_contract"]
    assert metrics["primary_estimand_id"] == "DELTA_N_MULTILINGUAL"
    assert metrics["stratum_estimand_id"] == "DELTA_J"
    assert tuple(metrics["required_companion_metrics"]) == REQUIRED_COMPANION_METRICS
    assert metrics["stratification_policy"]["languages_not_selected_for_yield"] is True
    assert metrics["denominator_rules"]["raw_search_hits_are_not_the_increment_unit"] is True

    gate = prereg["execution_gate"]
    assert gate["post_hoc_language_selection_prohibited"] is True
    assert gate["does_not_start_a5_or_later"] is True
    assert gate["freeze_alone_does_not_compute_delta_n"] is True


def test_delta_n_multilingual_uses_exact_offering_ids_not_raw_hits() -> None:
    result = compute_delta_n_multilingual(
        english_offering_ids=["PRD-A", "PRD-B", "PRD-A"],
        english_plus_native_offering_ids=["PRD-A", "PRD-B", "PRD-C"],
    )
    assert result["n_english"] == 2
    assert result["n_english_plus_native"] == 3
    assert result["delta_n_multilingual"] == 1
    assert result["unique_product_gain"] == 1
    assert result["unique_native_offering_ids"] == ["PRD-C"]

    with pytest.raises(ProductDiscoveryError, match="superset"):
        compute_delta_n_multilingual(
            english_offering_ids=["PRD-A", "PRD-Z"],
            english_plus_native_offering_ids=["PRD-A"],
        )


def test_companion_rates_required_alongside_unique_product_gain() -> None:
    rates = compute_companion_rates(
        raw_candidates=63,
        exclude_count=0,
        unresolved_count=12,
        known_identity_duplicate_count=0,
        within_round_duplicate_count=0,
    )
    assert rates["false_positive_rate"] == pytest.approx(0.0)
    assert rates["unresolved_rate"] == pytest.approx(12 / 63)
    assert rates["duplicate_rate"] == pytest.approx(0.0)

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
        validate_a4_multilingual_sensitivity_preregistration({})


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
        (lambda p: p.__setitem__("language_jurisdiction_strata_id", "WRONG"), "language_jurisdiction_strata_id"),
        (
            lambda p: p.__setitem__("language_jurisdiction_strata_sha256", "0" * 64),
            "language_jurisdiction_strata_sha256",
        ),
        (lambda p: p.__setitem__("f8_query_universe_id", "WRONG"), "f8_query_universe_id"),
        (lambda p: p.__setitem__("f8_query_universe_sha256", "0" * 64), "f8_query_universe_sha256"),
        (lambda p: p.__setitem__("f8_round_protocol_id", "WRONG"), "f8_round_protocol_id"),
        (lambda p: p.__setitem__("a3_preregistration_sha256", "0" * 64), "a3_preregistration_sha256"),
        (lambda p: p.__setitem__("a3_study_sha256", "0" * 64), "a3_study_sha256"),
        (lambda p: p.__setitem__("matched_protocol_set_id", "WRONG"), "matched_protocol_set_id"),
        (lambda p: p.__setitem__("boundary", "drift"), "boundary text drift"),
        (lambda p: p["bound_stratum_ids"].pop(), "bound_stratum_ids must equal"),
        (
            lambda p: p["bound_stratum_ids"].append("LL-POST-HOC"),
            "bound_stratum_ids must equal",
        ),
        (
            lambda p: p["matched_arms"][0].__setitem__("frame_ids", ["F1"]),
            "S_ENGLISH frame_ids must be F1-F6",
        ),
        (
            lambda p: p["matched_arms"][1].__setitem__("frame_ids", ["F1", "F8"]),
            "S_ENGLISH_PLUS_NATIVE frame_ids must be F1-F6\\+F8",
        ),
        (
            lambda p: p["native_arm"].__setitem__("frame_ids", ["F6", "F8"]),
            "native_arm.frame_ids must be F8 only",
        ),
        (
            lambda p: p["evidence_substrate"].__setitem__("no_post_hoc_language_selection", False),
            "no_post_hoc_language_selection must be true",
        ),
        (
            lambda p: p["evidence_substrate"].__setitem__("english_frame_ids", ["F1"]),
            "english_frame_ids must be F1-F6",
        ),
        (
            lambda p: p["metrics_contract"].__setitem__("primary_estimand_id", "RAW_HITS"),
            "DELTA_N_MULTILINGUAL",
        ),
        (
            lambda p: p["metrics_contract"].__setitem__("required_companion_metrics", ["UNIQUE_PRODUCT_GAIN"]),
            "required_companion_metrics",
        ),
        (
            lambda p: p["metrics_contract"]["stratification_policy"].__setitem__(
                "languages_not_selected_for_yield", False
            ),
            "languages_not_selected_for_yield must be true",
        ),
        (
            lambda p: p["metrics_contract"]["denominator_rules"].__setitem__(
                "raw_search_hits_are_not_the_increment_unit", False
            ),
            "raw_search_hits_are_not_the_increment_unit must be true",
        ),
        (
            lambda p: p["execution_gate"].__setitem__("post_hoc_language_selection_prohibited", False),
            "post_hoc_language_selection_prohibited must be true",
        ),
        (
            lambda p: p["execution_gate"].__setitem__("does_not_start_a5_or_later", False),
            "does_not_start_a5_or_later must be true",
        ),
        (
            lambda p: p.__setitem__("predeclaration_rule", "choose languages freely"),
            "predeclaration_rule must forbid",
        ),
    ],
)
def test_a4_preregistration_rejects_post_hoc_and_binding_drift(
    mutator: Callable[[dict[str, Any]], Any],
    match: str,
) -> None:
    prereg = deepcopy(load_default_a4_multilingual_sensitivity_preregistration())
    mutator(prereg)
    # Do not rehash when the mutation itself is a top-level digest spoof.
    if match not in {"content digest"} and not match.startswith("preregistration_sha256"):
        if "preregistration_sha256" in prereg:
            _rehash(prereg)
    with pytest.raises(ProductDiscoveryError, match=match):
        validate_a4_multilingual_sensitivity_preregistration(prereg)


def test_load_rejects_prereg_digest_constant_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "neuroai_workbench.a4_multilingual_sensitivity.A4_PREREG_SHA256",
        "0" * 64,
    )
    with pytest.raises(ProductDiscoveryError, match="A4_PREREG_SHA256"):
        load_default_a4_multilingual_sensitivity_preregistration()
