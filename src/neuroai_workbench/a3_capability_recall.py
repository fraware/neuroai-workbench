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


A3_STUDY_RESOURCE = "RELEASE_A_A3_CAPABILITY_FIRST_RECALL_STUDY.v1.0.json"
A3_STUDY_PACKET_ID = "RELEASE_A_A3_CAPABILITY_FIRST_RECALL_STUDY_v1.0"
A3_STUDY_PACKET_SHA256 = "b7a6cd6b509f1fa3b8481fbd821589b8f7c1eaf40cec8c14df992e38360285d8"

A3_STUDY_BOUNDARY = (
    "Repository-safe A3 capability-first recall study under the frozen A3 "
    "preregistration. ΔN_capability counts only exact canonical PRODUCT offering "
    "IDs. No identity allocation by implication. No global completeness, market "
    "share, effectiveness, unseen-population size, S2 publication authority, or "
    "v4.2 assessment effect. Does not execute A4+."
)

SOURCE_PACKET_SHA256 = {
    "F1": "4d4f8fdf655882315a6f53499f4932e91d1596c29c1a873c86dde243cd9c4c85",
    "F2": "d66590970362ac82b880e5fe4b9d7c66a913b6dc91618d31fbf67fa39a31c39b",
    "F3": "584ab1dae1fcf0885a51ec527bea953a2ee4ad5452c10b7bb6985ca652edb82b",
    "F4": "abaff10977ad1f7f84b3311b6619d403184da4d94d805714913851c7d87ebfc3",
    "F5": "0ce4e51a4f968ef452a1031d651e30119498fd4969563f91cadbccdeb2eaf3f5",
    "F6": "95e13cc7dc896a0bad3f2d3862fda7475ff5e35291341f6bdbe5b9a0372e2e4c",
}

KNOWN_OFFERING_IDS = (
    "PRD-EMOTIV-EPOC-X",
    "PRD-FLOW-FL-100",
    "PRD-MODIUS-SPERO",
    "PRD-MUSE-S-ATHENA",
    "PRD-NEXTSENSE-SMARTBUDS",
    "PRD-SYNCHRON-STENTRODE",
)


def load_default_a3_capability_recall_study() -> dict[str, Any]:
    """Load the frozen A3 capability-first recall study packet."""

    packet = _load_resource(A3_STUDY_RESOURCE)
    validate_a3_capability_recall_study(packet)
    if packet["packet_sha256"] != A3_STUDY_PACKET_SHA256:
        raise ProductDiscoveryError("Loaded A3 study digest drifted from frozen A3_STUDY_PACKET_SHA256")
    return packet


