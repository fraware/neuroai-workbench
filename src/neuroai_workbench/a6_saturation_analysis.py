"""Validators for Release-A A6 coverage and saturation preregistration.

Freezes the Product Discovery Coverage and Saturation Report contract, round
metrics / decomposition reuse rules, permitted stop descriptions, and A2–A5
digest bindings before any coverage/saturation interpretation. Freeze alone
does not emit the report, allocate canonical identities, or start A7+.
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
from neuroai_workbench.a5_snowball_discovery import (
    A5_PREREG_ID,
    A5_PREREG_SHA256,
    A5_STUDY_ID,
    A5_STUDY_PACKET_SHA256,
)
from neuroai_workbench.open_world_round_protocol import PROTOCOL_ID, PROTOCOL_SHA256
from neuroai_workbench.product_discovery_frames import (
    A1_INITIAL_KNOWN_IDENTITY_SHA256,
    A2_KNOWLEDGE_TIME_CUTOFF,
    A2_WORLD_TIME_CUTOFF,
    DEFAULT_ANALYSIS_UNIVERSE_ID,
    FRAME_REGISTER_VERSION,
    ProductDiscoveryError,
)

RESOURCE_PACKAGE = "neuroai_workbench.resources.discovery"

A6_PREREG_RESOURCE = "RELEASE_A_A6_COVERAGE_SATURATION_PREREGISTRATION.v1.0.json"
A6_PREREG_ID = "RELEASE_A_A6_COVERAGE_SATURATION_PREREGISTRATION_v1.0"
A6_PREREG_SHA256 = "5edcea38f40a4874bdc5404add331a888730277982315f66b5c4cf53c37be00d"
A6_STUDY_ID = "RELEASE_A_A6_PRODUCT_DISCOVERY_COVERAGE_SATURATION_REPORT_v1.0"

CHECKPOINT_SHA256 = "452c8c504990c05edd6ac7c29b542a49ffa4fd81ccdece2bd7ca8e9e0921ca32"
FRAME_REGISTER_BLOB_SHA = "bb3d95226dc0ed528e5eed8e6de707430399b9ae"
LANGUAGE_SCOPE_ID = "EN_PLUS_PRIORITY_NATIVE_v1"
REPORT_CONTRACT_ID = "A6_PRODUCT_DISCOVERY_COVERAGE_SATURATION_REPORT_CONTRACT_v1"

REQUIRED_REPORT_SECTIONS = (
    "UPSTREAM_DIGEST_BINDINGS",
    "ROUND_METRICS_LEDGER",
    "MARGINAL_YIELD_DECOMPOSITION",
    "FRAME_COVERAGE_STOP_INVENTORY",
    "PERMITTED_STOP_SUMMARY",
    "AUTHORITY_BOUNDARY",
)
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
FRAME_STOP_MAPPING = {
    "SATURATION_UNDER_DECLARED_PROTOCOL": "SATURATION_UNDER_DECLARED_PROTOCOL",
    "BOUNDED_FRAME_EXHAUSTED": "BOUNDED_SOURCE_EXHAUSTION",
    "MANUAL_DECLARED_LIMIT": "BUDGET_COVERAGE_TERMINATION",
    "UNRESOLVED_SOURCE_BARRIER": "UNRESOLVED_SOURCE_BARRIER",
}
COVERAGE_INVENTORY_FRAMES = (
    "F1",
    "F2",
    "F3",
    "F4",
    "F5",
    "F6",
    "F7",
    "F8",
    "F9",
    "F10",
    "F11",
)

A6_BOUNDARY = (
    "A6 coverage and saturation preregistration freezes the report contract, "
    "round-metrics/decomposition reuse rules, permitted stop descriptions, and "
    "A2–A5 digest bindings before coverage/saturation interpretation. It does not "
    "establish global completeness, market share, effectiveness, unseen-population "
    "size, commercialization, S2 publication authority, or v4.2 assessment effect. "
    "Freeze alone does not emit the Coverage and Saturation Report. Protocol "
    "saturation is not proof that every relevant product worldwide has been found. "
    "F7/F9/F11 remain estimator-excluded."
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


def load_default_a6_coverage_saturation_preregistration() -> dict[str, Any]:
    """Load the frozen A6 coverage and saturation preregistration."""

    prereg = _load_resource(A6_PREREG_RESOURCE)
    validate_a6_coverage_saturation_preregistration(prereg)
    if prereg["preregistration_sha256"] != A6_PREREG_SHA256:
        raise ProductDiscoveryError("Loaded A6 preregistration digest drifted from frozen A6_PREREG_SHA256")
    return prereg


def a6_freeze_does_not_emit_coverage_report() -> str:
    """Freeze alone never implies an emitted Coverage and Saturation Report."""

    return "PREREGISTERED_AWAITING_EXECUTION"


def map_frame_stop_to_permitted(declared_stop: str) -> str:
    """Map a frame-declared stop token onto a permitted A6 stop description."""

    mapped = FRAME_STOP_MAPPING.get(declared_stop)
    if mapped is None:
        raise ProductDiscoveryError(f"undeclared frame stop token cannot map to A6 permitted stop: {declared_stop}")
    if mapped not in PERMITTED_STOP_DESCRIPTIONS:
        raise ProductDiscoveryError(f"mapped stop {mapped} is not a permitted A6 stop description")
    return mapped


def validate_a6_coverage_saturation_preregistration(prereg: Mapping[str, Any]) -> None:
    """Validate the frozen A6 coverage and saturation preregistration."""

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
        "a3_preregistration_id",
        "a3_preregistration_sha256",
        "a3_study_id",
        "a3_study_sha256",
        "a4_preregistration_id",
        "a4_preregistration_sha256",
        "a4_study_id",
        "a4_study_sha256",
        "a5_preregistration_id",
        "a5_preregistration_sha256",
        "a5_study_id",
        "a5_study_sha256",
        "predeclaration_rule",
        "report_contract_id",
        "required_report_sections",
        "metrics_contract",
        "permitted_stop_descriptions",
        "stop_semantics",
        "evidence_substrate",
        "execution_gate",
        "boundary",
    )
    missing = [field for field in required if field not in prereg]
    if missing:
        raise ProductDiscoveryError("A6 preregistration missing fields: " + ", ".join(missing))

    if prereg["preregistration_id"] != A6_PREREG_ID:
        raise ProductDiscoveryError(f"preregistration_id must be {A6_PREREG_ID}")
    if prereg["status"] != "FROZEN_v1.0":
        raise ProductDiscoveryError("status must be FROZEN_v1.0")
    if prereg["study_id"] != A6_STUDY_ID:
        raise ProductDiscoveryError(f"study_id must be {A6_STUDY_ID}")
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
    if prereg["a5_preregistration_id"] != A5_PREREG_ID:
        raise ProductDiscoveryError("a5_preregistration_id must equal frozen A5 preregistration")
    if prereg["a5_preregistration_sha256"] != A5_PREREG_SHA256:
        raise ProductDiscoveryError("a5_preregistration_sha256 must equal frozen A5 preregistration digest")
    if prereg["a5_study_id"] != A5_STUDY_ID:
        raise ProductDiscoveryError("a5_study_id must equal frozen A5 study")
    if prereg["a5_study_sha256"] != A5_STUDY_PACKET_SHA256:
        raise ProductDiscoveryError("a5_study_sha256 must equal frozen A5 study digest")
    if prereg["report_contract_id"] != REPORT_CONTRACT_ID:
        raise ProductDiscoveryError("report_contract_id mismatch")
    if prereg["boundary"] != A6_BOUNDARY:
        raise ProductDiscoveryError("boundary text drift")

    sections = tuple(
        _require_str(item, "required_report_section")
        for item in _require_list(prereg["required_report_sections"], "required_report_sections")
    )
    if sections != REQUIRED_REPORT_SECTIONS:
        raise ProductDiscoveryError("required_report_sections must equal the frozen A6 report contract")

    metrics = _require_mapping(prereg["metrics_contract"], "metrics_contract")
    if tuple(metrics.get("primary_round_metrics", ())) != REQUIRED_ROUND_METRICS:
        raise ProductDiscoveryError("primary_round_metrics must be Y_r, D_r, X_r, U_r, m_r")
    if metrics.get("formula_m_r") != "m_r = Y_r / Candidates_r":
        raise ProductDiscoveryError("formula_m_r must be m_r = Y_r / Candidates_r")
    if metrics.get("primary_metrics_source") != "A5_CONTROLLED_SNOWBALL_STUDY_ROUND_LEDGER":
        raise ProductDiscoveryError("primary_metrics_source must be A5_CONTROLLED_SNOWBALL_STUDY_ROUND_LEDGER")
    if tuple(metrics.get("decomposition_dimensions", ())) != REQUIRED_DECOMPOSITION_DIMENSIONS:
        raise ProductDiscoveryError("decomposition_dimensions must match the frozen A6 set")
    decomp = _require_mapping(metrics.get("decomposition_policy"), "decomposition_policy")
    if not _require_bool(decomp.get("reuse_a5_declared_decompositions"), "reuse_a5_declared_decompositions"):
        raise ProductDiscoveryError("reuse_a5_declared_decompositions must be true")
    if decomp.get("fail_closed_missing_dimension") != "NOT_ATTRIBUTABLE":
        raise ProductDiscoveryError("fail_closed_missing_dimension must be NOT_ATTRIBUTABLE")
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
    if not _require_bool(
        denom.get("protocol_saturation_is_not_global_completeness"),
        "protocol_saturation_is_not_global_completeness",
    ):
        raise ProductDiscoveryError("protocol_saturation_is_not_global_completeness must be true")

    stops = tuple(
        _require_str(item, "permitted_stop_description")
        for item in _require_list(prereg["permitted_stop_descriptions"], "permitted_stop_descriptions")
    )
    if stops != PERMITTED_STOP_DESCRIPTIONS:
        raise ProductDiscoveryError("permitted_stop_descriptions must equal the frozen stop set")

    stop_sem = _require_mapping(prereg["stop_semantics"], "stop_semantics")
    if not _require_bool(stop_sem.get("stop_never_means_global_completeness"), "stop_never_means_global_completeness"):
        raise ProductDiscoveryError("stop_never_means_global_completeness must be true")
    mapping = _require_mapping(stop_sem.get("frame_stop_mapping"), "frame_stop_mapping")
    if dict(mapping) != FRAME_STOP_MAPPING:
        raise ProductDiscoveryError("frame_stop_mapping must equal the frozen A6 mapping")
    if stop_sem.get("primary_programme_stop_source") != "A5_STUDY_STOP_STATE_EVIDENCE":
        raise ProductDiscoveryError("primary_programme_stop_source must be A5_STUDY_STOP_STATE_EVIDENCE")

    substrate = _require_mapping(prereg["evidence_substrate"], "evidence_substrate")
    if not _require_bool(substrate.get("binds_a2_through_a5_digests"), "binds_a2_through_a5_digests"):
        raise ProductDiscoveryError("binds_a2_through_a5_digests must be true")
    if not _require_bool(substrate.get("f7_f9_f11_estimator_excluded"), "f7_f9_f11_estimator_excluded"):
        raise ProductDiscoveryError("f7_f9_f11_estimator_excluded must be true")
    if substrate.get("capture_estimation_eligible") is not False:
        raise ProductDiscoveryError("capture_estimation_eligible must be false")
    if not _require_bool(
        substrate.get("no_identity_allocation_by_implication"), "no_identity_allocation_by_implication"
    ):
        raise ProductDiscoveryError("no_identity_allocation_by_implication must be true")
    if not _require_bool(
        substrate.get("a6_does_not_allocate_canonical_identity"), "a6_does_not_allocate_canonical_identity"
    ):
        raise ProductDiscoveryError("a6_does_not_allocate_canonical_identity must be true")
    if tuple(substrate.get("coverage_inventory_frames", ())) != COVERAGE_INVENTORY_FRAMES:
        raise ProductDiscoveryError("coverage_inventory_frames must be F1–F11 in order")

    gate = _require_mapping(prereg["execution_gate"], "execution_gate")
    for field in (
        "requires_frozen_preregistration_before_report",
        "freeze_alone_does_not_emit_coverage_report",
        "does_not_start_a7_or_later",
        "does_not_mutate_rau",
        "does_not_allocate_canonical_identity",
        "post_hoc_stop_language_edits_prohibited",
        "f7_f9_f11_remain_estimator_excluded",
        "protocol_saturation_never_means_global_completeness",
    ):
        if not _require_bool(gate.get(field), field):
            raise ProductDiscoveryError(f"execution_gate.{field} must be true")

    rule = str(prereg["predeclaration_rule"]).lower()
    if "post-hoc" not in rule and "post_hoc" not in rule:
        raise ProductDiscoveryError("predeclaration_rule must forbid post-hoc stop/decomposition invention")
    if "worldwide" not in rule or "not" not in rule:
        raise ProductDiscoveryError("predeclaration_rule must refuse global-completeness claims")


A6_STUDY_RESOURCE = "RELEASE_A_A6_PRODUCT_DISCOVERY_COVERAGE_SATURATION_REPORT.v1.0.json"
A6_STUDY_PACKET_ID = "RELEASE_A_A6_PRODUCT_DISCOVERY_COVERAGE_SATURATION_REPORT_v1.0"
A6_STUDY_PACKET_SHA256 = "eb865319d27fb9904e1b1ad7685372e077445488236097f1e8d3f6814ead5b6b"

A6_STUDY_BOUNDARY = (
    "Repository-safe A6 Product Discovery Coverage and Saturation Report under the "
    "frozen A6 preregistration and A2–A5 digest bindings. Round metrics and "
    "decompositions reuse the declared A5 ledger. Stop language is limited to the "
    "four permitted bounded forms. Protocol saturation is not proof that every "
    "relevant product worldwide has been found. No global completeness, market "
    "share, effectiveness, unseen-population size, S2 publication authority, or "
    "v4.2 assessment effect. Does not execute A7+."
)

KNOWN_OFFERING_IDS = (
    "PRD-EMOTIV-EPOC-X",
    "PRD-FLOW-FL-100",
    "PRD-MODIUS-SPERO",
    "PRD-MUSE-S-ATHENA",
    "PRD-NEXTSENSE-SMARTBUDS",
    "PRD-SYNCHRON-STENTRODE",
)

EXPECTED_ROUND_METRICS: tuple[dict[str, object], ...] = (
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

FRAME_PACKET_SHA256 = {
    "F1": "4d4f8fdf655882315a6f53499f4932e91d1596c29c1a873c86dde243cd9c4c85",
    "F2": "d66590970362ac82b880e5fe4b9d7c66a913b6dc91618d31fbf67fa39a31c39b",
    "F3": "584ab1dae1fcf0885a51ec527bea953a2ee4ad5452c10b7bb6985ca652edb82b",
    "F4": "abaff10977ad1f7f84b3311b6619d403184da4d94d805714913851c7d87ebfc3",
    "F5": "0ce4e51a4f968ef452a1031d651e30119498fd4969563f91cadbccdeb2eaf3f5",
    "F6": "95e13cc7dc896a0bad3f2d3862fda7475ff5e35291341f6bdbe5b9a0372e2e4c",
    "F8": "07e79f2ba1501379315850d3756cb4758f632b5f337e47a140fe50c861e2043f",
    "F9": "ec36291d58685e30e19903a04ec83b9ba03a8cf3931f311881438eea4b3c8407",
    "F10": "2fb9cfddb9c49c97114127fb8fc5f14a0dcbb724195c6f7cd95b5ae7599b862c",
    "F11": "e6da0402653a89bb1c55e61b630864271f80daa7d0a1f11cc38d451917d3e88a",
}

EXPECTED_FRAME_STOPS: dict[str, tuple[str, str, bool]] = {
    "F1": ("SATURATION_UNDER_DECLARED_PROTOCOL", "SATURATION_UNDER_DECLARED_PROTOCOL", False),
    "F2": ("BOUNDED_FRAME_EXHAUSTED", "BOUNDED_SOURCE_EXHAUSTION", False),
    "F3": ("BOUNDED_FRAME_EXHAUSTED", "BOUNDED_SOURCE_EXHAUSTION", False),
    "F4": ("SATURATION_UNDER_DECLARED_PROTOCOL", "SATURATION_UNDER_DECLARED_PROTOCOL", False),
    "F5": ("SATURATION_UNDER_DECLARED_PROTOCOL", "SATURATION_UNDER_DECLARED_PROTOCOL", False),
    "F6": ("SATURATION_UNDER_DECLARED_PROTOCOL", "SATURATION_UNDER_DECLARED_PROTOCOL", False),
    "F7": ("MANUAL_DECLARED_LIMIT", "BUDGET_COVERAGE_TERMINATION", True),
    "F8": ("SATURATION_UNDER_DECLARED_PROTOCOL", "SATURATION_UNDER_DECLARED_PROTOCOL", False),
    "F9": ("BOUNDED_FRAME_EXHAUSTED", "BOUNDED_SOURCE_EXHAUSTION", True),
    "F10": ("BOUNDED_FRAME_EXHAUSTED", "BOUNDED_SOURCE_EXHAUSTION", False),
    "F11": ("SATURATION_UNDER_DECLARED_PROTOCOL", "SATURATION_UNDER_DECLARED_PROTOCOL", True),
}


def load_default_a6_coverage_saturation_report() -> dict[str, Any]:
    """Load the frozen A6 Product Discovery Coverage and Saturation Report."""

    packet = _load_resource(A6_STUDY_RESOURCE)
    validate_a6_coverage_saturation_report(packet)
    if packet["packet_sha256"] != A6_STUDY_PACKET_SHA256:
        raise ProductDiscoveryError("Loaded A6 report digest drifted from frozen A6_STUDY_PACKET_SHA256")
    return packet


def validate_a6_coverage_saturation_report(packet: Mapping[str, Any]) -> None:
    """Validate the executed A6 coverage/saturation report against the frozen preregistration."""

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
        "report_contract_id",
        "a3_preregistration_sha256",
        "a3_study_sha256",
        "a4_preregistration_sha256",
        "a4_study_sha256",
        "a5_preregistration_sha256",
        "a5_study_id",
        "a5_study_sha256",
        "upstream_digest_bindings",
        "round_metrics",
        "marginal_yield_decomposition",
        "frame_coverage_stop_inventory",
        "stop_state_evidence",
        "new_canonical_allocations",
        "authority_controls",
        "key_result",
        "next_required_state",
        "boundary",
    )
    missing = [field for field in required if field not in packet]
    if missing:
        raise ProductDiscoveryError("A6 report packet missing fields: " + ", ".join(missing))

    if packet["packet_id"] != A6_STUDY_PACKET_ID:
        raise ProductDiscoveryError(f"packet_id must be {A6_STUDY_PACKET_ID}")
    if packet["status"] != "CONTROLLED_RESEARCH_PACKET_REPOSITORY_SAFE":
        raise ProductDiscoveryError("status must be CONTROLLED_RESEARCH_PACKET_REPOSITORY_SAFE")
    if packet["study_id"] != A6_STUDY_ID:
        raise ProductDiscoveryError(f"study_id must be {A6_STUDY_ID}")
    if content_digest(packet, exclude="packet_sha256") != packet["packet_sha256"]:
        raise ProductDiscoveryError("packet_sha256 does not match content digest")
    if packet["preregistration_id"] != A6_PREREG_ID:
        raise ProductDiscoveryError("preregistration_id must equal frozen A6 preregistration")
    if packet["preregistration_sha256"] != A6_PREREG_SHA256:
        raise ProductDiscoveryError("preregistration_sha256 must equal frozen A6 preregistration digest")
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
    if packet["report_contract_id"] != REPORT_CONTRACT_ID:
        raise ProductDiscoveryError("report_contract_id mismatch")
    if packet["a3_preregistration_sha256"] != A3_PREREG_SHA256:
        raise ProductDiscoveryError("a3_preregistration_sha256 must equal frozen A3 preregistration digest")
    if packet["a3_study_sha256"] != A3_STUDY_PACKET_SHA256:
        raise ProductDiscoveryError("a3_study_sha256 must equal frozen A3 study digest")
    if packet["a4_preregistration_sha256"] != A4_PREREG_SHA256:
        raise ProductDiscoveryError("a4_preregistration_sha256 must equal frozen A4 preregistration digest")
    if packet["a4_study_sha256"] != A4_STUDY_PACKET_SHA256:
        raise ProductDiscoveryError("a4_study_sha256 must equal frozen A4 study digest")
    if packet["a5_preregistration_sha256"] != A5_PREREG_SHA256:
        raise ProductDiscoveryError("a5_preregistration_sha256 must equal frozen A5 preregistration digest")
    if packet["a5_study_id"] != A5_STUDY_ID:
        raise ProductDiscoveryError("a5_study_id must equal frozen A5 study")
    if packet["a5_study_sha256"] != A5_STUDY_PACKET_SHA256:
        raise ProductDiscoveryError("a5_study_sha256 must equal frozen A5 study digest")
    if packet["boundary"] != A6_STUDY_BOUNDARY:
        raise ProductDiscoveryError("boundary text drift")

    start_ids = [
        str(item) for item in _require_list(packet["round_start_known_identity_ids"], "round_start_known_identity_ids")
    ]
    final_ids = [str(item) for item in _require_list(packet["final_known_identity_ids"], "final_known_identity_ids")]
    if tuple(sorted(start_ids)) != KNOWN_OFFERING_IDS:
        raise ProductDiscoveryError("round_start_known_identity_ids must equal the frozen A1 six offering set")
    if tuple(sorted(final_ids)) != KNOWN_OFFERING_IDS:
        raise ProductDiscoveryError("final_known_identity_ids must equal the frozen A1 six offering set")
    if int(packet["new_canonical_allocations"]) != 0:
        raise ProductDiscoveryError("new_canonical_allocations must be 0")

    upstream = _require_mapping(packet["upstream_digest_bindings"], "upstream_digest_bindings")
    expected_upstream = {
        "a2_checkpoint_sha256": CHECKPOINT_SHA256,
        "a3_preregistration_sha256": A3_PREREG_SHA256,
        "a3_study_sha256": A3_STUDY_PACKET_SHA256,
        "a4_preregistration_sha256": A4_PREREG_SHA256,
        "a4_study_sha256": A4_STUDY_PACKET_SHA256,
        "a5_preregistration_sha256": A5_PREREG_SHA256,
        "a5_study_sha256": A5_STUDY_PACKET_SHA256,
        "known_identity_set_sha256": A1_INITIAL_KNOWN_IDENTITY_SHA256,
        "analysis_universe_id": DEFAULT_ANALYSIS_UNIVERSE_ID,
    }
    for key, value in expected_upstream.items():
        if upstream.get(key) != value:
            raise ProductDiscoveryError(f"upstream_digest_bindings.{key} mismatch")

    rounds = _require_list(packet["round_metrics"], "round_metrics")
    if len(rounds) != 3:
        raise ProductDiscoveryError("round_metrics must contain exactly R1–R3")
    for expected_row, row in zip(EXPECTED_ROUND_METRICS, rounds, strict=True):
        mapping = _require_mapping(row, "round_metrics row")
        round_id = str(expected_row["round_id"])
        for metric_key, expected_value in expected_row.items():
            if metric_key == "m_r":
                observed_m = mapping.get(metric_key)
                if not isinstance(expected_value, (int, float)):
                    raise ProductDiscoveryError(f"round {round_id} {metric_key} expected type mismatch")
                if not isinstance(observed_m, (int, float)) or float(observed_m) != float(expected_value):
                    raise ProductDiscoveryError(f"round {round_id} {metric_key} mismatch")
            elif mapping.get(metric_key) != expected_value:
                raise ProductDiscoveryError(f"round {round_id} {metric_key} mismatch")
        if int(mapping["Candidates_r"]) == 0:
            raise ProductDiscoveryError(f"round {round_id} Candidates_r must be positive")
        if float(mapping["m_r"]) != float(mapping["Y_r"]) / float(mapping["Candidates_r"]):
            raise ProductDiscoveryError(f"round {round_id} m_r does not equal Y_r/Candidates_r")

    decomp = _require_mapping(packet["marginal_yield_decomposition"], "marginal_yield_decomposition")
    for key in DECOMPOSITION_KEYS:
        rows = _require_list(decomp.get(key), key)
        if not rows:
            raise ProductDiscoveryError(f"{key} must be non-empty")
        for row in rows:
            mapping = _require_mapping(row, f"{key} row")
            _require_str(mapping.get("dimension_value"), "dimension_value")
            if int(mapping.get("Y_total", -1)) != 0:
                raise ProductDiscoveryError(f"{key} Y_total must be 0 under measured A6 evidence")
            if float(mapping.get("m", -1.0)) != 0.0:
                raise ProductDiscoveryError(f"{key} m must be 0.0 under measured A6 evidence")
    if decomp["by_product_class"][0]["dimension_value"] != "NOT_ATTRIBUTABLE":
        raise ProductDiscoveryError("by_product_class must fail closed to NOT_ATTRIBUTABLE")
    if decomp["by_capability_family"][0]["dimension_value"] != "NOT_ATTRIBUTABLE":
        raise ProductDiscoveryError("by_capability_family must fail closed to NOT_ATTRIBUTABLE")

    inventory = _require_list(packet["frame_coverage_stop_inventory"], "frame_coverage_stop_inventory")
    if len(inventory) != 11:
        raise ProductDiscoveryError("frame_coverage_stop_inventory must cover F1–F11")
    seen_frames: list[str] = []
    for row in inventory:
        mapping = _require_mapping(row, "frame inventory row")
        frame_id = _require_str(mapping.get("frame_id"), "frame_id")
        seen_frames.append(frame_id)
        declared_stop, permitted_stop, estimator_excluded = EXPECTED_FRAME_STOPS[frame_id]
        if mapping.get("declared_stop_state") != declared_stop:
            raise ProductDiscoveryError(f"{frame_id} declared_stop_state mismatch")
        if mapping.get("a6_permitted_stop_description") != permitted_stop:
            raise ProductDiscoveryError(f"{frame_id} a6_permitted_stop_description mismatch")
        if mapping.get("estimator_excluded") is not estimator_excluded:
            raise ProductDiscoveryError(f"{frame_id} estimator_excluded mismatch")
        if mapping.get("a6_permitted_stop_description") not in PERMITTED_STOP_DESCRIPTIONS:
            raise ProductDiscoveryError(f"{frame_id} stop description not permitted")
        mapped = map_frame_stop_to_permitted(str(mapping["declared_stop_state"]))
        if mapped != mapping.get("a6_permitted_stop_description"):
            raise ProductDiscoveryError(f"{frame_id} stop mapping inconsistent")
        if frame_id == "F7":
            if mapping.get("source_packet_id") is not None or mapping.get("source_packet_sha256") is not None:
                raise ProductDiscoveryError("F7 must have null source packet bindings")
        else:
            if mapping.get("source_packet_sha256") != FRAME_PACKET_SHA256[frame_id]:
                raise ProductDiscoveryError(f"{frame_id} source_packet_sha256 mismatch")
    if tuple(seen_frames) != COVERAGE_INVENTORY_FRAMES:
        raise ProductDiscoveryError("frame_coverage_stop_inventory must be ordered F1–F11")

    stop = _require_mapping(packet["stop_state_evidence"], "stop_state_evidence")
    if stop.get("final_stop_state") != "SATURATION_UNDER_DECLARED_PROTOCOL":
        raise ProductDiscoveryError("final_stop_state must be SATURATION_UNDER_DECLARED_PROTOCOL")
    if stop.get("final_stop_state") not in PERMITTED_STOP_DESCRIPTIONS:
        raise ProductDiscoveryError("final_stop_state must be a permitted stop description")
    if not _require_bool(stop.get("permitted"), "permitted"):
        raise ProductDiscoveryError("stop_state_evidence.permitted must be true")
    if stop.get("primary_programme_stop_source") != "A5_STUDY_STOP_STATE_EVIDENCE":
        raise ProductDiscoveryError("primary_programme_stop_source must be A5_STUDY_STOP_STATE_EVIDENCE")
    if stop.get("a5_final_stop_state") != "SATURATION_UNDER_DECLARED_PROTOCOL":
        raise ProductDiscoveryError("a5_final_stop_state must be SATURATION_UNDER_DECLARED_PROTOCOL")
    if tuple(stop.get("frames_with_saturation_under_declared_protocol", ())) != (
        "F1",
        "F4",
        "F5",
        "F6",
        "F8",
        "F11",
    ):
        raise ProductDiscoveryError("frames_with_saturation_under_declared_protocol mismatch")
    if tuple(stop.get("frames_with_bounded_source_exhaustion", ())) != ("F2", "F3", "F9", "F10"):
        raise ProductDiscoveryError("frames_with_bounded_source_exhaustion mismatch")
    if tuple(stop.get("frames_with_budget_coverage_termination", ())) != ("F7",):
        raise ProductDiscoveryError("frames_with_budget_coverage_termination mismatch")
    if list(stop.get("frames_with_unresolved_source_barrier", ("x",))) != []:
        raise ProductDiscoveryError("frames_with_unresolved_source_barrier must be empty")
    interpretation = _require_str(stop.get("interpretation"), "stop interpretation").lower()
    if "worldwide" in interpretation and "not" not in interpretation:
        raise ProductDiscoveryError("stop interpretation must refuse global-completeness claims")

    controls = _require_mapping(packet["authority_controls"], "authority_controls")
    for flag in (
        "no_identity_allocation_by_implication",
        "f7_f9_f11_estimator_excluded",
        "rau_not_mutated",
        "stop_never_means_global_completeness",
        "protocol_saturation_is_not_global_completeness",
        "does_not_start_a7_or_later",
    ):
        if not _require_bool(controls.get(flag), flag):
            raise ProductDiscoveryError(f"{flag} must be true")

    key_result = _require_mapping(packet["key_result"], "key_result")
    if key_result.get("headline") != "PRODUCT_DISCOVERY_COVERAGE_AND_SATURATION":
        raise ProductDiscoveryError("key_result.headline must be PRODUCT_DISCOVERY_COVERAGE_AND_SATURATION")
    if int(key_result.get("total_Y", -1)) != 0:
        raise ProductDiscoveryError("key_result.total_Y must be 0")
    if key_result.get("final_stop_state") != "SATURATION_UNDER_DECLARED_PROTOCOL":
        raise ProductDiscoveryError("key_result.final_stop_state mismatch")
    key_rounds = _require_list(key_result.get("rounds"), "key_result.rounds")
    if len(key_rounds) != 3:
        raise ProductDiscoveryError("key_result.rounds must contain R1–R3")

    next_state = str(packet["next_required_state"])
    if "A7" not in next_state:
        raise ProductDiscoveryError("next_required_state must gate A7 next")
    if "not A8" not in next_state and "not A8 or A-G" not in next_state:
        raise ProductDiscoveryError("next_required_state must keep A8/A-G out of scope")
