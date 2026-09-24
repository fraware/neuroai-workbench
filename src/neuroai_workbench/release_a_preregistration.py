from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from importlib.resources import files
from typing import Any, cast

from jsonschema import Draft202012Validator

from neuroai_workbench.product_discovery_frames import (
    FRAME_ID_SET,
    FRAME_REGISTER_VERSION,
    REGISTRY_PROJECTION_VERSION,
    load_default_frame_register,
    validate_product_capture,
)
from neuroai_workbench.product_registry import (
    BOUNDARY_CONTRACT_ID,
    BOUNDARY_CONTRACT_SEMANTIC_BLOB,
    CURRENTNESS_POLICY_ID,
    POPULATION_VIEW_POLICY_ID,
)

RESOURCE_PACKAGE = "neuroai_workbench.resources.analysis"
ESTIMATION_UNIVERSE_SCHEMA = "RELEASE_A_ESTIMATION_UNIVERSE.schema.json"
LANGUAGE_SCOPE_RESOURCE = "RELEASE_A_LANGUAGE_SCOPE.v1.0.json"

PREREGISTRATION_VERSION = "RELEASE_A_ANALYSIS_PREREGISTRATION_v1.0"
LANGUAGE_SCOPE_ID = "EN_PLUS_PRIORITY_NATIVE_v1"
REFERENCE_STANDARD_ID = "D4_PRODUCT_REFERENCE_STANDARD_v1.0"
REFERENCE_STANDARD_VERSION = "1.0"
REFERENCE_STANDARD_VALIDATION_STATE = "FROZEN_WORKING_REFERENCE"

PRIMARY_VIEWS = frozenset({"A-P1", "A-P6"})
SECONDARY_VIEWS = frozenset({"A-P4"})
ESTIMABLE_VIEWS = PRIMARY_VIEWS | SECONDARY_VIEWS
COUNTABLE_ENUMERATION_ROLES = frozenset(
    {"INTEGRATED_SYSTEM", "COMPONENT_OR_SUBSYSTEM", "STANDALONE_SOFTWARE_OR_SERVICE"}
)

REQUIRED_MODEL_FAMILIES = (
    "OBSERVED_ONLY_BASELINE",
    "PAIRWISE_CAPTURE_RECAPTURE_DIAGNOSTIC",
    "LOG_LINEAR_MULTIPLE_SYSTEMS",
    "DEPENDENCE_AWARE_INTERACTION",
    "STRATIFIED_MODEL",
    "BAYESIAN_HIERARCHICAL_SENSITIVITY",
)

REQUIRED_DIAGNOSTICS = frozenset(
    {
        "FRAME_DEPENDENCE",
        "CAPTURE_HETEROGENEITY",
        "SPARSE_OVERLAP_CELLS",
        "IDENTIFIABILITY_STABILITY",
        "FRAME_GROUPING_SENSITIVITY",
        "BOUNDARY_IDENTITY_SENSITIVITY",
        "ZERO_CAPTURE_RISK",
        "HELD_BACK_ROUND_PREDICTIVE_CHECK",
        "MODEL_SPREAD",
        "KNOWN_EXTERNAL_ONLY_IDENTITIES",
    }
)

REQUIRED_SENSITIVITIES = frozenset(
    {
        "UNRESOLVED_IDENTITY",
        "BORDERLINE_ABSTAIN",
        "CURRENTNESS_UNCERTAINTY",
        "MULTILINGUAL_GAIN",
        "ENUMERATION_ROLE",
        "FRAME_GROUPING",
    }
)

PREREGISTRATION_BOUNDARY = (
    "Release-A population estimates apply only to one preregistered product identity, population view, "
    "jurisdiction/language scope, cutoff pair, and discovery-frame universe. Observed identities remain "
    "distinct from the latent unseen residual; no estimate establishes a complete global census or market share."
)


class ReleaseAPreregistrationError(ValueError):
    """Raised when a Release-A estimation universe violates P0.5 semantics."""


def _schema() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(RESOURCE_PACKAGE).joinpath(ESTIMATION_UNIVERSE_SCHEMA).read_text(encoding="utf-8")),
    )


def _schema_errors(value: Any) -> list[str]:
    validator = Draft202012Validator(_schema())
    return [
        f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    ]


