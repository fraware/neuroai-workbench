from __future__ import annotations

from copy import deepcopy

import pytest

from neuroai_workbench.product_registry import (
    BOUNDARY_CONTRACT_ID,
    BOUNDARY_CONTRACT_SEMANTIC_BLOB,
    CURRENTNESS_POLICY_ID,
    POPULATION_VIEW_POLICY_ID,
    REFERENCE_STANDARD_ID,
    REFERENCE_STANDARD_VALIDATION_STATE,
    REFERENCE_STANDARD_VERSION,
    REGISTRY_BOUNDARY,
    REGISTRY_PROJECTION_VERSION,
    ProductRegistryError,
    population_view_identity_ids,
    registry_row_id,
    row_qualifies_for_population_view,
    validate_product_registry,
    validate_product_registry_row,
)


def _row(
    entity_id: str = "PRD-MUSE-S-ATHENA",
    *,
    entity_type: str = "PRODUCT",
    identity_level: str = "OFFERING",
    family_id: str | None = None,
    offering_id: str | None = None,
    configuration_id: str | None = None,
    configuration_state: str = "NOT_APPLICABLE",
    role: str = "OFFERING",
    offering_kind: str = "BUNDLE",
    enumeration_role: str = "INTEGRATED_SYSTEM",
    boundary_disposition: str = "INCLUDE",
    lifecycle: str = "RELEASED",
    access: str = "COMMERCIAL_DIRECT",
    regulatory: str = "NO_CONTROLLING_RECORD",
    deployment: str = "DOCUMENTED_CONSUMER_ACCESS",
    currentness: str = "CURRENT",
    jurisdiction: str = "GLOBAL",
) -> dict[str, object]:
    if offering_id is None and identity_level == "OFFERING":
        offering_id = entity_id
    row: dict[str, object] = {
        "registry_row_id": "",
        "registry_projection_version": REGISTRY_PROJECTION_VERSION,
        "boundary_contract_id": BOUNDARY_CONTRACT_ID,
        "boundary_contract_semantic_blob": BOUNDARY_CONTRACT_SEMANTIC_BLOB,
        "reference_standard_id": REFERENCE_STANDARD_ID,
        "reference_standard_version": REFERENCE_STANDARD_VERSION,
        "reference_standard_validation_state": REFERENCE_STANDARD_VALIDATION_STATE,
        "population_view_policy_id": POPULATION_VIEW_POLICY_ID,
        "currentness_policy_id": CURRENTNESS_POLICY_ID,
        "canonical_entity_id": entity_id,
        "canonical_entity_type": entity_type,
        "identity_level": identity_level,
        "product_family_id": family_id,
        "product_offering_id": offering_id,
        "configuration_system_id": configuration_id,
        "configuration_coverage_state": configuration_state,
        "system_or_offering_role": role,
        "offering_kind": offering_kind,
        "primary_enumeration_role": enumeration_role,
        "jurisdiction_scope": jurisdiction,
        "world_time_cutoff": "2026-09-24",
        "knowledge_time_cutoff": "2026-09-24T12:00:00Z",
        "identity_state": "RESOLVED",
        "boundary_disposition": boundary_disposition,
        "boundary_disposition_ref": "D4_PRODUCT_REFERENCE_STANDARD_v1.0:D4-REF-001",
        "lifecycle_state": lifecycle,
        "access_commercial_state": access,
        "regulatory_state": regulatory,
        "deployment_state": deployment,
        "currentness_state": currentness,
        "evidence_state": ["COMPANY_REPRESENTATION"],
        "organization_relationship_refs": ["REL-DEV-1"],
        "projected_assertion_refs": ["AST-1"],
        "source_observation_refs": ["OBS-1"],
        "first_observed_at": "2026-09-20T00:00:00Z",
        "last_observed_at": "2026-09-24T00:00:00Z",
        "signal_or_sensing_modality": ["SENSE_SCALP_EEG"],
        "inference_capability": ["STATE_ATTENTION_VIGILANCE"],
        "intervention_output_capability": ["OUTPUT_NEUROFEEDBACK"],
        "form_factor": ["FORM_HEADBAND"],
        "deployment_context": ["CONTEXT_CONSUMER_WELLNESS"],
        "target_population": ["GENERAL_ADULT"],
        "technical_equivalence_cluster_id": None,
        "technical_equivalence_evidence_refs": [],
        "boundary": REGISTRY_BOUNDARY,
    }
    row["registry_row_id"] = registry_row_id(row)
    return row


