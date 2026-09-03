from __future__ import annotations

import copy

import pytest

from neuroai_workbench.observatory_gate_a_review import (
    MIGRATION_MODES,
    REQUIRED_ORGANIZATION_REVIEW_CLASSES,
    ObservatoryGateAReviewError,
    build_gate_a_review_packet,
    verify_gate_a_review_packet,
)


def _org(index: int) -> dict:
    return {"organization_id": f"ORG-{index}", "canonical_name": f"Organization {index}"}


def _inputs() -> tuple[dict, dict, dict, dict, dict, list[dict], list[dict], dict]:
    organizations = [_org(index) for index in range(4)]
    v14 = {
        "metadata": {"version": "v1.4"},
        "methodology": {"version": "v1.4"},
        "coverage": {"scope": "bounded"},
        "organizations": organizations,
        "organization_resolution": [{"resolution_id": "RES-1", "disposition": "CURRENT_VERIFIED"}],
        "regional_expansion": [{"regional_record_id": "REG-1", "action": "ADD"}],
        "capital_and_ownership_events": [
            {"event_id": "CAP-YEAR", "date": "2026"},
            {"event_id": "CAP-NULL", "date": None},
        ],
        "representative_model_records": [{"model_id": "MDL-1"}],
        "model_and_dataset_registry": [{"registry_id": "REGISTRY-1"}],
        "trial_site_relationships": [{"relationship_id": "REL-1"}],
        "participant_authority_relationships": [{"authority_id": "AUTH-1"}],
        "supplier_dependency_relationships": [{"dependency_id": "DEP-1"}],
        "sources": [{"source_id": "SRC-1"}],
        "data_quality": [{"finding_id": "DQ-1"}],
    }
    v16 = {
        "metadata": {"version": "v1.6"},
        "methodology": {"version": "v1.6"},
        "baseline": {"predecessor": "v1.4"},
        "source_checks": [{"check_id": "CHK-1"}],
        "new_sources": [
            {"source_id": "SRC-16-DATE", "published": "2026-07-22"},
            {"source_id": "SRC-16-NULL", "published": None},
        ],
        "change_candidates": [
            {
                "candidate_id": "CAND-1",
                "change_class": "REGULATORY_AND_MARKET_STATE_CHANGE",
                "adjudication": "ACCEPT_WITH_EVIDENCE_BOUNDARY",
            }
        ],
        "adjudicated_delta": {"bound": True},
        "reopening_decisions": [{"decision_id": "ROP-16-001"}],
        "no_change_confirmations": [{"object": "Comparison"}],
        "withheld_claims": ["Global completeness"],
    }
    delta16 = {
        "regulatory_and_market_events": [{"event_id": "REG-16-1"}],
        "capital_and_ownership_events": [{"event_id": "CAP-16-1"}],
        "model_records": [{"model_id": "MDL-16-1"}],
        "supplier_dependency_relationships": [{"dependency_id": "DEP-16-1"}],
        "governance_and_leadership_events": [{"event_id": "GOV-16-1"}],
    }
    v17 = {
        "metadata": {"version": "v1.7"},
        "baseline_reference": {"sha256": "a" * 64},
        "baseline_counts": {},
        "delta_counts": {},
        "successor_effective_counts": {},
        "delta": copy.deepcopy(delta16),
        "reopening_decisions": [
            {"decision_id": "ROP-16-002"},
            {"decision_id": "ROP-17-001"},
        ],
        "provenance": {},
        "predecessor_reference": {},
        "assessment_successor_delta": {"embedded": True},
    }
    prima17 = {
        "metadata": {"version": "v1.7"},
        "predecessor_reference": {},
        "event_delta": {},
        "assessment_delta": {},
        "source_delta": {},
        "reopening_transition": {"successor_decision_id": "ROP-17-001"},
        "bounded_system_record": {},
        "prohibited_inferences": ["No endorsement inferred."],
    }
    source_register = [{"source_id": "SRC-1"}]
    monitor = [{"monitor_id": "MON-1", "source_id": "SRC-1"}]

    classes = [
        "MATERIALIZE_ACTIVE_ENTITY",
        "LEGACY_IDENTITY_UNRESOLVED",
        "PROVENANCE_ONLY_NODE",
        "HISTORICAL_CURRENT_IDENTITY_UNRESOLVED",
    ]
    native_trace = {
        "classification": classes[0],
        "record_index": 0,
        "predecessor_record": organizations[0],
    }
    preserved = [
        {
            "classification": classification,
            "record_index": index,
            "predecessor_record": organizations[index],
        }
        for index, classification in enumerate(classes[1:], start=1)
    ]
    checkpoint = {
        "representational_scope_complete": True,
        "release_authorized": False,
        "gate_a_complete": False,
        "candidate": {
            "core": {
                "entity_migration": {
                    "predecessor_traces": [native_trace],
                    "preserved_predecessor_records": preserved,
                }
            }
        },
    }
    return v14, v16, delta16, v17, prima17, source_register, monitor, checkpoint


