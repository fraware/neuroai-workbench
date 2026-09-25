from __future__ import annotations

from copy import deepcopy

import pytest

import neuroai_workbench.release_a_seed_registry as seed_module
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
    load_default_seed_artifacts,
    product_identity_registry_sha256,
    seed_evidence_index_sha256,
    seed_evidence_packet_sha256,
    seed_input_manifest_id,
    seed_registry_sha256,
    validate_product_identity_registry,
    validate_seed_identity_binding,
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
        ({"projected_assertion_refs": []}, "projected_assertion_refs"),
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
    with pytest.raises(ReleaseASeedRegistryError, match="source_observation_refs"):
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
        _build(
            [other],
            manifest,
            known_observation_ids={"OBS-PRODUCT-001"},
            known_assertion_ids={"AST-PRODUCT-001"},
        )


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


def test_materialized_a1_seed_artifacts_are_cross_bound_and_reproducible() -> None:
    artifacts = load_default_seed_artifacts()
    assert artifacts["manifest"]["seed_input_count"] == 6
    assert artifacts["registry"]["metadata"]["row_count"] == 6
    assert artifacts["packet_sha256"] == "ec04294c78dffbefa6b95a076b663df5a07d6b75a660d04b9d56598f4fc3c67f"
    assert artifacts["evidence_index_sha256"] == "6de1ece87016b74c859611e91cb3974bd55fbcd28f1b36a128582dffaf45fe60"
    assert artifacts["registry_sha256"] == "9ba43d5614fb1ebb668c097a20c2279dbaaa74511956c16ee6f278cbfc109672"
    assert artifacts["identity_registry_sha256"] == "65023d77ca9187ef068a40366c919e858149054764d06a7146e2282768e0fadc"
    assert artifacts["identity_binding_id"] == "RAIB-3d4fd6550011d5dd06368369479c1ee4f64eff88142af95b4b41258bfa8adc04"
    assert artifacts["identity_registry"]["record_count"] == 6
    assert all(observation["content_bytes_archived"] is False for observation in artifacts["packet"]["observations"])


def test_seed_evidence_packet_digest_is_order_and_content_sensitive() -> None:
    artifacts = load_default_seed_artifacts()
    packet = artifacts["packet"]
    assert seed_evidence_packet_sha256(packet) == artifacts["packet_sha256"]

    changed = deepcopy(packet)
    changed["observations"][0]["bounded_observation"] += " changed"
    assert seed_evidence_packet_sha256(changed) != artifacts["packet_sha256"]


def _patched_default_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    monkeypatch.undo()
    artifacts = load_default_seed_artifacts()
    packet = deepcopy(artifacts["packet"])
    manifest = deepcopy(artifacts["manifest"])
    registry = deepcopy(artifacts["registry"])
    identity_registry = deepcopy(artifacts["identity_registry"])
    identity_binding = deepcopy(artifacts["identity_binding"])

    def fake_resource_json(name: str) -> dict[str, object]:
        if name == seed_module.SEED_EVIDENCE_PACKET_RESOURCE:
            return packet
        if name == seed_module.SEED_INPUT_MANIFEST_RESOURCE:
            return manifest
        if name == seed_module.SEED_PRODUCT_REGISTRY_RESOURCE:
            return registry
        if name == seed_module.PRODUCT_IDENTITY_REGISTRY_RESOURCE:
            return identity_registry
        if name == seed_module.SEED_IDENTITY_BINDING_RESOURCE:
            return identity_binding
        raise AssertionError(f"unexpected resource {name}")

    monkeypatch.setattr(seed_module, "_resource_json", fake_resource_json)
    return packet, manifest, registry


def _rebind_packet_digest(packet: dict[str, object], manifest: dict[str, object]) -> None:
    manifest["controlled_packet_digests"] = [seed_evidence_packet_sha256(packet)]
    manifest["manifest_id"] = seed_input_manifest_id(manifest)


def test_default_seed_loader_rejects_unbound_packet_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    _, manifest, _ = _patched_default_artifacts(monkeypatch)
    manifest["controlled_packet_digests"] = ["0" * 64]
    manifest["manifest_id"] = seed_input_manifest_id(manifest)

    with pytest.raises(ReleaseASeedRegistryError, match="packet digest"):
        load_default_seed_artifacts()


