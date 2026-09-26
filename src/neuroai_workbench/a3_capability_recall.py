"""Validators for Release-A A3 capability-first recall preregistration.

Freezes conventional terminology versus capability-expanded search families and
the ΔN_capability metrics contract under the A2 checkpoint before any yield
difference is computed. Freeze alone does not execute the recall study, allocate
canonical identities, or start A4+.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from importlib.resources import files
from typing import Any, cast

from neuroai_workbench.a2_bounded_frame_checkpoint import CHECKPOINT_ID
from neuroai_workbench.product_discovery_frames import (
    A1_INITIAL_KNOWN_IDENTITY_SHA256,
    A2_KNOWLEDGE_TIME_CUTOFF,
    A2_WORLD_TIME_CUTOFF,
    DEFAULT_ANALYSIS_UNIVERSE_ID,
    FRAME_REGISTER_VERSION,
    ProductDiscoveryError,
    load_default_frame_register,
)
from neuroai_workbench.release_a_preregistration import FRAME_SET_SENSITIVITIES

RESOURCE_PACKAGE = "neuroai_workbench.resources.discovery"

A3_PREREG_RESOURCE = "RELEASE_A_A3_CAPABILITY_RECALL_PREREGISTRATION.v1.0.json"
A3_PREREG_ID = "RELEASE_A_A3_CAPABILITY_RECALL_PREREGISTRATION_v1.0"
A3_PREREG_SHA256 = "96feb85999f66c80f82ecafb0592db8cb5a00b957668bb01da63e8ccdd069a76"
A3_STUDY_ID = "RELEASE_A_A3_CAPABILITY_FIRST_RECALL_STUDY_v1.0"

CHECKPOINT_SHA256 = "452c8c504990c05edd6ac7c29b542a49ffa4fd81ccdece2bd7ca8e9e0921ca32"
FRAME_REGISTER_BLOB_SHA = "bb3d95226dc0ed528e5eed8e6de707430399b9ae"
F6_UNIVERSE_ID = "RELEASE_A_F6_OPEN_WORLD_QUERY_UNIVERSE_v1.0"
F6_UNIVERSE_SHA256 = "65ff66464b7cba60e0347c061069a59b59f6102041b7a3b24a723a7d09cbdfbc"
LANGUAGE_SCOPE_ID = "EN_PLUS_PRIORITY_NATIVE_v1"

CONVENTIONAL_FAMILY_SET_ID = "A3_CONVENTIONAL_TERMINOLOGY_v1"
CAPABILITY_FAMILY_SET_ID = "A3_CAPABILITY_EXPANDED_v1"

REQUIRED_CONVENTIONAL_FAMILY_IDS = (
    "CONVENTIONAL_BCI_CATEGORY",
    "CONVENTIONAL_NEUROTECHNOLOGY_CATEGORY",
    "CONVENTIONAL_EEG_NEURAL_SENSING_CATEGORY",
    "CONVENTIONAL_NEURAL_INTERFACE_CATEGORY",
    "CONVENTIONAL_NEUROSTIMULATION_CATEGORY",
    "CONVENTIONAL_NEUROFEEDBACK_CATEGORY",
    "CONVENTIONAL_CONSUMER_CLINICAL_NEURODEVICE",
)

REQUIRED_CAPABILITY_FAMILY_IDS = (
    "ATTENTION_VIGILANCE",
    "FATIGUE_DROWSINESS",
    "COGNITIVE_LOAD_WORKLOAD",
    "AFFECTIVE_STRESS_STATE",
    "ADAPTIVE_INTERFACE",
    "NEUROFEEDBACK_TRAINING",
    "BEHAVIORAL_PERSONALIZATION",
    "NEURAL_DECODING_CONTROL",
    "NONTRADITIONAL_FORM_FACTOR",
)

REQUIRED_COMPANION_RATES = (
    "FALSE_POSITIVE_RATE",
    "UNRESOLVED_RATE",
    "DUPLICATE_RATE",
    "UNIQUE_PRODUCT_GAIN",
)

CONVENTIONAL_FRAME_IDS = ("F1", "F2", "F3", "F4", "F5")
CAPABILITY_FRAME_IDS = ("F6",)
ALL_DISCOVERY_FRAME_IDS = ("F1", "F2", "F3", "F4", "F5", "F6")

A3_BOUNDARY = (
    "A3 capability-first recall preregistration freezes conventional terminology "
    "versus capability-expanded search families and the ΔN_capability metrics "
    "contract under the A2 analysis universe before yield interpretation. It does "
    "not establish global completeness, market share, effectiveness, unseen-population "
    "size, commercialization, S2 publication authority, or v4.2 assessment effect. "
    "Freeze alone does not compute ΔN_capability or allocate canonical PRODUCT identity."
)


def content_digest(material: Mapping[str, Any], *, exclude: str) -> str:
    """Return deterministic SHA-256 for a freeze artifact, excluding a self-digest field."""

    payload = {key: value for key, value in material.items() if key != exclude}
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_resource(resource_name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(RESOURCE_PACKAGE).joinpath(resource_name).read_text(encoding="utf-8")),
    )


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProductDiscoveryError(f"{label} must be an object")
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ProductDiscoveryError(f"{label} must be an array")
    return value


def _require_str(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProductDiscoveryError(f"{label} must be a non-empty string")
    return value


def _require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ProductDiscoveryError(f"{label} must be a boolean")
    return value


def _frame(frame_id: str) -> Mapping[str, Any]:
    register = load_default_frame_register()
    frames = cast(list[Mapping[str, Any]], register["frames"])
    return next(frame for frame in frames if frame["frame_id"] == frame_id)


def load_default_a3_capability_recall_preregistration() -> dict[str, Any]:
    """Load the frozen A3 capability-first recall preregistration."""

    prereg = _load_resource(A3_PREREG_RESOURCE)
    validate_a3_capability_recall_preregistration(prereg)
    if prereg["preregistration_sha256"] != A3_PREREG_SHA256:
        raise ProductDiscoveryError("Loaded A3 preregistration digest drifted from frozen A3_PREREG_SHA256")
    return prereg


def a3_freeze_does_not_compute_delta_n() -> str:
    """Freeze alone never implies a measured ΔN_capability result."""

    return "PREREGISTERED_AWAITING_EXECUTION"


def compute_delta_n_capability(
    *,
    conventional_offering_ids: Sequence[str],
    all_discovery_offering_ids: Sequence[str],
) -> dict[str, Any]:
    """Compute ΔN_capability on exact offering IDs only (fail-closed).

    This helper is for the execution stage. The preregistration freeze must not
    invoke it to choose or edit search families.
    """

    conventional = {str(item) for item in conventional_offering_ids if str(item).strip()}
    all_discovery = {str(item) for item in all_discovery_offering_ids if str(item).strip()}
    if not all_discovery >= conventional:
        raise ProductDiscoveryError(
            "N_all_discovery must be a superset of N_conventional_terminology; refuse incoherent increment inputs"
        )
    unique_capability = sorted(all_discovery - conventional)
    return {
        "n_conventional_terminology": len(conventional),
        "n_all_discovery": len(all_discovery),
        "delta_n_capability": len(unique_capability),
        "unique_capability_offering_ids": unique_capability,
        "unique_product_gain": len(unique_capability),
    }


def compute_companion_rates(
    *,
    raw_candidates: int,
    exclude_count: int,
    unresolved_count: int,
    known_identity_duplicate_count: int,
    within_round_duplicate_count: int,
) -> dict[str, float]:
    """Compute false-positive, unresolved, and duplicate rates for the capability arm."""

    if raw_candidates < 0:
        raise ProductDiscoveryError("raw_candidates cannot be negative")
    for label, value in (
        ("exclude_count", exclude_count),
        ("unresolved_count", unresolved_count),
        ("known_identity_duplicate_count", known_identity_duplicate_count),
        ("within_round_duplicate_count", within_round_duplicate_count),
    ):
        if value < 0:
            raise ProductDiscoveryError(f"{label} cannot be negative")
    if raw_candidates == 0:
        raise ProductDiscoveryError("raw_candidates must be positive to report companion rates")
    duplicate_count = known_identity_duplicate_count + within_round_duplicate_count
    return {
        "false_positive_rate": exclude_count / raw_candidates,
        "unresolved_rate": unresolved_count / raw_candidates,
        "duplicate_rate": duplicate_count / raw_candidates,
    }


def validate_a3_capability_recall_preregistration(prereg: Mapping[str, Any]) -> None:
    """Validate the frozen A3 search-family and metrics-contract preregistration."""

    required = (
        "preregistration_id",
        "preregistration_sha256",
        "status",
        "study_id",
        "census_registered_at",
        "analysis_universe_id",
        "world_time_cutoff",
        "knowledge_time_cutoff",
        "a2_checkpoint_id",
        "a2_checkpoint_sha256",
        "round_start_known_identity_set_sha256",
        "language_scope_id",
        "frame_register_version",
        "frame_register_blob_sha",
        "f6_query_universe_id",
        "f6_query_universe_sha256",
        "predeclaration_rule",
        "conventional_search_family_set_id",
        "capability_search_family_set_id",
        "conventional_search_families",
        "capability_search_families",
        "evidence_substrate",
        "metrics_contract",
        "execution_gate",
        "boundary",
    )
    missing = [field for field in required if field not in prereg]
    if missing:
        raise ProductDiscoveryError("A3 preregistration missing fields: " + ", ".join(missing))

    if prereg["preregistration_id"] != A3_PREREG_ID:
        raise ProductDiscoveryError(f"preregistration_id must be {A3_PREREG_ID}")
    if prereg["status"] != "FROZEN_v1.0":
        raise ProductDiscoveryError("status must be FROZEN_v1.0")
    if prereg["study_id"] != A3_STUDY_ID:
        raise ProductDiscoveryError(f"study_id must be {A3_STUDY_ID}")
    if content_digest(prereg, exclude="preregistration_sha256") != prereg["preregistration_sha256"]:
        raise ProductDiscoveryError("preregistration_sha256 does not match content digest")

    if prereg["analysis_universe_id"] != DEFAULT_ANALYSIS_UNIVERSE_ID:
        raise ProductDiscoveryError("analysis_universe_id must equal the frozen A2 analysis universe")
    if prereg["world_time_cutoff"] != A2_WORLD_TIME_CUTOFF:
        raise ProductDiscoveryError("world_time_cutoff must equal the frozen A2 world cutoff")
    if prereg["knowledge_time_cutoff"] != A2_KNOWLEDGE_TIME_CUTOFF:
        raise ProductDiscoveryError("knowledge_time_cutoff must equal the frozen A2 knowledge cutoff")
    if prereg["a2_checkpoint_id"] != CHECKPOINT_ID:
        raise ProductDiscoveryError("a2_checkpoint_id must equal the frozen A2 checkpoint")
    if prereg["a2_checkpoint_sha256"] != CHECKPOINT_SHA256:
        raise ProductDiscoveryError("a2_checkpoint_sha256 must equal the frozen A2 checkpoint")
    if prereg["round_start_known_identity_set_sha256"] != A1_INITIAL_KNOWN_IDENTITY_SHA256:
        raise ProductDiscoveryError("round_start_known_identity_set_sha256 must equal the A1 known-identity digest")
    if prereg["language_scope_id"] != LANGUAGE_SCOPE_ID:
        raise ProductDiscoveryError("language_scope_id must be EN_PLUS_PRIORITY_NATIVE_v1")
    if prereg["frame_register_version"] != FRAME_REGISTER_VERSION:
        raise ProductDiscoveryError("frame_register_version mismatch")
    if prereg["frame_register_blob_sha"] != FRAME_REGISTER_BLOB_SHA:
        raise ProductDiscoveryError("frame_register_blob_sha mismatch")
    if prereg["f6_query_universe_id"] != F6_UNIVERSE_ID:
        raise ProductDiscoveryError("f6_query_universe_id must equal the frozen F6 universe")
    if prereg["f6_query_universe_sha256"] != F6_UNIVERSE_SHA256:
        raise ProductDiscoveryError("f6_query_universe_sha256 must equal the frozen F6 universe digest")
    if prereg["conventional_search_family_set_id"] != CONVENTIONAL_FAMILY_SET_ID:
        raise ProductDiscoveryError("conventional_search_family_set_id mismatch")
    if prereg["capability_search_family_set_id"] != CAPABILITY_FAMILY_SET_ID:
        raise ProductDiscoveryError("capability_search_family_set_id mismatch")
    if prereg["boundary"] != A3_BOUNDARY:
        raise ProductDiscoveryError("boundary text drift")

    conventional = _require_list(prereg["conventional_search_families"], "conventional_search_families")
    capability = _require_list(prereg["capability_search_families"], "capability_search_families")
    conventional_ids: list[str] = []
    for row in conventional:
        mapping = _require_mapping(row, "conventional family")
        conventional_ids.append(_require_str(mapping.get("family_id"), "conventional family_id"))
    capability_ids: list[str] = []
    for row in capability:
        mapping = _require_mapping(row, "capability family")
        capability_ids.append(_require_str(mapping.get("family_id"), "capability family_id"))
    if tuple(conventional_ids) != REQUIRED_CONVENTIONAL_FAMILY_IDS:
        raise ProductDiscoveryError("conventional_search_families must equal the frozen conventional set in order")
    if tuple(capability_ids) != REQUIRED_CAPABILITY_FAMILY_IDS:
        raise ProductDiscoveryError("capability_search_families must equal the frozen capability set in order")

    for row in conventional:
        mapping = _require_mapping(row, "conventional family")
        if mapping.get("terminology_class") != "CATEGORY_BRANDED":
            raise ProductDiscoveryError("conventional families must be CATEGORY_BRANDED")
        terms = _require_list(mapping.get("example_terms"), "example_terms")
        if not terms:
            raise ProductDiscoveryError("conventional family example_terms cannot be empty")
        for term in terms:
            _require_str(term, "example term")

    f6_families = set(cast(list[str], _frame("F6")["query_families"]))
    for row in capability:
        mapping = _require_mapping(row, "capability family")
        if mapping.get("terminology_class") != "CAPABILITY_FUNCTION":
            raise ProductDiscoveryError("capability families must be CAPABILITY_FUNCTION")
        binding = _require_str(mapping.get("f6_query_family_binding"), "f6_query_family_binding")
        if binding not in f6_families:
            raise ProductDiscoveryError(f"f6_query_family_binding {binding!r} is not in the frozen F6 query family set")

    substrate = _require_mapping(prereg["evidence_substrate"], "evidence_substrate")
    if tuple(substrate.get("conventional_frame_ids", ())) != CONVENTIONAL_FRAME_IDS:
        raise ProductDiscoveryError("conventional_frame_ids must be F1-F5")
    if tuple(substrate.get("capability_frame_ids", ())) != CAPABILITY_FRAME_IDS:
        raise ProductDiscoveryError("capability_frame_ids must be F6 only")
    if tuple(substrate.get("all_discovery_frame_ids", ())) != ALL_DISCOVERY_FRAME_IDS:
        raise ProductDiscoveryError("all_discovery_frame_ids must be F1-F6")
    if substrate.get("conventional_frame_set_alignment") != "CONVENTIONAL_SOURCE_CORE":
        raise ProductDiscoveryError("conventional_frame_set_alignment must be CONVENTIONAL_SOURCE_CORE")
    if set(FRAME_SET_SENSITIVITIES["CONVENTIONAL_SOURCE_CORE"]) != set(CONVENTIONAL_FRAME_IDS):
        raise ProductDiscoveryError("CONVENTIONAL_SOURCE_CORE sensitivity drift relative to A3 conventional frames")
    for flag in (
        "f6_is_controlled_capability_frame",
        "f7_f9_f11_estimator_excluded",
        "f10_patent_leads_are_not_products",
        "f8_reserved_for_a4",
        "increment_requires_exact_offering_id",
        "no_identity_allocation_by_implication",
    ):
        if not _require_bool(substrate.get(flag), flag):
            raise ProductDiscoveryError(f"{flag} must be true")
    if substrate.get("identity_unit") != "CANONICAL_PRODUCT_OFFERING":
        raise ProductDiscoveryError("identity_unit must be CANONICAL_PRODUCT_OFFERING")

    metrics = _require_mapping(prereg["metrics_contract"], "metrics_contract")
    if metrics.get("primary_estimand_id") != "DELTA_N_CAPABILITY":
        raise ProductDiscoveryError("primary_estimand_id must be DELTA_N_CAPABILITY")
    if metrics.get("formula") != "DELTA_N_CAPABILITY = N_ALL_DISCOVERY - N_CONVENTIONAL_TERMINOLOGY":
        raise ProductDiscoveryError("metrics formula drift")
    rates = tuple(_require_list(metrics.get("required_companion_rates"), "required_companion_rates"))
    if rates != REQUIRED_COMPANION_RATES:
        raise ProductDiscoveryError("required_companion_rates must equal the frozen companion-rate set")
    stratification = _require_mapping(metrics.get("stratification_policy"), "stratification_policy")
    if not _require_bool(stratification.get("no_post_hoc_stratum_invention"), "no_post_hoc_stratum_invention"):
        raise ProductDiscoveryError("no_post_hoc_stratum_invention must be true")
    denominators = _require_mapping(metrics.get("denominator_rules"), "denominator_rules")
    for flag in (
        "raw_search_hits_are_not_the_increment_unit",
        "only_include_resolved_exact_offering_ids_enter_n_counts",
        "unresolved_borderline_abstain_exclude_do_not_inflate_delta_n",
        "known_a1_overlaps_are_duplicates_not_unique_gain",
    ):
        if not _require_bool(denominators.get(flag), flag):
            raise ProductDiscoveryError(f"{flag} must be true")

    gate = _require_mapping(prereg["execution_gate"], "execution_gate")
    for flag in (
        "requires_frozen_preregistration_before_yield",
        "freeze_alone_does_not_compute_delta_n",
        "does_not_start_a4_or_later",
        "does_not_mutate_rau",
        "does_not_allocate_canonical_identity",
        "post_hoc_family_edits_prohibited",
    ):
        if not _require_bool(gate.get(flag), flag):
            raise ProductDiscoveryError(f"{flag} must be true")

    _require_str(prereg["predeclaration_rule"], "predeclaration_rule")
    _require_str(prereg["census_registered_at"], "census_registered_at")