def load_default_language_scope() -> dict[str, Any]:
    scope = cast(
        dict[str, Any],
        json.loads(files(RESOURCE_PACKAGE).joinpath(LANGUAGE_SCOPE_RESOURCE).read_text(encoding="utf-8")),
    )
    if scope.get("language_scope_id") != LANGUAGE_SCOPE_ID:
        raise ReleaseAPreregistrationError(f"language_scope_id must be {LANGUAGE_SCOPE_ID}")
    if scope.get("status") != "FROZEN_v1.0":
        raise ReleaseAPreregistrationError("Release-A language scope must be FROZEN_v1.0")
    strata = scope.get("matched_native_strata")
    if not isinstance(strata, list) or not strata:
        raise ReleaseAPreregistrationError("Release-A language scope must define matched native strata")
    return scope


def default_estimation_frame_ids() -> tuple[str, ...]:
    """Return exactly the estimation-eligible frames in the frozen P0.4 register."""

    register = load_default_frame_register()
    frames = cast(list[Mapping[str, Any]], register["frames"])
    return tuple(sorted(frame["frame_id"] for frame in frames if frame["capture_estimation_eligible"]))


def estimation_universe_id(universe: Mapping[str, Any]) -> str:
    """Return a deterministic identifier for one preregistered estimation universe."""

    material = {
        key: universe.get(key)
        for key in (
            "preregistration_version",
            "role",
            "population_view_id",
            "identity_level",
            "included_enumeration_roles",
            "analysis_jurisdiction_scope",
            "world_time_cutoff",
            "knowledge_time_cutoff",
            "language_scope_id",
            "frame_register_version",
            "capture_frame_ids",
            "registry_projection_version",
            "population_view_policy_id",
            "currentness_policy_id",
            "technical_equivalence_policy_id",
        )
    }
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "RAEU-" + hashlib.sha256(encoded).hexdigest()


def validate_estimation_universe(universe: Mapping[str, Any]) -> None:
    errors = _schema_errors(universe)
    if errors:
        raise ReleaseAPreregistrationError(
            "Release-A estimation-universe schema validation failed: " + "; ".join(errors)
        )

    expected = {
        "preregistration_version": PREREGISTRATION_VERSION,
        "boundary_contract_id": BOUNDARY_CONTRACT_ID,
        "boundary_contract_semantic_blob": BOUNDARY_CONTRACT_SEMANTIC_BLOB,
        "reference_standard_id": REFERENCE_STANDARD_ID,
        "reference_standard_version": REFERENCE_STANDARD_VERSION,
        "reference_standard_validation_state": REFERENCE_STANDARD_VALIDATION_STATE,
        "registry_projection_version": REGISTRY_PROJECTION_VERSION,
        "population_view_policy_id": POPULATION_VIEW_POLICY_ID,
        "currentness_policy_id": CURRENTNESS_POLICY_ID,
        "frame_register_version": FRAME_REGISTER_VERSION,
        "language_scope_id": LANGUAGE_SCOPE_ID,
        "identity_level": "OFFERING",
        "observed_identity_unit": "CANONICAL_PRODUCT_OFFERING",
        "latent_residual_unit": "UNOBSERVED_DISTINCT_PRODUCT_OFFERINGS",
        "naive_pairwise_role": "DIAGNOSTIC_ONLY",
        "technical_equivalence_policy_id": None,
    }
    for field, value in expected.items():
        if universe.get(field) != value:
            raise ReleaseAPreregistrationError(f"{field} must be {value!r}")

    if universe["universe_id"] != estimation_universe_id(universe):
        raise ReleaseAPreregistrationError("universe_id does not match the deterministic estimand boundary")

    load_default_language_scope()

    view_id = str(universe["population_view_id"])
    role = str(universe["role"])
    if view_id == "A-P8":
        raise ReleaseAPreregistrationError(
            "A-P8 unseen estimation is not enabled in v1.0; it requires a preregistration successor after "
            "technical-equivalence semantics are frozen before capture construction"
        )
    if view_id not in ESTIMABLE_VIEWS:
        raise ReleaseAPreregistrationError(f"Population view {view_id} is not preregistered for unseen estimation")
    if role == "PRIMARY" and view_id not in PRIMARY_VIEWS:
        raise ReleaseAPreregistrationError("Only A-P1 and A-P6 are primary Release-A estimation views in v1.0")
    if role == "SECONDARY" and view_id not in SECONDARY_VIEWS:
        raise ReleaseAPreregistrationError("Only A-P4 is a secondary Release-A estimation view in v1.0")

    roles = set(cast(list[str], universe["included_enumeration_roles"]))
    if not roles or not roles <= COUNTABLE_ENUMERATION_ROLES:
        raise ReleaseAPreregistrationError("included_enumeration_roles contains a non-countable role")
    if view_id == "A-P4" and roles != {"INTEGRATED_SYSTEM"}:
        raise ReleaseAPreregistrationError("A-P4 estimation must use only INTEGRATED_SYSTEM offerings")

    frames = set(cast(list[str], universe["capture_frame_ids"]))
    if not frames or not frames <= FRAME_ID_SET:
        raise ReleaseAPreregistrationError("capture_frame_ids contains an unknown or empty frame set")
    expected_frames = set(default_estimation_frame_ids())
    if frames != expected_frames:
        raise ReleaseAPreregistrationError(
            "capture_frame_ids must exactly match the frozen v1.0 estimation-eligible frame set"
        )

    models = tuple(cast(list[str], universe["model_families"]))
    if set(models) != set(REQUIRED_MODEL_FAMILIES) or len(models) != len(REQUIRED_MODEL_FAMILIES):
        raise ReleaseAPreregistrationError("model_families must contain the complete preregistered v1.0 comparison set")

    diagnostics = set(cast(list[str], universe["required_diagnostics"]))
    if diagnostics != REQUIRED_DIAGNOSTICS:
        raise ReleaseAPreregistrationError("required_diagnostics must equal the preregistered v1.0 diagnostic set")

    sensitivities = set(cast(list[str], universe["required_sensitivities"]))
    if sensitivities != REQUIRED_SENSITIVITIES:
        raise ReleaseAPreregistrationError("required_sensitivities must equal the preregistered v1.0 sensitivity set")


