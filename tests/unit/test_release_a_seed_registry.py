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
    registry_row_id,
)
from neuroai_workbench.release_a_seed_registry import (
    OBSERVATORY_DATA_REPO,
    SEED_EVIDENCE_BASIS,
    SEED_MANIFEST_VERSION,
    SEED_REGISTRY_BOUNDARY,
    ReleaseASeedRegistryError,
    build_seed_product_registry,
    seed_input_manifest_id,
    seed_registry_sha256,
    validate_seed_input_manifest,
)

WORKBENCH_BASELINE = "f581a3613681e6261218a31c5abb5c8950eca965"
S2_BASELINE = "35dcf13431eca40321bb64a88e1743d9313f9247"
PACKET_DIGEST = "1" * 64


def _row(
    entity_id: str = "PRD-MUSE-S-ATHENA",
    *,
    identity_level: str = "OFFERING",
    entity_type: str = "PRODUCT",
    offering_id: str | None = None,
    configuration_id: str | None = None,
    configuration_state: str = "NOT_APPLICABLE",
    role: str = "OFFERING",
    offering_kind: str = "BUNDLE",
    enumeration_role: str = "INTEGRATED_SYSTEM",
    disposition: str = "INCLUDE",
    identity_state: str = "RESOLVED",
    evidence_state: list[str] | None = None,
    assertion_refs: list[str] | None = None,
    observation_refs: list[str] | None = None,
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
        "product_family_id": None,
        "product_offering_id": offering_id,
        "configuration_system_id": configuration_id,
        "configuration_coverage_state": configuration_state,
        "system_or_offering_role": role,
        "offering_kind": offering_kind,
        "primary_enumeration_role": enumeration_role,
        "jurisdiction_scope": "GLOBAL_PROTOCOL_SCOPE",
        "world_time_cutoff": "2026-09-24",
        "knowledge_time_cutoff": "2026-09-24T14:00:00Z",
        "identity_state": identity_state,
        "boundary_disposition": disposition,
        "boundary_disposition_ref": "D4_PRODUCT_REFERENCE_STANDARD_v1.0:D4-REF-001",
        "lifecycle_state": "RELEASED",
        "access_commercial_state": "COMMERCIAL_DIRECT",
        "regulatory_state": "NO_CONTROLLING_RECORD",
        "deployment_state": "DOCUMENTED_CONSUMER_ACCESS",
        "currentness_state": "CURRENT",
        "evidence_state": evidence_state if evidence_state is not None else ["COMPANY_REPRESENTATION"],
        "organization_relationship_refs": ["REL-DEV-001"],
        "projected_assertion_refs": assertion_refs if assertion_refs is not None else ["AST-PRODUCT-001"],
        "source_observation_refs": observation_refs if observation_refs is not None else ["OBS-PRODUCT-001"],
        "first_observed_at": "2026-09-20T00:00:00Z",
        "last_observed_at": "2026-09-24T13:00:00Z",
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


def _binding(row: dict[str, object]) -> dict[str, object]:
    return {
        "registry_row_id": row["registry_row_id"],
        "canonical_entity_id": row["canonical_entity_id"],
        "exact_product_label": str(row["canonical_entity_id"]),
        "evidence_basis": SEED_EVIDENCE_BASIS,
        "source_observation_refs": list(row["source_observation_refs"]),
        "projected_assertion_refs": list(row["projected_assertion_refs"]),
        "boundary_disposition_ref": row["boundary_disposition_ref"],
        "organization_seed_refs": ["ORG-0001"],
    }


def _manifest(rows: list[dict[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {
        "manifest_id": "",
        "manifest_version": SEED_MANIFEST_VERSION,
        "registry_projection_version": REGISTRY_PROJECTION_VERSION,
        "workbench_baseline_sha": WORKBENCH_BASELINE,
        "observatory_data_repo": OBSERVATORY_DATA_REPO,
        "observatory_data_commit": S2_BASELINE,
        "observatory_release_refs": ["data-v0.1.0-public-governing"],
        "controlled_packet_digests": [PACKET_DIGEST],
        "evidence_index_sha256": seed_evidence_index_sha256(
            (str(ref) for row in rows for ref in row["source_observation_refs"]),
            (str(ref) for row in rows for ref in row["projected_assertion_refs"]),
        ),
        "world_time_cutoff": "2026-09-24",
        "knowledge_time_cutoff": "2026-09-24T14:00:00Z",
        "jurisdiction_scope": "GLOBAL_PROTOCOL_SCOPE",
        "seed_input_count": len(rows),
        "bindings": [_binding(row) for row in rows],
        "boundary": SEED_REGISTRY_BOUNDARY,
    }
    value["manifest_id"] = seed_input_manifest_id(value)
    return value


def _build(
    rows: list[dict[str, object]],
    manifest: dict[str, object] | None = None,
    *,
    known_observation_ids: set[str] | None = None,
    known_assertion_ids: set[str] | None = None,
) -> dict[str, object]:
    manifest = manifest or _manifest(rows)
    observation_ids = known_observation_ids
    if observation_ids is None:
        observation_ids = {str(ref) for row in rows for ref in row["source_observation_refs"]}
    assertion_ids = known_assertion_ids
    if assertion_ids is None:
        assertion_ids = {str(ref) for row in rows for ref in row["projected_assertion_refs"]}
    return build_seed_product_registry(
        rows,
        manifest,
        known_observation_ids=observation_ids,
        known_assertion_ids=assertion_ids,
    )


def test_seed_manifest_and_registry_are_deterministic() -> None:
    first = _row("PRD-A")
    second = _row("PRD-B", assertion_refs=["AST-B"], observation_refs=["OBS-B"])
    manifest = _manifest([first, second])

    validate_seed_input_manifest(manifest)
    registry = _build([second, first], manifest)

    assert registry["metadata"]["row_count"] == 2
    assert [row["canonical_entity_id"] for row in registry["rows"]] == [
        row["canonical_entity_id"] for row in sorted([first, second], key=lambda item: str(item["registry_row_id"]))
    ]
    assert len(seed_registry_sha256(registry)) == 64

    permuted = deepcopy(manifest)
    permuted["observatory_release_refs"] = list(reversed(permuted["observatory_release_refs"]))
    permuted["controlled_packet_digests"] = list(reversed(permuted["controlled_packet_digests"]))
    permuted["bindings"] = list(reversed(permuted["bindings"]))
    for binding in permuted["bindings"]:
        binding["source_observation_refs"] = list(reversed(binding["source_observation_refs"]))
        binding["projected_assertion_refs"] = list(reversed(binding["projected_assertion_refs"]))
        binding["organization_seed_refs"] = list(reversed(binding["organization_seed_refs"]))
    assert seed_input_manifest_id(permuted) == manifest["manifest_id"]


def test_organization_only_evidence_cannot_be_a_seed_product_basis() -> None:
    row = _row()
    manifest = _manifest([row])
    manifest["bindings"][0]["evidence_basis"] = "ORGANIZATION_ONLY"
    manifest["manifest_id"] = seed_input_manifest_id(manifest)

    with pytest.raises(ReleaseASeedRegistryError, match="schema validation failed"):
        validate_seed_input_manifest(manifest)


def test_manifest_identity_count_and_boundary_fail_closed() -> None:
    row = _row()
    manifest = _manifest([row])

    count_drift = deepcopy(manifest)
    count_drift["seed_input_count"] = 2
    count_drift["manifest_id"] = seed_input_manifest_id(count_drift)
    with pytest.raises(ReleaseASeedRegistryError, match="seed_input_count"):
        validate_seed_input_manifest(count_drift)

    wrong_boundary = deepcopy(manifest)
    wrong_boundary["boundary"] = "weaker boundary"
    wrong_boundary["manifest_id"] = seed_input_manifest_id(wrong_boundary)
    with pytest.raises(ReleaseASeedRegistryError, match="frozen A1 boundary"):
        validate_seed_input_manifest(wrong_boundary)

    wrong_id = deepcopy(manifest)
    wrong_id["manifest_id"] = "RASIM-" + "0" * 64
    with pytest.raises(ReleaseASeedRegistryError, match="manifest_id"):
        validate_seed_input_manifest(wrong_id)


def test_duplicate_manifest_bindings_are_rejected() -> None:
    row = _row()
    manifest = _manifest([row])
    manifest["bindings"].append(deepcopy(manifest["bindings"][0]))
    manifest["seed_input_count"] = 2
    manifest["manifest_id"] = seed_input_manifest_id(manifest)

    with pytest.raises(ReleaseASeedRegistryError, match="Duplicate seed registry_row_id"):
        validate_seed_input_manifest(manifest)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"identity_level": "FAMILY"}, "Family-only"),
        ({"identity_state": "UNRESOLVED"}, "resolved exact identity"),
        ({"boundary_disposition": "EXCLUDE"}, "INCLUDE boundary"),
        ({"primary_enumeration_role": "OTHER_REVIEW_REQUIRED"}, "resolved primary enumeration role"),
        ({"projected_assertion_refs": []}, "assertion references"),
        ({"evidence_state": ["UNRESOLVED"]}, "substantive evidence state"),
    ],
)
def test_non_high_confidence_rows_are_rejected(mutation: dict[str, object], message: str) -> None:
    row = _row()
    row.update(mutation)
    if mutation.get("identity_level") == "FAMILY":
        row["product_family_id"] = row["canonical_entity_id"]
        row["product_offering_id"] = None
        row["system_or_offering_role"] = "OFFERING_FAMILY"
        row["primary_enumeration_role"] = "OTHER_REVIEW_REQUIRED"
    row["registry_row_id"] = registry_row_id(row)
    manifest = _manifest([row])

    with pytest.raises(ReleaseASeedRegistryError, match=message):
        _build([row], manifest)


