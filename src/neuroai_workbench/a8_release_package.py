"""Validators for Release-A A8 product population release-package contract.

Freezes the A8 package manifest contract, required components, claim-class
separations, forbidden claim classes, and exact upstream digest bindings before
any package materialization. Freeze alone does not emit the Release A package
or start A-G reconstruction.
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
    LANGUAGE_STRATA_SHA256,
)
from neuroai_workbench.a5_snowball_discovery import (
    A5_PREREG_ID,
    A5_PREREG_SHA256,
    A5_STUDY_ID,
    A5_STUDY_PACKET_SHA256,
)
from neuroai_workbench.a6_saturation_analysis import (
    A6_PREREG_ID,
    A6_PREREG_SHA256,
    A6_STUDY_ID,
    A6_STUDY_PACKET_SHA256,
)
from neuroai_workbench.a7_population_estimation import (
    A7_CAPTURE_HISTORY_ID,
    A7_CAPTURE_HISTORY_SHA256,
    A7_ELIGIBLE_CAPTURE_RECORDS_SHA256,
    A7_MODEL_SPEC_ID,
    A7_MODEL_SPEC_SHA256,
    A7_STUDY_ID,
    A7_STUDY_PACKET_ID,
    A7_STUDY_PACKET_SHA256,
    N_OBSERVED,
    VALID_NO_ESTIMATE_OUTCOME,
)
from neuroai_workbench.f8_f10_protocol import LANGUAGE_STRATA_ID
from neuroai_workbench.product_discovery_frames import (
    A1_INITIAL_KNOWN_IDENTITY_SHA256,
    A2_FRAME_REGISTER_BLOB_SHA,
    A2_KNOWLEDGE_TIME_CUTOFF,
    A2_WORLD_TIME_CUTOFF,
    DEFAULT_ANALYSIS_UNIVERSE_ID,
    FRAME_REGISTER_VERSION,
    ProductDiscoveryError,
)
from neuroai_workbench.release_a_seed_registry import (
    PRODUCT_IDENTITY_REGISTRY_ID,
    PRODUCT_IDENTITY_REGISTRY_RESOURCE,
    SEED_PRODUCT_REGISTRY_RESOURCE,
    product_identity_registry_sha256,
    seed_registry_sha256,
)

RESOURCE_PACKAGE = "neuroai_workbench.resources.discovery"
PRODUCT_REGISTRY_PACKAGE = "neuroai_workbench.resources.product_registry"

A8_CONTRACT_RESOURCE = "RELEASE_A_A8_PACKAGE_MANIFEST_CONTRACT.v1.0.json"
A8_CONTRACT_SCHEMA_RESOURCE = "RELEASE_A_A8_PACKAGE_MANIFEST_CONTRACT.schema.json"
A8_CONTRACT_ID = "RELEASE_A_A8_PACKAGE_MANIFEST_CONTRACT_v1.0"
A8_PACKAGE_ID = "RELEASE_A_A8_PRODUCT_POPULATION_RELEASE_PACKAGE_v1.0"
A8_CONTRACT_SHA256 = "f5acad2896c767b80bd75a951ea933cc1d2c319a9580aa560e46db46e824cf78"

CHECKPOINT_SHA256 = "452c8c504990c05edd6ac7c29b542a49ffa4fd81ccdece2bd7ca8e9e0921ca32"
F9_LEDGER_ID = "RELEASE_A_F9_ACTOR_COMPLETION_LEDGER_008_v1.0"
F9_LEDGER_SHA256 = "8ed73ad8e53c341f28a749527e5cc6e7277b5a37ba205231ed8219d24c27fc9e"
POPULATION_VIEW_ID = "A-P1"
D4_REFERENCE_STANDARD_ID = "D4_PRODUCT_REFERENCE_STANDARD_v1.0"
D4_REFERENCE_STANDARD_VERSION = "1.0"
D4_WORKING_DISTRIBUTION = {
    "INCLUDE": 49,
    "EXCLUDE": 11,
    "BORDERLINE": 0,
    "ABSTAIN": 0,
    "TOTAL": 60,
}

REQUIRED_PACKAGE_COMPONENTS = (
    "PRODUCT_REGISTRY",
    "D4_REFERENCE_STANDARD_SUMMARY",
    "DISCOVERY_FRAME_REGISTER",
    "A3_CAPABILITY_FIRST_RECALL_STUDY",
    "A4_MULTILINGUAL_COVERAGE_SENSITIVITY_REPORT",
    "A6_COVERAGE_SATURATION_REPORT",
    "A7_POPULATION_ESTIMATION_REPORT",
    "ANALYTICAL_WORKBOOK_FIGURE_DATA",
    "SOURCE_COVERAGE_UNCERTAINTY_REGISTER",
    "EXPLICIT_UNKNOWN_UNRESOLVED_REGISTER",
)

CLAIM_CLASSES = (
    "OBSERVED_FACT",
    "DERIVED_QUANTITATIVE_RESULT",
    "BOUNDED_INFERENCE",
    "POLICY_INTERPRETATION",
)

FORBIDDEN_CLAIM_CLASSES = (
    "MARKET_SHARE",
    "COMPARATIVE_EFFECTIVENESS",
    "NATIONAL_LEADERSHIP",
    "UNQUALIFIED_HETEROGENEOUS_PRODUCT_COUNT",
    "INVENTED_N_ESTIMATED",
    "F9_EXHAUSTION_AS_GLOBAL_COMPLETENESS",
    "OPEN_WORLD_SATURATION_AS_CENSUS",
    "GLOBAL_PRODUCT_CENSUS",
)

A8_BOUNDARY = (
    "A8 package-manifest contract freezes required Release-A package components, "
    "claim-class separations, forbidden claim classes, headline-denominator rules, "
    "and exact upstream digest bindings before package materialization. It does not "
    "establish market share, comparative effectiveness, national leadership, global "
    "completeness, S2 publication authority, or v4.2 assessment effect. Freeze alone "
    "does not emit the Product Population Release Package. A7 fail-closed "
    "N_observed=6 with no N_estimated is preserved. F9 exhaustion is not global "
    "completeness; open-world saturation is not a census. Does not start A-G."
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


def frozen_product_registry_sha256() -> str:
    """Return the frozen A1 seed Product Registry digest."""

    return seed_registry_sha256(_load_resource(SEED_PRODUCT_REGISTRY_RESOURCE, package=PRODUCT_REGISTRY_PACKAGE))


def frozen_product_identity_registry_sha256() -> str:
    """Return the frozen A1 product identity registry digest."""

    return product_identity_registry_sha256(
        _load_resource(PRODUCT_IDENTITY_REGISTRY_RESOURCE, package=PRODUCT_REGISTRY_PACKAGE)
    )


def a8_freeze_does_not_emit_package() -> str:
    """Freeze alone never implies an emitted Product Population Release Package."""

    return "PREREGISTERED_AWAITING_PACKAGE_MATERIALIZATION"


def load_default_a8_package_manifest_contract() -> dict[str, Any]:
    """Load the frozen A8 package-manifest contract."""

    contract = _load_resource(A8_CONTRACT_RESOURCE)
    validate_a8_package_manifest_contract(contract)
    if contract["contract_sha256"] != A8_CONTRACT_SHA256:
        raise ProductDiscoveryError("Loaded A8 contract digest drifted from frozen A8_CONTRACT_SHA256")
    return contract


def validate_a8_package_manifest_contract(contract: Mapping[str, Any]) -> None:
    """Validate the frozen A8 package-manifest contract against upstream locks."""

    required = (
        "contract_id",
        "contract_sha256",
        "status",
        "package_id",
        "census_registered_at",
        "analysis_universe_id",
        "world_time_cutoff",
        "knowledge_time_cutoff",
        "a2_checkpoint_id",
        "a2_checkpoint_sha256",
        "observed_offering_set_sha256",
        "n_observed_declared",
        "population_view_id",
        "frame_register_version",
        "frame_register_blob_sha",
        "predeclaration_rule",
        "upstream_digest_bindings",
        "required_package_components",
        "claim_classes",
        "forbidden_claim_classes",
        "headline_count_rules",
        "d4_binding_policy",
        "a7_fail_closed_preservation",
        "execution_gate",
        "boundary",
    )
    missing = [field for field in required if field not in contract]
    if missing:
        raise ProductDiscoveryError("A8 package-manifest contract missing fields: " + ", ".join(missing))

    if contract["contract_id"] != A8_CONTRACT_ID:
        raise ProductDiscoveryError(f"contract_id must be {A8_CONTRACT_ID}")
    if contract["status"] != "FROZEN_v1.0":
        raise ProductDiscoveryError("status must be FROZEN_v1.0")
    if contract["package_id"] != A8_PACKAGE_ID:
        raise ProductDiscoveryError(f"package_id must be {A8_PACKAGE_ID}")
    if content_digest(contract, exclude="contract_sha256") != contract["contract_sha256"]:
        raise ProductDiscoveryError("contract_sha256 does not match content digest")

    if contract["analysis_universe_id"] != DEFAULT_ANALYSIS_UNIVERSE_ID:
        raise ProductDiscoveryError("analysis_universe_id must equal frozen A2 analysis universe")
    if contract["world_time_cutoff"] != A2_WORLD_TIME_CUTOFF:
        raise ProductDiscoveryError("world_time_cutoff drift")
    if contract["knowledge_time_cutoff"] != A2_KNOWLEDGE_TIME_CUTOFF:
        raise ProductDiscoveryError("knowledge_time_cutoff drift")
    if contract["a2_checkpoint_id"] != CHECKPOINT_ID:
        raise ProductDiscoveryError("a2_checkpoint_id must equal frozen A2 checkpoint")
    if contract["a2_checkpoint_sha256"] != CHECKPOINT_SHA256:
        raise ProductDiscoveryError("a2_checkpoint_sha256 drift from frozen A2 checkpoint")
    if contract["observed_offering_set_sha256"] != A1_INITIAL_KNOWN_IDENTITY_SHA256:
        raise ProductDiscoveryError("observed_offering_set_sha256 must equal A1 known-identity digest")
    if _require_int(contract["n_observed_declared"], "n_observed_declared") != N_OBSERVED:
        raise ProductDiscoveryError(f"n_observed_declared must be {N_OBSERVED}")
    if contract["population_view_id"] != POPULATION_VIEW_ID:
        raise ProductDiscoveryError(f"population_view_id must be {POPULATION_VIEW_ID}")
    if contract["frame_register_version"] != FRAME_REGISTER_VERSION:
        raise ProductDiscoveryError("frame_register_version drift")
    if contract["frame_register_blob_sha"] != A2_FRAME_REGISTER_BLOB_SHA:
        raise ProductDiscoveryError("frame_register_blob_sha drift")
    if contract["boundary"] != A8_BOUNDARY:
        raise ProductDiscoveryError("boundary text drift")

    bindings = _require_mapping(contract["upstream_digest_bindings"], "upstream_digest_bindings")
    expected_bindings = {
        "product_registry_resource": SEED_PRODUCT_REGISTRY_RESOURCE,
        "product_registry_sha256": frozen_product_registry_sha256(),
        "product_identity_registry_id": PRODUCT_IDENTITY_REGISTRY_ID,
        "product_identity_registry_sha256": frozen_product_identity_registry_sha256(),
        "d4_reference_standard_id": D4_REFERENCE_STANDARD_ID,
        "d4_reference_standard_version": D4_REFERENCE_STANDARD_VERSION,
        "frame_register_version": FRAME_REGISTER_VERSION,
        "frame_register_blob_sha": A2_FRAME_REGISTER_BLOB_SHA,
        "f9_completion_ledger_id": F9_LEDGER_ID,
        "f9_completion_ledger_sha256": F9_LEDGER_SHA256,
        "language_jurisdiction_strata_id": LANGUAGE_STRATA_ID,
        "language_jurisdiction_strata_sha256": LANGUAGE_STRATA_SHA256,
        "a3_preregistration_id": A3_PREREG_ID,
        "a3_preregistration_sha256": A3_PREREG_SHA256,
        "a3_study_id": A3_STUDY_ID,
        "a3_study_sha256": A3_STUDY_PACKET_SHA256,
        "a4_preregistration_id": A4_PREREG_ID,
        "a4_preregistration_sha256": A4_PREREG_SHA256,
        "a4_study_id": A4_STUDY_ID,
        "a4_study_sha256": A4_STUDY_PACKET_SHA256,
        "a5_preregistration_id": A5_PREREG_ID,
        "a5_preregistration_sha256": A5_PREREG_SHA256,
        "a5_study_id": A5_STUDY_ID,
        "a5_study_sha256": A5_STUDY_PACKET_SHA256,
        "a6_preregistration_id": A6_PREREG_ID,
        "a6_preregistration_sha256": A6_PREREG_SHA256,
        "a6_study_id": A6_STUDY_ID,
        "a6_study_sha256": A6_STUDY_PACKET_SHA256,
        "a7_capture_history_id": A7_CAPTURE_HISTORY_ID,
        "a7_capture_history_sha256": A7_CAPTURE_HISTORY_SHA256,
        "a7_model_specification_id": A7_MODEL_SPEC_ID,
        "a7_model_specification_sha256": A7_MODEL_SPEC_SHA256,
        "a7_eligible_capture_records_sha256": A7_ELIGIBLE_CAPTURE_RECORDS_SHA256,
        "a7_estimation_report_id": A7_STUDY_PACKET_ID,
        "a7_estimation_report_sha256": A7_STUDY_PACKET_SHA256,
        "a7_study_id": A7_STUDY_ID,
    }
    for key, expected in expected_bindings.items():
        if bindings.get(key) != expected:
            raise ProductDiscoveryError(f"upstream_digest_bindings.{key} drift")

    components = _require_list(contract["required_package_components"], "required_package_components")
    if tuple(components) != REQUIRED_PACKAGE_COMPONENTS:
        raise ProductDiscoveryError("required_package_components drift")

    claim_classes = _require_list(contract["claim_classes"], "claim_classes")
    if tuple(claim_classes) != CLAIM_CLASSES:
        raise ProductDiscoveryError("claim_classes drift")

    forbidden = _require_list(contract["forbidden_claim_classes"], "forbidden_claim_classes")
    if tuple(forbidden) != FORBIDDEN_CLAIM_CLASSES:
        raise ProductDiscoveryError("forbidden_claim_classes drift")

    headline = _require_mapping(contract["headline_count_rules"], "headline_count_rules")
    for field in (
        "every_headline_must_name_denominator",
        "every_headline_must_name_population_view",
        "heterogeneous_inventory_is_not_unqualified_product_count",
        "offering_role_mix_requires_explicit_role_breakdown",
    ):
        if not _require_bool(headline.get(field), field):
            raise ProductDiscoveryError(f"headline_count_rules.{field} must be true")
    if headline.get("primary_population_view_id") != POPULATION_VIEW_ID:
        raise ProductDiscoveryError("headline_count_rules.primary_population_view_id drift")
    if headline.get("primary_denominator_label") != (
        "distinct resolved in-scope canonical PRODUCT/OFFERING identities under A-P1"
    ):
        raise ProductDiscoveryError("headline_count_rules.primary_denominator_label drift")

    d4 = _require_mapping(contract["d4_binding_policy"], "d4_binding_policy")
    if d4.get("reference_standard_id") != D4_REFERENCE_STANDARD_ID:
        raise ProductDiscoveryError("d4_binding_policy.reference_standard_id drift")
    if d4.get("reference_standard_version") != D4_REFERENCE_STANDARD_VERSION:
        raise ProductDiscoveryError("d4_binding_policy.reference_standard_version drift")
    if not _require_bool(d4.get("bind_version_and_working_summary_only"), "bind_version_and_working_summary_only"):
        raise ProductDiscoveryError("d4_binding_policy.bind_version_and_working_summary_only must be true")
    if not _require_bool(d4.get("do_not_invent_d4_case_results"), "do_not_invent_d4_case_results"):
        raise ProductDiscoveryError("d4_binding_policy.do_not_invent_d4_case_results must be true")
    distribution = _require_mapping(d4.get("working_distribution"), "working_distribution")
    for disposition, count in D4_WORKING_DISTRIBUTION.items():
        if distribution.get(disposition) != count:
            raise ProductDiscoveryError(f"d4_binding_policy.working_distribution.{disposition} drift")

    a7 = _require_mapping(contract["a7_fail_closed_preservation"], "a7_fail_closed_preservation")
    if a7.get("n_observed") != N_OBSERVED:
        raise ProductDiscoveryError("a7_fail_closed_preservation.n_observed drift")
    if a7.get("n_estimated") is not None:
        raise ProductDiscoveryError("a7_fail_closed_preservation must keep n_estimated null")
    if a7.get("estimation_outcome") != "FAIL_CLOSED":
        raise ProductDiscoveryError("a7_fail_closed_preservation.estimation_outcome must be FAIL_CLOSED")
    if a7.get("fail_closed_outcome") != VALID_NO_ESTIMATE_OUTCOME:
        raise ProductDiscoveryError("a7_fail_closed_preservation.fail_closed_outcome drift")
    if not _require_bool(
        a7.get("observed_count_reported_separately_from_estimate"), "observed_count_reported_separately"
    ):
        raise ProductDiscoveryError(
            "a7_fail_closed_preservation.observed_count_reported_separately_from_estimate must be true"
        )
    if not _require_bool(a7.get("forbid_invented_n_estimated"), "forbid_invented_n_estimated"):
        raise ProductDiscoveryError("a7_fail_closed_preservation.forbid_invented_n_estimated must be true")

    gate = _require_mapping(contract["execution_gate"], "execution_gate")
    for field in (
        "requires_frozen_contract_before_package",
        "freeze_alone_does_not_emit_package",
        "does_not_start_ag",
        "does_not_mutate_rau",
        "does_not_allocate_canonical_identity",
        "does_not_reopen_closed_discovery_fitting",
        "does_not_start_release_b_c_d",
        "preserves_a7_fail_closed",
        "forbids_market_share_comparative_effectiveness_national_leadership",
        "f9_exhaustion_is_not_global_completeness",
        "open_world_saturation_is_not_census",
    ):
        if not _require_bool(gate.get(field), field):
            raise ProductDiscoveryError(f"execution_gate.{field} must be true")

    predeclaration = _require_str(contract.get("predeclaration_rule"), "predeclaration_rule")
    lowered = predeclaration.lower()
    if "claim class" not in lowered and "claim-class" not in lowered:
        raise ProductDiscoveryError("predeclaration_rule must require claim-class separation")
    if "denominator" not in lowered:
        raise ProductDiscoveryError("predeclaration_rule must require denominators")
    if "a-g" not in lowered:
        raise ProductDiscoveryError("predeclaration_rule must refuse starting A-G")
