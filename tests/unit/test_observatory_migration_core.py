from __future__ import annotations

import json

import pytest

from neuroai_workbench.observatory_migration_core import (
    CORE_MIGRATION_BOUNDARY,
    ObservatoryMigrationCoreError,
    build_predecessor_migration_core,
    verify_predecessor_migration_core,
    write_predecessor_migration_core_package,
)
from neuroai_workbench.util import canonical_json_bytes, sha256_bytes


def _organization(org_id: str = "ORG-1") -> dict:
    return {
        "organization_id": org_id,
        "canonical_name": "Example Organization",
        "aliases": [],
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


def _legacy() -> dict:
    return {
        "organization_id": "ORG-LEGACY",
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


def _source(source_id: str = "SRC-1") -> dict:
    return {
        "source_id": source_id,
        "title": "Official source",
        "publisher": "Publisher",
        "url": f"https://example.test/{source_id}",
        "source_class": "OFFICIAL_PAGE",
        "retrieved": "2026-07-29",
        "verification_state": "CURRENT_VERIFIED",
        "evidence_state": "CURRENT_SOURCE_RETRIEVED",
        "supports": "Bounded source statement",
        "claim_boundary": "Retrieval is not substantive truth.",
        "legacy_source_ids": [],
    }


def _new_source(source_id: str = "SRC-16-1") -> dict:
    return {
        "source_id": source_id,
        "title": "Announcement",
        "publisher": "Publisher",
        "url": f"https://example.test/{source_id}",
        "published": "2026-07-22",
        "retrieved": "2026-07-29T12:38:00Z",
        "source_class": "OFFICIAL_COMPANY_ANNOUNCEMENT",
        "evidence_state": "COMPANY_ANNOUNCEMENT",
        "supports": "Bounded source statement",
        "claim_boundary": "No broader inference.",
    }


def _check(source_id: str = "SRC-16-1") -> dict:
    return {
        "check_id": "CHK-1",
        "source_id": source_id,
        "retrieved": "2026-07-29T12:38:00Z",
        "retrieval_outcome": "SUCCESS_VIA_WEB_RESEARCH",
        "baseline_match": "NEW_SOURCE_OR_BACKFILL",
        "page_content_hash": "NOT_AVAILABLE_FROM_WEB_RESEARCH_INTERFACE",
        "metadata_digest": "a" * 64,
    }


def _inputs() -> tuple[dict, dict]:
    v14 = {
        "organizations": [_organization(), _legacy()],
        "sources": [_source()],
    }
    v16 = {
        "new_sources": [_new_source()],
        "source_checks": [_check()],
    }
    return v14, v16


def test_core_reconciles_native_and_preserved_state_without_overclaiming() -> None:
    v14, v16 = _inputs()
    result = build_predecessor_migration_core(v14_release=v14, v16_refresh=v16)

    assert result["mechanical_verification"] == "PASS"
    assert result["state"] == "NONCANONICAL_CANDIDATE"
    assert result["release_authorized"] is False
    assert result["native_v2_materialization_complete"] is False
    assert result["counts"] == {
        "input_v14_organization_records": 2,
        "native_entities": 1,
        "preserved_organization_records": 1,
        "native_sources": 2,
        "predecessor_observation_evidence_records": 1,
        "native_observations": 0,
        "native_core_objects": 3,
    }
    assert {record["object_class"] for record in result["native_objects"]} == {"Entity", "Source"}
    assert result["remaining_unmaterialized_families"]
    assert result["boundaries"]["core"] == CORE_MIGRATION_BOUNDARY
    assert verify_predecessor_migration_core(result)["valid"] is True


def test_core_requires_source_binding_for_predecessor_observation_evidence() -> None:
    v14, v16 = _inputs()
    v16["source_checks"][0]["source_id"] = "SRC-MISSING"

    with pytest.raises(Exception, match="non-materialized Source SRC-MISSING"):
        build_predecessor_migration_core(v14_release=v14, v16_refresh=v16)


def test_core_verifier_detects_cross_slice_tampering() -> None:
    v14, v16 = _inputs()
    result = build_predecessor_migration_core(v14_release=v14, v16_refresh=v16)
    result["predecessor_observation_evidence"]["records"][0]["source_id"] = "SRC-SUBSTITUTED"

    report = verify_predecessor_migration_core(result)
    assert report["valid"] is False
    assert any("source_id binding mismatch" in error or "missing Source" in error for error in report["errors"])


def test_core_package_is_deterministic_and_manifest_bound(tmp_path) -> None:
    v14, v16 = _inputs()
    result = build_predecessor_migration_core(v14_release=v14, v16_refresh=v16)
    first = write_predecessor_migration_core_package(
        result,
        tmp_path / "first",
        v14_input_sha256="a" * 64,
        v16_input_sha256="b" * 64,
        producer_commit="c" * 40,
        runtime_execution_pin="d" * 40,
        s2_predecessor_commit="e" * 40,
    )
    second = write_predecessor_migration_core_package(
        result,
        tmp_path / "second",
        v14_input_sha256="a" * 64,
        v16_input_sha256="b" * 64,
        producer_commit="c" * 40,
        runtime_execution_pin="d" * 40,
        s2_predecessor_commit="e" * 40,
    )

    assert first == second
    filenames = (
        "entities.jsonl",
        "entity-predecessor-traces.jsonl",
        "preserved-organizations.jsonl",
        "sources.jsonl",
        "source-predecessor-traces.jsonl",
        "predecessor-observation-evidence.jsonl",
        "descriptor.json",
        "manifest.json",
    )
    for filename in filenames:
        assert (tmp_path / "first" / filename).read_bytes() == (tmp_path / "second" / filename).read_bytes()

    manifest = json.loads((tmp_path / "first" / "manifest.json").read_text(encoding="utf-8"))
    controlled = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    assert manifest["manifest_sha256"] == sha256_bytes(canonical_json_bytes(controlled))
    assert manifest["release_authorized"] is False
    assert manifest["native_v2_materialization_complete"] is False


def test_core_package_refuses_authority_or_completion_upgrade(tmp_path) -> None:
    v14, v16 = _inputs()
    result = build_predecessor_migration_core(v14_release=v14, v16_refresh=v16)
    result["release_authorized"] = True
    with pytest.raises(ObservatoryMigrationCoreError, match="invalid migration core"):
        write_predecessor_migration_core_package(
            result,
            tmp_path / "bad-authority",
            v14_input_sha256="a" * 64,
            v16_input_sha256="b" * 64,
            producer_commit="c" * 40,
            runtime_execution_pin="d" * 40,
            s2_predecessor_commit="e" * 40,
        )

    result = build_predecessor_migration_core(v14_release=v14, v16_refresh=v16)
    result["native_v2_materialization_complete"] = True
    with pytest.raises(ObservatoryMigrationCoreError, match="invalid migration core"):
        write_predecessor_migration_core_package(
            result,
            tmp_path / "bad-complete",
            v14_input_sha256="a" * 64,
            v16_input_sha256="b" * 64,
            producer_commit="c" * 40,
            runtime_execution_pin="d" * 40,
            s2_predecessor_commit="e" * 40,
        )
