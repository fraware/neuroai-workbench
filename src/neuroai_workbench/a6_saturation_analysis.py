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
