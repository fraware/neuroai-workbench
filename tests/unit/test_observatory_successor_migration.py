from __future__ import annotations

import copy

import pytest

from neuroai_workbench.observatory_successor_migration import (
    SUCCESSOR_MIGRATION_STATE,
    ObservatorySuccessorMigrationError,
    preserve_v17_successor_lineage,
    verify_v17_successor_lineage,
)


def _delta() -> dict:
    return {"regulatory_and_market_events": [{"event_id": "REG-16-1"}]}


def _v16() -> dict:
    return {
        "reopening_decisions": [
            {
                "decision_id": "ROP-16-001",
                "object": "PRIMA observatory system record",
                "decision": "REOPEN_REQUIRED",
                "basis": ["REG-16-1"],
                "required_actions": ["Assess exact system"],
            },
            {
                "decision_id": "ROP-16-002",
                "object": "Other object",
                "decision": "NO_REOPENING_TRIGGER_IDENTIFIED",
                "basis": [],
                "required_actions": [],
            },
        ]
    }


def _prima() -> dict:
    return {
        "metadata": {
            "version": "v1.7",
            "predecessor": "v1.6",
            "status": "CONTROLLED_SUCCESSOR",
        },
        "predecessor_reference": {"archive_sha256": "b" * 64, "immutable": True},
        "event_delta": {"new_post_cutoff_material_events": 0},
        "assessment_delta": {
            "assessment_id": "PRIMA-PUBLIC-2026-001",
            "decision": "CL-4_NOT_ESTABLISHED",
        },
        "source_delta": {},
        "reopening_transition": {
            "predecessor_decision_id": "ROP-16-001",
            "predecessor_state": "REOPEN_REQUIRED",
            "successor_decision_id": "ROP-17-001",
            "successor_state": "REOPENING_EXECUTED_RECORD_UPDATED_OPEN_CONDITIONS",
            "resolved_actions": ["Assessment executed"],
            "open_actions": ["Open condition"],
        },
        "bounded_system_record": {"system": "PRIMA retinal prosthesis"},
        "prohibited_inferences": ["No regulatory endorsement is inferred."],
    }


def _v17(delta: dict, prima: dict) -> dict:
    return {
        "metadata": {
            "version": "v1.7",
            "predecessor": "v1.6",
            "status": "CONTROLLED_SUCCESSOR_SNAPSHOT",
        },
        "baseline_reference": {"canonical_sha256": "a" * 64, "immutable": True},
        "baseline_counts": {},
        "delta_counts": {},
        "successor_effective_counts": {},
        "delta": copy.deepcopy(delta),
        "reopening_decisions": [
            {
                "decision_id": "ROP-16-002",
                "object": "Other object",
                "decision": "NO_REOPENING_TRIGGER_IDENTIFIED",
                "basis": [],
                "required_actions": [],
            },
            {
                "decision_id": "ROP-17-001",
                "object": "PRIMA observatory system record",
                "decision": "REOPENING_EXECUTED_RECORD_UPDATED_OPEN_CONDITIONS",
                "basis": ["PRIMA-PUBLIC-2026-001", "REG-16-1"],
                "required_actions": ["Open condition"],
            },
        ],
        "provenance": {
            "baseline_sha256": "a" * 64,
            "predecessor_archive_sha256": "b" * 64,
        },
        "predecessor_reference": {"v1_6_archive_sha256": "b" * 64, "immutable": True},
        "assessment_successor_delta": copy.deepcopy(prima),
    }


def test_v17_successor_lineage_preserves_exact_duplicate_containers_and_reopening_transition() -> None:
    delta = _delta()
    prima = _prima()
    result = preserve_v17_successor_lineage(
        v16_refresh=_v16(),
        delta16=delta,
        v17_successor=_v17(delta, prima),
        prima17=prima,
    )
    assert result["migration_state"] == SUCCESSOR_MIGRATION_STATE
    assert result["release_authorized"] is False
    assert result["native_objects_created"] == 0
    assert result["embedded_delta_sha256"] == result["standalone_delta_sha256"]
    assert result["embedded_prima_sha256"] == result["standalone_prima_sha256"]
    assert result["reopening_predecessor_decision_id"] == "ROP-16-001"
    assert result["reopening_successor_decision_id"] == "ROP-17-001"
    assert result["unchanged_reopening_decision_count"] == 1
    assert verify_v17_successor_lineage(result) == []


def test_v17_successor_rejects_embedded_delta_or_prima_drift() -> None:
    delta = _delta()
    prima = _prima()
    v17 = _v17(delta, prima)
    v17["delta"]["regulatory_and_market_events"][0]["event_id"] = "SUBSTITUTED"
    with pytest.raises(ObservatorySuccessorMigrationError, match="embedded delta"):
        preserve_v17_successor_lineage(v16_refresh=_v16(), delta16=delta, v17_successor=v17, prima17=prima)

    v17 = _v17(delta, prima)
    v17["assessment_successor_delta"]["assessment_delta"]["decision"] = "SUBSTITUTED"
    with pytest.raises(ObservatorySuccessorMigrationError, match="embedded PRIMA"):
        preserve_v17_successor_lineage(v16_refresh=_v16(), delta16=delta, v17_successor=v17, prima17=prima)


def test_v17_successor_rejects_unrelated_reopening_rewrite() -> None:
    delta = _delta()
    prima = _prima()
    v17 = _v17(delta, prima)
    v17["reopening_decisions"][0]["decision"] = "CHANGED"
    with pytest.raises(ObservatorySuccessorMigrationError, match="unrelated reopening decisions changed"):
        preserve_v17_successor_lineage(v16_refresh=_v16(), delta16=delta, v17_successor=v17, prima17=prima)


def test_v17_successor_rejects_dropped_predecessor_trigger_or_missing_assessment_trigger() -> None:
    delta = _delta()
    prima = _prima()
    v17 = _v17(delta, prima)
    v17["reopening_decisions"][1]["basis"] = ["PRIMA-PUBLIC-2026-001"]
    with pytest.raises(ObservatorySuccessorMigrationError, match="dropped predecessor trigger"):
        preserve_v17_successor_lineage(v16_refresh=_v16(), delta16=delta, v17_successor=v17, prima17=prima)

    v17 = _v17(delta, prima)
    v17["reopening_decisions"][1]["basis"] = ["REG-16-1"]
    with pytest.raises(ObservatorySuccessorMigrationError, match="executed assessment id"):
        preserve_v17_successor_lineage(v16_refresh=_v16(), delta16=delta, v17_successor=v17, prima17=prima)


def test_successor_verifier_detects_preserved_payload_tampering_or_authority_upgrade() -> None:
    delta = _delta()
    prima = _prima()
    result = preserve_v17_successor_lineage(
        v16_refresh=_v16(),
        delta16=delta,
        v17_successor=_v17(delta, prima),
        prima17=prima,
    )
    result["v17_successor"]["metadata"]["status"] = "SUBSTITUTED"
    assert "v17_successor_sha256 mismatch" in verify_v17_successor_lineage(result)
    result["native_authority"] = True
    assert "native_authority must remain false" in verify_v17_successor_lineage(result)
