from __future__ import annotations

import pytest

from neuroai_workbench.observatory_delta_capital_migration import (
    DeltaCapitalMigrationError,
    materialize_delta16_capital_events,
)
from neuroai_workbench.observatory_gate_a_migration import (
    _expected_delta16_residual_keys,
    _expected_remaining_families,
    _residual_family_keys,
)
from neuroai_workbench.observatory_graph import build_entity
from neuroai_workbench.observatory_residual_migration import (
    MONITOR_REGISTRY_STATE,
    RESIDUAL_MIGRATION_BOUNDARY,
    RESIDUAL_POLICIES,
    SOURCE_REGISTER_DUPLICATE_STATE,
    ObservatoryResidualMigrationError,
    _preserve_family,
    _validate_source_refs,
    verify_residual_gate_a_state,
)


def _entity() -> dict:
    return build_entity(
        entity_id="ENT-SCI",
        entity_type="ORGANIZATION",
        canonical_label="Science Corporation",
    )


def _capital_record(event_id: str = "CAP-16-1") -> dict:
    return {
        "event_id": event_id,
        "date": "2026-03-05",
        "event_type": "EQUITY_FINANCING",
        "subject": "Science Corporation",
        "source_ids": ["SRC-1"],
        "boundary": "Company-announced financing; no valuation or control inference.",
    }


def test_delta_capital_rejects_container_and_record_shape_errors() -> None:
    with pytest.raises(DeltaCapitalMigrationError, match="capital_and_ownership_events array"):
        materialize_delta16_capital_events(
            {}, entities=[_entity()], known_source_ids={"SRC-1"}
        )
    with pytest.raises(DeltaCapitalMigrationError, match="must be an object"):
        materialize_delta16_capital_events(
            {"capital_and_ownership_events": ["bad"]},
            entities=[_entity()],
            known_source_ids={"SRC-1"},
        )


def test_delta_capital_rejects_required_fields_sources_and_dates() -> None:
    with pytest.raises(DeltaCapitalMigrationError, match="missing required fields"):
        materialize_delta16_capital_events(
            {"capital_and_ownership_events": [{}]},
            entities=[_entity()],
            known_source_ids={"SRC-1"},
        )

    invalid_refs = _capital_record()
    invalid_refs["source_ids"] = "SRC-1"
    with pytest.raises(DeltaCapitalMigrationError, match="source_ids are invalid"):
        materialize_delta16_capital_events(
            {"capital_and_ownership_events": [invalid_refs]},
            entities=[_entity()],
            known_source_ids={"SRC-1"},
        )

    missing_source = _capital_record()
    missing_source["source_ids"] = ["SRC-MISSING"]
    with pytest.raises(DeltaCapitalMigrationError, match="missing Sources"):
        materialize_delta16_capital_events(
            {"capital_and_ownership_events": [missing_source]},
            entities=[_entity()],
            known_source_ids={"SRC-1"},
        )

    missing_date = _capital_record()
    missing_date.pop("date")
    with pytest.raises(DeltaCapitalMigrationError, match="explicit date"):
        materialize_delta16_capital_events(
            {"capital_and_ownership_events": [missing_date]},
            entities=[_entity()],
            known_source_ids={"SRC-1"},
        )


def test_delta_capital_preserves_exact_identity_failure_and_duplicate_guard() -> None:
    with pytest.raises(DeltaCapitalMigrationError):
        materialize_delta16_capital_events(
            {"capital_and_ownership_events": [_capital_record()]},
            entities=[],
            known_source_ids={"SRC-1"},
        )

    first = _capital_record()
    second = _capital_record()
    with pytest.raises(DeltaCapitalMigrationError, match="duplicate delta16 capital event id"):
        materialize_delta16_capital_events(
            {"capital_and_ownership_events": [first, second]},
            entities=[_entity()],
            known_source_ids={"SRC-1"},
        )


def test_residual_source_reference_walk_is_recursive_and_fail_closed() -> None:
    payload = {
        "outer": [
            {"source_id": "SRC-MISSING"},
            {"nested": {"source_ids": ["SRC-OK", "SRC-MISSING-2"]}},
        ]
    }
    assert _validate_source_refs(payload, {"SRC-OK"}) == [
        "SRC-MISSING",
        "SRC-MISSING-2",
    ]

    with pytest.raises(ObservatoryResidualMigrationError, match="array of non-empty strings"):
        _validate_source_refs({"source_ids": [""]}, set())


def test_residual_family_preservation_rejects_unsafe_shapes_and_sources() -> None:
    with pytest.raises(ObservatoryResidualMigrationError, match="no governed residual policy"):
        _preserve_family(
            role="V14",
            family="unknown",
            payload=[],
            known_source_ids=set(),
        )
    with pytest.raises(ObservatoryResidualMigrationError, match="must be an array"):
        _preserve_family(
            role="V14",
            family="data_quality",
            payload={},
            known_source_ids=set(),
        )
    with pytest.raises(ObservatoryResidualMigrationError, match="entries must be objects"):
        _preserve_family(
            role="V14",
            family="data_quality",
            payload=["bad"],
            known_source_ids=set(),
        )
    with pytest.raises(ObservatoryResidualMigrationError, match="references missing Sources"):
        _preserve_family(
            role="V14",
            family="data_quality",
            payload=[{"source_ids": ["SRC-MISSING"]}],
            known_source_ids=set(),
        )

    preserved = _preserve_family(
        role="V14",
        family="data_quality",
        payload=[{"source_ids": ["SRC-1"]}],
        known_source_ids={"SRC-1"},
    )
    assert preserved["native_authority"] is False
    assert preserved["native_object_count"] == 0
    assert preserved["blocked_reason"] == RESIDUAL_POLICIES[("V14", "data_quality")]