def test_missing_source_observation_is_rejected_by_underlying_registry_contract() -> None:
    row = _row(observation_refs=[])
    manifest = _manifest([row])
    with pytest.raises(ReleaseASeedRegistryError, match="Resolved identity requires source_observation_refs"):
        _build([row], manifest)


def test_seed_rows_must_match_manifest_cutoffs_and_binding_set() -> None:
    row = _row()
    manifest = _manifest([row])

    drift = deepcopy(row)
    drift["knowledge_time_cutoff"] = "2026-09-25T14:00:00Z"
    drift["registry_row_id"] = registry_row_id(drift)
    drift_manifest = _manifest([drift])
    drift_manifest["knowledge_time_cutoff"] = "2026-09-24T14:00:00Z"
    drift_manifest["manifest_id"] = seed_input_manifest_id(drift_manifest)
    with pytest.raises(ReleaseASeedRegistryError, match="knowledge_time_cutoff"):
        _build([drift], drift_manifest)

    other = _row("PRD-OTHER", assertion_refs=["AST-O"], observation_refs=["OBS-O"])
    with pytest.raises(ReleaseASeedRegistryError, match="exactly match"):
        _build([other], manifest)


def test_seed_binding_must_exactly_match_row_evidence_and_boundary() -> None:
    row = _row()

    for field, value, message in (
        ("canonical_entity_id", "PRD-WRONG", "canonical_entity_id"),
        ("source_observation_refs", ["OBS-WRONG"], "source observations"),
        ("projected_assertion_refs", ["AST-WRONG"], "assertions"),
        ("boundary_disposition_ref", "D4-WRONG", "boundary disposition"),
    ):
        manifest = _manifest([row])
        manifest["bindings"][0][field] = value
        manifest["manifest_id"] = seed_input_manifest_id(manifest)
        with pytest.raises(ReleaseASeedRegistryError, match=message):
            _build([row], manifest)


