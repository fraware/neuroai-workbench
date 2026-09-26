"""Validators for Release-A A4 multilingual coverage sensitivity preregistration.

Freezes the matched English versus English+native protocol and metrics contract
under the frozen EN_PLUS_PRIORITY_NATIVE_v1 language/jurisdiction strata before
any yield difference is computed. Freeze alone does not execute the sensitivity
study, allocate canonical identities, or start A5+.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from importlib.resources import files
from typing import Any, cast

from neuroai_workbench.a2_bounded_frame_checkpoint import CHECKPOINT_ID
from neuroai_workbench.a3_capability_recall import (
    A3_PREREG_ID,
    A3_PREREG_SHA256,
    A3_STUDY_ID,
    A3_STUDY_PACKET_SHA256,
)
from neuroai_workbench.f8_f10_protocol import (
    F8_PROTOCOL_ID,
    F8_PROTOCOL_SHA256,
    F8_UNIVERSE_ID,
    F8_UNIVERSE_SHA256,
    LANGUAGE_STRATA_ID,
    LANGUAGE_STRATA_SHA256,
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

A4_PREREG_RESOURCE = "RELEASE_A_A4_MULTILINGUAL_SENSITIVITY_PREREGISTRATION.v1.0.json"
A4_PREREG_ID = "RELEASE_A_A4_MULTILINGUAL_SENSITIVITY_PREREGISTRATION_v1.0"
A4_PREREG_SHA256 = "1ee891d1fc2641f2eadaa015c2d95a9983241696233da5a93fc401b5b56bba23"
A4_STUDY_ID = "RELEASE_A_A4_MULTILINGUAL_COVERAGE_SENSITIVITY_STUDY_v1.0"

CHECKPOINT_SHA256 = "452c8c504990c05edd6ac7c29b542a49ffa4fd81ccdece2bd7ca8e9e0921ca32"
FRAME_REGISTER_BLOB_SHA = "bb3d95226dc0ed528e5eed8e6de707430399b9ae"
LANGUAGE_SCOPE_ID = "EN_PLUS_PRIORITY_NATIVE_v1"
MATCHED_PROTOCOL_SET_ID = "A4_MATCHED_EN_VS_EN_PLUS_NATIVE_v1"

REQUIRED_STRATUM_IDS = (
    "LL-ES-ES",
    "LL-DE-DE-AT",
    "LL-FR-FR",
    "LL-ZH-CN",
    "LL-JA-JP",
    "LL-HE-IL",
    "LL-SV-SE",
)

REQUIRED_COMPANION_METRICS = (
    "UNIQUE_PRODUCT_GAIN",
    "FALSE_POSITIVE_RATE",
    "UNRESOLVED_RATE",
    "DUPLICATE_RATE",
    "CAPABILITY_GAIN",
    "SOURCE_CLASS_GAIN",
)

ENGLISH_FRAME_IDS = ("F1", "F2", "F3", "F4", "F5", "F6")
NATIVE_FRAME_IDS = ("F8",)
ENGLISH_PLUS_NATIVE_FRAME_IDS = ("F1", "F2", "F3", "F4", "F5", "F6", "F8")

NATIVE_QUERY_FAMILIES = (
    "NATIVE_LANGUAGE_CATEGORY",
    "NATIVE_LANGUAGE_CAPABILITY",
    "LOCAL_PRODUCT_SOURCE",
)
NATIVE_SOURCE_CLASSES = (
    "LOCAL_LANGUAGE_PUBLIC",
    "LOCAL_REGULATORY_OR_INSTITUTIONAL",
    "MANUFACTURER_VENDOR_OFFICIAL",
)

A4_BOUNDARY = (
    "A4 multilingual coverage sensitivity preregistration freezes the matched "
    "English versus English+native protocol and metrics contract under the frozen "
    "EN_PLUS_PRIORITY_NATIVE_v1 language/jurisdiction strata before yield "
    "interpretation. It does not establish global completeness, market share, "
    "effectiveness, unseen-population size, commercialization, S2 publication "
    "authority, or v4.2 assessment effect. Freeze alone does not compute "
    "ΔN_multilingual or allocate canonical PRODUCT identity. Languages are not "
    "chosen because they looked fruitful during exploratory work."
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


def id_set_digest(ids: Sequence[str]) -> str:
    """Return SHA-256 over the sorted unique ID list."""

    encoded = json.dumps(sorted({str(item) for item in ids}), ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
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


def load_default_a4_multilingual_sensitivity_preregistration() -> dict[str, Any]:
    """Load the frozen A4 multilingual sensitivity preregistration."""

    prereg = _load_resource(A4_PREREG_RESOURCE)
    validate_a4_multilingual_sensitivity_preregistration(prereg)
    if prereg["preregistration_sha256"] != A4_PREREG_SHA256:
        raise ProductDiscoveryError("Loaded A4 preregistration digest drifted from frozen A4_PREREG_SHA256")
    return prereg


def a4_freeze_does_not_compute_delta_n() -> str:
    """Freeze alone never implies a measured ΔN_multilingual result."""

    return "PREREGISTERED_AWAITING_EXECUTION"


def compute_delta_n_multilingual(
    *,
    english_offering_ids: Sequence[str],
    english_plus_native_offering_ids: Sequence[str],
) -> dict[str, Any]:
    """Compute ΔN_multilingual on exact offering IDs only (fail-closed).

    This helper is for the execution stage. The preregistration freeze must not
    invoke it to choose or edit language strata.
    """

    english = {str(item) for item in english_offering_ids if str(item).strip()}
    english_plus_native = {str(item) for item in english_plus_native_offering_ids if str(item).strip()}
    if not english_plus_native >= english:
        raise ProductDiscoveryError(
            "N_english_plus_native must be a superset of N_english; refuse incoherent increment inputs"
        )
    unique_native = sorted(english_plus_native - english)
    return {
        "n_english": len(english),
        "n_english_plus_native": len(english_plus_native),
        "delta_n_multilingual": len(unique_native),
        "unique_native_offering_ids": unique_native,
        "unique_product_gain": len(unique_native),
    }


def compute_companion_rates(
    *,
    raw_candidates: int,
    exclude_count: int,
    unresolved_count: int,
    known_identity_duplicate_count: int,
    within_round_duplicate_count: int,
) -> dict[str, float]:
    """Compute false-positive, unresolved, and duplicate rates for the native (F8) arm."""

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


def validate_a4_multilingual_sensitivity_preregistration(prereg: Mapping[str, Any]) -> None:
    """Validate the frozen A4 matched EN vs EN+native preregistration."""

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
        "language_jurisdiction_strata_id",
        "language_jurisdiction_strata_sha256",
        "frame_register_version",
        "frame_register_blob_sha",
        "f8_round_protocol_id",
        "f8_round_protocol_sha256",
        "f8_query_universe_id",
        "f8_query_universe_sha256",
        "a3_preregistration_id",
        "a3_preregistration_sha256",
        "a3_study_id",
        "a3_study_sha256",
        "predeclaration_rule",
        "matched_protocol_set_id",
        "matched_arms",
        "native_arm",
        "bound_stratum_ids",
        "evidence_substrate",
        "metrics_contract",
        "execution_gate",
        "boundary",
    )
    missing = [field for field in required if field not in prereg]
    if missing:
        raise ProductDiscoveryError("A4 preregistration missing fields: " + ", ".join(missing))

    if prereg["preregistration_id"] != A4_PREREG_ID:
        raise ProductDiscoveryError(f"preregistration_id must be {A4_PREREG_ID}")
    if prereg["status"] != "FROZEN_v1.0":
        raise ProductDiscoveryError("status must be FROZEN_v1.0")
    if prereg["study_id"] != A4_STUDY_ID:
        raise ProductDiscoveryError(f"study_id must be {A4_STUDY_ID}")
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
    if prereg["language_jurisdiction_strata_id"] != LANGUAGE_STRATA_ID:
        raise ProductDiscoveryError("language_jurisdiction_strata_id must equal the frozen language strata")
    if prereg["language_jurisdiction_strata_sha256"] != LANGUAGE_STRATA_SHA256:
        raise ProductDiscoveryError("language_jurisdiction_strata_sha256 must equal frozen strata digest 25010299…")
    if prereg["frame_register_version"] != FRAME_REGISTER_VERSION:
        raise ProductDiscoveryError("frame_register_version mismatch")
    if prereg["frame_register_blob_sha"] != FRAME_REGISTER_BLOB_SHA:
        raise ProductDiscoveryError("frame_register_blob_sha mismatch")
    if prereg["f8_round_protocol_id"] != F8_PROTOCOL_ID:
        raise ProductDiscoveryError("f8_round_protocol_id must equal the frozen F8 protocol")
    if prereg["f8_round_protocol_sha256"] != F8_PROTOCOL_SHA256:
        raise ProductDiscoveryError("f8_round_protocol_sha256 must equal the frozen F8 protocol digest")
    if prereg["f8_query_universe_id"] != F8_UNIVERSE_ID:
        raise ProductDiscoveryError("f8_query_universe_id must equal the frozen F8 universe")
    if prereg["f8_query_universe_sha256"] != F8_UNIVERSE_SHA256:
        raise ProductDiscoveryError("f8_query_universe_sha256 must equal the frozen F8 universe digest")
    if prereg["a3_preregistration_id"] != A3_PREREG_ID:
        raise ProductDiscoveryError("a3_preregistration_id must equal frozen A3 preregistration")
    if prereg["a3_preregistration_sha256"] != A3_PREREG_SHA256:
        raise ProductDiscoveryError("a3_preregistration_sha256 must equal frozen A3 preregistration digest")
    if prereg["a3_study_id"] != A3_STUDY_ID:
        raise ProductDiscoveryError("a3_study_id must equal frozen A3 study")
    if prereg["a3_study_sha256"] != A3_STUDY_PACKET_SHA256:
        raise ProductDiscoveryError("a3_study_sha256 must equal frozen A3 study digest")
    if prereg["matched_protocol_set_id"] != MATCHED_PROTOCOL_SET_ID:
        raise ProductDiscoveryError("matched_protocol_set_id mismatch")
    if prereg["boundary"] != A4_BOUNDARY:
        raise ProductDiscoveryError("boundary text drift")

    bound = tuple(_require_str(item, "bound_stratum_id") for item in _require_list(prereg["bound_stratum_ids"], "bound_stratum_ids"))
    if bound != REQUIRED_STRATUM_IDS:
        raise ProductDiscoveryError("bound_stratum_ids must equal the frozen EN_PLUS_PRIORITY_NATIVE_v1 stratum set in order")

    arms = _require_list(prereg["matched_arms"], "matched_arms")
    if len(arms) != 2:
        raise ProductDiscoveryError("matched_arms must contain exactly S_ENGLISH and S_ENGLISH_PLUS_NATIVE")
    arm_ids = [_require_str(_require_mapping(row, "matched arm").get("arm_id"), "arm_id") for row in arms]
    if arm_ids != ["S_ENGLISH", "S_ENGLISH_PLUS_NATIVE"]:
        raise ProductDiscoveryError("matched_arms must be ordered S_ENGLISH then S_ENGLISH_PLUS_NATIVE")
    english_arm = _require_mapping(arms[0], "S_ENGLISH")
    plus_arm = _require_mapping(arms[1], "S_ENGLISH_PLUS_NATIVE")
    if tuple(english_arm.get("frame_ids", ())) != ENGLISH_FRAME_IDS:
        raise ProductDiscoveryError("S_ENGLISH frame_ids must be F1-F6")
    if tuple(plus_arm.get("frame_ids", ())) != ENGLISH_PLUS_NATIVE_FRAME_IDS:
        raise ProductDiscoveryError("S_ENGLISH_PLUS_NATIVE frame_ids must be F1-F6+F8")

    native = _require_mapping(prereg["native_arm"], "native_arm")
    if native.get("arm_id") != "S_NATIVE_F8":
        raise ProductDiscoveryError("native_arm.arm_id must be S_NATIVE_F8")
    if tuple(native.get("frame_ids", ())) != NATIVE_FRAME_IDS:
        raise ProductDiscoveryError("native_arm.frame_ids must be F8 only")
    if not _require_bool(native.get("controlled_local_language_frame"), "controlled_local_language_frame"):
        raise ProductDiscoveryError("controlled_local_language_frame must be true")
    if tuple(native.get("query_families", ())) != NATIVE_QUERY_FAMILIES:
        raise ProductDiscoveryError("native_arm.query_families must equal the frozen F8 query family set")
    if tuple(native.get("source_classes", ())) != NATIVE_SOURCE_CLASSES:
        raise ProductDiscoveryError("native_arm.source_classes must equal the frozen F8 source-class set")

    substrate = _require_mapping(prereg["evidence_substrate"], "evidence_substrate")
    if tuple(substrate.get("english_frame_ids", ())) != ENGLISH_FRAME_IDS:
        raise ProductDiscoveryError("english_frame_ids must be F1-F6")
    if tuple(substrate.get("native_frame_ids", ())) != NATIVE_FRAME_IDS:
        raise ProductDiscoveryError("native_frame_ids must be F8 only")
    if tuple(substrate.get("english_plus_native_frame_ids", ())) != ENGLISH_PLUS_NATIVE_FRAME_IDS:
        raise ProductDiscoveryError("english_plus_native_frame_ids must be F1-F6+F8")
    for flag in (
        "f8_is_controlled_local_language_frame",
        "f7_f9_f11_estimator_excluded",
        "f10_patent_leads_are_not_products",
        "increment_requires_exact_offering_id",
        "no_identity_allocation_by_implication",
        "no_post_hoc_language_selection",
    ):
        if not _require_bool(substrate.get(flag), flag):
            raise ProductDiscoveryError(f"{flag} must be true")
    if substrate.get("identity_unit") != "CANONICAL_PRODUCT_OFFERING":
        raise ProductDiscoveryError("identity_unit must be CANONICAL_PRODUCT_OFFERING")

    metrics = _require_mapping(prereg["metrics_contract"], "metrics_contract")
    if metrics.get("primary_estimand_id") != "DELTA_N_MULTILINGUAL":
        raise ProductDiscoveryError("primary_estimand_id must be DELTA_N_MULTILINGUAL")
    if metrics.get("formula") != "DELTA_N_MULTILINGUAL = N_ENGLISH_PLUS_NATIVE - N_ENGLISH":
        raise ProductDiscoveryError("metrics formula drift")
    if metrics.get("stratum_estimand_id") != "DELTA_J":
        raise ProductDiscoveryError("stratum_estimand_id must be DELTA_J")
    if metrics.get("stratum_formula") != "DELTA_J = N_J_ENGLISH_PLUS_NATIVE - N_J_ENGLISH":
        raise ProductDiscoveryError("stratum formula drift")
    rates = tuple(_require_list(metrics.get("required_companion_metrics"), "required_companion_metrics"))
    if rates != REQUIRED_COMPANION_METRICS:
        raise ProductDiscoveryError("required_companion_metrics must equal the frozen companion-metric set")
    stratification = _require_mapping(metrics.get("stratification_policy"), "stratification_policy")
    for flag in (
        "no_post_hoc_stratum_invention",
        "no_post_hoc_language_selection",
        "languages_not_selected_for_yield",
    ):
        if not _require_bool(stratification.get(flag), flag):
            raise ProductDiscoveryError(f"{flag} must be true")
    denominators = _require_mapping(metrics.get("denominator_rules"), "denominator_rules")
    for flag in (
        "raw_search_hits_are_not_the_increment_unit",
        "only_include_resolved_exact_offering_ids_enter_n_counts",
        "unresolved_borderline_abstain_exclude_do_not_inflate_delta_n",
        "known_a1_overlaps_are_duplicates_not_unique_gain",
    ):
        if not _require_bool(denominators.get(flag), flag):
            raise ProductDiscoveryError(f"{flag} must be true")
    _require_str(metrics.get("substantive_conclusion_change_rule"), "substantive_conclusion_change_rule")

    gate = _require_mapping(prereg["execution_gate"], "execution_gate")
    for flag in (
        "requires_frozen_preregistration_before_yield",
        "requires_frozen_language_jurisdiction_strata",
        "freeze_alone_does_not_compute_delta_n",
        "does_not_start_a5_or_later",
        "does_not_mutate_rau",
        "does_not_allocate_canonical_identity",
        "post_hoc_language_selection_prohibited",
        "post_hoc_stratum_edits_prohibited",
    ):
        if not _require_bool(gate.get(flag), flag):
            raise ProductDiscoveryError(f"{flag} must be true")

    _require_str(prereg["predeclaration_rule"], "predeclaration_rule")
    _require_str(prereg["census_registered_at"], "census_registered_at")
    if "fruitful" not in str(prereg["predeclaration_rule"]).lower() and "post-hoc" not in str(
        prereg["predeclaration_rule"]
    ).lower():
        raise ProductDiscoveryError("predeclaration_rule must forbid post-hoc/fruitful language selection")
