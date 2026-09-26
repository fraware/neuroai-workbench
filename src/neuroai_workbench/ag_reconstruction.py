"""Validators for Release-A A-G reconstruction protocol freeze.

Freezes the A-G reconstruction checklist that binds the exact A8 Product
Population Release Package digest and the twelve required reconstruction
fields before any reconstruction packet is emitted. Freeze alone does not
emit a PASSED/UNPASSED A-G outcome or authorize Release B/C/D.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from importlib.resources import files
from typing import Any, cast

from neuroai_workbench.a8_release_package import (
    A8_CONTRACT_SHA256,
    A8_PACKAGE_ID,
    A8_PACKAGE_SHA256,
    D4_WORKING_DISTRIBUTION,
    N_OBSERVED,
    OBSERVED_OFFERING_IDS,
    POPULATION_VIEW_ID,
    UNRESOLVED_CANDIDATE_COUNT,
)
from neuroai_workbench.product_discovery_frames import (
    A2_JURISDICTION_SCOPE,
    A2_KNOWLEDGE_TIME_CUTOFF,
    A2_LANGUAGE_SCOPE_ID,
    A2_WORLD_TIME_CUTOFF,
    DEFAULT_ANALYSIS_UNIVERSE_ID,
    PRIMARY_ESTIMATION_EXCLUDED_FRAME_IDS,
    ProductDiscoveryError,
)

RESOURCE_PACKAGE = "neuroai_workbench.resources.discovery"

AG_PROTOCOL_RESOURCE = "RELEASE_A_AG_RECONSTRUCTION_PROTOCOL.v1.0.json"
AG_PROTOCOL_SCHEMA_RESOURCE = "RELEASE_A_AG_RECONSTRUCTION_PROTOCOL.schema.json"
AG_PROTOCOL_ID = "RELEASE_A_AG_RECONSTRUCTION_PROTOCOL_v1.0"
AG_STUDY_ID = "RELEASE_A_AG_RECONSTRUCTION_PACKET_v1.0"

AG_PROTOCOL_SHA256 = "5fba335b37459d0b474f9b868d14275f8bf62372332aba2d6cb1a9b565aebb76"

REQUIRED_RECONSTRUCTION_FIELDS = (
    "counted_object",
    "exact_identity",
    "source_observations",
    "source_frames",
    "language_jurisdiction_scope",
    "world_knowledge_cutoffs",
    "discovery_stopping_rule",
    "observed_vs_estimated",
    "model_assumptions",
    "uncertainty",
    "unresolved_evidence",
    "publication_authority",
)

REQUIRED_HEADLINE_IDS = (
    "N_OBSERVED_A_P1",
    "N_ESTIMATED_A_P1",
    "DELTA_N_CAPABILITY",
    "DELTA_N_MULTILINGUAL",
    "D4_WORKING_INCLUDE",
    "UNRESOLVED_CANDIDATES_RETAINED",
    "FRAME_STOP_STATE_A6",
)

AG_PROTOCOL_BOUNDARY = (
    "A-G reconstruction protocol freezes the Release-A reconstruction checklist "
    "and binds the exact A8 Product Population Release Package digest before any "
    "reconstruction packet is emitted. It requires reconstructability of the "
    "twelve declared fields for each required headline from immutable artifacts. "
    "Freeze alone does not emit a PASSED or UNPASSED A-G outcome, authorize "
    "Release B/C/D, establish S2 publication authority, or create v4.2 "
    "assessment effect. A7 fail-closed N_observed=6 with no N_estimated is "
    "preserved. F9 exhaustion is not global completeness; open-world "
    "saturation is not a census."
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


def _load_resource(resource_name: str, *, package: str = RESOURCE_PACKAGE) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(package).joinpath(resource_name).read_text(encoding="utf-8")),
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


def _require_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProductDiscoveryError(f"{label} must be an integer")
    return value


def ag_freeze_does_not_emit_outcome() -> str:
    """Freeze alone never implies a PASSED or UNPASSED A-G reconstruction outcome."""

    return "PREREGISTERED_AWAITING_RECONSTRUCTION_PACKET"


def load_default_ag_reconstruction_protocol() -> dict[str, Any]:
    """Load the frozen A-G reconstruction protocol."""

    protocol = _load_resource(AG_PROTOCOL_RESOURCE)
    validate_ag_reconstruction_protocol(protocol)
    if protocol["protocol_sha256"] != AG_PROTOCOL_SHA256:
        raise ProductDiscoveryError("Loaded A-G protocol digest drifted from frozen AG_PROTOCOL_SHA256")
    return protocol


def validate_ag_reconstruction_protocol(protocol: Mapping[str, Any]) -> None:
    """Validate the frozen A-G reconstruction protocol against A8 bindings."""

    required = (
        "protocol_id",
        "protocol_sha256",
        "status",
        "study_id",
        "census_registered_at",
        "a8_package_id",
        "a8_package_sha256",
        "a8_contract_sha256",
        "analysis_universe_id",
        "world_time_cutoff",
        "knowledge_time_cutoff",
        "language_scope_id",
        "jurisdiction_scope",
        "population_view_id",
        "n_observed_declared",
        "n_estimated_declared",
        "unresolved_candidate_count_declared",
        "d4_working_include_declared",
        "d4_working_total_declared",
        "observed_offering_ids",
        "required_reconstruction_fields",
        "required_headline_ids",
        "headline_reconstruction_bindings",
        "fail_closed_rules",
        "estimator_exclusion_policy",
        "execution_gate",
        "predeclaration_rule",
        "boundary",
    )
    missing = [field for field in required if field not in protocol]
    if missing:
        raise ProductDiscoveryError("A-G reconstruction protocol missing fields: " + ", ".join(missing))

    if protocol["protocol_id"] != AG_PROTOCOL_ID:
        raise ProductDiscoveryError(f"protocol_id must be {AG_PROTOCOL_ID}")
    if protocol["status"] != "FROZEN_v1.0":
        raise ProductDiscoveryError("status must be FROZEN_v1.0")
    if protocol["study_id"] != AG_STUDY_ID:
        raise ProductDiscoveryError(f"study_id must be {AG_STUDY_ID}")
    if content_digest(protocol, exclude="protocol_sha256") != protocol["protocol_sha256"]:
        raise ProductDiscoveryError("protocol_sha256 does not match content digest")
    if protocol["boundary"] != AG_PROTOCOL_BOUNDARY:
        raise ProductDiscoveryError("boundary text drift")

    if protocol["a8_package_id"] != A8_PACKAGE_ID:
        raise ProductDiscoveryError(f"a8_package_id must be {A8_PACKAGE_ID}")
    if protocol["a8_package_sha256"] != A8_PACKAGE_SHA256:
        raise ProductDiscoveryError("a8_package_sha256 must equal frozen A8 package digest")
    if protocol["a8_contract_sha256"] != A8_CONTRACT_SHA256:
        raise ProductDiscoveryError("a8_contract_sha256 must equal frozen A8 contract digest")
    if protocol["analysis_universe_id"] != DEFAULT_ANALYSIS_UNIVERSE_ID:
        raise ProductDiscoveryError("analysis_universe_id must equal frozen A2 analysis universe")
    if protocol["world_time_cutoff"] != A2_WORLD_TIME_CUTOFF:
        raise ProductDiscoveryError("world_time_cutoff drift")
    if protocol["knowledge_time_cutoff"] != A2_KNOWLEDGE_TIME_CUTOFF:
        raise ProductDiscoveryError("knowledge_time_cutoff drift")
    if protocol["language_scope_id"] != A2_LANGUAGE_SCOPE_ID:
        raise ProductDiscoveryError("language_scope_id drift")
    if protocol["jurisdiction_scope"] != A2_JURISDICTION_SCOPE:
        raise ProductDiscoveryError("jurisdiction_scope drift")
    if protocol["population_view_id"] != POPULATION_VIEW_ID:
        raise ProductDiscoveryError(f"population_view_id must be {POPULATION_VIEW_ID}")
    if _require_int(protocol["n_observed_declared"], "n_observed_declared") != N_OBSERVED:
        raise ProductDiscoveryError(f"n_observed_declared must be {N_OBSERVED}")
    if protocol["n_estimated_declared"] is not None:
        raise ProductDiscoveryError("n_estimated_declared must remain null under A7 fail-closed")
    if _require_int(protocol["unresolved_candidate_count_declared"], "unresolved_candidate_count_declared") != (
        UNRESOLVED_CANDIDATE_COUNT
    ):
        raise ProductDiscoveryError("unresolved_candidate_count_declared drift")
    if (
        _require_int(protocol["d4_working_include_declared"], "d4_working_include_declared")
        != D4_WORKING_DISTRIBUTION["INCLUDE"]
    ):
        raise ProductDiscoveryError("d4_working_include_declared drift")
    if (
        _require_int(protocol["d4_working_total_declared"], "d4_working_total_declared")
        != D4_WORKING_DISTRIBUTION["TOTAL"]
    ):
        raise ProductDiscoveryError("d4_working_total_declared drift")
    if tuple(protocol["observed_offering_ids"]) != OBSERVED_OFFERING_IDS:
        raise ProductDiscoveryError("observed_offering_ids drift")

    fields = _require_list(protocol["required_reconstruction_fields"], "required_reconstruction_fields")
    if tuple(fields) != REQUIRED_RECONSTRUCTION_FIELDS:
        raise ProductDiscoveryError("required_reconstruction_fields drift")

    headlines = _require_list(protocol["required_headline_ids"], "required_headline_ids")
    if tuple(headlines) != REQUIRED_HEADLINE_IDS:
        raise ProductDiscoveryError("required_headline_ids drift")

    bindings = _require_mapping(protocol["headline_reconstruction_bindings"], "headline_reconstruction_bindings")
    if set(bindings.keys()) != set(REQUIRED_HEADLINE_IDS):
        raise ProductDiscoveryError("headline_reconstruction_bindings key set drift")
    for headline_id in REQUIRED_HEADLINE_IDS:
        binding = _require_mapping(bindings[headline_id], headline_id)
        _require_str(binding.get("a8_component_path"), f"{headline_id}.a8_component_path")
        _require_str(binding.get("upstream_digest_field"), f"{headline_id}.upstream_digest_field")
        _require_str(binding.get("expected_value_description"), f"{headline_id}.expected_value_description")
        field_checklist = _require_list(binding.get("required_fields"), f"{headline_id}.required_fields")
        if tuple(field_checklist) != REQUIRED_RECONSTRUCTION_FIELDS:
            raise ProductDiscoveryError(f"{headline_id} must require all twelve reconstruction fields")

    fail_closed = _require_mapping(protocol["fail_closed_rules"], "fail_closed_rules")
    for field in (
        "missing_upstream_digest_is_unpassed",
        "invented_n_estimated_is_rejected",
        "completeness_overclaim_is_rejected",
        "mixed_universe_is_rejected",
        "estimator_contamination_f7_f9_f11_is_rejected",
        "unresolved_required_field_is_unpassed",
    ):
        if not _require_bool(fail_closed.get(field), field):
            raise ProductDiscoveryError(f"fail_closed_rules.{field} must be true")

    exclusion = _require_mapping(protocol["estimator_exclusion_policy"], "estimator_exclusion_policy")
    excluded = _require_list(exclusion.get("excluded_frame_ids"), "excluded_frame_ids")
    if set(excluded) != PRIMARY_ESTIMATION_EXCLUDED_FRAME_IDS:
        raise ProductDiscoveryError("estimator exclusion must be exactly F7/F9/F11")
    if not _require_bool(
        exclusion.get("reject_primary_estimator_contamination"), "reject_primary_estimator_contamination"
    ):
        raise ProductDiscoveryError("reject_primary_estimator_contamination must be true")

    gate = _require_mapping(protocol["execution_gate"], "execution_gate")
    for field in (
        "requires_frozen_protocol_before_packet",
        "freeze_alone_does_not_emit_outcome",
        "does_not_authorize_release_b_c_d",
        "does_not_establish_s2_publication_authority",
        "does_not_create_v4_2_assessment_effect",
        "does_not_mutate_rau",
        "does_not_allocate_canonical_identity",
        "does_not_reopen_closed_discovery_fitting",
        "preserves_a7_fail_closed",
        "f9_exhaustion_is_not_global_completeness",
        "open_world_saturation_is_not_census",
        "reconstruction_not_paperwork_signoff",
    ):
        if not _require_bool(gate.get(field), field):
            raise ProductDiscoveryError(f"execution_gate.{field} must be true")

    predeclaration = _require_str(protocol.get("predeclaration_rule"), "predeclaration_rule")
    lowered = predeclaration.lower()
    if "twelve" not in lowered and "12" not in lowered:
        raise ProductDiscoveryError("predeclaration_rule must require the twelve reconstruction fields")
    if "a8" not in lowered:
        raise ProductDiscoveryError("predeclaration_rule must bind the A8 package")
    if "b/c/d" not in lowered and "release b" not in lowered:
        raise ProductDiscoveryError("predeclaration_rule must refuse authorizing Release B/C/D")
