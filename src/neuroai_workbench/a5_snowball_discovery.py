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
    identity_set_digest,
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
    max_yield = stop_sem.get("maximum_marginal_new_identity_yield")
    if not isinstance(max_yield, (int, float)) or float(max_yield) != 0.05:
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


A5_STUDY_RESOURCE = "RELEASE_A_A5_CONTROLLED_SNOWBALL_DISCOVERY_STUDY.v1.0.json"
A5_STUDY_PACKET_ID = "RELEASE_A_A5_CONTROLLED_SNOWBALL_DISCOVERY_STUDY_v1.0"
A5_STUDY_PACKET_SHA256 = "b8279338c577c54fc5674c08324b95272a20e992a8240b11f7d542cbc55c3cbd"

A5_STUDY_BOUNDARY = (
    "Repository-safe A5 controlled snowball discovery study under the frozen A5 "
    "preregistration and F11 diagnostic substrate. Y_r counts only new exact canonical "
    "PRODUCT offering IDs. A snowball edge never establishes inclusion or identity. No "
    "global completeness, market share, effectiveness, unseen-population size, S2 "
    "publication authority, or v4.2 assessment effect. Does not execute A6+."
)

KNOWN_OFFERING_IDS = (
    "PRD-EMOTIV-EPOC-X",
    "PRD-FLOW-FL-100",
    "PRD-MODIUS-SPERO",
    "PRD-MUSE-S-ATHENA",
    "PRD-NEXTSENSE-SMARTBUDS",
    "PRD-SYNCHRON-STENTRODE",
)

EXPECTED_ROUND_METRICS = (
    {"round_id": "R1", "Y_r": 0, "D_r": 15, "X_r": 0, "U_r": 4, "Candidates_r": 40, "m_r": 0.0},
    {"round_id": "R2", "Y_r": 0, "D_r": 15, "X_r": 0, "U_r": 4, "Candidates_r": 40, "m_r": 0.0},
    {"round_id": "R3", "Y_r": 0, "D_r": 15, "X_r": 0, "U_r": 4, "Candidates_r": 40, "m_r": 0.0},
)

DECOMPOSITION_KEYS = (
    "by_source_frame",
    "by_language",
    "by_jurisdiction",
    "by_product_class",
    "by_capability_family",
    "by_discovery_round",
)


def load_default_a5_snowball_discovery_study() -> dict[str, Any]:
    """Load the frozen A5 controlled snowball discovery study packet."""

    packet = _load_resource(A5_STUDY_RESOURCE)
    validate_a5_snowball_discovery_study(packet)
    if packet["packet_sha256"] != A5_STUDY_PACKET_SHA256:
        raise ProductDiscoveryError("Loaded A5 study digest drifted from frozen A5_STUDY_PACKET_SHA256")
    return packet


