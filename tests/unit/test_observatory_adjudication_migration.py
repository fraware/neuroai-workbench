from __future__ import annotations

import pytest

from neuroai_workbench.observatory_adjudication_migration import (
    NO_CHANGE_STATE,
    REOPENING_STATE,
    WITHHELD_STATE,
    ObservatoryAdjudicationMigrationError,
    preserve_v16_adjudication_state,
    verify_v16_adjudication_state,
)


def _delta() -> dict:
    return {
        "regulatory_and_market_events": [{"event_id": "REG-16-001"}],
        "capital_and_ownership_events": [{"event_id": "CAP-16-002"}],
        "model_records": [{"model_id": "MDL-16-001"}],
        "supplier_dependency_relationships": [],
        "governance_and_leadership_events": [{"event_id": "GOV-16-002"}],
    }


def _v16() -> dict:
    return {
        "no_change_confirmations": [
            {
                "object": "Neuralink official update index",
                "result": "NO_POST_BASELINE_MATERIAL_EVENT_IDENTIFIED",
                "source_ids": ["SRC-16-011"],
            }
        ],
        "reopening_decisions": [
            {
                "decision_id": "ROP-16-001",
                "object": "PRIMA observatory system record",
                "decision": "REOPEN_REQUIRED",
                "basis": ["REG-16-001"],
                "required_actions": ["Create exact system record"],
            },
            {
                "decision_id": "ROP-16-002",
                "object": "Other pilot",
                "decision": "NO_REOPENING_TRIGGER_IDENTIFIED",
                "basis": [],
                "required_actions": [],
            },
        ],
        "withheld_claims": ["Global completeness", "Absence of unannounced events"],
    }


def test_v16_adjudication_preserves_nonclaim_and_nonmutation_semantics() -> None:
    delta = _delta()
    state = preserve_v16_adjudication_state(
        v16_refresh=_v16(),
        delta16=delta,
        known_source_ids={"SRC-16-011"},
    )
    no_change = state["no_change_confirmations"][0]
    reopening = state["reopening_decisions"][0]
    withheld = state["withheld_claims"][0]
    assert no_change["migration_state"] == NO_CHANGE_STATE
    assert no_change["global_absence_claimed"] is False
    assert reopening["migration_state"] == REOPENING_STATE
    assert reopening["assessment_mutation_performed_by_migration"] is False
    assert withheld["migration_state"] == WITHHELD_STATE
    assert withheld["substantive_claim_created"] is False
    assert state["native_object_count"] == 0
    assert state["release_authorized"] is False
    assert verify_v16_adjudication_state(
        state,
        known_source_ids={"SRC-16-011"},
        delta_ids={"REG-16-001", "CAP-16-002", "MDL-16-001", "GOV-16-002"},
    ) == []


def test_no_change_rejects_unknown_source_and_unreviewed_shape() -> None:
    with pytest.raises(ObservatoryAdjudicationMigrationError, match="missing Sources"):
        preserve_v16_adjudication_state(v16_refresh=_v16(), delta16=_delta(), known_source_ids=set())
    v16 = _v16()
    v16["no_change_confirmations"][0]["unexpected"] = True
    with pytest.raises(ObservatoryAdjudicationMigrationError, match="shape mismatch"):
        preserve_v16_adjudication_state(
            v16_refresh=v16,
            delta16=_delta(),
            known_source_ids={"SRC-16-011"},
        )


def test_reopening_rejects_unknown_basis_and_duplicate_decision() -> None:
    v16 = _v16()
    v16["reopening_decisions"][0]["basis"] = ["MISSING"]
    with pytest.raises(ObservatoryAdjudicationMigrationError, match="unknown delta basis ids"):
        preserve_v16_adjudication_state(
            v16_refresh=v16,
            delta16=_delta(),
            known_source_ids={"SRC-16-011"},
        )

    v16 = _v16()
    v16["reopening_decisions"][1]["decision_id"] = "ROP-16-001"
    with pytest.raises(ObservatoryAdjudicationMigrationError, match="duplicate reopening decision"):
        preserve_v16_adjudication_state(
            v16_refresh=v16,
            delta16=_delta(),
            known_source_ids={"SRC-16-011"},
        )


def test_withheld_claims_must_be_unique_nonempty_values() -> None:
    v16 = _v16()
    v16["withheld_claims"] = ["Global completeness", "Global completeness"]
    with pytest.raises(ObservatoryAdjudicationMigrationError, match="duplicate withheld claim"):
        preserve_v16_adjudication_state(
            v16_refresh=v16,
            delta16=_delta(),
            known_source_ids={"SRC-16-011"},
        )


def test_adjudication_verifier_detects_global_absence_or_assessment_mutation_upgrade() -> None:
    state = preserve_v16_adjudication_state(
        v16_refresh=_v16(),
        delta16=_delta(),
        known_source_ids={"SRC-16-011"},
    )
    state["no_change_confirmations"][0]["global_absence_claimed"] = True
    state["reopening_decisions"][0]["assessment_mutation_performed_by_migration"] = True
    errors = verify_v16_adjudication_state(
        state,
        known_source_ids={"SRC-16-011"},
        delta_ids={"REG-16-001", "CAP-16-002", "MDL-16-001", "GOV-16-002"},
    )
    assert "no-change state must not claim global absence" in errors
    assert "reopening migration must not mutate assessment" in errors
