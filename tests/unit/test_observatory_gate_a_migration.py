from __future__ import annotations

import copy

import pytest

from neuroai_workbench.observatory_gate_a_migration import (
    REMAINING_GATE_REQUIREMENTS,
    ObservatoryGateAMigrationError,
    build_gate_a_migration_checkpoint,
    verify_gate_a_migration_checkpoint,
)


def _delta() -> dict:
    return {
        "regulatory_and_market_events": [{"event_id": "REG-16-001", "source_ids": ["SRC-1"]}],
        "capital_and_ownership_events": [],
        "model_records": [],
        "supplier_dependency_relationships": [],
        "governance_and_leadership_events": [],
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
        "baseline_claim_boundary": "Retrieval is not truth.",
        "network_access_required": True,
        "current_status": "BASELINE_REGISTERED",
        "next_action": "RETRIEVE_AND_COMPARE",
    }


def _inputs() -> tuple[dict, dict, dict, dict, dict, list[dict], list[dict]]:
    delta = _delta()
    v14 = {
        "metadata": {"version": "v1.4"},
        "methodology": {"version": "v1.4"},
        "coverage": {"scope": "bounded"},
        "organizations": [
            {
                "organization_id": "ORG-1",
                "canonical_name": "Science Corporation",
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
        ],
        "organization_resolution": [
            {
                "resolution_id": "RES-1",
                "organization_id": "ORG-1",
                "name_before": "Science Corporation",
                "verification_before": "CURRENT_PARTIAL",
                "disposition": "CURRENT_VERIFIED",
                "verification_after": "CURRENT_VERIFIED",
                "source_ids": ["SRC-1"],
                "rationale": "Current identity verified.",
                "effective_date": "2026-07-29",
            }
        ],
        "regional_expansion": [
            {
                "regional_record_id": "REG-1",
                "organization_id": "ORG-1",
                "canonical_name": "Science Corporation",
                "unesco_region": "Europe and North America",
                "country_or_scope": "United States",
                "action": "ADD",
                "inclusion_rule": "Official source.",
                "verification_state": "CURRENT_VERIFIED",
                "source_ids": ["SRC-1"],
                "claim_boundary": "Coverage only.",
            }
        ],
        "sources": [
            {
                "source_id": "SRC-1",
                "title": "Official source",
                "publisher": "Publisher",
                "url": "https://example.test/source",
                "source_class": "OFFICIAL_PAGE",
                "retrieved": "2026-07-29",
                "verification_state": "CURRENT_VERIFIED",
                "evidence_state": "CURRENT_SOURCE_RETRIEVED",
                "supports": "Bounded source statement",
                "claim_boundary": "Retrieval is not truth.",
                "legacy_source_ids": [],
            }
        ],
        "capital_and_ownership_events": [
            {
                "event_id": "CAP-1",
                "date": "2026",
                "event_type": "EQUITY_FINANCING",
                "subject": "Science Corporation",
                "counterparties": ["Investor A"],
                "amount": None,
                "currency": "USD",
                "amount_state": "NOT_DISCLOSED",
                "ownership_effect": "UNRESOLVED",
                "source_ids": ["SRC-1"],
                "evidence_state": "COMPANY_ANNOUNCEMENT",
                "boundary": "No valuation inference.",
            }
        ],
        "representative_model_records": [{"model_id": "MDL-OLD-1", "source_ids": ["SRC-1"]}],
        "model_and_dataset_registry": [{"registry_id": "REGISTRY-1", "source_ids": ["SRC-1"]}],
        "trial_site_relationships": [{"relationship_id": "REL-1", "source_ids": ["SRC-1"]}],
        "participant_authority_relationships": [{"authority_id": "AUTH-1", "source_ids": ["SRC-1"]}],
        "supplier_dependency_relationships": [{"dependency_id": "DEP-1", "source_ids": ["SRC-1"]}],
        "data_quality": [{"finding_id": "DQ-1", "severity": "HIGH"}],
    }
    v16 = {
        "metadata": {"version": "v1.6"},
        "methodology": {"version": "v1.6"},
        "baseline": {"predecessor": "v1.4"},
        "new_sources": [
            {
                "source_id": "SRC-16-1",
                "title": "Announcement",
                "publisher": "Publisher",
                "url": "https://example.test/announcement",
                "published": "2026-07-22",
                "retrieved": "2026-07-29T12:38:00Z",
                "source_class": "OFFICIAL_COMPANY_ANNOUNCEMENT",
                "evidence_state": "COMPANY_ANNOUNCEMENT",
                "supports": "Bounded source statement",
                "claim_boundary": "No broader inference.",
            }
        ],
        "source_checks": [
            {
                "check_id": "CHK-1",
                "source_id": "SRC-16-1",
                "retrieved": "2026-07-29T12:38:00Z",
                "retrieval_outcome": "SUCCESS_VIA_WEB_RESEARCH",
                "baseline_match": "NEW_SOURCE_OR_BACKFILL",
                "page_content_hash": "NOT_AVAILABLE_FROM_WEB_RESEARCH_INTERFACE",
                "metadata_digest": "a" * 64,
            }
        ],
        "change_candidates": [
            {
                "candidate_id": "CAND-1",
                "event_date": "2026-07-22",
                "discovery_class": "NEW_EVIDENCE",
                "change_class": "REGULATORY_AND_MARKET_STATE_CHANGE",
                "subject": "Science Corporation",
                "summary": "Bounded update.",
                "source_ids": ["SRC-16-1"],
                "materiality": "HIGH",
                "adjudication": "ACCEPT_WITH_EVIDENCE_BOUNDARY",
                "reopening": "SYSTEM_RECORD_REOPEN_REQUIRED",
            }
        ],
        "adjudicated_delta": copy.deepcopy(delta),
        "no_change_confirmations": [
            {
                "object": "Official update index",
                "result": "NO_POST_BASELINE_MATERIAL_EVENT_IDENTIFIED",
                "source_ids": ["SRC-16-1"],
            }
        ],
        "reopening_decisions": [
            {
                "decision_id": "ROP-16-001",
                "object": "PRIMA observatory system record",
                "decision": "REOPEN_REQUIRED",
                "basis": ["REG-16-001"],
                "required_actions": ["Assess exact system"],
            },
            {
                "decision_id": "ROP-16-002",
                "object": "Other object",
                "decision": "NO_REOPENING_TRIGGER_IDENTIFIED",
                "basis": [],
                "required_actions": [],
            },
        ],
        "withheld_claims": ["Global completeness"],
    }
    prima = {
        "metadata": {"version": "v1.7", "predecessor": "v1.6", "status": "CONTROLLED_SUCCESSOR"},
        "predecessor_reference": {"archive_sha256": "b" * 64, "immutable": True},
        "event_delta": {"new_post_cutoff_material_events": 0},
        "assessment_delta": {"assessment_id": "PRIMA-PUBLIC-2026-001", "decision": "CL-4_NOT_ESTABLISHED"},
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
        "prohibited_inferences": ["No endorsement inferred."],
    }
    v17 = {
        "metadata": {"version": "v1.7", "predecessor": "v1.6", "status": "CONTROLLED_SUCCESSOR_SNAPSHOT"},
        "baseline_reference": {"canonical_sha256": "a" * 64, "immutable": True},
        "baseline_counts": {},
        "delta_counts": {},
        "successor_effective_counts": {},
        "delta": copy.deepcopy(delta),
        "reopening_decisions": [
            copy.deepcopy(v16["reopening_decisions"][1]),
            {
                "decision_id": "ROP-17-001",
                "object": "PRIMA observatory system record",
                "decision": "REOPENING_EXECUTED_RECORD_UPDATED_OPEN_CONDITIONS",
                "basis": ["PRIMA-PUBLIC-2026-001", "REG-16-001"],
                "required_actions": ["Open condition"],
            },
        ],
        "provenance": {"baseline_sha256": "a" * 64, "predecessor_archive_sha256": "b" * 64},
        "predecessor_reference": {"v1_6_archive_sha256": "b" * 64, "immutable": True},
        "assessment_successor_delta": copy.deepcopy(prima),
    }
    source_register = copy.deepcopy(v14["sources"])
    monitor = [_monitor()]
    return v14, v16, delta, v17, prima, source_register, monitor


def test_full_gate_a_checkpoint_reaches_representational_completeness_without_authority() -> None:
    v14, v16, delta, v17, prima, source_register, monitor = _inputs()
    result = build_gate_a_migration_checkpoint(
        v14_release=v14,
        v16_refresh=v16,
        delta16=delta,
        v17_successor=v17,
        prima17=prima,
        source_register14=source_register,
        monitor15=monitor,
    )
    assert result["mechanical_verification"] == "PASS"
    assert result["release_authorized"] is False
    assert result["representational_scope_complete"] is True
    assert result["gate_a_complete"] is False
    assert result["remaining_unresolved_families"] == []
    assert result["remaining_gate_requirements"] == list(REMAINING_GATE_REQUIREMENTS)
    assert result["counts"]["native_objects"] == 5
    assert result["counts"]["governed_v14_history_records"] == 2
    assert result["counts"]["governed_v16_adjudication_records"] == 4
    assert result["counts"]["governed_successor_packages"] == 2
    assert result["counts"]["residual_family_records"] == 7
    assert result["counts"]["source_register_records"] == 1
    assert result["counts"]["monitor_registry_records"] == 1
    assert result["duplicate_container_proofs"]["v16_embedded_delta_equals_delta16"] is True
    assert result["duplicate_container_proofs"]["v17_embedded_delta_equals_delta16"] is True
    assert result["duplicate_container_proofs"]["v17_embedded_prima_equals_standalone_prima"] is True
    assert verify_gate_a_migration_checkpoint(result, delta16=delta)["valid"] is True


def test_full_gate_a_checkpoint_rejects_v16_embedded_delta_drift() -> None:
    v14, v16, delta, v17, prima, source_register, monitor = _inputs()
    v16["adjudicated_delta"] = {"changed": True}
    with pytest.raises(ObservatoryGateAMigrationError, match="adjudicated_delta container"):
        build_gate_a_migration_checkpoint(
            v14_release=v14,
            v16_refresh=v16,
            delta16=delta,
            v17_successor=v17,
            prima17=prima,
            source_register14=source_register,
            monitor15=monitor,
        )


def test_full_gate_a_verifier_detects_false_completion_claim() -> None:
    v14, v16, delta, v17, prima, source_register, monitor = _inputs()
    result = build_gate_a_migration_checkpoint(
        v14_release=v14,
        v16_refresh=v16,
        delta16=delta,
        v17_successor=v17,
        prima17=prima,
        source_register14=source_register,
        monitor15=monitor,
    )
    result["gate_a_complete"] = True
    report = verify_gate_a_migration_checkpoint(result, delta16=delta)
    assert report["valid"] is False
    assert "Gate-A completion must remain false until all non-representational gates close" in report["errors"]


def test_full_gate_a_verifier_detects_false_representational_completion() -> None:
    v14, v16, delta, v17, prima, source_register, monitor = _inputs()
    result = build_gate_a_migration_checkpoint(
        v14_release=v14,
        v16_refresh=v16,
        delta16=delta,
        v17_successor=v17,
        prima17=prima,
        source_register14=source_register,
        monitor15=monitor,
    )
    result["remaining_unresolved_families"] = ["V14.synthetic_unresolved"]
    report = verify_gate_a_migration_checkpoint(result, delta16=delta)
    assert report["valid"] is False
    assert any("representational_scope_complete" in error for error in report["errors"])