def test_default_seed_loader_rejects_malformed_or_duplicate_evidence_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet, manifest, _ = _patched_default_artifacts(monkeypatch)
    packet["assertions"] = None
    _rebind_packet_digest(packet, manifest)
    with pytest.raises(ReleaseASeedRegistryError, match="observation and assertion lists"):
        load_default_seed_artifacts()

    packet, manifest, _ = _patched_default_artifacts(monkeypatch)
    packet["observations"][1]["observation_id"] = packet["observations"][0]["observation_id"]
    _rebind_packet_digest(packet, manifest)
    with pytest.raises(ReleaseASeedRegistryError, match="missing or duplicate observation IDs"):
        load_default_seed_artifacts()


def test_default_seed_loader_rejects_evidence_index_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    packet, manifest, _ = _patched_default_artifacts(monkeypatch)
    previous_id = packet["observations"][0]["observation_id"]
    packet["observations"][0]["observation_id"] = "OBS-A1-CHANGED"
    for assertion in packet["assertions"]:
        assertion["source_observation_refs"] = [
            "OBS-A1-CHANGED" if ref == previous_id else ref for ref in assertion["source_observation_refs"]
        ]
    _rebind_packet_digest(packet, manifest)

    with pytest.raises(ReleaseASeedRegistryError, match="evidence identity index"):
        load_default_seed_artifacts()


def test_default_seed_loader_wraps_registry_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, registry = _patched_default_artifacts(monkeypatch)
    registry["metadata"]["row_count"] = 7

    with pytest.raises(ReleaseASeedRegistryError, match="row_count"):
        load_default_seed_artifacts()


def test_default_seed_loader_rejects_materialized_registry_order_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, registry = _patched_default_artifacts(monkeypatch)
    registry["rows"] = list(reversed(registry["rows"]))

    with pytest.raises(ReleaseASeedRegistryError, match="does not match deterministic compiler output"):
        load_default_seed_artifacts()


def test_default_seed_loader_rejects_evidence_graph_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    packet, manifest, _ = _patched_default_artifacts(monkeypatch)
    packet["assertions"][0]["canonical_entity_id"] = "PRD-WRONG"
    _rebind_packet_digest(packet, manifest)
    with pytest.raises(ReleaseASeedRegistryError, match="canonical entity"):
        load_default_seed_artifacts()

    packet, manifest, _ = _patched_default_artifacts(monkeypatch)
    packet["observations"][0]["exact_product_label"] = "Wrong product"
    _rebind_packet_digest(packet, manifest)
    with pytest.raises(ReleaseASeedRegistryError, match="exact product label"):
        load_default_seed_artifacts()

    packet, manifest, _ = _patched_default_artifacts(monkeypatch)
    packet["assertions"][0]["source_observation_refs"] = [packet["observations"][1]["observation_id"]]
    _rebind_packet_digest(packet, manifest)
    with pytest.raises(ReleaseASeedRegistryError, match="does not bind every source observation"):
        load_default_seed_artifacts()


def test_default_seed_loader_rejects_unknown_assertion_source_and_cutoff_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet, manifest, _ = _patched_default_artifacts(monkeypatch)
    packet["assertions"][0]["source_observation_refs"] = ["OBS-UNKNOWN"]
    _rebind_packet_digest(packet, manifest)
    with pytest.raises(ReleaseASeedRegistryError, match="unknown source observations"):
        load_default_seed_artifacts()

    packet, manifest, _ = _patched_default_artifacts(monkeypatch)
    packet["knowledge_time_cutoff"] = "2026-09-24T20:59:59Z"
    _rebind_packet_digest(packet, manifest)
    with pytest.raises(ReleaseASeedRegistryError, match="knowledge cutoff"):
        load_default_seed_artifacts()


