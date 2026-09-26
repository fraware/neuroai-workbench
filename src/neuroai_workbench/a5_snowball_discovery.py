"""Validators for Release-A A5 controlled snowball discovery preregistration.

Freezes the snowball edge taxonomy, parent-seed provenance rules, round metrics
contract (Y_r, D_r, X_r, U_r, m_r), marginal-yield decomposition dimensions, and
permitted stop descriptions under the A2 checkpoint before any round yield is
computed. Freeze alone does not execute the snowball study, allocate canonical
identities, or start A6+.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from importlib.resources import files
from typing import Any, cast

from neuroai_workbench.a2_bounded_frame_checkpoint import CHECKPOINT_ID
from neuroai_workbench.a3_capability_recall import (
    A3_PREREG_ID,
    A3_PREREG_SHA256,
    A3_STUDY_ID,
    A3_STUDY_PACKET_SHA256,
)
from neuroai_workbench.a4_multilingual_sensitivity import (
    A4_PREREG_ID,
    A4_PREREG_SHA256,
    A4_STUDY_ID,
    A4_STUDY_PACKET_SHA256,
)
from neuroai_workbench.open_world_round_protocol import (
    PROTOCOL_ID,
    PROTOCOL_SHA256,
    UNIVERSE_IDS,
    UNIVERSE_SHA256,
)
from neuroai_workbench.product_discovery_frames import (
    A1_INITIAL_KNOWN_IDENTITY_SHA256,
    A2_KNOWLEDGE_TIME_CUTOFF,
    A2_WORLD_TIME_CUTOFF,
    DEFAULT_ANALYSIS_UNIVERSE_ID,
    FRAME_REGISTER_VERSION,
    ProductDiscoveryError,
)

RESOURCE_PACKAGE = "neuroai_workbench.resources.discovery"

A5_PREREG_RESOURCE = "RELEASE_A_A5_SNOWBALL_DISCOVERY_PREREGISTRATION.v1.0.json"
A5_PREREG_ID = "RELEASE_A_A5_SNOWBALL_DISCOVERY_PREREGISTRATION_v1.0"
A5_PREREG_SHA256 = "127e4ba8fb17ce071ad50a8ef628125031b6625bcda27f812bbaf26d8ca114ad"
A5_STUDY_ID = "RELEASE_A_A5_CONTROLLED_SNOWBALL_DISCOVERY_STUDY_v1.0"

CHECKPOINT_SHA256 = "452c8c504990c05edd6ac7c29b542a49ffa4fd81ccdece2bd7ca8e9e0921ca32"
FRAME_REGISTER_BLOB_SHA = "bb3d95226dc0ed528e5eed8e6de707430399b9ae"
F11_PACKET_ID = "RELEASE_A_A2_F11_OPEN_WORLD_ROUNDS_1_3_TRANCHE_1_v1.0"
F11_PACKET_SHA256 = "e6da0402653a89bb1c55e61b630864271f80daa7d0a1f11cc38d451917d3e88a"
LANGUAGE_SCOPE_ID = "EN_PLUS_PRIORITY_NATIVE_v1"
EDGE_TAXONOMY_SET_ID = "A5_CONTROLLED_SNOWBALL_EDGE_TAXONOMY_v1"

REQUIRED_EDGE_TYPE_IDS = (
    "PRODUCT_TO_ORGANIZATION",
    "ORGANIZATION_TO_PRODUCT",
    "PRODUCT_TO_TRIAL",
    "PRODUCT_TO_REGULATORY",
    "PRODUCT_TO_PUBLICATION",
    "PRODUCT_TO_DISTRIBUTOR",
    "PRODUCT_TO_RELATED_PRODUCT",
    "PRODUCT_TO_CAPABILITY_QUERY",
)

F11_QUERY_FAMILY_BINDINGS = {
    "PRODUCT_TO_ORGANIZATION": "PRODUCT_TO_ORGANIZATION",
    "ORGANIZATION_TO_PRODUCT": "ORGANIZATION_TO_PRODUCT",
    "PRODUCT_TO_TRIAL": "PRODUCT_TO_TRIAL_REGULATORY_PUBLICATION",
    "PRODUCT_TO_REGULATORY": "PRODUCT_TO_TRIAL_REGULATORY_PUBLICATION",
    "PRODUCT_TO_PUBLICATION": "PRODUCT_TO_TRIAL_REGULATORY_PUBLICATION",
    "PRODUCT_TO_DISTRIBUTOR": "PRODUCT_TO_DISTRIBUTOR",
    "PRODUCT_TO_RELATED_PRODUCT": "PRODUCT_TO_RELATED_PRODUCT",
    "PRODUCT_TO_CAPABILITY_QUERY": "PRODUCT_TO_CAPABILITY_QUERY",
}

REQUIRED_ROUND_METRICS = ("Y_r", "D_r", "X_r", "U_r", "m_r")
REQUIRED_DECOMPOSITION_DIMENSIONS = (
    "SOURCE_FRAME",
    "LANGUAGE",
    "JURISDICTION",
    "PRODUCT_CLASS",
    "CAPABILITY_FAMILY",
    "DISCOVERY_ROUND",
)
PERMITTED_STOP_DESCRIPTIONS = (
    "SATURATION_UNDER_DECLARED_PROTOCOL",
    "BUDGET_COVERAGE_TERMINATION",
    "BOUNDED_SOURCE_EXHAUSTION",
    "UNRESOLVED_SOURCE_BARRIER",
)

A5_BOUNDARY = (
    "A5 controlled snowball discovery preregistration freezes the edge taxonomy, "
    "parent-seed provenance rules, Y_r/D_r/X_r/U_r/m_r metrics contract, "
    "marginal-yield decomposition dimensions, and permitted stop descriptions "
    "under the A2 analysis universe before yield interpretation. It does not "
    "establish global completeness, market share, effectiveness, unseen-population "
    "size, commercialization, S2 publication authority, or v4.2 assessment effect. "
    "A snowball edge never establishes inclusion or canonical PRODUCT identity. "
    "Freeze alone does not compute round metrics. F11 remains estimator-excluded."
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


def load_default_a5_snowball_discovery_preregistration() -> dict[str, Any]:
    """Load the frozen A5 controlled snowball discovery preregistration."""

    prereg = _load_resource(A5_PREREG_RESOURCE)
    validate_a5_snowball_discovery_preregistration(prereg)
    if prereg["preregistration_sha256"] != A5_PREREG_SHA256:
        raise ProductDiscoveryError("Loaded A5 preregistration digest drifted from frozen A5_PREREG_SHA256")
    return prereg


def a5_freeze_does_not_compute_round_metrics() -> str:
    """Freeze alone never implies measured Y_r/D_r/X_r/U_r/m_r results."""

    return "PREREGISTERED_AWAITING_EXECUTION"


def compute_round_metrics(
    *,
    y_r: int,
    d_r: int,
    x_r: int,
    u_r: int,
    candidates_r: int,
) -> dict[str, Any]:
    """Compute A5 round metrics including m_r = Y_r / Candidates_r (fail-closed).

    This helper is for the execution stage. The preregistration freeze must not
    invoke it to choose or edit edge taxonomy.
    """

    for label, value in (
        ("Y_r", y_r),
        ("D_r", d_r),
        ("X_r", x_r),
        ("U_r", u_r),
        ("Candidates_r", candidates_r),
    ):
        if value < 0:
            raise ProductDiscoveryError(f"{label} cannot be negative")
    if candidates_r == 0:
        raise ProductDiscoveryError("Candidates_r must be positive to compute m_r")
    return {
        "Y_r": y_r,
        "D_r": d_r,
        "X_r": x_r,
        "U_r": u_r,
        "Candidates_r": candidates_r,
        "m_r": y_r / candidates_r,
    }


def validate_a5_snowball_discovery_preregistration(prereg: Mapping[str, Any]) -> None:
    """Validate the frozen A5 controlled snowball discovery preregistration."""

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
        "open_world_round_protocol_id",
        "open_world_round_protocol_sha256",
        "f11_query_universe_id",
        "f11_query_universe_sha256",
        "f11_execution_packet_id",
        "f11_execution_packet_sha256",
        "a3_preregistration_id",
        "a3_preregistration_sha256",
        "a3_study_id",
        "a3_study_sha256",
        "a4_preregistration_id",
        "a4_preregistration_sha256",
        "a4_study_id",
        "a4_study_sha256",
        "predeclaration_rule",
        "edge_taxonomy_set_id",
        "edge_types",
        "parent_seed_rules",
        "evidence_substrate",
        "metrics_contract",
        "permitted_stop_descriptions",
        "stop_semantics",
        "execution_gate",
        "boundary",
    )
    missing = [field for field in required if field not in prereg]
    if missing:
        raise ProductDiscoveryError("A5 preregistration missing fields: " + ", ".join(missing))

    if prereg["preregistration_id"] != A5_PREREG_ID:
        raise ProductDiscoveryError(f"preregistration_id must be {A5_PREREG_ID}")
    if prereg["status"] != "FROZEN_v1.0":
        raise ProductDiscoveryError("status must be FROZEN_v1.0")
    if prereg["study_id"] != A5_STUDY_ID:
        raise ProductDiscoveryError(f"study_id must be {A5_STUDY_ID}")
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
    if prereg["open_world_round_protocol_id"] != PROTOCOL_ID:
        raise ProductDiscoveryError("open_world_round_protocol_id must equal the frozen open-world protocol")
    if prereg["open_world_round_protocol_sha256"] != PROTOCOL_SHA256:
        raise ProductDiscoveryError("open_world_round_protocol_sha256 must equal the frozen open-world protocol digest")
    if prereg["f11_query_universe_id"] != UNIVERSE_IDS["F11"]:
        raise ProductDiscoveryError("f11_query_universe_id must equal the frozen F11 universe")
    if prereg["f11_query_universe_sha256"] != UNIVERSE_SHA256["F11"]:
        raise ProductDiscoveryError("f11_query_universe_sha256 must equal the frozen F11 universe digest")
    if prereg["f11_execution_packet_id"] != F11_PACKET_ID:
        raise ProductDiscoveryError("f11_execution_packet_id must equal the frozen F11 execution packet")
    if prereg["f11_execution_packet_sha256"] != F11_PACKET_SHA256:
        raise ProductDiscoveryError("f11_execution_packet_sha256 must equal the frozen F11 packet digest")
    if prereg["a3_preregistration_id"] != A3_PREREG_ID:
        raise ProductDiscoveryError("a3_preregistration_id must equal frozen A3 preregistration")
    if prereg["a3_preregistration_sha256"] != A3_PREREG_SHA256:
        raise ProductDiscoveryError("a3_preregistration_sha256 must equal frozen A3 preregistration digest")
    if prereg["a3_study_id"] != A3_STUDY_ID:
        raise ProductDiscoveryError("a3_study_id must equal frozen A3 study")
    if prereg["a3_study_sha256"] != A3_STUDY_PACKET_SHA256:
        raise ProductDiscoveryError("a3_study_sha256 must equal frozen A3 study digest")
    if prereg["a4_preregistration_id"] != A4_PREREG_ID:
        raise ProductDiscoveryError("a4_preregistration_id must equal frozen A4 preregistration")
    if prereg["a4_preregistration_sha256"] != A4_PREREG_SHA256:
        raise ProductDiscoveryError("a4_preregistration_sha256 must equal frozen A4 preregistration digest")
    if prereg["a4_study_id"] != A4_STUDY_ID:
        raise ProductDiscoveryError("a4_study_id must equal frozen A4 study")
    if prereg["a4_study_sha256"] != A4_STUDY_PACKET_SHA256:
        raise ProductDiscoveryError("a4_study_sha256 must equal frozen A4 study digest")
    if prereg["edge_taxonomy_set_id"] != EDGE_TAXONOMY_SET_ID:
        raise ProductDiscoveryError("edge_taxonomy_set_id mismatch")
    if prereg["boundary"] != A5_BOUNDARY:
        raise ProductDiscoveryError("boundary text drift")

    edges = _require_list(prereg["edge_types"], "edge_types")
    if len(edges) != len(REQUIRED_EDGE_TYPE_IDS):
        raise ProductDiscoveryError("edge_types must contain exactly the frozen A5 edge taxonomy")
    edge_ids: list[str] = []
    for row in edges:
        mapping = _require_mapping(row, "edge_type")
        edge_id = _require_str(mapping.get("edge_type_id"), "edge_type_id")
        edge_ids.append(edge_id)
        expected_family = F11_QUERY_FAMILY_BINDINGS[edge_id]
        if mapping.get("f11_query_family_binding") != expected_family:
            raise ProductDiscoveryError(f"edge_type {edge_id} must bind f11_query_family_binding={expected_family}")
    if tuple(edge_ids) != REQUIRED_EDGE_TYPE_IDS:
        raise ProductDiscoveryError("edge_types must equal the frozen A5 edge taxonomy set in order")

    parent_rules = _require_mapping(prereg["parent_seed_rules"], "parent_seed_rules")
    for field in (
        "every_edge_requires_parent_seed",
        "parent_seed_must_be_among_permitted_edge_types",
        "parent_seed_offering_id_required_when_parent_is_product",
        "parent_seed_recorded_on_every_edge",
        "snowball_edge_never_establishes_inclusion",
        "generated_object_reenters_as_candidate",
        "no_identity_allocation_by_implication",
        "no_inclusion_from_edge_alone",
    ):
        if not _require_bool(parent_rules.get(field), field):
            raise ProductDiscoveryError(f"parent_seed_rules.{field} must be true")

    substrate = _require_mapping(prereg["evidence_substrate"], "evidence_substrate")
    if substrate.get("controlled_snowball_frame_id") != "F11":
        raise ProductDiscoveryError("controlled_snowball_frame_id must be F11")
    if not _require_bool(
        substrate.get("f11_is_path_dependent_diagnostic_frame"), "f11_is_path_dependent_diagnostic_frame"
    ):
        raise ProductDiscoveryError("f11_is_path_dependent_diagnostic_frame must be true")
    if not _require_bool(substrate.get("f7_f9_f11_estimator_excluded"), "f7_f9_f11_estimator_excluded"):
        raise ProductDiscoveryError("f7_f9_f11_estimator_excluded must be true")
    if substrate.get("capture_estimation_eligible") is not False:
        raise ProductDiscoveryError("capture_estimation_eligible must be false")
    if not _require_bool(
        substrate.get("no_identity_allocation_by_implication"), "no_identity_allocation_by_implication"
    ):
        raise ProductDiscoveryError("no_identity_allocation_by_implication must be true")
    if not _require_bool(
        substrate.get("post_cutoff_include_requires_world_time_support_ref"),
        "post_cutoff_include_requires_world_time_support_ref",
    ):
        raise ProductDiscoveryError("post_cutoff_include_requires_world_time_support_ref must be true")
    if tuple(substrate.get("minimum_rounds", ())) != ("R1", "R2", "R3"):
        raise ProductDiscoveryError("evidence_substrate.minimum_rounds must be R1–R3")

    metrics = _require_mapping(prereg["metrics_contract"], "metrics_contract")
    if tuple(metrics.get("primary_round_metrics", ())) != REQUIRED_ROUND_METRICS:
        raise ProductDiscoveryError("primary_round_metrics must be Y_r, D_r, X_r, U_r, m_r")
    if metrics.get("formula_m_r") != "m_r = Y_r / Candidates_r":
        raise ProductDiscoveryError("formula_m_r must be m_r = Y_r / Candidates_r")
    if tuple(metrics.get("decomposition_dimensions", ())) != REQUIRED_DECOMPOSITION_DIMENSIONS:
        raise ProductDiscoveryError("decomposition_dimensions must match the frozen A5 set")
    decomp = _require_mapping(metrics.get("decomposition_policy"), "decomposition_policy")
    if not _require_bool(decomp.get("no_post_hoc_dimension_invention"), "no_post_hoc_dimension_invention"):
        raise ProductDiscoveryError("no_post_hoc_dimension_invention must be true")
    denom = _require_mapping(metrics.get("denominator_rules"), "denominator_rules")
    if not _require_bool(denom.get("raw_edges_are_not_validated_products"), "raw_edges_are_not_validated_products"):
        raise ProductDiscoveryError("raw_edges_are_not_validated_products must be true")
    if not _require_bool(
        denom.get("only_include_resolved_exact_offering_ids_enter_y_r"),
        "only_include_resolved_exact_offering_ids_enter_y_r",
    ):
        raise ProductDiscoveryError("only_include_resolved_exact_offering_ids_enter_y_r must be true")

    stops = tuple(
        _require_str(item, "permitted_stop_description")
        for item in _require_list(prereg["permitted_stop_descriptions"], "permitted_stop_descriptions")
    )
    if stops != PERMITTED_STOP_DESCRIPTIONS:
        raise ProductDiscoveryError("permitted_stop_descriptions must equal the frozen stop set")

    stop_sem = _require_mapping(prereg["stop_semantics"], "stop_semantics")
    if not _require_bool(stop_sem.get("stop_never_means_global_completeness"), "stop_never_means_global_completeness"):
        raise ProductDiscoveryError("stop_never_means_global_completeness must be true")
    if stop_sem.get("minimum_completed_rounds") != 3:
        raise ProductDiscoveryError("minimum_completed_rounds must be 3")
    if stop_sem.get("consecutive_low_yield_rounds") != 2:
        raise ProductDiscoveryError("consecutive_low_yield_rounds must be 2")
    if float(stop_sem.get("maximum_marginal_new_identity_yield")) != 0.05:
        raise ProductDiscoveryError("maximum_marginal_new_identity_yield must be 0.05")
    if stop_sem.get("minimum_raw_candidates_per_round") != 20:
        raise ProductDiscoveryError("minimum_raw_candidates_per_round must be 20")

    gate = _require_mapping(prereg["execution_gate"], "execution_gate")
    for field in (
        "requires_frozen_preregistration_before_yield",
        "requires_parent_seed_on_every_edge",
        "freeze_alone_does_not_compute_round_metrics",
        "does_not_start_a6_or_later",
        "does_not_mutate_rau",
        "does_not_allocate_canonical_identity",
        "snowball_edge_never_establishes_inclusion",
        "post_hoc_edge_taxonomy_edits_prohibited",
        "f7_f9_f11_remain_estimator_excluded",
    ):
        if not _require_bool(gate.get(field), field):
            raise ProductDiscoveryError(f"execution_gate.{field} must be true")

    rule = str(prereg["predeclaration_rule"]).lower()
    if "post-hoc" not in rule and "post_hoc" not in rule:
        raise ProductDiscoveryError("predeclaration_rule must forbid post-hoc edge taxonomy edits")
    if "never establishes inclusion" not in rule and "never establish inclusion" not in rule:
        raise ProductDiscoveryError("predeclaration_rule must state that a snowball edge never establishes inclusion")
