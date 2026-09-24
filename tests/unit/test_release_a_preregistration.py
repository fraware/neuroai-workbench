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
    FRAME_SET_SENSITIVITIES,
    PREREGISTRATION_BOUNDARY,
    PREREGISTRATION_VERSION,
    PRIMARY_ESTIMATION_FRAME_IDS,
    REQUIRED_DIAGNOSTICS,
    REQUIRED_MODEL_FAMILIES,
    REQUIRED_SENSITIVITIES,
    ReleaseAPreregistrationError,
    admissible_model_envelope,
    decompose_observed_and_unseen,
    estimation_universe_id,
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
        "analysis_jurisdiction_scope": "GLOBAL_PROTOCOL_SCOPE",
        "world_time_cutoff": "2026-09-24",
        "knowledge_time_cutoff": "2026-09-24T12:00:00Z",
        "language_scope_id": "EN_PLUS_PRIORITY_NATIVE_v1",
        "frame_register_version": FRAME_REGISTER_VERSION,
        "capture_frame_ids": frames or list(PRIMARY_ESTIMATION_FRAME_IDS),
        "frame_set_policy_id": "RELEASE_A_FRAME_SET_POLICY_v1.0",
        "holdback_policy_id": "RELEASE_A_LATE_ROUND_HOLDBACK_v1.0",
        "reporting_policy_id": "RELEASE_A_MODEL_ENVELOPE_REPORTING_v1.0",
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


def _capture(frame_id: str = "F1") -> dict[str, object]:
    capture: dict[str, object] = {
        "capture_id": "",
        "frame_id": frame_id,
        "frame_version": FRAME_VERSION,
        "round_id": "R1",
        "query_or_seed_id": "Q1",
        "query_family": "Q1",
        "source_class": "PUBLIC",
        "candidate_key": "candidate-a",
        "canonical_offering_id": "PRD-A",
        "source_observation_ref": "OBS-1",
        "language": "en",
        "jurisdiction": "US",
        "outcome": "INCLUDE_RESOLVED",
        "capture_estimation_eligible": True,
        "observed_at": "2026-09-24T11:00:00Z",
        "registry_projection_version": "PRODUCT_REGISTRY_v1.0",
        "frame_register_version": FRAME_REGISTER_VERSION,
        "population_view_id": "A-P1",
        "analysis_jurisdiction_scope": "GLOBAL_PROTOCOL_SCOPE",
        "language_scope_id": "EN_PLUS_PRIORITY_NATIVE_v1",
        "world_time_cutoff": "2026-09-24",
        "knowledge_time_cutoff": "2026-09-24T12:00:00Z",
        "boundary": DISCOVERY_BOUNDARY,
    }
    capture["capture_id"] = product_capture_id(capture)
    return capture


def test_primary_estimands_are_ap1_and_ap6_and_ap4_is_secondary() -> None:
    validate_estimation_universe(_universe(view="A-P1"))
    validate_estimation_universe(_universe(view="A-P6"))
    validate_estimation_universe(
        _universe(view="A-P4", role="SECONDARY", enumeration_roles=["INTEGRATED_SYSTEM"])
    )

    invalid = _universe(view="A-P4", role="SECONDARY", enumeration_roles=["INTEGRATED_SYSTEM"])
    invalid["role"] = "PRIMARY"
    invalid["universe_id"] = estimation_universe_id(invalid)
    with pytest.raises(ReleaseAPreregistrationError, match="Only A-P1 and A-P6"):
        validate_estimation_universe(invalid)


def test_primary_frame_set_is_exact_and_purposive_frames_are_excluded() -> None:
    validate_estimation_universe(_universe())
    for excluded in ("F7", "F9", "F11"):
        frames = list(PRIMARY_ESTIMATION_FRAME_IDS)
        frames[-1] = excluded
        invalid = _universe(frames=frames)
        with pytest.raises(ReleaseAPreregistrationError, match="primary estimation frame set"):
            validate_estimation_universe(invalid)


def test_frame_set_sensitivities_are_predeclared_and_nested_in_primary_set() -> None:
    primary = set(PRIMARY_ESTIMATION_FRAME_IDS)
    assert set(FRAME_SET_SENSITIVITIES) == {
        "NO_PATENT_CROSSOVER",
        "CONVENTIONAL_SOURCE_CORE",
        "NO_CAPABILITY_OR_LOCAL_LANGUAGE",
    }
    assert all(set(frames) < primary for frames in FRAME_SET_SENSITIVITIES.values())


def test_primary_enumeration_roles_cannot_be_silently_narrowed() -> None:
    invalid = _universe(enumeration_roles=["INTEGRATED_SYSTEM"])
    with pytest.raises(ReleaseAPreregistrationError, match="complete countable enumeration-role set"):
        validate_estimation_universe(invalid)


def test_a_p8_is_not_an_unseen_population_estimand_in_v1() -> None:
    invalid = _universe()
    invalid["population_view_id"] = "A-P8"
    invalid["universe_id"] = estimation_universe_id(invalid)
    with pytest.raises(ReleaseAPreregistrationError, match="schema validation failed"):
        validate_estimation_universe(invalid)


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


def test_capture_set_rejects_incompatible_population_view() -> None:
    universe = _universe()
    capture = _capture()
    validate_captures_against_estimation_universe(universe, [capture])

    drift = deepcopy(capture)
    drift["population_view_id"] = "A-P6"
    drift["capture_id"] = product_capture_id(drift)
    with pytest.raises(ReleaseAPreregistrationError, match="population_view_id"):
        validate_captures_against_estimation_universe(universe, [drift])


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


def test_model_envelope_ignores_diagnostic_families_and_spans_admissible_models() -> None:
    envelope = admissible_model_envelope(
        {
            "PAIRWISE_CAPTURE_RECAPTURE_DIAGNOSTIC": (80.0, 500.0),
            "LOG_LINEAR_DEPENDENCE_INTERACTIONS": (125.0, 155.0),
            "BAYESIAN_HIERARCHICAL_SENSITIVITY": (130.0, 170.0),
        },
        n_observed_total=120,
    )
    assert envelope == (125.0, 170.0)


def test_model_envelope_rejects_interval_below_known_observed() -> None:
    with pytest.raises(ReleaseAPreregistrationError, match="below the known observed"):
        admissible_model_envelope(
            {"LOG_LINEAR_DEPENDENCE_INTERACTIONS": (119.0, 150.0)},
            n_observed_total=120,
        )