def validate_a5_snowball_discovery_study(packet: Mapping[str, Any]) -> None:
    """Validate the executed A5 snowball study against the frozen preregistration."""

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
        "round_start_known_identity_ids",
        "round_start_known_identity_set_sha256",
        "final_known_identity_ids",
        "final_known_identity_set_sha256",
        "language_scope_id",
        "edge_taxonomy_set_id",
        "open_world_round_protocol_id",
        "open_world_round_protocol_sha256",
        "f11_query_universe_id",
        "f11_query_universe_sha256",
        "f11_execution_packet_id",
        "f11_execution_packet_sha256",
        "a4_study_id",
        "a4_study_sha256",
        "evidence_substrate_bindings",
        "round_metrics",
        "edge_provenance_summary",
        "edge_provenance_ledger",
        "marginal_yield_decomposition",
        "marginal_yield_by_f11_query_family",
        "stop_state_evidence",
        "new_canonical_allocations",
        "authority_controls",
        "key_result",
        "next_required_state",
        "boundary",
    )
    missing = [field for field in required if field not in packet]
    if missing:
        raise ProductDiscoveryError("A5 study packet missing fields: " + ", ".join(missing))

    if packet["packet_id"] != A5_STUDY_PACKET_ID:
        raise ProductDiscoveryError(f"packet_id must be {A5_STUDY_PACKET_ID}")
    if packet["status"] != "CONTROLLED_RESEARCH_PACKET_REPOSITORY_SAFE":
        raise ProductDiscoveryError("status must be CONTROLLED_RESEARCH_PACKET_REPOSITORY_SAFE")
    if packet["study_id"] != A5_STUDY_ID:
        raise ProductDiscoveryError(f"study_id must be {A5_STUDY_ID}")
    if content_digest(packet, exclude="packet_sha256") != packet["packet_sha256"]:
        raise ProductDiscoveryError("packet_sha256 does not match content digest")
    if packet["preregistration_id"] != A5_PREREG_ID:
        raise ProductDiscoveryError("preregistration_id must equal frozen A5 preregistration")
    if packet["preregistration_sha256"] != A5_PREREG_SHA256:
        raise ProductDiscoveryError("preregistration_sha256 must equal frozen A5 preregistration digest")
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
    if packet["final_known_identity_set_sha256"] != A1_INITIAL_KNOWN_IDENTITY_SHA256:
        raise ProductDiscoveryError("final_known_identity_set_sha256 must equal the A1 known-identity digest")
    if packet["language_scope_id"] != LANGUAGE_SCOPE_ID:
        raise ProductDiscoveryError("language_scope_id must be EN_PLUS_PRIORITY_NATIVE_v1")
    if packet["edge_taxonomy_set_id"] != EDGE_TAXONOMY_SET_ID:
        raise ProductDiscoveryError("edge_taxonomy_set_id mismatch")
    if packet["open_world_round_protocol_id"] != PROTOCOL_ID:
        raise ProductDiscoveryError("open_world_round_protocol_id must equal the frozen open-world protocol")
    if packet["open_world_round_protocol_sha256"] != PROTOCOL_SHA256:
        raise ProductDiscoveryError("open_world_round_protocol_sha256 must equal the frozen open-world protocol digest")
    if packet["f11_query_universe_id"] != UNIVERSE_IDS["F11"]:
        raise ProductDiscoveryError("f11_query_universe_id must equal the frozen F11 universe")
    if packet["f11_query_universe_sha256"] != UNIVERSE_SHA256["F11"]:
        raise ProductDiscoveryError("f11_query_universe_sha256 must equal the frozen F11 universe digest")
    if packet["f11_execution_packet_id"] != F11_PACKET_ID:
        raise ProductDiscoveryError("f11_execution_packet_id must equal the frozen F11 execution packet")
    if packet["f11_execution_packet_sha256"] != F11_PACKET_SHA256:
        raise ProductDiscoveryError("f11_execution_packet_sha256 must equal the frozen F11 packet digest")
    if packet["a4_study_id"] != A4_STUDY_ID:
        raise ProductDiscoveryError("a4_study_id must equal frozen A4 study")
    if packet["a4_study_sha256"] != A4_STUDY_PACKET_SHA256:
        raise ProductDiscoveryError("a4_study_sha256 must equal frozen A4 study digest")
    if packet["boundary"] != A5_STUDY_BOUNDARY:
        raise ProductDiscoveryError("boundary text drift")

    start_ids = [
        str(item) for item in _require_list(packet["round_start_known_identity_ids"], "round_start_known_identity_ids")
    ]
    final_ids = [str(item) for item in _require_list(packet["final_known_identity_ids"], "final_known_identity_ids")]
    if tuple(sorted(start_ids)) != KNOWN_OFFERING_IDS:
        raise ProductDiscoveryError("round_start_known_identity_ids must equal the frozen A1 six offering set")
    if tuple(sorted(final_ids)) != KNOWN_OFFERING_IDS:
        raise ProductDiscoveryError("final_known_identity_ids must equal the frozen A1 six offering set")
    if identity_set_digest(start_ids) != A1_INITIAL_KNOWN_IDENTITY_SHA256:
        raise ProductDiscoveryError("round_start_known_identity_ids digest drift")
    if identity_set_digest(final_ids) != A1_INITIAL_KNOWN_IDENTITY_SHA256:
        raise ProductDiscoveryError("final_known_identity_ids digest drift")
    if int(packet["new_canonical_allocations"]) != 0:
        raise ProductDiscoveryError("new_canonical_allocations must be 0")

    substrate = _require_mapping(packet["evidence_substrate_bindings"], "evidence_substrate_bindings")
    if substrate.get("controlled_snowball_frame_id") != "F11":
        raise ProductDiscoveryError("controlled_snowball_frame_id must be F11")
    sources = _require_list(substrate.get("source_packets"), "source_packets")
    if len(sources) != 1:
        raise ProductDiscoveryError("source_packets must bind exactly the F11 execution packet")
    source = _require_mapping(sources[0], "F11 source packet")
    if source.get("frame_id") != "F11":
        raise ProductDiscoveryError("source packet frame_id must be F11")
    if source.get("packet_sha256") != F11_PACKET_SHA256:
        raise ProductDiscoveryError("F11 source packet digest drift")
    if int(source.get("new_validated_product_count", -1)) != 0:
        raise ProductDiscoveryError("new_validated_product_count must be 0")

    rounds = _require_list(packet["round_metrics"], "round_metrics")
    if len(rounds) != 3:
        raise ProductDiscoveryError("round_metrics must contain exactly R1–R3")
    for expected, row in zip(EXPECTED_ROUND_METRICS, rounds, strict=True):
        mapping = _require_mapping(row, "round_metrics row")
        for key, value in expected.items():
            if key == "m_r":
                observed_m = mapping.get(key)
                if not isinstance(observed_m, (int, float)) or float(observed_m) != value:
                    raise ProductDiscoveryError(f"round {expected['round_id']} {key} mismatch")
            elif mapping.get(key) != value:
                raise ProductDiscoveryError(f"round {expected['round_id']} {key} mismatch")
        computed = compute_round_metrics(
            y_r=int(mapping["Y_r"]),
            d_r=int(mapping["D_r"]),
            x_r=int(mapping["X_r"]),
            u_r=int(mapping["U_r"]),
            candidates_r=int(mapping["Candidates_r"]),
        )
        if float(mapping["m_r"]) != computed["m_r"]:
            raise ProductDiscoveryError(f"round {expected['round_id']} m_r does not equal Y_r/Candidates_r")
        if int(mapping["D_r"]) != int(mapping["known_identity_duplicate_count"]) + int(
            mapping["within_round_duplicate_count"]
        ):
            raise ProductDiscoveryError(f"round {expected['round_id']} D_r must equal known+within-round duplicates")

    summary = _require_mapping(packet["edge_provenance_summary"], "edge_provenance_summary")
    if int(summary["edge_count"]) != 120:
        raise ProductDiscoveryError("edge_count must be 120")
    if int(summary["edges_with_parent_seed"]) != 120:
        raise ProductDiscoveryError("edges_with_parent_seed must equal edge_count")
    if int(summary["edges_missing_parent_seed"]) != 0:
        raise ProductDiscoveryError("edges_missing_parent_seed must be 0")
    if int(summary["edges_establishing_inclusion"]) != 0:
        raise ProductDiscoveryError("edges_establishing_inclusion must be 0")
    if not _require_bool(summary.get("all_parents_among_a1_known_identities"), "all_parents_among_a1_known_identities"):
        raise ProductDiscoveryError("all_parents_among_a1_known_identities must be true")
    if int(summary["candidate_reentry_count"]) != 120:
        raise ProductDiscoveryError("candidate_reentry_count must equal edge_count")

    ledger = _require_list(packet["edge_provenance_ledger"], "edge_provenance_ledger")
    if len(ledger) != 120:
        raise ProductDiscoveryError("edge_provenance_ledger must contain 120 edges")
    known = set(KNOWN_OFFERING_IDS)
    for row in ledger:
        mapping = _require_mapping(row, "edge ledger row")
        parent = _require_str(mapping.get("parent_seed_offering_id"), "parent_seed_offering_id")
        if parent not in known:
            raise ProductDiscoveryError("parent_seed_offering_id must be among A1 known identities")
        if not _require_bool(mapping.get("candidate_reentered"), "candidate_reentered"):
            raise ProductDiscoveryError("candidate_reentered must be true")
        if mapping.get("edge_establishes_inclusion") is not False:
            raise ProductDiscoveryError("edge_establishes_inclusion must be false")
        family = _require_str(mapping.get("f11_query_family"), "f11_query_family")
        if family not in set(F11_QUERY_FAMILY_BINDINGS.values()):
            raise ProductDiscoveryError(f"unexpected f11_query_family {family}")

    decomp = _require_mapping(packet["marginal_yield_decomposition"], "marginal_yield_decomposition")
    for key in DECOMPOSITION_KEYS:
        rows = _require_list(decomp.get(key), key)
        if not rows:
            raise ProductDiscoveryError(f"{key} must be non-empty")
        for row in rows:
            mapping = _require_mapping(row, f"{key} row")
            _require_str(mapping.get("dimension_value"), "dimension_value")
            if int(mapping.get("Y_total", -1)) != 0:
                raise ProductDiscoveryError(f"{key} Y_total must be 0 under measured A5 evidence")
            if float(mapping.get("m", -1.0)) != 0.0:
                raise ProductDiscoveryError(f"{key} m must be 0.0 under measured A5 evidence")

    families = _require_list(packet["marginal_yield_by_f11_query_family"], "marginal_yield_by_f11_query_family")
    if len(families) != 6:
        raise ProductDiscoveryError("marginal_yield_by_f11_query_family must cover all six F11 query families")
    for row in families:
        mapping = _require_mapping(row, "family yield row")
        if int(mapping.get("Y_total", -1)) != 0:
            raise ProductDiscoveryError("family Y_total must be 0")
        if float(mapping.get("m", -1.0)) != 0.0:
            raise ProductDiscoveryError("family m must be 0.0")

    stop = _require_mapping(packet["stop_state_evidence"], "stop_state_evidence")
    if stop.get("final_stop_state") != "SATURATION_UNDER_DECLARED_PROTOCOL":
        raise ProductDiscoveryError("final_stop_state must be SATURATION_UNDER_DECLARED_PROTOCOL")
    if stop.get("final_stop_state") not in PERMITTED_STOP_DESCRIPTIONS:
        raise ProductDiscoveryError("final_stop_state must be a permitted stop description")
    if not _require_bool(stop.get("permitted"), "permitted"):
        raise ProductDiscoveryError("stop_state_evidence.permitted must be true")
    if stop.get("f11_packet_final_stop_state") != "SATURATION_UNDER_DECLARED_PROTOCOL":
        raise ProductDiscoveryError("f11_packet_final_stop_state must match F11 packet")
    if not _require_bool(
        stop.get("each_qualifying_round_raw_candidates_gte_20"),
        "each_qualifying_round_raw_candidates_gte_20",
    ):
        raise ProductDiscoveryError("each_qualifying_round_raw_candidates_gte_20 must be true")
    if not _require_bool(stop.get("each_qualifying_round_m_r_lte_0_05"), "each_qualifying_round_m_r_lte_0_05"):
        raise ProductDiscoveryError("each_qualifying_round_m_r_lte_0_05 must be true")
    interpretation = _require_str(stop.get("interpretation"), "stop interpretation").lower()
    if "worldwide" in interpretation and "not proof" not in interpretation and "not" not in interpretation:
        raise ProductDiscoveryError("stop interpretation must refuse global-completeness claims")

    controls = _require_mapping(packet["authority_controls"], "authority_controls")
    for flag in (
        "no_identity_allocation_by_implication",
        "no_inclusion_from_edge_alone",
        "snowball_edge_never_establishes_inclusion",
        "generated_object_reenters_as_candidate",
        "increments_only_on_exact_offering_ids",
        "f7_f9_f11_estimator_excluded",
        "post_cutoff_include_requires_world_time_support_ref",
        "rau_not_mutated",
        "stop_never_means_global_completeness",
    ):
        if not _require_bool(controls.get(flag), flag):
            raise ProductDiscoveryError(f"{flag} must be true")

    key_result = _require_mapping(packet["key_result"], "key_result")
    if key_result.get("headline") != "CONTROLLED_SNOWBALL_ROUND_METRICS":
        raise ProductDiscoveryError("key_result.headline must be CONTROLLED_SNOWBALL_ROUND_METRICS")
    if int(key_result.get("total_Y", -1)) != 0:
        raise ProductDiscoveryError("key_result.total_Y must be 0")
    if key_result.get("final_stop_state") != "SATURATION_UNDER_DECLARED_PROTOCOL":
        raise ProductDiscoveryError("key_result.final_stop_state mismatch")
    key_rounds = _require_list(key_result.get("rounds"), "key_result.rounds")
    if len(key_rounds) != 3:
        raise ProductDiscoveryError("key_result.rounds must contain R1–R3")

    next_state = str(packet["next_required_state"])
    if "A6" not in next_state:
        raise ProductDiscoveryError("next_required_state must gate A6 next")
    if "not A7" not in next_state and "not A7–A8" not in next_state:
        raise ProductDiscoveryError("next_required_state must keep A7+ out of scope")
