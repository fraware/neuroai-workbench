from __future__ import annotations

import json

import pytest

from neuroai_workbench.observatory_entity_migration import (
    ENTITY_MIGRATION_BOUNDARY,
    HISTORICAL_CURRENT_IDENTITY_UNRESOLVED,
    LEGACY_IDENTITY_UNRESOLVED,
    MATERIALIZE_ACTIVE_ENTITY,
    NATIVE_ENTITY_TYPE,
    PROVENANCE_ONLY_NODE,
    ObservatoryEntityMigrationError,
    classify_predecessor_organization,
    materialize_predecessor_organization,
    materialize_predecessor_organizations,
    verify_materialized_organization,
    verify_organization_migration_record,
    verify_organization_partition,
    write_predecessor_entity_package,
)
from neuroai_workbench.util import canonical_json_bytes, sha256_bytes


def _active(org_id: str = "ORG-1") -> dict:
    return {
        "organization_id": org_id,
        "canonical_name": "Example Organization",
        "aliases": ["Example Org"],
        "organization_type": "COMPANY",
        "roles": ["SYSTEM_DEVELOPER"],
        "current_status": "CURRENT",
        "verification_state": "CURRENT_VERIFIED",
        "evidence_state": "OFFICIAL_CURRENT_REPRESENTATION",
        "official_url": "https://example.test/",
        "source_ids": ["SRC-1"],
        "last_verified": "2026-07-29",
        "claim_boundary": "Presence only.",
    }


def _legacy(org_id: str = "ORG-LEGACY") -> dict:
    return {
        "organization_id": org_id,
        "canonical_name": "Legacy endpoint",
        "aliases": [],
        "organization_type": "LEGACY_STUB",
        "roles": ["LEGACY_RELATIONSHIP_ENDPOINT"],
        "current_status": "ACTIVE_OR_CURRENTLY_REPRESENTED",
        "verification_state": "LEGACY_ONLY",
        "evidence_state": "LEGACY_UNVERIFIED",
        "source_ids": [],
        "last_verified": None,
    }


def _provenance(org_id: str = "ORG-PROV") -> dict:
    return {
        "organization_id": org_id,
        "canonical_name": "Author collective",
        "aliases": [],
        "organization_type": "RESEARCH_CONSORTIUM",
        "current_status": "RECLASSIFIED",
        "verification_state": "NON_ORGANIZATION_PROVENANCE_NODE",
        "source_ids": [],
        "last_verified": None,
    }


def _historical(org_id: str = "ORG-HIST") -> dict:
    return {
        "organization_id": org_id,
        "canonical_name": "Historical initiative",
        "aliases": [],
        "organization_type": "NATIONAL_OR_INTERNATIONAL_INITIATIVE",
        "current_status": "HISTORICAL_ARCHIVED",
        "verification_state": "HISTORICAL_ARCHIVED",
        "source_ids": ["SRC-H"],
        "last_verified": "2026-07-29",
    }


def test_exact_identity_state_partition() -> None:
    assert classify_predecessor_organization(_active()) == MATERIALIZE_ACTIVE_ENTITY
    assert classify_predecessor_organization(_legacy()) == LEGACY_IDENTITY_UNRESOLVED
    assert classify_predecessor_organization(_provenance()) == PROVENANCE_ONLY_NODE
    assert classify_predecessor_organization(_historical()) == HISTORICAL_CURRENT_IDENTITY_UNRESOLVED


def test_inconsistent_special_states_fail_closed() -> None:
    broken = _legacy()
    broken["organization_type"] = "COMPANY"
    with pytest.raises(ObservatoryEntityMigrationError, match="both LEGACY_ONLY and LEGACY_STUB"):
        classify_predecessor_organization(broken)

    broken = _provenance()
    broken["current_status"] = "CURRENT"
    with pytest.raises(ObservatoryEntityMigrationError, match="both NON_ORGANIZATION_PROVENANCE_NODE and RECLASSIFIED"):
        classify_predecessor_organization(broken)


def test_unreviewed_identity_state_fails_closed() -> None:
    record = _active()
    record["verification_state"] = "NEW_UNREVIEWED_STATE"
    with pytest.raises(ObservatoryEntityMigrationError, match="Unreviewed predecessor organization identity state"):
        classify_predecessor_organization(record)


def test_active_entity_materialization_uses_v2_organization_type_not_predecessor_subtype() -> None:
    predecessor = _active("ORG-EXACT")
    entity, trace = materialize_predecessor_organization(predecessor, record_index=4)

    assert entity["entity_id"] == "ORG-EXACT"
    assert entity["canonical_label"] == predecessor["canonical_name"]
    assert entity["entity_type"] == NATIVE_ENTITY_TYPE == "ORGANIZATION"
    assert entity["entity_type"] != predecessor["organization_type"]
    assert entity["aliases"] == predecessor["aliases"]
    assert entity["status"] == "ACTIVE"
    assert entity["identifiers"] == []
    assert entity["boundary"] == ENTITY_MIGRATION_BOUNDARY
    assert trace["predecessor_record"] == predecessor
    assert trace["native_object_class"] == "Entity"
    assert trace["migration_generated_fields"]["entity_type"] == "ORGANIZATION"
    assert verify_organization_migration_record(trace, expected_native_object_id="ORG-EXACT") == []
    assert verify_materialized_organization(entity, trace) == []