def test_gate_a_delta_wildcard_requires_complete_actual_residual_set() -> None:
    expected_delta = _expected_delta16_residual_keys()
    assert expected_delta

    candidate = {
        "remaining_unmaterialized_families": [
            "DELTA16.*",
            *sorted(expected_delta),
            "V14.synthetic",
        ]
    }
    partial = {
        "residual_families": [
            {"role": "DELTA16", "family": key.split(".", 1)[1]}
            for key in sorted(expected_delta)[:-1]
        ]
    }
    partial_remaining = _expected_remaining_families(candidate, partial)
    assert "DELTA16.*" in partial_remaining

    complete = {
        "residual_families": [
            {"role": "DELTA16", "family": key.split(".", 1)[1]}
            for key in sorted(expected_delta)
        ]
    }
    complete_remaining = _expected_remaining_families(candidate, complete)
    assert "DELTA16.*" not in complete_remaining
    assert all(key not in complete_remaining for key in expected_delta)
    assert complete_remaining == ["V14.synthetic"]


def test_gate_a_residual_key_extraction_and_missing_candidate_ledger_fail_closed() -> None:
    residual = {
        "residual_families": [
            None,
            {"role": "DELTA16", "family": "model_records"},
            {"role": "DELTA16", "family": None},
        ]
    }
    assert _residual_family_keys(residual) == {"DELTA16.model_records"}
    assert _residual_family_keys({"residual_families": "bad"}) == set()
    assert _expected_remaining_families({}, residual) == [
        "CANDIDATE_REMAINING_FAMILY_LEDGER_MISSING"
    ]


def test_residual_verifier_reports_coordinated_tampering_without_authority_upgrade() -> None:
    state = {
        "state": "CANONICAL",
        "release_authorized": True,
        "native_object_count": 1,
        "boundary": "wrong",
        "residual_families": [
            None,
            {
                "role": "V14",
                "family": "data_quality",
                "blocked_reason": "wrong",
                "payload": [],
                "payload_sha256": "wrong",
                "record_count": 1,
                "native_object_count": 1,
                "native_authority": True,
            },
        ],
        "release_level_state": [
            None,
            {
                "migration_state": "wrong",
                "payload": {},
                "payload_sha256": "wrong",
                "native_object_count": 1,
                "native_authority": True,
            },
        ],
        "source_register_proof": {
            "migration_state": "wrong",
            "record_count": 0,
            "exact_duplicate": False,
            "source_register_sha256": "a",
            "v14_sources_sha256": "b",
        },
        "monitor_registry": {
            "migration_state": "wrong",
            "record_count": 0,
            "one_to_one_source_identity": False,
            "monitor_registry_sha256": "wrong",
            "payload": [],
            "native_object_count": 1,
            "native_authority": True,
        },
        "counts": {},
    }
    errors = verify_residual_gate_a_state(state, known_source_ids=set())
    text = "\n".join(errors)
    assert "noncanonical and unauthorized" in text
    assert "must not claim native objects" in text
    assert "boundary mismatch" in text
    assert "residual family policy mismatch" in text
    assert "residual family digest mismatch" in text
    assert "release-level migration_state mismatch" in text
    assert "source-register exact-duplicate proof failed" in text
    assert "monitor registry must remain one-to-one" in text
    assert "count reconciliation mismatch" in text


def test_residual_verifier_rejects_missing_collections() -> None:
    errors = verify_residual_gate_a_state(
        {
            "state": "NONCANONICAL_CANDIDATE",
            "release_authorized": False,
            "native_object_count": 0,
            "boundary": RESIDUAL_MIGRATION_BOUNDARY,
            "residual_families": [],
            "release_level_state": "bad",
            "source_register_proof": None,
            "monitor_registry": None,
            "counts": {
                "residual_family_count": 0,
                "residual_record_count": 0,
                "release_level_bundle_count": 0,
                "source_register_records": 0,
                "monitor_registry_records": 0,
            },
        },
        known_source_ids=set(),
    )
    assert "release_level_state must be an array" in errors
    assert "source_register_proof missing" in errors
    assert "monitor_registry missing" in errors


def test_residual_verifier_accepts_empty_structural_baseline() -> None:
    state = {
        "state": "NONCANONICAL_CANDIDATE",
        "release_authorized": False,
        "native_object_count": 0,
        "boundary": RESIDUAL_MIGRATION_BOUNDARY,
        "residual_families": [],
        "release_level_state": [],
        "source_register_proof": {
            "migration_state": SOURCE_REGISTER_DUPLICATE_STATE,
            "record_count": 0,
            "exact_duplicate": True,
            "source_register_sha256": "same",
            "v14_sources_sha256": "same",
        },
        "monitor_registry": {
            "migration_state": MONITOR_REGISTRY_STATE,
            "record_count": 0,
            "one_to_one_source_identity": True,
            "monitor_registry_sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e2f1f6d2f8f8f9f9f9f9f9f",
            "payload": [],
            "native_object_count": 0,
            "native_authority": False,
        },
        "counts": {
            "residual_family_count": 0,
            "residual_record_count": 0,
            "release_level_bundle_count": 0,
            "source_register_records": 0,
            "monitor_registry_records": 0,
        },
    }
    errors = verify_residual_gate_a_state(state, known_source_ids=set())
    assert any("monitor-registry payload digest mismatch" in error for error in errors)
    assert all("release-level" not in error for error in errors)
