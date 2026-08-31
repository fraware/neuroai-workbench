from __future__ import annotations

import copy

import pytest

from neuroai_workbench.observatory_residual_migration import (
    ObservatoryResidualMigrationError,
    preserve_residual_gate_a_state,
    verify_residual_gate_a_state,
)


def _source() -> dict:
    return {
        "source_id": "SRC-1",
        "title": "Source",
        "publisher": "Publisher",
        "url": "https://example.test/source",
        "source_class": "OFFICIAL_PAGE",
        "retrieved": "2026-07-29",
        "verification_state": "CURRENT_VERIFIED",
        "evidence_state": "CURRENT_SOURCE_RETRIEVED",
        "supports": "Bounded",
        "claim_boundary": "Bounded source",
        "legacy_source_ids": [],
    }


def _monitor() -> dict:
    return {
        "monitor_id": "MON-SRC-1",
        "source_id": "SRC-1",
        "url": "https://example.test/source",
        "publisher": "Publisher",
        "source_class": "OFFICIAL_PAGE",
        "cadence": "MONTHLY",
        "last_successful_retrieval": "2026-07-29",
        "baseline_evidence_state": "CURRENT_SOURCE_RETRIEVED",
        "baseline_verification_state": "CURRENT_VERIFIED",
        "baseline_claim_boundary": "Bounded source",
        "network_access_required": True,
        "current_status": "BASELINE_REGISTERED",
        "next_action": "RETRIEVE_AND_COMPARE",
    }


def _v14() -> dict:
    base = {
        "metadata": {"version": "v1.4"},
        "methodology": {"version": "v1.4"},
        "coverage": {"scope": "bounded"},
        "sources": [_source()],
    }
    for family in (
        "representative_model_records",
        "model_and_dataset_registry",
        "trial_site_relationships",
        "participant_authority_relationships",
        "supplier_dependency_relationships",
        "data_quality",
    ):
        base[family] = [{"record_id": family, "source_ids": ["SRC-1"]}] if family != "data_quality" else [{"finding_id": "DQ-1"}]
    return base


def _delta() -> dict:
    return {
        "regulatory_and_market_events": [{"event_id": "REG-1", "source_ids": ["SRC-1"]}],
        "capital_and_ownership_events": [{"event_id": "CAP-1", "source_ids": ["SRC-1"]}],
        "model_records": [{"model_id": "MDL-1", "source_ids": ["SRC-1"]}],
        "supplier_dependency_relationships": [{"dependency_id": "DEP-1", "source_ids": ["SRC-1"]}],
        "governance_and_leadership_events": [{"event_id": "GOV-1", "source_ids": ["SRC-1"]}],
    }


def test_residual_state_preserves_all_blocked_families_and_registry_identity() -> None:
    v14 = _v14()
    state = preserve_residual_gate_a_state(
        v14_release=v14,
        v16_refresh={"metadata": {}, "methodology": {}, "baseline": {}},
        delta16=_delta(),
        source_register14=copy.deepcopy(v14["sources"]),
        monitor15=[_monitor()],
        known_source_ids={"SRC-1"},
    )
    assert state["release_authorized"] is False
    assert state["native_object_count"] == 0
    assert state["counts"]["residual_family_count"] == 11
    assert state["source_register_proof"]["exact_duplicate"] is True
    assert state["monitor_registry"]["one_to_one_source_identity"] is True
    assert verify_residual_gate_a_state(state, known_source_ids={"SRC-1"}) == []


def test_residual_state_rejects_source_register_drift() -> None:
    v14 = _v14()
    register = copy.deepcopy(v14["sources"])
    register[0]["title"] = "Changed"
    with pytest.raises(ObservatoryResidualMigrationError, match="Source Register"):
        preserve_residual_gate_a_state(
            v14_release=v14,
            v16_refresh={"metadata": {}, "methodology": {}, "baseline": {}},
            delta16=_delta(),
            source_register14=register,
            monitor15=[_monitor()],
            known_source_ids={"SRC-1"},
        )


def test_residual_state_rejects_monitor_or_family_source_drift() -> None:
    v14 = _v14()
    monitor = _monitor()
    monitor["publisher"] = "Substituted"
    with pytest.raises(ObservatoryResidualMigrationError, match="does not match predecessor Source"):
        preserve_residual_gate_a_state(
            v14_release=v14,
            v16_refresh={"metadata": {}, "methodology": {}, "baseline": {}},
            delta16=_delta(),
            source_register14=copy.deepcopy(v14["sources"]),
            monitor15=[monitor],
            known_source_ids={"SRC-1"},
        )

    delta = _delta()
    delta["model_records"][0]["source_ids"] = ["MISSING"]
    with pytest.raises(ObservatoryResidualMigrationError, match="references missing Sources"):
        preserve_residual_gate_a_state(
            v14_release=v14,
            v16_refresh={"metadata": {}, "methodology": {}, "baseline": {}},
            delta16=delta,
            source_register14=copy.deepcopy(v14["sources"]),
            monitor15=[_monitor()],
            known_source_ids={"SRC-1"},
        )


def test_residual_verifier_detects_payload_tampering() -> None:
    v14 = _v14()
    state = preserve_residual_gate_a_state(
        v14_release=v14,
        v16_refresh={"metadata": {}, "methodology": {}, "baseline": {}},
        delta16=_delta(),
        source_register14=copy.deepcopy(v14["sources"]),
        monitor15=[_monitor()],
        known_source_ids={"SRC-1"},
    )
    state["residual_families"][0]["payload"][0]["record_id"] = "Changed"
    errors = verify_residual_gate_a_state(state, known_source_ids={"SRC-1"})
    assert any("digest mismatch" in error for error in errors)