def test_registry_row_id_is_deterministic_and_cutoff_sensitive() -> None:
    first = _row()
    second = deepcopy(first)
    second["registry_row_id"] = registry_row_id(second)
    assert first["registry_row_id"] == second["registry_row_id"]

    second["knowledge_time_cutoff"] = "2026-09-25T12:00:00Z"
    second["registry_row_id"] = registry_row_id(second)
    assert first["registry_row_id"] != second["registry_row_id"]


def test_family_is_aggregation_not_offering_denominator() -> None:
    family = _row(
        "PRD-ENOBIO-FAMILY",
        identity_level="FAMILY",
        family_id="PRD-ENOBIO-FAMILY",
        offering_id=None,
        configuration_state="NOT_APPLICABLE",
        role="OFFERING_FAMILY",
        offering_kind="RESEARCH_PLATFORM",
        enumeration_role="OTHER_REVIEW_REQUIRED",
    )
    validate_product_registry_row(family)
    assert not row_qualifies_for_population_view(family, "A-P1")
    assert not row_qualifies_for_population_view(family, "A-P5")

    invalid = deepcopy(family)
    invalid["canonical_entity_type"] = "SYSTEM"
    invalid["registry_row_id"] = registry_row_id(invalid)
    with pytest.raises(ProductRegistryError, match="FAMILY rows must project canonical PRODUCT"):
        validate_product_registry_row(invalid)


def test_current_offering_views_separate_commercial_and_investigational_access() -> None:
    muse = _row()
    assert row_qualifies_for_population_view(muse, "A-P1")
    assert row_qualifies_for_population_view(muse, "A-P2")
    assert not row_qualifies_for_population_view(muse, "A-P3")
    assert row_qualifies_for_population_view(muse, "A-P4")
    assert row_qualifies_for_population_view(muse, "A-P5")
    assert row_qualifies_for_population_view(muse, "A-P6")
    assert not row_qualifies_for_population_view(muse, "A-P7")

    braingate = _row(
        "PRD-BRAINGATE2",
        role="FORMAL_INVESTIGATIONAL_OFFERING",
        offering_kind="FORMAL_INVESTIGATIONAL_OFFERING",
        lifecycle="IN_DEVELOPMENT",
        access="TRIAL_INVESTIGATIONAL",
        regulatory="INVESTIGATIONAL_AUTHORIZATION",
        deployment="TRIAL_USE",
    )
    assert row_qualifies_for_population_view(braingate, "A-P1")
    assert not row_qualifies_for_population_view(braingate, "A-P2")
    assert row_qualifies_for_population_view(braingate, "A-P3")
    assert row_qualifies_for_population_view(braingate, "A-P4")
    assert row_qualifies_for_population_view(braingate, "A-P6")


def test_component_and_software_roles_do_not_silently_enter_integrated_system_view() -> None:
    layer7 = _row(
        "PRD-LAYER7T",
        offering_kind="REGULATED_MEDICAL_PRODUCT",
        enumeration_role="COMPONENT_OR_SUBSYSTEM",
        regulatory="CLEARANCE",
        deployment="TRIAL_USE",
    )
    assert row_qualifies_for_population_view(layer7, "A-P1")
    assert row_qualifies_for_population_view(layer7, "A-P2")
    assert not row_qualifies_for_population_view(layer7, "A-P4")

    eeg_module = _row(
        "PRD-IMOTIONS-EEG-MODULE",
        role="SERVICE_OFFERING",
        offering_kind="SOFTWARE",
        enumeration_role="STANDALONE_SOFTWARE_OR_SERVICE",
        access="RESEARCH_USE_SOLD_OR_LICENSED",
        deployment="RESEARCH_DEPLOYMENT",
    )
    assert row_qualifies_for_population_view(eeg_module, "A-P2")
    assert row_qualifies_for_population_view(eeg_module, "A-P3")
    assert not row_qualifies_for_population_view(eeg_module, "A-P4")


