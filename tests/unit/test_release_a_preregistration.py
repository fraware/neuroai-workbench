from __future__ import annotations

from copy import deepcopy

import pytest

from neuroai_workbench.product_discovery_frames import (
    DISCOVERY_BOUNDARY,
    FRAME_REGISTER_VERSION,
    FRAME_VERSION,
    product_capture_id,
)
from neuroai_workbench.release_a_preregistration import (
    LANGUAGE_SCOPE_ID,
    PREREGISTRATION_BOUNDARY,
    PREREGISTRATION_VERSION,
    REQUIRED_DIAGNOSTICS,
    REQUIRED_MODEL_FAMILIES,
    REQUIRED_SENSITIVITIES,
    ReleaseAPreregistrationError,
    decompose_observed_and_unseen,
    default_estimation_frame_ids,
    estimation_universe_id,
    load_default_language_scope,
    validate_captures_against_estimation_universe,
    validate_estimation_universe,
)


def _universe(
    *,
    view: str = "A-P1",
    role: str = "PRIMARY",
    frames: list[str] | None = None,
    enumeration_roles: list[str] | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "universe_id": "",
        "preregistration_version": PREREGISTRATION_VERSION,
        "role": role,
        "boundary_contract_id": "PRODUCT_MEASUREMENT_CONTRACT_v1.0",
        "boundary_contract_semantic_blob": "7cbd7f086d80505da7a7c35a38f3aa0ce690ec41",
        "reference_standard_id": "D4_PRODUCT_REFERENCE_STANDARD_v1.0",
        "reference_standard_version": "1.0",
        "reference_standard_validation_state": "FROZEN_WORKING_REFERENCE",
        "registry_projection_version": "PRODUCT_REGISTRY_v1.0",
        "population_view_policy_id": "PRODUCT_POPULATION_VIEW_POLICY_v1.0",
        "currentness_policy_id": "PRODUCT_CURRENTNESS_POLICY_v1.0",
        "population_view_id": view,
        "identity_level": "OFFERING",
        "included_enumeration_roles": enumeration_roles
        or ["INTEGRATED_SYSTEM", "COMPONENT_OR_SUBSYSTEM", "STANDALONE_SOFTWARE_OR_SERVICE"],
        "analysis_jurisdiction_scope": "GLOBAL",
        "world_time_cutoff": "2026-09-24",
        "knowledge_time_cutoff": "2026-09-24T12:00:00Z",
        "language_scope_id": LANGUAGE_SCOPE_ID,
        "frame_register_version": FRAME_REGISTER_VERSION,
        "capture_frame_ids": frames or list(default_estimation_frame_ids()),
        "technical_equivalence_policy_id": None,
        "observed_identity_unit": "CANONICAL_PRODUCT_OFFERING",
        "latent_residual_unit": "UNOBSERVED_DISTINCT_PRODUCT_OFFERINGS",
        "model_families": list(REQUIRED_MODEL_FAMILIES),
        "naive_pairwise_role": "DIAGNOSTIC_ONLY",
        "required_diagnostics": sorted(REQUIRED_DIAGNOSTICS),
        "required_sensitivities": sorted(REQUIRED_SENSITIVITIES),
        "boundary": PREREGISTRATION_BOUNDARY,
    }
    value["universe_id"] = estimation_universe_id(value)
    return value


def _capture(frame_id: str = "F1", *, eligible: bool = True) -> dict[str, object]:
    capture: dict[str, object] = {
        "capture_id": "",
        "frame_id": frame_id,
        "frame_version": FRAME_VERSION,
        "round_id": "R1",
        "query_or_seed_id": "Q1",
        "candidate_key": "candidate-a",
        "canonical_offering_id": "PRD-A",
        "source_observation_ref": "OBS-1",
        "language": "en",
        "jurisdiction": "US",
        "outcome": "INCLUDE_RESOLVED",
        "capture_estimation_eligible": eligible,
        "observed_at": "2026-09-24T11:00:00Z",
        "registry_projection_version": "PRODUCT_REGISTRY_v1.0",
        "frame_register_version": FRAME_REGISTER_VERSION,
        "population_view_id": "A-P1",
        "analysis_jurisdiction_scope": "GLOBAL",
        "language_scope_id": LANGUAGE_SCOPE_ID,
        "world_time_cutoff": "2026-09-24",
        "knowledge_time_cutoff": "2026-09-24T12:00:00Z",
        "boundary": DISCOVERY_BOUNDARY,
    }
    capture["capture_id"] = product_capture_id(capture)
    return capture


def test_default_language_and_estimation_frame_scopes_are_frozen() -> None:
    scope = load_default_language_scope()
    assert scope["language_scope_id"] == LANGUAGE_SCOPE_ID
    assert {item["stratum_id"] for item in scope["matched_native_strata"]} == {
        "CN_ZH_HANS",
        "DACH_DE",
        "ES_ES",
        "FR_FR",
        "JP_JA",
        "KR_KO",
    }
    assert set(default_estimation_frame_ids()) == {"F1", "F2", "F3", "F4", "F5", "F6", "F8", "F10"}


