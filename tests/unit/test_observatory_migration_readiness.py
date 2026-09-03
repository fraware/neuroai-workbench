from __future__ import annotations

from neuroai_workbench.observatory_migration_readiness import (
    BLOCKED,
    READINESS_BOUNDARY,
    analyze_remaining_migration_readiness,
)


def _source_ids() -> set[str]:
    return {"SRC-1", "SRC-2"}


def test_readiness_analysis_blocks_free_text_relationship_endpoints() -> None:
    v14 = {
        "trial_site_relationships": [
            {
                "relationship_id": "TRS-1",
                "system_or_study": "Programme A",
                "site": "Hospital A",
                "relationship_type": "NAMED_CLINICAL_TRIAL_SITE",
                "source_ids": ["SRC-1"],
                "evidence_state": "SOURCE_STATED",
                "boundary": "Bounded relation.",
            }
        ],
        "participant_authority_relationships": [],
        "supplier_dependency_relationships": [],
        "representative_model_records": [],
    }
    result = analyze_remaining_migration_readiness(
        v14_release=v14,
        v16_refresh={"reopening_decisions": []},
        delta16={
            "model_records": [],
            "regulatory_and_market_events": [],
            "capital_and_ownership_events": [],
            "governance_and_leadership_events": [],
        },
        v17_successor={"reopening_decisions": []},
        materialized_source_ids=_source_ids(),
    )
    record = result["families"]["V14.trial_site_relationships"][0]
    assert record["state"] == BLOCKED
    assert "SUBJECT_CONTROLLED_ENTITY_ID_UNRESOLVED" in record["blockers"]
    assert "OBJECT_CONTROLLED_ENTITY_ID_UNRESOLVED" in record["blockers"]
    assert result["release_authorized"] is False
    assert result["boundary"] == READINESS_BOUNDARY


def test_model_readiness_does_not_invent_entity_status() -> None:
    v14 = {
        "trial_site_relationships": [],
        "participant_authority_relationships": [],
        "supplier_dependency_relationships": [],
        "representative_model_records": [
            {
                "model_id": "MDL-1",
                "name": "Model A",
                "source_ids": ["SRC-1"],
                "publication_state": "OFFICIAL_CURRENT_REPRESENTATION",
                "verification_state": "CURRENT_VERIFIED",
            }
        ],
    }
    result = analyze_remaining_migration_readiness(
        v14_release=v14,
        v16_refresh={"reopening_decisions": []},
        delta16={
            "model_records": [],
            "regulatory_and_market_events": [],
            "capital_and_ownership_events": [],
            "governance_and_leadership_events": [],
        },
        v17_successor={"reopening_decisions": []},
        materialized_source_ids=_source_ids(),
    )
    record = result["families"]["V14.representative_model_records"][0]
    assert record["state"] == BLOCKED
    assert "NATIVE_ENTITY_STATUS_NOT_GOVERNED" in record["blockers"]
    assert "MODEL_ENTITY_TYPE_MAPPING_REQUIRES_GOVERNED_RULE" in record["blockers"]


def test_reopening_decision_identifies_temporal_and_identity_gaps() -> None:
    v14 = {
        "trial_site_relationships": [],
        "participant_authority_relationships": [],
        "supplier_dependency_relationships": [],
        "representative_model_records": [],
    }
    result = analyze_remaining_migration_readiness(
        v14_release=v14,
        v16_refresh={
            "reopening_decisions": [
                {
                    "decision_id": "ROP-1",
                    "object": "System record",
                    "decision": "REOPEN_REQUIRED",
                    "basis": ["EVT-1"],
                    "required_actions": [],
                }
            ]
        },
        delta16={
            "model_records": [],
            "regulatory_and_market_events": [],
            "capital_and_ownership_events": [],
            "governance_and_leadership_events": [],
        },
        v17_successor={"reopening_decisions": []},
        materialized_source_ids=_source_ids(),
    )
    record = result["families"]["V16.reopening_decisions"][0]
    assert "SUBJECT_CONTROLLED_ENTITY_ID_UNRESOLVED" in record["blockers"]
    assert "DECIDED_AT_NOT_GOVERNED" in record["blockers"]
    assert "TRIGGER_REFERENCE_CLASS_UNRESOLVED" in record["blockers"]


def test_delta_event_reports_missing_source_and_native_semantic_gaps() -> None:
    v14 = {
        "trial_site_relationships": [],
        "participant_authority_relationships": [],
        "supplier_dependency_relationships": [],
        "representative_model_records": [],
    }
    result = analyze_remaining_migration_readiness(
        v14_release=v14,
        v16_refresh={"reopening_decisions": []},
        delta16={
            "model_records": [],
            "regulatory_and_market_events": [
                {
                    "event_id": "REG-1",
                    "system": "System A",
                    "event_type": "REGULATORY_CHANGE",
                    "source_ids": ["SRC-MISSING"],
                    "bounded_effect": "Bounded update.",
                }
            ],
            "capital_and_ownership_events": [],
            "governance_and_leadership_events": [],
        },
        v17_successor={"reopening_decisions": []},
        materialized_source_ids=_source_ids(),
    )
    record = result["families"]["DELTA16.regulatory_and_market_events"][0]
    assert "SOURCE_NOT_MATERIALIZED:SRC-MISSING" in record["blockers"]
    assert "SUBJECT_CONTROLLED_ENTITY_ID_UNRESOLVED" in record["blockers"]
    assert "EVIDENCE_STATE_NOT_GOVERNED_FOR_NATIVE_EVENT" in record["blockers"]
    assert "VERIFICATION_STATE_NOT_GOVERNED_FOR_NATIVE_EVENT" in record["blockers"]


def test_summary_counts_records_and_blockers_deterministically() -> None:
    v14 = {
        "trial_site_relationships": [],
        "participant_authority_relationships": [],
        "supplier_dependency_relationships": [],
        "representative_model_records": [],
    }
    result = analyze_remaining_migration_readiness(
        v14_release=v14,
        v16_refresh={"reopening_decisions": []},
        delta16={
            "model_records": [],
            "regulatory_and_market_events": [],
            "capital_and_ownership_events": [],
            "governance_and_leadership_events": [],
        },
        v17_successor={"reopening_decisions": []},
        materialized_source_ids=_source_ids(),
    )
    assert result["ready_record_count"] == 0
    assert result["blocked_record_count"] == 0
    assert all(
        summary == {"record_count": 0, "ready_count": 0, "blocked_count": 0}
        for summary in result["family_summary"].values()
    )
    assert result["blocker_counts"] == {}
