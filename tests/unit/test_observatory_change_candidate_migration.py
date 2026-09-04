from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench.observatory_change_candidate_migration import (
    CHANGE_CANDIDATE_MIGRATION_BOUNDARY,
    MIGRATION_PROVENANCE_MODE,
    ObservatoryChangeCandidateMigrationError,
    materialize_v16_change_candidate,
    materialize_v16_change_candidates,
    verify_change_candidate_trace,
    write_change_candidate_migration_package,
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
    assert (
        verify_change_candidate_trace(
            candidate,
            trace,
            known_source_ids={"SRC-16-001"},
        )
        == []
    )


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


def _package_input() -> dict:
    return materialize_v16_change_candidates(
        {"change_candidates": [_candidate("CAND-PACKAGE", ["SRC-1"])]},
        known_source_ids={"SRC-1"},
    )


def test_change_candidate_package_writes_deterministic_complete_artifacts(tmp_path: Path) -> None:
    result = _package_input()
    first = tmp_path / "first"
    second = tmp_path / "second"
    kwargs = {
        "known_source_ids": {"SRC-1"},
        "v16_input_sha256": "a" * 64,
        "producer_commit": "b" * 40,
        "runtime_execution_pin": "c" * 40,
        "s2_predecessor_commit": "d" * 40,
        "observatory_graph_schema_version": "1",
    }

    package = write_change_candidate_migration_package(result, first, **kwargs)
    second_package = write_change_candidate_migration_package(result, second, **kwargs)

    assert package == second_package
    assert package["descriptor"]["package_type"] == "OBSERVATORY_V2_PREDECESSOR_CHANGE_CANDIDATE_MIGRATION"
    assert package["descriptor"]["object_count"] == 1
    assert package["descriptor"]["release_authorized"] is False
    assert package["descriptor"]["inputs"] == {"V16": "a" * 64}
    assert package["manifest"]["release_authorized"] is False
    assert {item["path"] for item in package["manifest"]["files"]} == {
        "candidates.jsonl",
        "predecessor-traces.jsonl",
    }

    candidate_lines = [
        json.loads(line) for line in (first / "candidates.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    trace_lines = [
        json.loads(line) for line in (first / "predecessor-traces.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert candidate_lines[0]["candidate_id"] == "CAND-PACKAGE"
    assert trace_lines[0]["native_object_id"] == "CAND-PACKAGE"
    assert json.loads((first / "descriptor.json").read_text(encoding="utf-8")) == package["descriptor"]
    assert json.loads((first / "manifest.json").read_text(encoding="utf-8")) == package["manifest"]
    for name in ("candidates.jsonl", "predecessor-traces.jsonl", "descriptor.json", "manifest.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_change_candidate_package_fails_closed_on_incomplete_or_tampered_input(tmp_path: Path) -> None:
    result = _package_input()
    kwargs = {
        "known_source_ids": {"SRC-1"},
        "v16_input_sha256": "a" * 64,
        "producer_commit": "b" * 40,
        "runtime_execution_pin": "c" * 40,
        "s2_predecessor_commit": "d" * 40,
    }

    noncanonical = dict(result)
    noncanonical["state"] = "CANONICAL"
    with pytest.raises(ObservatoryChangeCandidateMigrationError, match="must remain noncanonical"):
        write_change_candidate_migration_package(noncanonical, tmp_path / "noncanonical", **kwargs)

    missing_trace = dict(result)
    missing_trace["predecessor_traces"] = []
    with pytest.raises(ObservatoryChangeCandidateMigrationError, match="one trace per Candidate"):
        write_change_candidate_migration_package(missing_trace, tmp_path / "missing-trace", **kwargs)

    incomplete = dict(result)
    incomplete["input_record_count"] = 2
    with pytest.raises(ObservatoryChangeCandidateMigrationError, match="complete family materialization"):
        write_change_candidate_migration_package(incomplete, tmp_path / "incomplete", **kwargs)

    tampered = json.loads(json.dumps(result))
    tampered["candidates"][0]["status"] = "SUBSTITUTED"
    with pytest.raises(ObservatoryChangeCandidateMigrationError, match="verification failed"):
        write_change_candidate_migration_package(tampered, tmp_path / "tampered", **kwargs)

    non_object = json.loads(json.dumps(result))
    non_object["candidates"][0] = "not-an-object"
    with pytest.raises(ObservatoryChangeCandidateMigrationError, match="entries must be objects"):
        write_change_candidate_migration_package(non_object, tmp_path / "non-object", **kwargs)


def test_change_candidate_package_refuses_invalid_identity_or_schema_inputs(tmp_path: Path) -> None:
    result = _package_input()
    base = {
        "known_source_ids": {"SRC-1"},
        "v16_input_sha256": "a" * 64,
        "producer_commit": "b" * 40,
        "runtime_execution_pin": "c" * 40,
        "s2_predecessor_commit": "d" * 40,
    }

    for field, value in (
        ("v16_input_sha256", "A" * 64),
        ("producer_commit", "b" * 39),
        ("runtime_execution_pin", "g" * 40),
        ("s2_predecessor_commit", 123),
    ):
        kwargs = dict(base)
        kwargs[field] = value
        with pytest.raises(ObservatoryChangeCandidateMigrationError, match=field):
            write_change_candidate_migration_package(result, tmp_path / field, **kwargs)

    with pytest.raises(ObservatoryChangeCandidateMigrationError, match="schema_version must be non-empty"):
        write_change_candidate_migration_package(
            result,
            tmp_path / "schema",
            **base,
            observatory_graph_schema_version=" ",
        )