def test_primary_estimands_are_fixed_to_ap1_and_ap6() -> None:
    validate_estimation_universe(_universe(view="A-P1"))
    validate_estimation_universe(_universe(view="A-P6"))

    secondary = _universe(view="A-P4", role="SECONDARY", enumeration_roles=["INTEGRATED_SYSTEM"])
    validate_estimation_universe(secondary)

    invalid = deepcopy(secondary)
    invalid["role"] = "PRIMARY"
    invalid["universe_id"] = estimation_universe_id(invalid)
    with pytest.raises(ReleaseAPreregistrationError, match="Only A-P1 and A-P6"):
        validate_estimation_universe(invalid)


def test_ap8_is_not_enabled_in_v1_preregistration() -> None:
    universe = _universe(view="A-P8", role="SECONDARY")
    with pytest.raises(ReleaseAPreregistrationError, match="not enabled in v1.0"):
        validate_estimation_universe(universe)


def test_frame_shopping_and_purposive_frames_are_rejected() -> None:
    subset = _universe(frames=["F1", "F2", "F3"])
    with pytest.raises(ReleaseAPreregistrationError, match="exactly match"):
        validate_estimation_universe(subset)

    for frame_id in ("F7", "F9", "F11"):
        frames = list(default_estimation_frame_ids()) + [frame_id]
        universe = _universe(frames=frames)
        with pytest.raises(ReleaseAPreregistrationError, match="exactly match"):
            validate_estimation_universe(universe)


def test_required_model_diagnostics_and_sensitivities_are_exact() -> None:
    universe = _universe()
    validate_estimation_universe(universe)

    missing_model = deepcopy(universe)
    missing_model["model_families"] = list(REQUIRED_MODEL_FAMILIES[:-1])
    missing_model["universe_id"] = estimation_universe_id(missing_model)
    with pytest.raises(ReleaseAPreregistrationError, match="model_families"):
        validate_estimation_universe(missing_model)

    missing_diag = deepcopy(universe)
    missing_diag["required_diagnostics"] = sorted(REQUIRED_DIAGNOSTICS - {"ZERO_CAPTURE_RISK"})
    missing_diag["universe_id"] = estimation_universe_id(missing_diag)
    with pytest.raises(ReleaseAPreregistrationError, match="required_diagnostics"):
        validate_estimation_universe(missing_diag)

    missing_sensitivity = deepcopy(universe)
    missing_sensitivity["required_sensitivities"] = sorted(REQUIRED_SENSITIVITIES - {"FRAME_GROUPING"})
    missing_sensitivity["universe_id"] = estimation_universe_id(missing_sensitivity)
    with pytest.raises(ReleaseAPreregistrationError, match="required_sensitivities"):
        validate_estimation_universe(missing_sensitivity)


def test_capture_set_rejects_incompatible_population_view_and_eligibility_drift() -> None:
    universe = _universe()
    capture = _capture()
    validate_captures_against_estimation_universe(universe, [capture])

    drift = deepcopy(capture)
    drift["population_view_id"] = "A-P6"
    drift["capture_id"] = product_capture_id(drift)
    with pytest.raises(ReleaseAPreregistrationError, match="population_view_id"):
        validate_captures_against_estimation_universe(universe, [drift])

    wrong_eligibility = _capture("F9", eligible=True)
    with pytest.raises(ReleaseAPreregistrationError, match="eligibility conflicts"):
        validate_captures_against_estimation_universe(universe, [wrong_eligibility])

    valid_external_only = _capture("F9", eligible=False)
    validate_captures_against_estimation_universe(universe, [valid_external_only])


def test_external_only_observed_products_are_not_double_counted_as_unseen() -> None:
    result = decompose_observed_and_unseen(
        n_observed_total=120,
        n_observed_capture_support=100,
        model_total_estimate=150.0,
    )
    assert result["n_observed_external_only"] == 20
    assert result["model_zero_capture_estimate"] == 50.0
    assert result["n_unobserved_estimated"] == 30.0
    assert result["coverage_estimated"] == pytest.approx(0.8)


def test_model_total_below_known_observed_is_retained_as_incoherent_not_floored() -> None:
    result = decompose_observed_and_unseen(
        n_observed_total=120,
        n_observed_capture_support=100,
        model_total_estimate=110.0,
    )
    assert result["model_consistent_with_known_observed"] is False
    assert result["n_observed_external_only"] == 20
    assert str(result["n_unobserved_estimated"]) == "nan"
    assert str(result["coverage_estimated"]) == "nan"


def test_count_decomposition_rejects_impossible_inputs() -> None:
    with pytest.raises(ReleaseAPreregistrationError, match="cannot be negative"):
        decompose_observed_and_unseen(
            n_observed_total=-1,
            n_observed_capture_support=0,
            model_total_estimate=0.0,
        )

    with pytest.raises(ReleaseAPreregistrationError, match="cannot exceed"):
        decompose_observed_and_unseen(
            n_observed_total=10,
            n_observed_capture_support=11,
            model_total_estimate=15.0,
        )

    with pytest.raises(ReleaseAPreregistrationError, match="Model total cannot be below"):
        decompose_observed_and_unseen(
            n_observed_total=10,
            n_observed_capture_support=8,
            model_total_estimate=7.0,
        )
