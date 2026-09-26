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

    encoded = json.dumps(sorted({str(item) for item in ids}), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
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

    bound = tuple(
        _require_str(item, "bound_stratum_id")
        for item in _require_list(prereg["bound_stratum_ids"], "bound_stratum_ids")
    )
    if bound != REQUIRED_STRATUM_IDS:
        raise ProductDiscoveryError(
            "bound_stratum_ids must equal the frozen EN_PLUS_PRIORITY_NATIVE_v1 stratum set in order"
        )

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
    if (
        "fruitful" not in str(prereg["predeclaration_rule"]).lower()
        and "post-hoc" not in str(prereg["predeclaration_rule"]).lower()
    ):
        raise ProductDiscoveryError("predeclaration_rule must forbid post-hoc/fruitful language selection")


A4_STUDY_RESOURCE = "RELEASE_A_A4_MULTILINGUAL_COVERAGE_SENSITIVITY_STUDY.v1.0.json"
A4_STUDY_PACKET_ID = "RELEASE_A_A4_MULTILINGUAL_COVERAGE_SENSITIVITY_STUDY_v1.0"
A4_STUDY_PACKET_SHA256 = "a82fc5081630fc0af2d8843e6ad6009a9cbcb544509ce31f2a7b1fc94d8236ed"

A4_STUDY_BOUNDARY = (
    "Repository-safe A4 multilingual coverage sensitivity study under the frozen "
    "A4 preregistration and EN_PLUS_PRIORITY_NATIVE_v1 strata. ΔN_multilingual "
    "counts only exact canonical PRODUCT offering IDs. No identity allocation by "
    "implication. No post-hoc language selection. No global completeness, market "
    "share, effectiveness, unseen-population size, S2 publication authority, or "
    "v4.2 assessment effect. Does not execute A5+."
)

SOURCE_PACKET_SHA256 = {
    "F1": "4d4f8fdf655882315a6f53499f4932e91d1596c29c1a873c86dde243cd9c4c85",
    "F2": "d66590970362ac82b880e5fe4b9d7c66a913b6dc91618d31fbf67fa39a31c39b",
    "F3": "584ab1dae1fcf0885a51ec527bea953a2ee4ad5452c10b7bb6985ca652edb82b",
    "F4": "abaff10977ad1f7f84b3311b6619d403184da4d94d805714913851c7d87ebfc3",
    "F5": "0ce4e51a4f968ef452a1031d651e30119498fd4969563f91cadbccdeb2eaf3f5",
    "F6": "95e13cc7dc896a0bad3f2d3862fda7475ff5e35291341f6bdbe5b9a0372e2e4c",
    "F8": "07e79f2ba1501379315850d3756cb4758f632b5f337e47a140fe50c861e2043f",
}

KNOWN_OFFERING_IDS = (
    "PRD-EMOTIV-EPOC-X",
    "PRD-FLOW-FL-100",
    "PRD-MODIUS-SPERO",
    "PRD-MUSE-S-ATHENA",
    "PRD-NEXTSENSE-SMARTBUDS",
    "PRD-SYNCHRON-STENTRODE",
)

STRATUM_LANGUAGE_CODES = {
    "LL-ES-ES": "es",
    "LL-DE-DE-AT": "de",
    "LL-FR-FR": "fr",
    "LL-ZH-CN": "zh",
    "LL-JA-JP": "ja",
    "LL-HE-IL": "he",
    "LL-SV-SE": "sv",
}


def load_default_a4_multilingual_sensitivity_study() -> dict[str, Any]:
    """Load the frozen A4 multilingual coverage sensitivity study packet."""

    packet = _load_resource(A4_STUDY_RESOURCE)
    validate_a4_multilingual_sensitivity_study(packet)
    if packet["packet_sha256"] != A4_STUDY_PACKET_SHA256:
        raise ProductDiscoveryError("Loaded A4 study digest drifted from frozen A4_STUDY_PACKET_SHA256")
    return packet


def validate_a4_multilingual_sensitivity_study(packet: Mapping[str, Any]) -> None:
    """Validate the executed A4 sensitivity study against the frozen preregistration."""

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
        "language_jurisdiction_strata_id",
        "language_jurisdiction_strata_sha256",
        "matched_protocol_set_id",
        "f8_query_universe_id",
        "f8_query_universe_sha256",
        "f8_round_protocol_id",
        "f8_round_protocol_sha256",
        "a3_study_id",
        "a3_study_sha256",
        "evidence_substrate_bindings",
        "n_english",
        "n_english_plus_native",
        "delta_n_multilingual",
        "unique_product_gain",
        "capability_gain",
        "english_offering_ids",
        "english_plus_native_offering_ids",
        "unique_native_offering_ids",
        "capability_gain_offering_ids",
        "english_offering_set_sha256",
        "english_plus_native_offering_set_sha256",
        "native_arm_rates",
        "source_class_gain",
        "stratification",
        "new_canonical_allocations",
        "authority_controls",
        "key_result",
        "substantive_conclusion_change",
        "next_required_state",
        "boundary",
    )
    missing = [field for field in required if field not in packet]
    if missing:
        raise ProductDiscoveryError("A4 study packet missing fields: " + ", ".join(missing))

    if packet["packet_id"] != A4_STUDY_PACKET_ID:
        raise ProductDiscoveryError(f"packet_id must be {A4_STUDY_PACKET_ID}")
    if packet["status"] != "CONTROLLED_RESEARCH_PACKET_REPOSITORY_SAFE":
        raise ProductDiscoveryError("status must be CONTROLLED_RESEARCH_PACKET_REPOSITORY_SAFE")
    if packet["study_id"] != A4_STUDY_ID:
        raise ProductDiscoveryError(f"study_id must be {A4_STUDY_ID}")
    if content_digest(packet, exclude="packet_sha256") != packet["packet_sha256"]:
        raise ProductDiscoveryError("packet_sha256 does not match content digest")
    if packet["preregistration_id"] != A4_PREREG_ID:
        raise ProductDiscoveryError("preregistration_id must equal frozen A4 preregistration")
    if packet["preregistration_sha256"] != A4_PREREG_SHA256:
        raise ProductDiscoveryError("preregistration_sha256 must equal frozen A4 preregistration digest")
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
    if packet["language_jurisdiction_strata_id"] != LANGUAGE_STRATA_ID:
        raise ProductDiscoveryError("language_jurisdiction_strata_id must equal the frozen language strata")
    if packet["language_jurisdiction_strata_sha256"] != LANGUAGE_STRATA_SHA256:
        raise ProductDiscoveryError("language_jurisdiction_strata_sha256 must equal frozen strata digest 25010299…")
    if packet["matched_protocol_set_id"] != MATCHED_PROTOCOL_SET_ID:
        raise ProductDiscoveryError("matched_protocol_set_id mismatch")
    if packet["f8_query_universe_id"] != F8_UNIVERSE_ID:
        raise ProductDiscoveryError("f8_query_universe_id must equal the frozen F8 universe")
    if packet["f8_query_universe_sha256"] != F8_UNIVERSE_SHA256:
        raise ProductDiscoveryError("f8_query_universe_sha256 must equal the frozen F8 universe digest")
    if packet["f8_round_protocol_id"] != F8_PROTOCOL_ID:
        raise ProductDiscoveryError("f8_round_protocol_id must equal the frozen F8 protocol")
    if packet["f8_round_protocol_sha256"] != F8_PROTOCOL_SHA256:
        raise ProductDiscoveryError("f8_round_protocol_sha256 must equal the frozen F8 protocol digest")
    if packet["a3_study_id"] != A3_STUDY_ID:
        raise ProductDiscoveryError("a3_study_id must equal frozen A3 study")
    if packet["a3_study_sha256"] != A3_STUDY_PACKET_SHA256:
        raise ProductDiscoveryError("a3_study_sha256 must equal frozen A3 study digest")
    if packet["boundary"] != A4_STUDY_BOUNDARY:
        raise ProductDiscoveryError("boundary text drift")

    final_ids = [str(item) for item in _require_list(packet["final_known_identity_ids"], "final_known_identity_ids")]
    if tuple(sorted(final_ids)) != KNOWN_OFFERING_IDS:
        raise ProductDiscoveryError("final_known_identity_ids must equal the frozen A1 six offering set")
    if packet["final_known_identity_set_sha256"] != A1_INITIAL_KNOWN_IDENTITY_SHA256:
        raise ProductDiscoveryError("final_known_identity_set_sha256 must equal the A1 known-identity digest")

    english_ids = [str(item) for item in _require_list(packet["english_offering_ids"], "english_offering_ids")]
    plus_ids = [
        str(item)
        for item in _require_list(packet["english_plus_native_offering_ids"], "english_plus_native_offering_ids")
    ]
    unique_ids = [
        str(item) for item in _require_list(packet["unique_native_offering_ids"], "unique_native_offering_ids")
    ]
    capability_ids = [
        str(item) for item in _require_list(packet["capability_gain_offering_ids"], "capability_gain_offering_ids")
    ]
    computed = compute_delta_n_multilingual(
        english_offering_ids=english_ids,
        english_plus_native_offering_ids=plus_ids,
    )
    if int(packet["n_english"]) != computed["n_english"]:
        raise ProductDiscoveryError("n_english does not match exact offering set")
    if int(packet["n_english_plus_native"]) != computed["n_english_plus_native"]:
        raise ProductDiscoveryError("n_english_plus_native does not match exact offering set")
    if int(packet["delta_n_multilingual"]) != computed["delta_n_multilingual"]:
        raise ProductDiscoveryError("delta_n_multilingual does not match exact offering increment")
    if int(packet["unique_product_gain"]) != computed["unique_product_gain"]:
        raise ProductDiscoveryError("unique_product_gain must equal delta_n_multilingual")
    if unique_ids != computed["unique_native_offering_ids"]:
        raise ProductDiscoveryError("unique_native_offering_ids drift from computed increment")
    if int(packet["capability_gain"]) != len(capability_ids):
        raise ProductDiscoveryError("capability_gain must equal capability_gain_offering_ids cardinality")
    if not set(capability_ids).issubset(set(unique_ids)):
        raise ProductDiscoveryError("capability_gain_offering_ids must be a subset of unique_native_offering_ids")
    if packet["english_offering_set_sha256"] != id_set_digest(english_ids):
        raise ProductDiscoveryError("english_offering_set_sha256 mismatch")
    if packet["english_plus_native_offering_set_sha256"] != id_set_digest(plus_ids):
        raise ProductDiscoveryError("english_plus_native_offering_set_sha256 mismatch")
    if int(packet["new_canonical_allocations"]) != 0:
        raise ProductDiscoveryError("new_canonical_allocations must be 0")

    substrate = _require_mapping(packet["evidence_substrate_bindings"], "evidence_substrate_bindings")
    if tuple(substrate.get("english_frame_ids", ())) != ENGLISH_FRAME_IDS:
        raise ProductDiscoveryError("english_frame_ids must be F1-F6")
    if tuple(substrate.get("native_frame_ids", ())) != NATIVE_FRAME_IDS:
        raise ProductDiscoveryError("native_frame_ids must be F8 only")
    if tuple(substrate.get("english_plus_native_frame_ids", ())) != ENGLISH_PLUS_NATIVE_FRAME_IDS:
        raise ProductDiscoveryError("english_plus_native_frame_ids must be F1-F6+F8")
    sources = _require_list(substrate.get("source_packets"), "source_packets")
    if len(sources) != 7:
        raise ProductDiscoveryError("source_packets must bind exactly F1-F6 and F8 packets")
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
    if tuple(seen_frames) != ENGLISH_PLUS_NATIVE_FRAME_IDS:
        raise ProductDiscoveryError("source_packets must be ordered F1-F6 then F8")

    rates = _require_mapping(packet["native_arm_rates"], "native_arm_rates")
    if rates.get("frame_id") != "F8":
        raise ProductDiscoveryError("native_arm_rates.frame_id must be F8")
    computed_rates = compute_companion_rates(
        raw_candidates=int(rates["raw_candidates"]),
        exclude_count=int(rates["exclude_count"]),
        unresolved_count=int(rates["unresolved_count"]),
        known_identity_duplicate_count=int(rates["known_identity_duplicate_count"]),
        within_round_duplicate_count=int(rates["within_round_duplicate_count"]),
    )
    for key, value in computed_rates.items():
        if float(rates[key]) != value:
            raise ProductDiscoveryError(f"{key} does not match native-arm accounting")

    source_gains = _require_list(packet["source_class_gain"], "source_class_gain")
    if len(source_gains) != len(NATIVE_SOURCE_CLASSES):
        raise ProductDiscoveryError("source_class_gain must cover all frozen F8 source classes")
    seen_classes: list[str] = []
    for row in source_gains:
        mapping = _require_mapping(row, "source_class_gain row")
        source_class = _require_str(mapping.get("source_class"), "source_class")
        seen_classes.append(source_class)
        gain_ids = [str(item) for item in _require_list(mapping.get("unique_offering_ids"), "unique_offering_ids")]
        if int(mapping["unique_offering_gain"]) != len(gain_ids):
            raise ProductDiscoveryError("source_class unique_offering_gain must match unique_offering_ids cardinality")
        if not set(gain_ids).issubset(set(unique_ids)):
            raise ProductDiscoveryError("source_class unique offerings must be subset of unique_native_offering_ids")
    if tuple(seen_classes) != NATIVE_SOURCE_CLASSES:
        raise ProductDiscoveryError("source_class_gain must equal the frozen F8 source-class set in order")

    stratification = _require_mapping(packet["stratification"], "stratification")
    strata_rows = _require_list(stratification.get("by_frozen_language_stratum"), "by_frozen_language_stratum")
    if len(strata_rows) != len(REQUIRED_STRATUM_IDS):
        raise ProductDiscoveryError("by_frozen_language_stratum must cover all bound strata")
    seen_strata: list[str] = []
    for row in strata_rows:
        mapping = _require_mapping(row, "stratum row")
        stratum_id = _require_str(mapping.get("stratum_id"), "stratum_id")
        seen_strata.append(stratum_id)
        expected_lang = STRATUM_LANGUAGE_CODES.get(stratum_id)
        if expected_lang is None:
            raise ProductDiscoveryError(f"unexpected stratum_id {stratum_id}")
        if mapping.get("language_code") != expected_lang:
            raise ProductDiscoveryError(f"language_code drift for {stratum_id}")
        if int(mapping["delta_j"]) != int(mapping["n_j_english_plus_native"]) - int(mapping["n_j_english"]):
            raise ProductDiscoveryError(f"delta_j arithmetic drift for {stratum_id}")
        if int(mapping["native_include_resolved"]) < 0:
            raise ProductDiscoveryError("native_include_resolved cannot be negative")
    if tuple(seen_strata) != REQUIRED_STRATUM_IDS:
        raise ProductDiscoveryError("by_frozen_language_stratum must equal frozen stratum set in order")

    controls = _require_mapping(packet["authority_controls"], "authority_controls")
    for flag in (
        "no_identity_allocation_by_implication",
        "increments_only_on_exact_offering_ids",
        "raw_search_hits_are_not_the_increment_unit",
        "f7_f9_f11_estimator_excluded",
        "f10_patent_leads_are_not_products",
        "no_post_hoc_language_selection",
        "languages_not_selected_for_yield",
        "rau_not_mutated",
        "post_hoc_stratum_edits_prohibited",
    ):
        if not _require_bool(controls.get(flag), flag):
            raise ProductDiscoveryError(f"{flag} must be true")

    key_result = _require_mapping(packet["key_result"], "key_result")
    if key_result.get("headline") != "DELTA_N_MULTILINGUAL":
        raise ProductDiscoveryError("key_result.headline must be DELTA_N_MULTILINGUAL")
    if int(key_result["delta_n_multilingual"]) != int(packet["delta_n_multilingual"]):
        raise ProductDiscoveryError("key_result.delta_n_multilingual mismatch")
    if int(key_result["unique_product_gain"]) != int(packet["unique_product_gain"]):
        raise ProductDiscoveryError("key_result.unique_product_gain mismatch")
    if int(key_result["capability_gain"]) != int(packet["capability_gain"]):
        raise ProductDiscoveryError("key_result.capability_gain mismatch")

    conclusion = _require_mapping(packet["substantive_conclusion_change"], "substantive_conclusion_change")
    changed = _require_bool(conclusion.get("any_substantive_conclusion_changed"), "any_substantive_conclusion_changed")
    _require_str(conclusion.get("statement"), "substantive conclusion statement")
    _require_list(conclusion.get("unchanged_conclusions"), "unchanged_conclusions")
    changed_list = _require_list(conclusion.get("changed_conclusions"), "changed_conclusions")
    if int(packet["delta_n_multilingual"]) == 0 and changed:
        raise ProductDiscoveryError(
            "any_substantive_conclusion_changed must be false when delta_n_multilingual is zero"
        )
    if int(packet["delta_n_multilingual"]) == 0 and changed_list:
        raise ProductDiscoveryError("changed_conclusions must be empty when delta_n_multilingual is zero")

    if "A5" not in str(packet["next_required_state"]):
        raise ProductDiscoveryError("next_required_state must gate A5 next")
    if "not A6" not in str(packet["next_required_state"]) and "not A6–A8" not in str(packet["next_required_state"]):
        raise ProductDiscoveryError("next_required_state must keep A6+ out of scope")
