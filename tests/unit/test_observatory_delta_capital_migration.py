from __future__ import annotations

import pytest

from neuroai_workbench.observatory_delta_capital_migration import (
    DELTA_CAPITAL_BOUNDARY,
    PREDECESSOR_EVIDENCE_STATE_UNSPECIFIED,
    PREDECESSOR_VERIFICATION_STATE_UNSPECIFIED,
    DeltaCapitalMigrationError,
    materialize_delta16_capital_events,
    verify_delta_capital_event,
)
from neuroai_workbench.observatory_graph import build_entity


def _entity(entity_id: str, label: str) -> dict:
    return build_entity(
        entity_id=entity_id,
        entity_type="COMPANY",
        canonical_label=label,
        status="ACTIVE",
    )


def _event(event_id: str = "CAP-16-001", subject: str = "Science Corporation") -> dict:
    return {
        "event_id": event_id,
        "date": "2026-03-05",
        "event_type": "EQUITY_FINANCING",
        "subject": subject,
        "amount": 230000000,
        "currency": "USD",
        "source_ids": ["SRC-16-004"],
        "boundary": "Company-announced financing; no valuation or control inference.",
    }


def test_delta_capital_event_materializes_without_inventing_evidence() -> None:
    entities = [_entity("ORG-1", "Science Corporation")]
    result = materialize_delta16_capital_events(
        {"capital_and_ownership_events": [_event()]},
        entities=entities,
        known_source_ids={"SRC-16-004"},
    )
    event = result["events"][0]
    trace = result["predecessor_traces"][0]

    assert event["subject"]["entity_id"] == "ORG-1"
    assert event["objects"] == []
    assert event["observation_ids"] == []
    assert event["evidence_state"] == PREDECESSOR_EVIDENCE_STATE_UNSPECIFIED
    assert event["verification_state"] == PREDECESSOR_VERIFICATION_STATE_UNSPECIFIED
    assert event["occurred_at"]["precision"] == "DATE"
    assert event["occurred_at"]["value"] == "2026-03-05"
    assert event["boundary"] == DELTA_CAPITAL_BOUNDARY
    assert trace["predecessor_record"] == _event()
    assert verify_delta_capital_event(
        event,
        trace,
        entity_index={"ORG-1": entities[0]},
        known_source_ids={"SRC-16-004"},
    ) == []


def test_delta_capital_family_requires_exact_entity_and_source_bindings() -> None:
    entities = [_entity("ORG-1", "Science Corporation")]
    with pytest.raises(DeltaCapitalMigrationError, match="no exact materialized Entity match"):
        materialize_delta16_capital_events(
            {"capital_and_ownership_events": [_event(subject="Unknown") ]},
            entities=entities,
            known_source_ids={"SRC-16-004"},
        )
    with pytest.raises(DeltaCapitalMigrationError, match="missing Sources"):
        materialize_delta16_capital_events(
            {"capital_and_ownership_events": [_event()]},
            entities=entities,
            known_source_ids=set(),
        )


def test_delta_capital_verifier_detects_mapped_field_tampering() -> None:
    entities = [_entity("ORG-1", "Science Corporation")]
    result = materialize_delta16_capital_events(
        {"capital_and_ownership_events": [_event()]},
        entities=entities,
        known_source_ids={"SRC-16-004"},
    )
    event = result["events"][0]
    trace = result["predecessor_traces"][0]

    tampered = dict(event)
    tampered["claim_boundary"] = "Broader claim"
    errors = verify_delta_capital_event(
        tampered,
        trace,
        entity_index={"ORG-1": entities[0]},
        known_source_ids={"SRC-16-004"},
    )
    assert "claim_boundary binding mismatch" in errors

    trace["predecessor_record"]["amount"] = 1
    errors = verify_delta_capital_event(
        event,
        trace,
        entity_index={"ORG-1": entities[0]},
        known_source_ids={"SRC-16-004"},
    )
    assert "predecessor_record_sha256 mismatch" in errors


def test_delta_capital_duplicate_ids_fail_closed() -> None:
    entities = [_entity("ORG-1", "Science Corporation")]
    with pytest.raises(DeltaCapitalMigrationError, match="duplicate delta16 capital event id"):
        materialize_delta16_capital_events(
            {"capital_and_ownership_events": [_event("CAP-X"), _event("CAP-X")]},
            entities=entities,
            known_source_ids={"SRC-16-004"},
        )
