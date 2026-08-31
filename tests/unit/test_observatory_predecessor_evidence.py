from __future__ import annotations

import json

import pytest

from neuroai_workbench.observatory_predecessor_evidence import (
    PREDECESSOR_OBSERVATION_BOUNDARY,
    PREDECESSOR_OBSERVATION_TRANSPORT_UNRESOLVED,
    PredecessorObservationEvidenceError,
    preserve_source_check,
    preserve_v16_source_checks,
    verify_preserved_source_check,
    write_predecessor_observation_evidence_package,
)
from neuroai_workbench.util import canonical_json_bytes, sha256_bytes


def _check(check_id: str = "CHK-1", source_id: str = "SRC-1") -> dict:
    return {
        "check_id": check_id,
        "source_id": source_id,
        "retrieved": "2026-07-29T12:38:00Z",
        "retrieval_outcome": "SUCCESS_VIA_WEB_RESEARCH",
        "baseline_match": "NEW_SOURCE_OR_BACKFILL",
        "page_content_hash": "NOT_AVAILABLE_FROM_WEB_RESEARCH_INTERFACE",
        "metadata_digest": "a" * 64,
    }


def test_source_check_preserves_knowledge_time_without_transport_invention() -> None:
    predecessor = _check()
    evidence = preserve_source_check(predecessor, record_index=2)

    assert evidence["migration_state"] == PREDECESSOR_OBSERVATION_TRANSPORT_UNRESOLVED
    assert evidence["source_id"] == "SRC-1"
    assert evidence["observed_at"]["value"] == "2026-07-29T12:38:00Z"
    assert evidence["observed_at"]["precision"] == "TIMESTAMP"
    assert evidence["predecessor_retrieval_outcome"] == "SUCCESS_VIA_WEB_RESEARCH"
    assert evidence["unresolved_native_observation_fields"] == ["retrieval_method", "requested_locator"]
    assert "retrieval_method" not in evidence
    assert "requested_locator" not in evidence
    assert evidence["native_observation_created"] is False
    assert evidence["native_authority"] is False
    assert evidence["boundary"] == PREDECESSOR_OBSERVATION_BOUNDARY
    assert evidence["predecessor_record"] == predecessor
    assert verify_preserved_source_check(evidence) == []


def test_source_check_rejects_unreviewed_field_shape() -> None:
    predecessor = _check()
    predecessor["new_field"] = "unreviewed"
    with pytest.raises(PredecessorObservationEvidenceError, match="unreviewed source-check fields"):
        preserve_source_check(predecessor, record_index=0)

    predecessor = _check()
    predecessor.pop("metadata_digest")
    with pytest.raises(PredecessorObservationEvidenceError, match="source-check fields missing"):
        preserve_source_check(predecessor, record_index=0)


def test_source_check_requires_exact_timestamp_and_metadata_digest() -> None:
    predecessor = _check()
    predecessor["retrieved"] = "2026-07-29"
    with pytest.raises(Exception):
        preserve_source_check(predecessor, record_index=0)

    predecessor = _check()
    predecessor["metadata_digest"] = "not-a-digest"
    with pytest.raises(PredecessorObservationEvidenceError, match="metadata_digest"):
        preserve_source_check(predecessor, record_index=0)


def test_verifier_detects_transport_fabrication_and_tampering() -> None:
    evidence = preserve_source_check(_check(), record_index=0)

    fabricated = {**evidence, "retrieval_method": "HTTP_GET"}
    assert "unresolved transport fields must not be populated in migration evidence" in verify_preserved_source_check(
        fabricated
    )

    elevated = {**evidence, "native_observation_created": True}
    assert "native_observation_created must remain false" in verify_preserved_source_check(elevated)

    tampered = {**evidence, "predecessor_record": {**evidence["predecessor_record"], "baseline_match": "CHANGED"}}
    assert "predecessor_record_sha256 mismatch" in verify_preserved_source_check(tampered)


def test_v16_source_checks_must_bind_materialized_sources_one_to_one() -> None:
    result = preserve_v16_source_checks(
        {"source_checks": [_check("CHK-1", "SRC-1"), _check("CHK-2", "SRC-2")]},
        known_source_ids={"SRC-1", "SRC-2"},
    )
    assert result["state"] == "NONCANONICAL_CANDIDATE"
    assert result["release_authorized"] is False
    assert result["native_observation_count"] == 0
    assert result["predecessor_observation_evidence_count"] == 2
    assert result["transport_unresolved_count"] == 2

    with pytest.raises(PredecessorObservationEvidenceError, match="non-materialized Source SRC-X"):
        preserve_v16_source_checks(
            {"source_checks": [_check("CHK-X", "SRC-X")]},
            known_source_ids={"SRC-1"},
        )

    with pytest.raises(PredecessorObservationEvidenceError, match="multiple predecessor source checks"):
        preserve_v16_source_checks(
            {"source_checks": [_check("CHK-1", "SRC-1"), _check("CHK-2", "SRC-1")]},
            known_source_ids={"SRC-1"},
        )


def test_predecessor_observation_package_is_deterministic(tmp_path) -> None:
    result = preserve_v16_source_checks(
        {"source_checks": [_check()]},
        known_source_ids={"SRC-1"},
    )
    first = write_predecessor_observation_evidence_package(
        result,
        tmp_path / "first",
        v16_input_sha256="a" * 64,
        producer_commit="b" * 40,
        runtime_execution_pin="c" * 40,
        s2_predecessor_commit="d" * 40,
    )
    second = write_predecessor_observation_evidence_package(
        result,
        tmp_path / "second",
        v16_input_sha256="a" * 64,
        producer_commit="b" * 40,
        runtime_execution_pin="c" * 40,
        s2_predecessor_commit="d" * 40,
    )

    assert first == second
    for filename in ("predecessor-observation-evidence.jsonl", "descriptor.json", "manifest.json"):
        assert (tmp_path / "first" / filename).read_bytes() == (tmp_path / "second" / filename).read_bytes()

    manifest = json.loads((tmp_path / "first" / "manifest.json").read_text(encoding="utf-8"))
    controlled = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    assert manifest["manifest_sha256"] == sha256_bytes(canonical_json_bytes(controlled))
    assert manifest["release_authorized"] is False


def test_package_refuses_native_observation_upgrade(tmp_path) -> None:
    result = preserve_v16_source_checks(
        {"source_checks": [_check()]},
        known_source_ids={"SRC-1"},
    )
    result["native_observation_count"] = 1
    with pytest.raises(PredecessorObservationEvidenceError, match="cannot claim native Observations"):
        write_predecessor_observation_evidence_package(
            result,
            tmp_path / "bad",
            v16_input_sha256="a" * 64,
            producer_commit="b" * 40,
            runtime_execution_pin="c" * 40,
            s2_predecessor_commit="d" * 40,
        )