def validate_a3_capability_recall_study(packet: Mapping[str, Any]) -> None:
    """Validate the executed A3 recall study against the frozen preregistration."""

    required = (
        "packet_id",
        "packet_sha256",
        "status",
        "assembled_on",
        "study_id",
        "preregistration_id",
        "preregistration_sha256",
        "analysis_universe_id",
        "world_time_cutoff",
        "knowledge_time_cutoff",
        "a2_checkpoint_id",
        "a2_checkpoint_sha256",
        "round_start_known_identity_set_sha256",
        "final_known_identity_ids",
        "final_known_identity_set_sha256",
        "language_scope_id",
        "conventional_search_family_set_id",
        "capability_search_family_set_id",
        "f6_query_universe_id",
        "f6_query_universe_sha256",
        "evidence_substrate_bindings",
        "n_conventional_terminology",
        "n_all_discovery",
        "delta_n_capability",
        "unique_product_gain",
        "conventional_offering_ids",
        "all_discovery_offering_ids",
        "unique_capability_offering_ids",
        "conventional_offering_set_sha256",
        "all_discovery_offering_set_sha256",
        "capability_arm_rates",
        "stratification",
        "new_canonical_allocations",
        "authority_controls",
        "key_result",
        "next_required_state",
        "boundary",
    )
    missing = [field for field in required if field not in packet]
    if missing:
        raise ProductDiscoveryError("A3 study packet missing fields: " + ", ".join(missing))

    if packet["packet_id"] != A3_STUDY_PACKET_ID:
        raise ProductDiscoveryError(f"packet_id must be {A3_STUDY_PACKET_ID}")
    if packet["status"] != "CONTROLLED_RESEARCH_PACKET_REPOSITORY_SAFE":
        raise ProductDiscoveryError("status must be CONTROLLED_RESEARCH_PACKET_REPOSITORY_SAFE")
    if packet["study_id"] != A3_STUDY_ID:
        raise ProductDiscoveryError(f"study_id must be {A3_STUDY_ID}")
    if content_digest(packet, exclude="packet_sha256") != packet["packet_sha256"]:
        raise ProductDiscoveryError("packet_sha256 does not match content digest")
    if packet["preregistration_id"] != A3_PREREG_ID:
        raise ProductDiscoveryError("preregistration_id must equal frozen A3 preregistration")
    if packet["preregistration_sha256"] != A3_PREREG_SHA256:
        raise ProductDiscoveryError("preregistration_sha256 must equal frozen A3 preregistration digest")
    if packet["analysis_universe_id"] != DEFAULT_ANALYSIS_UNIVERSE_ID:
        raise ProductDiscoveryError("analysis_universe_id must equal the frozen A2 analysis universe")
    if packet["world_time_cutoff"] != A2_WORLD_TIME_CUTOFF:
        raise ProductDiscoveryError("world_time_cutoff must equal the frozen A2 world cutoff")
    if packet["knowledge_time_cutoff"] != A2_KNOWLEDGE_TIME_CUTOFF:
        raise ProductDiscoveryError("knowledge_time_cutoff must equal the frozen A2 knowledge cutoff")
    if packet["a2_checkpoint_id"] != CHECKPOINT_ID:
        raise ProductDiscoveryError("a2_checkpoint_id must equal the frozen A2 checkpoint")
    if packet["a2_checkpoint_sha256"] != CHECKPOINT_SHA256:
        raise ProductDiscoveryError("a2_checkpoint_sha256 must equal the frozen A2 checkpoint")
    if packet["round_start_known_identity_set_sha256"] != A1_INITIAL_KNOWN_IDENTITY_SHA256:
        raise ProductDiscoveryError("round_start_known_identity_set_sha256 must equal the A1 known-identity digest")
    if packet["language_scope_id"] != LANGUAGE_SCOPE_ID:
        raise ProductDiscoveryError("language_scope_id must be EN_PLUS_PRIORITY_NATIVE_v1")
    if packet["conventional_search_family_set_id"] != CONVENTIONAL_FAMILY_SET_ID:
        raise ProductDiscoveryError("conventional_search_family_set_id mismatch")
    if packet["capability_search_family_set_id"] != CAPABILITY_FAMILY_SET_ID:
        raise ProductDiscoveryError("capability_search_family_set_id mismatch")
    if packet["f6_query_universe_id"] != F6_UNIVERSE_ID:
        raise ProductDiscoveryError("f6_query_universe_id must equal the frozen F6 universe")
    if packet["f6_query_universe_sha256"] != F6_UNIVERSE_SHA256:
        raise ProductDiscoveryError("f6_query_universe_sha256 must equal the frozen F6 universe digest")
    if packet["boundary"] != A3_STUDY_BOUNDARY:
        raise ProductDiscoveryError("boundary text drift")

    final_ids = [str(item) for item in _require_list(packet["final_known_identity_ids"], "final_known_identity_ids")]
    if tuple(sorted(final_ids)) != KNOWN_OFFERING_IDS:
        raise ProductDiscoveryError("final_known_identity_ids must equal the frozen A1 six offering set")
    if packet["final_known_identity_set_sha256"] != A1_INITIAL_KNOWN_IDENTITY_SHA256:
        raise ProductDiscoveryError("final_known_identity_set_sha256 must equal the A1 known-identity digest")

    conventional_ids = [
        str(item) for item in _require_list(packet["conventional_offering_ids"], "conventional_offering_ids")
    ]
    all_ids = [str(item) for item in _require_list(packet["all_discovery_offering_ids"], "all_discovery_offering_ids")]
    unique_ids = [
        str(item) for item in _require_list(packet["unique_capability_offering_ids"], "unique_capability_offering_ids")
    ]
    computed = compute_delta_n_capability(
        conventional_offering_ids=conventional_ids,
        all_discovery_offering_ids=all_ids,
    )
    if int(packet["n_conventional_terminology"]) != computed["n_conventional_terminology"]:
        raise ProductDiscoveryError("n_conventional_terminology does not match exact offering set")
    if int(packet["n_all_discovery"]) != computed["n_all_discovery"]:
        raise ProductDiscoveryError("n_all_discovery does not match exact offering set")
    if int(packet["delta_n_capability"]) != computed["delta_n_capability"]:
        raise ProductDiscoveryError("delta_n_capability does not match exact offering increment")
    if int(packet["unique_product_gain"]) != computed["unique_product_gain"]:
        raise ProductDiscoveryError("unique_product_gain must equal delta_n_capability")
    if unique_ids != computed["unique_capability_offering_ids"]:
        raise ProductDiscoveryError("unique_capability_offering_ids drift from computed increment")
    if packet["conventional_offering_set_sha256"] != id_set_digest(conventional_ids):
        raise ProductDiscoveryError("conventional_offering_set_sha256 mismatch")
    if packet["all_discovery_offering_set_sha256"] != id_set_digest(all_ids):
        raise ProductDiscoveryError("all_discovery_offering_set_sha256 mismatch")
    if int(packet["new_canonical_allocations"]) != 0:
        raise ProductDiscoveryError("new_canonical_allocations must be 0")

    substrate = _require_mapping(packet["evidence_substrate_bindings"], "evidence_substrate_bindings")
    if tuple(substrate.get("conventional_frame_ids", ())) != CONVENTIONAL_FRAME_IDS:
        raise ProductDiscoveryError("conventional_frame_ids must be F1-F5")
    if tuple(substrate.get("capability_frame_ids", ())) != CAPABILITY_FRAME_IDS:
        raise ProductDiscoveryError("capability_frame_ids must be F6 only")
    if tuple(substrate.get("all_discovery_frame_ids", ())) != ALL_DISCOVERY_FRAME_IDS:
        raise ProductDiscoveryError("all_discovery_frame_ids must be F1-F6")
    sources = _require_list(substrate.get("source_packets"), "source_packets")
    if len(sources) != 6:
        raise ProductDiscoveryError("source_packets must bind exactly F1-F6 packets")
    seen_frames: list[str] = []
    for row in sources:
        mapping = _require_mapping(row, "source packet")
        frame_id = _require_str(mapping.get("frame_id"), "source frame_id")
        seen_frames.append(frame_id)
        expected = SOURCE_PACKET_SHA256.get(frame_id)
        if expected is None:
            raise ProductDiscoveryError(f"unexpected source frame_id {frame_id}")
        if mapping.get("packet_sha256") != expected:
            raise ProductDiscoveryError(f"source packet digest drift for {frame_id}")
    if tuple(seen_frames) != ALL_DISCOVERY_FRAME_IDS:
        raise ProductDiscoveryError("source_packets must be ordered F1-F6")

    rates = _require_mapping(packet["capability_arm_rates"], "capability_arm_rates")
    if rates.get("frame_id") != "F6":
        raise ProductDiscoveryError("capability_arm_rates.frame_id must be F6")
    computed_rates = compute_companion_rates(
        raw_candidates=int(rates["raw_candidates"]),
        exclude_count=int(rates["exclude_count"]),
        unresolved_count=int(rates["unresolved_count"]),
        known_identity_duplicate_count=int(rates["known_identity_duplicate_count"]),
        within_round_duplicate_count=int(rates["within_round_duplicate_count"]),
    )
    for key, value in computed_rates.items():
        if float(rates[key]) != value:
            raise ProductDiscoveryError(f"{key} does not match capability-arm accounting")

    stratification = _require_mapping(packet["stratification"], "stratification")
    _require_list(stratification.get("by_product_class"), "by_product_class")
    _require_list(stratification.get("by_jurisdiction"), "by_jurisdiction")

    controls = _require_mapping(packet["authority_controls"], "authority_controls")
    for flag in (
        "no_identity_allocation_by_implication",
        "increments_only_on_exact_offering_ids",
        "raw_search_hits_are_not_the_increment_unit",
        "f7_f9_f11_estimator_excluded",
        "f10_patent_leads_are_not_products",
        "f8_reserved_for_a4_not_executed",
        "rau_not_mutated",
        "post_hoc_family_edits_prohibited",
    ):
        if not _require_bool(controls.get(flag), flag):
            raise ProductDiscoveryError(f"{flag} must be true")

    key_result = _require_mapping(packet["key_result"], "key_result")
    if key_result.get("headline") != "DELTA_N_CAPABILITY":
        raise ProductDiscoveryError("key_result.headline must be DELTA_N_CAPABILITY")
    if int(key_result["delta_n_capability"]) != int(packet["delta_n_capability"]):
        raise ProductDiscoveryError("key_result.delta_n_capability mismatch")
    if "A4" not in str(packet["next_required_state"]):
        raise ProductDiscoveryError("next_required_state must gate A4 next")
    if "A5" in str(packet["next_required_state"]) and "not A5" not in str(packet["next_required_state"]):
        raise ProductDiscoveryError("next_required_state must keep A5+ out of scope")


def id_set_digest(ids: Sequence[str]) -> str:
    """Return SHA-256 over the sorted unique ID list."""

    encoded = json.dumps(sorted({str(item) for item in ids}), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
