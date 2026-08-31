from __future__ import annotations

from pathlib import Path

import pytest

from neuroai_workbench.observatory_graph import (
    GRAPH_BOUNDARY,
    KIND_RESOLVED_ENTITY_REFERENCE,
    build_entity,
    persistable,
)
from neuroai_workbench.release.compiler import ReleaseCompiler


def _entity(entity_id: str, label: str) -> dict:
    return persistable(build_entity(entity_id=entity_id, entity_type="SYSTEM", canonical_label=label))


def test_compiler_mechanical_pass_does_not_authorize(tmp_path: Path) -> None:
    result = ReleaseCompiler().build(
        [_entity("ENT-A", "A")],
        tmp_path / "candidate",
        candidate_id="CAND-REL-1",
        producer_commit="cbd756bd3a5be21e697605be01ab95d5392e3281",
        runtime_execution_pin="cbd756bd3a5be21e697605be01ab95d5392e3281",
    )
    assert result["descriptor"]["mechanical_verification"] == "PASS"
    assert result["descriptor"]["release_authorized"] is False
    assert result["pending_attestation"]["software_inferred_pass"] is False
    assert all(item["state"] == "PENDING" for item in result["pending_attestation"]["track_assessments"])
    assert (tmp_path / "candidate" / "descriptor.json").is_file()
    assert (tmp_path / "candidate" / "manifest.json").is_file()
    assert (tmp_path / "candidate" / "SHA256SUMS").is_file()
    assert (tmp_path / "candidate" / "verification_report.json").is_file()
    assert (tmp_path / "candidate" / "attestation" / "pending_attestation.json").is_file()


def test_dangling_refs_and_duplicate_ids_block(tmp_path: Path) -> None:
    from neuroai_workbench.observatory_graph import build_observation
    from neuroai_workbench.temporal import TIME_VALUE_BOUNDARY

    observation = persistable(
        build_observation(
            observation_id="OBS-DANGLE",
            source_id="SRC-MISSING",
            observed_at={"value": "2026-08-31T12:00:00Z", "precision": "TIMESTAMP", "boundary": TIME_VALUE_BOUNDARY},
            retrieval_method="HTTP_GET",
            retrieval_outcome="RETRIEVED",
            requested_locator="https://example.org/x",
        )
    )
    dangling = ReleaseCompiler().build([observation], tmp_path / "dangle", candidate_id="CAND-DANGLE")
    assert dangling["verification"]["mechanical_verification"] == "FAIL"
    assert any(item["code"] == "DANGLING_REF" for item in dangling["verification"]["blockers"])
    assert dangling["descriptor"]["release_authorized"] is False

    duplicate = ReleaseCompiler().build(
        [_entity("ENT-DUP", "One"), {**_entity("ENT-DUP", "Two"), "canonical_label": "Two"}],
        tmp_path / "dup",
        candidate_id="CAND-DUP",
    )
    # Second persistable recomputes digest; duplicate id still detected.
    assert any(item["code"] == "DUPLICATE_ID" for item in duplicate["verification"]["blockers"])


def test_protected_byte_scan_and_count_mismatch(tmp_path: Path) -> None:
    dirty = _entity("ENT-DIRTY", "label")
    dirty["canonical_label"] = "-----BEGIN RSA PRIVATE KEY----- abc"
    from neuroai_workbench.observatory_graph.digest import attach_digest

    dirty = attach_digest({key: value for key, value in dirty.items() if key != "canonical_sha256"})
    scanned = ReleaseCompiler().build([dirty], tmp_path / "scan", candidate_id="CAND-SCAN")
    assert any(item["code"] == "PROTECTED_BYTE_SCAN" for item in scanned["verification"]["blockers"])

    mismatch = ReleaseCompiler().build(
        [_entity("ENT-C", "C")],
        tmp_path / "mismatch",
        candidate_id="CAND-MISMATCH",
        declared_counts={"Entity": 99},
    )
    assert any(item["code"] == "SEMANTIC_COUNT_MISMATCH" for item in mismatch["verification"]["blockers"])