def test_discontinued_but_deployed_product_enters_legacy_view_only() -> None:
    embrace2 = _row(
        "PRD-EMPATICA-EMBRACE2",
        lifecycle="DISCONTINUED",
        access="DISCONTINUED_UNAVAILABLE",
        deployment="DOCUMENTED_CONSUMER_ACCESS",
        currentness="NOT_CURRENT",
    )
    validate_product_registry_row(embrace2)
    assert not row_qualifies_for_population_view(embrace2, "A-P1")
    assert row_qualifies_for_population_view(embrace2, "A-P5")
    assert row_qualifies_for_population_view(embrace2, "A-P7")


def test_excluded_adjacent_product_never_enters_primary_views() -> None:
    mudra = _row("PRD-MUDRA-BAND", boundary_disposition="EXCLUDE")
    for view_id in ("A-P1", "A-P2", "A-P3", "A-P4", "A-P5", "A-P6", "A-P7"):
        assert not row_qualifies_for_population_view(mudra, view_id)


def test_configuration_view_requires_qualifying_parent_offering() -> None:
    parent = _row(
        "PRD-PERCEPT-RC",
        offering_kind="REGULATED_MEDICAL_PRODUCT",
        regulatory="APPROVAL_AUTHORIZATION",
        deployment="DOCUMENTED_CLINICAL_DEPLOYMENT",
    )
    config = _row(
        "SYS-PERCEPT-RC-ADBS",
        entity_type="SYSTEM",
        identity_level="CONFIGURATION",
        offering_id="PRD-PERCEPT-RC",
        configuration_id="SYS-PERCEPT-RC-ADBS",
        configuration_state="RESOLVED",
        role="PRODUCT_CONFIGURATION",
        offering_kind="NOT_APPLICABLE",
        regulatory="APPROVAL_AUTHORIZATION",
        deployment="DOCUMENTED_CLINICAL_DEPLOYMENT",
    )
    validate_product_registry_row(config)
    assert population_view_identity_ids([parent, config], "A-P8") == {"SYS-PERCEPT-RC-ADBS"}

    excluded_parent = deepcopy(parent)
    excluded_parent["boundary_disposition"] = "EXCLUDE"
    excluded_parent["registry_row_id"] = registry_row_id(excluded_parent)
    assert population_view_identity_ids([excluded_parent, config], "A-P8") == set()


def test_registry_validation_rejects_duplicate_projection_and_row_count_drift() -> None:
    row = _row()
    registry = {
        "metadata": {
            "title": "Synthetic product registry",
            "registry_projection_version": REGISTRY_PROJECTION_VERSION,
            "row_count": 1,
            "world_time_cutoff": "2026-09-24",
            "knowledge_time_cutoff": "2026-09-24T12:00:00Z",
            "jurisdiction_scope": "GLOBAL",
            "boundary_contract_id": BOUNDARY_CONTRACT_ID,
            "reference_standard_id": REFERENCE_STANDARD_ID,
            "population_view_policy_id": POPULATION_VIEW_POLICY_ID,
            "currentness_policy_id": CURRENTNESS_POLICY_ID,
        },
        "rows": [row],
        "boundary": REGISTRY_BOUNDARY,
    }
    validate_product_registry(registry)

    duplicate = deepcopy(registry)
    duplicate["rows"].append(deepcopy(row))
    duplicate["metadata"]["row_count"] = 2
    with pytest.raises(ProductRegistryError, match="Duplicate registry_row_id"):
        validate_product_registry(duplicate)

    drift = deepcopy(registry)
    drift["metadata"]["row_count"] = 2
    with pytest.raises(ProductRegistryError, match="does not match observed row count"):
        validate_product_registry(drift)
