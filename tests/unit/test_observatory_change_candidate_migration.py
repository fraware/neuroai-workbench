from __future__ import annotations

import pytest

from neuroai_workbench.observatory_change_candidate_migration import (
    CHANGE_CANDIDATE_MIGRATION_BOUNDARY,
    MIGRATION_PROVENANCE_MODE,
    ObservatoryChangeCandidateMigrationError,
    materialize_v16_change_candidate,
    materialize_v16_change_candidates,
    verify_change_candidate_trace,
)


def _candidate(candidate_id: str = "CAND-16-001", source_ids: list[str] | None = None) -> dict:
    return {
        "candidate_id": candidate_id,
        "event_date": "2026-07-22",
        "discovery_class": "PRE_CUTOFF_EVIDENCE_DISCOVERED_AFTER_FREEZE",
        "change_class": "REGULATORY_AND_MARKET_STATE_CHANGE",
        "subject": "PRIMA retinal prosthesis",
        "summary": "CE-mark and European commercial-launch announcement.",
        "source_ids": source_ids or ["SRC-16-001"],
        "materiality": "HIGH",
        "adjudication": "ACCEPT_WITH_EVIDENCE_BOUNDARY",
        "reopening": "SYSTEM_RECORD_REOPEN_REQUIRED",
    }


def test_change_candidate_preserves_exact_payload_and_adjudication() -> None:
    predecessor = _candidate()
    candidate, trace = materialize_v16_change_candidate(
        predecessor,
        record_index=0,
        known_source_ids={"SRC-16-001"},
    )

    assert candidate["candidate_id"] == predecessor["candidate_id"]
    assert candidate["candidate_class"] == predecessor["change_class"]
    assert candidate["status"] == predecessor["adjudication"]
    assert candidate["payload"] == predecessor
    assert candidate["provenance_mode"] == MIGRATION_PROVENANCE_MODE
    assert candidate["canonical_write_performed"] is False
    assert candidate["boundary"] == CHANGE_CANDIDATE_MIGRATION_BOUNDARY
    assert trace["predecessor_record"] == predecessor
    assert verify_change_candidate_trace(
        candidate,
        trace,
        known_source_ids={"SRC-16-001"},
    ) == []


def test_change_candidate_does_not_resolve_free_text_subject() -> None:
    candidate, _ = materialize_v16_change_candidate(
        _candidate(),
        record_index=0,
        known_source_ids={"SRC-16-001"},
    )
    assert candidate["payload"]["subject"] == "PRIMA retinal prosthesis"
    assert "subject" not in {key for key in candidate if key != "payload"}


def test_change_candidate_requires_source_binding() -> None:
    with pytest.raises(ObservatoryChangeCandidateMigrationError, match="non-materialized Sources"):
        materialize_v16_change_candidate(
            _candidate(source_ids=["SRC-MISSING"]),
            record_index=0,
            known_source_ids={"SRC-16-001"},
        )


def test_verifier_detects_native_or_predecessor_tampering() -> None:
    candidate, trace = materialize_v16_change_candidate(
        _candidate(),
        record_index=0,
        known_source_ids={"SRC-16-001"},
    )
    candidate["status"] = "SUBSTITUTED"
    assert "candidate status/adjudication binding mismatch" in verify_change_candidate_trace(
        candidate,
        trace,
        known_source_ids={"SRC-16-001"},
    )

    candidate, trace = materialize_v16_change_candidate(
        _candidate(),
        record_index=0,
        known_source_ids={"SRC-16-001"},
    )
    trace["predecessor_record"]["summary"] = "Tampered"
    errors = verify_change_candidate_trace(candidate, trace, known_source_ids={"SRC-16-001"})
    assert "predecessor_record_sha256 mismatch" in errors
    assert "Candidate.payload must equal exact predecessor record" in errors


def test_complete_change_candidate_family_materializes_or_fails_closed() -> None:
    result = materialize_v16_change_candidates(
        {
            "change_candidates": [
                _candidate("CAND-1", ["SRC-1"]),
                _candidate("CAND-2", ["SRC-2"]),
            ]
        },
        known_source_ids={"SRC-1", "SRC-2"},
    )
    assert result["state"] == "NONCANONICAL_CANDIDATE"
    assert result["release_authorized"] is False
    assert result["input_record_count"] == 2
    assert result["object_count"] == 2
    assert result["predecessor_trace_count"] == 2

    with pytest.raises(ObservatoryChangeCandidateMigrationError, match="duplicate predecessor change candidate id"):
        materialize_v16_change_candidates(
            {"change_candidates": [_candidate("CAND-DUP"), _candidate("CAND-DUP")]},
            known_source_ids={"SRC-16-001"},
        )