def test_configuration_seed_requires_parent_offering_in_same_registry() -> None:
    parent = _row("PRD-PERCEPT")
    config = _row(
        "SYS-PERCEPT-ADBS",
        identity_level="CONFIGURATION",
        entity_type="SYSTEM",
        offering_id="PRD-PERCEPT",
        configuration_id="SYS-PERCEPT-ADBS",
        configuration_state="RESOLVED",
        role="PRODUCT_CONFIGURATION",
        offering_kind="NOT_APPLICABLE",
        assertion_refs=["AST-CONFIG"],
        observation_refs=["OBS-CONFIG"],
    )

    with pytest.raises(ReleaseASeedRegistryError, match="requires its parent offering"):
        _build([config], _manifest([config]))

    registry = _build([parent, config], _manifest([parent, config]))
    assert registry["metadata"]["row_count"] == 2


def test_duplicate_seed_rows_are_rejected() -> None:
    row = _row()
    manifest = _manifest([row])
    with pytest.raises(ReleaseASeedRegistryError, match="Duplicate seed registry rows"):
        _build([row, deepcopy(row)], manifest)


def test_seed_registry_digest_rejects_invalid_registry() -> None:
    row = _row()
    registry = _build([row], _manifest([row]))
    registry["metadata"]["row_count"] = 2
    with pytest.raises(ReleaseASeedRegistryError, match="row_count"):
        seed_registry_sha256(registry)


def test_evidence_index_is_order_invariant_and_unknown_refs_fail_closed() -> None:
    row = _row()
    manifest = _manifest([row])

    assert seed_evidence_index_sha256(["OBS-B", "OBS-A"], ["AST-B", "AST-A"]) == seed_evidence_index_sha256(
        ["OBS-A", "OBS-B"], ["AST-A", "AST-B"]
    )

    with pytest.raises(ReleaseASeedRegistryError, match="Evidence index digest"):
        _build(
            [row],
            manifest,
            known_observation_ids={"OBS-PRODUCT-001", "OBS-EXTRA"},
            known_assertion_ids={"AST-PRODUCT-001"},
        )

    bad_observation_manifest = deepcopy(manifest)
    bad_observation_manifest["evidence_index_sha256"] = seed_evidence_index_sha256(
        {"OBS-OTHER"},
        {"AST-PRODUCT-001"},
    )
    bad_observation_manifest["manifest_id"] = seed_input_manifest_id(bad_observation_manifest)
    with pytest.raises(ReleaseASeedRegistryError, match="unknown source observations"):
        _build(
            [row],
            bad_observation_manifest,
            known_observation_ids={"OBS-OTHER"},
            known_assertion_ids={"AST-PRODUCT-001"},
        )

    bad_assertion_manifest = deepcopy(manifest)
    bad_assertion_manifest["evidence_index_sha256"] = seed_evidence_index_sha256(
        {"OBS-PRODUCT-001"},
        {"AST-OTHER"},
    )
    bad_assertion_manifest["manifest_id"] = seed_input_manifest_id(bad_assertion_manifest)
    with pytest.raises(ReleaseASeedRegistryError, match="unknown product assertions"):
        _build(
            [row],
            bad_assertion_manifest,
            known_observation_ids={"OBS-PRODUCT-001"},
            known_assertion_ids={"AST-OTHER"},
        )