def test_native_entity_verifier_detects_coordinated_field_tampering() -> None:
    entity, trace = materialize_predecessor_organization(_active("ORG-A"), record_index=0)
    entity["canonical_label"] = "Substituted"
    assert "Entity.canonical_label binding mismatch" in verify_materialized_organization(entity, trace)

    entity, trace = materialize_predecessor_organization(_active("ORG-A"), record_index=0)
    entity["entity_type"] = "COMPANY"
    assert "Entity.entity_type must be ORGANIZATION under v2 ontology" in verify_materialized_organization(
        entity, trace
    )


def test_non_native_states_cannot_be_materialized() -> None:
    for record in (_legacy(), _provenance(), _historical()):
        with pytest.raises(ObservatoryEntityMigrationError, match="not eligible for native Entity materialization"):
            materialize_predecessor_organization(record, record_index=0)


def test_complete_partition_contains_every_input_exactly_once() -> None:
    release = {"organizations": [_active("ORG-A"), _legacy(), _provenance(), _historical()]}
    result = materialize_predecessor_organizations(release)

    assert result["state"] == "NONCANONICAL_CANDIDATE"
    assert result["release_authorized"] is False
    assert result["input_record_count"] == 4
    assert result["object_count"] == 1
    assert result["preserved_record_count"] == 3
    assert result["classification_counts"] == {
        HISTORICAL_CURRENT_IDENTITY_UNRESOLVED: 1,
        LEGACY_IDENTITY_UNRESOLVED: 1,
        MATERIALIZE_ACTIVE_ENTITY: 1,
        PROVENANCE_ONLY_NODE: 1,
    }
    assert result["migration_generated_metadata"]["native_entity_type"] == "ORGANIZATION"
    assert verify_organization_partition(result)["valid"] is True


def test_partition_verifier_detects_missing_and_tampered_records() -> None:
    result = materialize_predecessor_organizations(
        {"organizations": [_active("ORG-A"), _legacy(), _provenance()]}
    )
    result["preserved_predecessor_records"].pop()
    report = verify_organization_partition(result)
    assert report["valid"] is False
    assert any("cover every input record" in error or "do not equal input count" in error for error in report["errors"])

    result = materialize_predecessor_organizations({"organizations": [_active("ORG-A"), _legacy()]})
    result["predecessor_traces"][0]["predecessor_record"]["canonical_name"] = "Substituted"
    report = verify_organization_partition(result)
    assert report["valid"] is False
    assert "predecessor_record_sha256 mismatch" in report["errors"]


def test_duplicate_materialized_entity_ids_fail_closed() -> None:
    with pytest.raises(ObservatoryEntityMigrationError, match="Duplicate materialized entity id ORG-DUP"):
        materialize_predecessor_organizations(
            {"organizations": [_active("ORG-DUP"), _active("ORG-DUP")]}
        )


def test_entity_package_is_deterministic_and_manifest_bound(tmp_path) -> None:
    result = materialize_predecessor_organizations(
        {"organizations": [_active("ORG-A"), _legacy(), _provenance(), _historical()]}
    )
    first = write_predecessor_entity_package(
        result,
        tmp_path / "first",
        v14_input_sha256="a" * 64,
        producer_commit="b" * 40,
        runtime_execution_pin="c" * 40,
        s2_predecessor_commit="d" * 40,
    )
    second = write_predecessor_entity_package(
        result,
        tmp_path / "second",
        v14_input_sha256="a" * 64,
        producer_commit="b" * 40,
        runtime_execution_pin="c" * 40,
        s2_predecessor_commit="d" * 40,
    )

    assert first == second
    for filename in (
        "entities.jsonl",
        "predecessor-traces.jsonl",
        "preserved-organizations.jsonl",
        "descriptor.json",
        "manifest.json",
    ):
        assert (tmp_path / "first" / filename).read_bytes() == (tmp_path / "second" / filename).read_bytes()

    manifest = json.loads((tmp_path / "first" / "manifest.json").read_text(encoding="utf-8"))
    controlled = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    assert manifest["manifest_sha256"] == sha256_bytes(canonical_json_bytes(controlled))
    assert manifest["release_authorized"] is False


def test_package_refuses_invalid_identity_binding(tmp_path) -> None:
    result = materialize_predecessor_organizations({"organizations": [_active("ORG-A")]})
    with pytest.raises(ObservatoryEntityMigrationError, match="producer_commit"):
        write_predecessor_entity_package(
            result,
            tmp_path / "bad",
            v14_input_sha256="a" * 64,
            producer_commit="not-a-sha",
            runtime_execution_pin="c" * 40,
            s2_predecessor_commit="d" * 40,
        )