def test_manifest_tamper_and_attestation_digest_binding(tmp_path: Path) -> None:
    result = ReleaseCompiler().build([_entity("ENT-T", "T")], tmp_path / "bind", candidate_id="CAND-BIND")
    manifest = result["manifest"]
    pending = result["pending_attestation"]
    assert pending["manifest_sha256"] == manifest["manifest_sha256"]
    tampered = {**manifest, "files": []}
    from neuroai_workbench.util import canonical_json_bytes, sha256_bytes

    assert (
        sha256_bytes(canonical_json_bytes({k: v for k, v in tampered.items() if k != "manifest_sha256"}))
        != manifest["manifest_sha256"]
    )


def test_unresolved_subject_cannot_enter_compiler_via_literal() -> None:
    from neuroai_workbench.observatory_graph import UnresolvedLiteralError, build_assertion

    with pytest.raises(UnresolvedLiteralError):
        build_assertion(
            assertion_id="AST-LIT",
            subject={"kind": "UNRESOLVED_LITERAL", "value": "a hospital", "boundary": GRAPH_BOUNDARY},
            predicate="TRIAL_AT",
            value="guessed",
            evidence_state="UNSUPPORTED",
            verification_state="UNVERIFIED",
            review_state="NOT_REVIEWED",
            claim_boundary=GRAPH_BOUNDARY,
        )
    _ = KIND_RESOLVED_ENTITY_REFERENCE


def test_unknown_object_class_is_mechanical_fail(tmp_path: Path) -> None:
    result = ReleaseCompiler().build(
        [{"object_class": "NotAClass", "entity_id": "x"}],
        tmp_path / "unknown",
        candidate_id="CAND-UNKNOWN",
    )
    assert result["verification"]["mechanical_verification"] == "FAIL"
    assert any(item["code"] == "SCHEMA_INVALID" for item in result["verification"]["blockers"])
    assert result["descriptor"]["release_authorized"] is False


def test_dangling_resolved_refs_and_schema_invalid_records(tmp_path: Path) -> None:
    from neuroai_workbench.observatory_graph import build_assertion, build_relationship

    entity = _entity("ENT-REF", "Ref")
    dangling_assertion = build_assertion(
        assertion_id="AST-REF",
        subject={"kind": KIND_RESOLVED_ENTITY_REFERENCE, "entity_id": "ENT-MISSING", "boundary": GRAPH_BOUNDARY},
        predicate="STATUS",
        value="X",
        evidence_state="SOURCE_STATED",
        verification_state="UNVERIFIED",
        review_state="NOT_REVIEWED",
        claim_boundary="b",
    )
    result = ReleaseCompiler().build(
        [entity, dangling_assertion],
        tmp_path / "dangle-subject",
        candidate_id="CAND-SUBJ",
    )
    assert any(item["code"] == "DANGLING_REF" for item in result["verification"]["blockers"])

    rel = build_relationship(
        relationship_id="REL-REF",
        relationship_type="RELATED_TO",
        subject={"kind": KIND_RESOLVED_ENTITY_REFERENCE, "entity_id": "ENT-REF", "boundary": GRAPH_BOUNDARY},
        object_ref={"kind": KIND_RESOLVED_ENTITY_REFERENCE, "entity_id": "ENT-MISSING", "boundary": GRAPH_BOUNDARY},
        evidence_state="SOURCE_STATED",
        claim_boundary="b",
    )
    rel_result = ReleaseCompiler().build(
        [entity, rel],
        tmp_path / "dangle-object",
        candidate_id="CAND-OBJ",
    )
    assert any(item["code"] == "DANGLING_REF" for item in rel_result["verification"]["blockers"])

    schema_fail = ReleaseCompiler().build(
        [{"object_class": "Entity", "entity_id": "ENT-BAD"}],
        tmp_path / "schema-fail",
        candidate_id="CAND-SCHEMA",
    )
    assert any(item["code"] == "SCHEMA_INVALID" for item in schema_fail["verification"]["blockers"])
    assert schema_fail["descriptor"]["release_authorized"] is False
