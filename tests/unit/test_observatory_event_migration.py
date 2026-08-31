from __future__ import annotations

import pytest

from neuroai_workbench.observatory_event_migration import (
    EVENT_MIGRATION_BOUNDARY,
    MIGRATED_PREDECESSOR_VERIFICATION_STATE,
    ObservatoryEventMigrationError,
    exact_entity_name_index,
    materialize_v14_capital_event,
    materialize_v14_capital_events,
    resolve_exact_entity_name,
    verify_capital_event_trace,
)
from neuroai_workbench.observatory_graph import build_entity


def _entity(entity_id: str, label: str) -> dict:
    return build_entity(
        entity_id=entity_id,
        entity_type="COMPANY",
        canonical_label=label,
        status="ACTIVE",
    )


def _event(event_id: str = "CAP-1", subject: str = "Science Corporation") -> dict:
    return {
        "event_id": event_id,
        "date": "2026-03-05",
        "event_type": "EQUITY_FINANCING",
        "subject": subject,
        "counterparties": ["Investor A", "Investor B"],
        "amount": 230000000,
        "currency": "USD",
        "amount_state": "ANNOUNCED_EXACT",
        "ownership_effect": "UNRESOLVED",
        "source_ids": ["SRC-1"],
        "evidence_state": "COMPANY_ANNOUNCEMENT",
        "boundary": "Company-announced financing; no valuation or control inference.",
    }


def test_exact_name_resolution_requires_unique_controlled_entity() -> None:
    index = exact_entity_name_index(
        [_entity("ORG-1", "Science Corporation"), _entity("ORG-2", "Duplicate Name"), _entity("ORG-3", "Duplicate Name")]
    )
    assert resolve_exact_entity_name("Science Corporation", index) == "ORG-1"
    with pytest.raises(ObservatoryEventMigrationError, match="no exact materialized Entity match"):
        resolve_exact_entity_name("science corporation", index)
    with pytest.raises(ObservatoryEventMigrationError, match="ambiguous"):
        resolve_exact_entity_name("Duplicate Name", index)


def test_capital_event_preserves_subject_sources_and_unresolved_counterparties() -> None:
    entities = [_entity("ORG-1", "Science Corporation")]
    event, trace = materialize_v14_capital_event(
        _event(),
        record_index=0,
        entity_name_index=exact_entity_name_index(entities),
        known_source_ids={"SRC-1"},
    )

    assert event["event_id"] == "CAP-1"
    assert event["subject"]["kind"] == "RESOLVED_ENTITY_REFERENCE"
    assert event["subject"]["entity_id"] == "ORG-1"
    assert [item["kind"] for item in event["objects"]] == ["UNRESOLVED_LITERAL", "UNRESOLVED_LITERAL"]
    assert [item["value"] for item in event["objects"]] == ["Investor A", "Investor B"]
    assert event["source_ids"] == ["SRC-1"]
    assert event["observation_ids"] == []
    assert event["evidence_state"] == "COMPANY_ANNOUNCEMENT"
    assert event["verification_state"] == MIGRATED_PREDECESSOR_VERIFICATION_STATE
    assert event["occurred_at"]["precision"] == "DATE"
    assert event["boundary"] == EVENT_MIGRATION_BOUNDARY
    assert trace["predecessor_record"] == _event()
    assert trace["subject_entity_id"] == "ORG-1"
    assert verify_capital_event_trace(trace, expected_event_id="CAP-1", expected_subject_entity_id="ORG-1") == []


def test_capital_event_refuses_missing_subject_or_source_identity() -> None:
    index = exact_entity_name_index([_entity("ORG-1", "Science Corporation")])
    with pytest.raises(ObservatoryEventMigrationError, match="no exact materialized Entity match"):
        materialize_v14_capital_event(
            _event(subject="Unknown Organization"),
            record_index=0,
            entity_name_index=index,
            known_source_ids={"SRC-1"},
        )
    with pytest.raises(ObservatoryEventMigrationError, match="non-materialized Sources"):
        materialize_v14_capital_event(
            _event(),
            record_index=0,
            entity_name_index=index,
            known_source_ids=set(),
        )


def test_capital_event_trace_detects_predecessor_tampering() -> None:
    event, trace = materialize_v14_capital_event(
        _event(),
        record_index=0,
        entity_name_index=exact_entity_name_index([_entity("ORG-1", "Science Corporation")]),
        known_source_ids={"SRC-1"},
    )
    trace["predecessor_record"]["amount"] = 1
    assert "predecessor_record_sha256 mismatch" in verify_capital_event_trace(trace)
    assert event["event_id"] == "CAP-1"


def test_complete_capital_family_materializes_or_fails_closed() -> None:
    result = materialize_v14_capital_events(
        {"capital_and_ownership_events": [_event("CAP-1"), _event("CAP-2")]},
        entities=[_entity("ORG-1", "Science Corporation")],
        known_source_ids={"SRC-1"},
    )
    assert result["state"] == "NONCANONICAL_CANDIDATE"
    assert result["release_authorized"] is False
    assert result["input_record_count"] == 2
    assert result["object_count"] == 2
    assert result["predecessor_trace_count"] == 2

    with pytest.raises(ObservatoryEventMigrationError, match="duplicate predecessor capital event id"):
        materialize_v14_capital_events(
            {"capital_and_ownership_events": [_event("CAP-DUP"), _event("CAP-DUP")]},
            entities=[_entity("ORG-1", "Science Corporation")],
            known_source_ids={"SRC-1"},
        )