def test_default_seed_loader_binds_attributable_observation_chronology(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet, manifest, registry = _patched_default_artifacts(monkeypatch)
    assert all(
        observation["observation_registered_at"] == "2026-09-24T17:23:06Z" for observation in packet["observations"]
    )
    assert all(row["first_observed_at"] == "2026-09-24T17:23:06Z" for row in registry["rows"])
    assert all(row["last_observed_at"] == "2026-09-24T17:23:06Z" for row in registry["rows"])

    packet["observations"][0]["observation_registered_at"] = "2026-09-24T21:00:01Z"
    _rebind_packet_digest(packet, manifest)
    with pytest.raises(ReleaseASeedRegistryError, match="cannot exceed"):
        load_default_seed_artifacts()


def test_default_seed_loader_rejects_fabricated_registry_observation_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, registry = _patched_default_artifacts(monkeypatch)
    registry["rows"][0]["first_observed_at"] = "2026-09-24T21:00:00Z"
    registry["rows"][0]["last_observed_at"] = "2026-09-24T21:00:00Z"

    with pytest.raises(ReleaseASeedRegistryError, match="observation chronology"):
        load_default_seed_artifacts()


def test_product_identity_registry_is_separate_from_projection_and_exactly_bound() -> None:
    artifacts = load_default_seed_artifacts()
    identity_registry = artifacts["identity_registry"]
    validate_product_identity_registry(identity_registry)
    assert product_identity_registry_sha256(identity_registry) == artifacts["identity_registry_sha256"]

    identity_ids = {record["entity"]["entity_id"] for record in identity_registry["records"]}
    row_ids = {row["canonical_entity_id"] for row in artifacts["registry"]["rows"]}
    assert identity_ids == row_ids
    assert all(record["entity"]["entity_type"] == "PRODUCT" for record in identity_registry["records"])
    assert all(record["product_identity_level"] == "OFFERING" for record in identity_registry["records"])


def test_seed_identity_authority_fails_closed_on_missing_or_drifted_entity() -> None:
    artifacts = load_default_seed_artifacts()
    identity_registry = deepcopy(artifacts["identity_registry"])
    identity_binding = deepcopy(artifacts["identity_binding"])

    identity_registry["records"][0]["entity"]["canonical_label"] = "Wrong offering"
    identity_binding["identity_registry_sha256"] = product_identity_registry_sha256(identity_registry)
    identity_binding["binding_id"] = seed_module.seed_identity_binding_id(identity_binding)
    with pytest.raises(ReleaseASeedRegistryError, match="label"):
        validate_seed_identity_binding(
            identity_binding,
            manifest=artifacts["manifest"],
            registry=artifacts["registry"],
            identity_registry=identity_registry,
        )

    identity_registry = deepcopy(artifacts["identity_registry"])
    identity_registry["records"] = identity_registry["records"][1:]
    identity_registry["record_count"] = 5
    with pytest.raises(ReleaseASeedRegistryError, match="digest mismatch|cover exactly"):
        validate_seed_identity_binding(
            identity_binding,
            manifest=artifacts["manifest"],
            registry=artifacts["registry"],
            identity_registry=identity_registry,
        )


def test_seed_identity_authority_fails_closed_on_projection_evidence_mismatch() -> None:
    artifacts = load_default_seed_artifacts()
    identity_registry = deepcopy(artifacts["identity_registry"])
    identity_binding = deepcopy(artifacts["identity_binding"])

    identity_registry["records"][0]["source_observation_refs"] = ["OBS-A1-WRONG"]
    identity_binding["identity_registry_sha256"] = product_identity_registry_sha256(identity_registry)
    identity_binding["binding_id"] = seed_module.seed_identity_binding_id(identity_binding)
    with pytest.raises(ReleaseASeedRegistryError, match="evidence does not match"):
        validate_seed_identity_binding(
            identity_binding,
            manifest=artifacts["manifest"],
            registry=artifacts["registry"],
            identity_registry=identity_registry,
        )


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("registry_id", "registry_id"),
        ("version", "frozen v1.0"),
        ("identity_unit", "PRODUCT/OFFERING"),
        ("boundary", "identity boundary"),
        ("empty_records", "non-empty list"),
        ("record_count", "record_count"),
        ("record_not_object", "records must be objects"),
        ("missing_entity", "requires an Entity object"),
        ("schema_error", "schema validation failed"),
        ("wrong_product_type", "PRODUCT entities"),
        ("inactive_entity", "must be ACTIVE"),
        ("entity_boundary", "Entity boundary"),
        ("duplicate_entity", "Duplicate canonical product"),
        ("wrong_identity_level", "OFFERING level"),
        ("missing_source_refs", "source_observation_refs"),
        ("duplicate_row_binding", "unique seed_registry_row_id"),
    ],
)
def test_product_identity_registry_validator_fails_closed(case: str, message: str) -> None:
    registry = deepcopy(load_default_seed_artifacts()["identity_registry"])

    if case == "registry_id":
        registry["registry_id"] = "OTHER"
    elif case == "version":
        registry["version"] = "2.0"
    elif case == "identity_unit":
        registry["identity_unit"] = "PRODUCT"
    elif case == "boundary":
        registry["boundary"] = "weaker boundary"
    elif case == "empty_records":
        registry["records"] = []
        registry["record_count"] = 0
    elif case == "record_count":
        registry["record_count"] = 7
    elif case == "record_not_object":
        registry["records"][0] = "not-an-object"
    elif case == "missing_entity":
        registry["records"][0].pop("entity")
    elif case == "schema_error":
        registry["records"][0]["entity"]["object_class"] = "Wrong"
    elif case == "wrong_product_type":
        registry["records"][0]["entity"]["entity_type"] = "SYSTEM"
    elif case == "inactive_entity":
        registry["records"][0]["entity"]["status"] = "SUPERSEDED"
    elif case == "entity_boundary":
        registry["records"][0]["entity"]["boundary"] = "weaker boundary"
    elif case == "duplicate_entity":
        registry["records"][1]["entity"]["entity_id"] = registry["records"][0]["entity"]["entity_id"]
    elif case == "wrong_identity_level":
        registry["records"][0]["product_identity_level"] = "FAMILY"
    elif case == "missing_source_refs":
        registry["records"][0]["source_observation_refs"] = []
    elif case == "duplicate_row_binding":
        registry["records"][1]["seed_registry_row_id"] = registry["records"][0]["seed_registry_row_id"]
    else:
        raise AssertionError(f"unhandled case {case}")

    with pytest.raises(ReleaseASeedRegistryError, match=message):
        validate_product_identity_registry(registry)


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("invalid_seed_registry", "row_count"),
        ("binding_version", "binding_version"),
        ("binding_status", "FROZEN_v1.0"),
        ("binding_boundary", "binding boundary"),
        ("binding_id", "binding_id"),
        ("seed_manifest_id", "seed manifest"),
        ("seed_registry_digest", "seed registry digest"),
        ("identity_registry_id", "product identity registry"),
        ("identity_registry_digest", "identity registry digest mismatch"),
        ("declared_entity_set", "cover exactly"),
        ("row_binding", "exact A1 seed registry row"),
    ],
)
def test_seed_identity_binding_validator_fails_closed(case: str, message: str) -> None:
    artifacts = load_default_seed_artifacts()
    manifest = deepcopy(artifacts["manifest"])
    registry = deepcopy(artifacts["registry"])
    identity_registry = deepcopy(artifacts["identity_registry"])
    binding = deepcopy(artifacts["identity_binding"])

    if case == "invalid_seed_registry":
        registry["metadata"]["row_count"] = 7
    elif case == "binding_version":
        binding["binding_version"] = "OTHER"
    elif case == "binding_status":
        binding["status"] = "DRAFT"
    elif case == "binding_boundary":
        binding["boundary"] = "weaker boundary"
    elif case == "binding_id":
        binding["binding_id"] = "RAIB-" + "0" * 64
    elif case == "seed_manifest_id":
        binding["seed_manifest_id"] = "OTHER"
        binding["binding_id"] = seed_module.seed_identity_binding_id(binding)
    elif case == "seed_registry_digest":
        binding["seed_registry_sha256"] = "0" * 64
        binding["binding_id"] = seed_module.seed_identity_binding_id(binding)
    elif case == "identity_registry_id":
        binding["identity_registry_id"] = "OTHER"
        binding["binding_id"] = seed_module.seed_identity_binding_id(binding)
    elif case == "identity_registry_digest":
        binding["identity_registry_sha256"] = "0" * 64
        binding["binding_id"] = seed_module.seed_identity_binding_id(binding)
    elif case == "declared_entity_set":
        binding["entity_ids"] = binding["entity_ids"][1:]
        binding["binding_id"] = seed_module.seed_identity_binding_id(binding)
    elif case == "row_binding":
        identity_registry["records"][0]["seed_registry_row_id"] = "PRR-" + "0" * 64
        binding["identity_registry_sha256"] = product_identity_registry_sha256(identity_registry)
        binding["binding_id"] = seed_module.seed_identity_binding_id(binding)
    else:
        raise AssertionError(f"unhandled case {case}")

    with pytest.raises(ReleaseASeedRegistryError, match=message):
        validate_seed_identity_binding(
            binding,
            manifest=manifest,
            registry=registry,
            identity_registry=identity_registry,
        )
