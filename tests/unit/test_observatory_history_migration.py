from __future__ import annotations

import pytest

from neuroai_workbench.observatory_history_migration import (
    HISTORY_MIGRATION_BOUNDARY,
    IDENTITY_RESOLUTION_STATE,
    REGIONAL_EXPANSION_STATE,
    ObservatoryHistoryMigrationError,
    preserve_v14_organization_resolution_history,
    preserve_v14_regional_expansion_history,
    verify_preserved_history_record,
)


def _org(org_id: str = "ORG-1", *, name: str = "Example Org", verification: str = "CURRENT_VERIFIED") -> dict:
    return {
        "organization_id": org_id,
        "canonical_name": name,
        "verification_state": verification,
    }


def _resolution() -> dict:
    return {
        "resolution_id": "RES-1",
        "organization_id": "ORG-1",
        "name_before": "Example Org",
        "verification_before": "CURRENT_PARTIAL",
        "disposition": "CURRENT_VERIFIED",
        "verification_after": "CURRENT_VERIFIED",
        "source_ids": ["SRC-1"],
        "rationale": "Current identity verified within bounded source universe.",
        "effective_date": "2026-07-29",
    }


def _regional() -> dict:
    return {
        "regional_record_id": "REG-1",
        "organization_id": "ORG-1",
        "canonical_name": "Example Org",
        "unesco_region": "Africa",
        "country_or_scope": "Africa",
        "action": "ADD",
        "inclusion_rule": "Official source in frozen expansion universe.",
        "verification_state": "CURRENT_VERIFIED",
        "source_ids": ["SRC-1"],
        "claim_boundary": "Acquisition coverage only.",
    }


def test_resolution_history_preserves_after_state_and_exact_record() -> None:
    result = preserve_v14_organization_resolution_history(
        {"organization_resolution": [_resolution()]},
        organization_records={"ORG-1": _org()},
        known_source_ids={"SRC-1"},
    )
    assert result["state"] == "NONCANONICAL_CANDIDATE"
    assert result["release_authorized"] is False
    assert result["native_object_count"] == 0
    assert result["preserved_record_count"] == 1
    record = result["records"][0]
    assert record["migration_state"] == IDENTITY_RESOLUTION_STATE
    assert record["effective_at"]["precision"] == "DATE"
    assert record["predecessor_record"] == _resolution()
    assert record["boundary"] == HISTORY_MIGRATION_BOUNDARY
    assert verify_preserved_history_record(record) == []


def test_resolution_history_rejects_after_state_rewrite_or_missing_source() -> None:
    bad = _resolution()
    bad["verification_after"] = "CURRENT_PARTIAL"
    with pytest.raises(ObservatoryHistoryMigrationError, match="verification_after"):
        preserve_v14_organization_resolution_history(
            {"organization_resolution": [bad]},
            organization_records={"ORG-1": _org()},
            known_source_ids={"SRC-1"},
        )
    with pytest.raises(ObservatoryHistoryMigrationError, match="missing Sources"):
        preserve_v14_organization_resolution_history(
            {"organization_resolution": [_resolution()]},
            organization_records={"ORG-1": _org()},
            known_source_ids=set(),
        )


def test_resolution_history_allows_explicitly_source_unresolved_predecessor_record() -> None:
    record = _resolution()
    record["source_ids"] = []
    record["disposition"] = "HISTORICAL_ARCHIVED"
    record["verification_after"] = "HISTORICAL_ARCHIVED"
    result = preserve_v14_organization_resolution_history(
        {"organization_resolution": [record]},
        organization_records={"ORG-1": _org(verification="HISTORICAL_ARCHIVED")},
        known_source_ids=set(),
    )
    assert result["records"][0]["source_ids"] == []


def test_regional_history_preserves_contemporaneous_verification_state() -> None:
    result = preserve_v14_regional_expansion_history(
        {"regional_expansion": [_regional()]},
        organization_records={"ORG-1": _org(verification="CURRENT_VERIFIED_CORRECTED")},
        materialized_entity_ids={"ORG-1"},
        known_source_ids={"SRC-1"},
    )
    record = result["records"][0]
    assert record["migration_state"] == REGIONAL_EXPANSION_STATE
    assert record["contemporaneous_verification_state"] == "CURRENT_VERIFIED"
    assert record["predecessor_record"]["verification_state"] == "CURRENT_VERIFIED"
    assert verify_preserved_history_record(record) == []


def test_regional_history_requires_identity_safe_entity_and_exact_name() -> None:
    with pytest.raises(ObservatoryHistoryMigrationError, match="not an identity-safe materialized Entity"):
        preserve_v14_regional_expansion_history(
            {"regional_expansion": [_regional()]},
            organization_records={"ORG-1": _org()},
            materialized_entity_ids=set(),
            known_source_ids={"SRC-1"},
        )
    bad = _regional()
    bad["canonical_name"] = "Substituted"
    with pytest.raises(ObservatoryHistoryMigrationError, match="canonical_name"):
        preserve_v14_regional_expansion_history(
            {"regional_expansion": [bad]},
            organization_records={"ORG-1": _org()},
            materialized_entity_ids={"ORG-1"},
            known_source_ids={"SRC-1"},
        )


def test_unknown_history_field_fails_closed() -> None:
    record = _resolution()
    record["unexpected"] = True
    with pytest.raises(ObservatoryHistoryMigrationError, match="shape mismatch"):
        preserve_v14_organization_resolution_history(
            {"organization_resolution": [record]},
            organization_records={"ORG-1": _org()},
            known_source_ids={"SRC-1"},
        )


def test_history_verifier_detects_payload_tampering_and_authority_upgrade() -> None:
    result = preserve_v14_regional_expansion_history(
        {"regional_expansion": [_regional()]},
        organization_records={"ORG-1": _org()},
        materialized_entity_ids={"ORG-1"},
        known_source_ids={"SRC-1"},
    )
    record = result["records"][0]
    record["predecessor_record"]["action"] = "REVERIFY"
    assert "predecessor_record_sha256 mismatch" in verify_preserved_history_record(record)
    record["native_authority"] = True
    assert "native_authority must remain false" in verify_preserved_history_record(record)