def validate_captures_against_estimation_universe(
    universe: Mapping[str, Any],
    captures: Sequence[Mapping[str, Any]],
) -> None:
    """Reject discovery captures from an incompatible estimand boundary."""

    validate_estimation_universe(universe)
    register = load_default_frame_register()
    frame_eligibility = {
        frame["frame_id"]: bool(frame["capture_estimation_eligible"])
        for frame in cast(list[Mapping[str, Any]], register["frames"])
    }
    allowed_frames = set(cast(list[str], universe["capture_frame_ids"]))

    for capture in captures:
        validate_product_capture(capture)
        expected_eligible = frame_eligibility[str(capture["frame_id"])]
        if bool(capture["capture_estimation_eligible"]) != expected_eligible:
            raise ReleaseAPreregistrationError(
                "Capture estimation eligibility conflicts with the frozen discovery-frame register"
            )

        for capture_field, universe_field in (
            ("registry_projection_version", "registry_projection_version"),
            ("frame_register_version", "frame_register_version"),
            ("population_view_id", "population_view_id"),
            ("analysis_jurisdiction_scope", "analysis_jurisdiction_scope"),
            ("language_scope_id", "language_scope_id"),
            ("world_time_cutoff", "world_time_cutoff"),
            ("knowledge_time_cutoff", "knowledge_time_cutoff"),
        ):
            if capture[capture_field] != universe[universe_field]:
                raise ReleaseAPreregistrationError(
                    f"Capture {capture_field} is incompatible with the preregistered estimation universe"
                )

        if expected_eligible and capture["frame_id"] not in allowed_frames:
            raise ReleaseAPreregistrationError(
                "Estimation-eligible capture comes from a frame outside the preregistered model universe"
            )


def decompose_observed_and_unseen(
    *,
    n_observed_total: int,
    n_observed_capture_support: int,
    model_total_estimate: float,
) -> dict[str, float | int | bool]:
    """Separate known external-only products from the model's zero-capture residual."""

    if n_observed_total < 0 or n_observed_capture_support < 0:
        raise ReleaseAPreregistrationError("Observed counts cannot be negative")
    if n_observed_capture_support > n_observed_total:
        raise ReleaseAPreregistrationError("Capture-support count cannot exceed total observed identities")
    if model_total_estimate < n_observed_capture_support:
        raise ReleaseAPreregistrationError("Model total cannot be below identities used in its capture support")

    external_only = n_observed_total - n_observed_capture_support
    zero_capture_estimate = model_total_estimate - n_observed_capture_support
    coherent = model_total_estimate >= n_observed_total
    unseen = zero_capture_estimate - external_only if coherent else float("nan")
    coverage = n_observed_total / model_total_estimate if coherent and model_total_estimate > 0 else float("nan")

    return {
        "n_observed_total": n_observed_total,
        "n_observed_capture_support": n_observed_capture_support,
        "n_observed_external_only": external_only,
        "model_total_estimate": model_total_estimate,
        "model_zero_capture_estimate": zero_capture_estimate,
        "model_consistent_with_known_observed": coherent,
        "n_unobserved_estimated": unseen,
        "coverage_estimated": coverage,
    }