def _build() -> dict:
    v14, v16, delta16, v17, prima17, source_register, monitor, checkpoint = _inputs()
    return build_gate_a_review_packet(
        checkpoint=checkpoint,
        v14_release=v14,
        v16_refresh=v16,
        delta16=delta16,
        v17_successor=v17,
        prima17=prima17,
        source_register14=source_register,
        monitor15=monitor,
    )


def test_review_packet_covers_every_declared_family_and_forces_known_edge_cases() -> None:
    packet = _build()

    assert packet["state"] == "PENDING_HUMAN_REVIEW"
    assert packet["release_authorized"] is False
    assert packet["gate_a_complete"] is False
    assert packet["software_approval_performed"] is False
    assert packet["family_coverage_count"] == len(MIGRATION_MODES)
    assert set(packet["covered_families"]) == {f"{role}.{family}" for role, family in MIGRATION_MODES}
    assert verify_gate_a_review_packet(packet) == []

    organization_edges = {
        unit["edge_case"]
        for unit in packet["review_units"]
        if unit["role"] == "V14" and unit["family"] == "organizations"
    }
    assert organization_edges == set(REQUIRED_ORGANIZATION_REVIEW_CLASSES)

    event_edges = {
        unit["edge_case"]
        for unit in packet["review_units"]
        if unit["role"] == "V14" and unit["family"] == "capital_and_ownership_events"
    }
    assert {"YEAR_TIME", "NULL_TIME"}.issubset(event_edges)

    source_edges = {
        unit["edge_case"]
        for unit in packet["review_units"]
        if unit["role"] == "V16" and unit["family"] == "new_sources"
    }
    assert {"EXPLICIT_PUBLICATION_TIME", "NULL_PUBLICATION_TIME"}.issubset(source_edges)

    assert any(
        unit["edge_case"] == "SUCCESSOR_REOPENING_DECISION"
        for unit in packet["review_units"]
        if unit["role"] == "V17" and unit["family"] == "reopening_decisions"
    )


def test_review_packet_never_prefills_human_judgment() -> None:
    packet = _build()
    assert packet["review_units"]
    for unit in packet["review_units"]:
        assert unit["human_disposition"] is None
        assert unit["reviewer_identity"] is None
        assert unit["review_notes"] is None
        assert unit["reviewed_at"] is None
        assert unit["required_checks"]


def test_review_packet_digest_and_human_boundary_detect_tampering() -> None:
    packet = _build()
    packet["review_units"][0]["source_payload"] = {"tampered": True}
    errors = verify_gate_a_review_packet(packet)
    assert any("payload digest mismatch" in error for error in errors)
    assert "review_packet_sha256 mismatch" in errors

    packet = _build()
    packet["review_units"][0]["human_disposition"] = "APPROVE"
    errors = verify_gate_a_review_packet(packet)
    assert any("software prefilled human_disposition" in error for error in errors)


def test_review_packet_refuses_missing_required_organization_class() -> None:
    v14, v16, delta16, v17, prima17, source_register, monitor, checkpoint = _inputs()
    checkpoint["candidate"]["core"]["entity_migration"]["preserved_predecessor_records"].pop()

    with pytest.raises(ObservatoryGateAReviewError, match="lacks required migration classifications"):
        build_gate_a_review_packet(
            checkpoint=checkpoint,
            v14_release=v14,
            v16_refresh=v16,
            delta16=delta16,
            v17_successor=v17,
            prima17=prima17,
            source_register14=source_register,
            monitor15=monitor,
        )


def test_review_packet_refuses_unknown_predecessor_family() -> None:
    v14, v16, delta16, v17, prima17, source_register, monitor, checkpoint = _inputs()
    v14["new_unreviewed_family"] = [{"x": 1}]

    with pytest.raises(ObservatoryGateAReviewError, match="Unreviewed predecessor review family"):
        build_gate_a_review_packet(
            checkpoint=checkpoint,
            v14_release=v14,
            v16_refresh=v16,
            delta16=delta16,
            v17_successor=v17,
            prima17=prima17,
            source_register14=source_register,
            monitor15=monitor,
        )
