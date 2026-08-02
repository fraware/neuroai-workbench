from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench.successor import (
    advance_release_gate,
    generate_from_observatory_release,
    generate_successor_candidate,
    reconcile_reopening_register,
    summarize_successor_candidate,
    validate_successor_candidate,
    verify_predecessor_reference,
)
from neuroai_workbench.util import canonical_json_bytes

ROOT = Path(__file__).resolve().parents[2]
SUCCESSOR = ROOT / "examples" / "observatory" / "canonical_successor_snapshot_v1.7.json"

AUTHORITY = {
    "name_or_role": "Release control reviewer",
    "authority_basis": "Local programme release checklist",
    "organization": "Local workflow",
    "accountability_state": "CLAIMED LOCAL IDENTITY ONLY",
}


def test_generate_candidate_from_v17_release():
    candidate = generate_from_observatory_release(SUCCESSOR, version="v1.7-candidate")
    summary = summarize_successor_candidate(candidate)
    assert summary["valid"] is True
    assert summary["current_gate"] == "CANDIDATE"
    assert summary["operation_count"] == 9
    assert len(candidate["withheld_claims"]) >= 3


def test_gate_progression_candidate_to_published():
    candidate = generate_from_observatory_release(SUCCESSOR, version="v1.8-candidate")
    reviewed, gate1 = advance_release_gate(
        candidate,
        target_gate="REVIEWED",
        authority_claim=AUTHORITY,
        rationale="Schema, predecessor hash, and reopening reconciliation reviewed.",
    )
    assert reviewed["metadata"]["status"] == "REVIEWED"
    authorized, gate2 = advance_release_gate(
        reviewed,
        target_gate="AUTHORIZED",
        authority_claim=AUTHORITY,
        rationale="Domain and security review complete for bounded delta.",
    )
    published, gate3 = advance_release_gate(
        authorized,
        target_gate="PUBLISHED",
        authority_claim={
            **AUTHORITY,
            "name_or_role": "Named release authority",
            "authority_basis": "Explicit release decision record",
        },
        rationale="Named release authority approves publication.",
    )
    assert published["metadata"]["status"] == "PUBLISHED"
    assert gate3["automatic_publication_performed"] is False
    assert len(published["release_gate"]["history"]) == 3


def test_gate_advancement_cannot_skip():
    candidate = generate_from_observatory_release(SUCCESSOR, version="v1.8-skip")
    with pytest.raises(ValueError, match="sequentially"):
        advance_release_gate(
            candidate,
            target_gate="AUTHORIZED",
            authority_claim=AUTHORITY,
            rationale="Attempted skip.",
        )


def test_predecessor_hash_mismatch_detected():
    candidate = generate_from_observatory_release(SUCCESSOR, version="v1.8-hash")
    errors = verify_predecessor_reference(candidate, b"tampered-predecessor-bytes")
    assert any(item["code"] == "PREDECESSOR_SHA256_MISMATCH" for item in errors)


def _strip_nondeterministic(candidate: dict) -> dict:
    payload = json.loads(json.dumps(candidate))
    metadata = payload.get("metadata", {})
    if isinstance(metadata, dict):
        metadata.pop("generated_at", None)
        metadata.pop("candidate_id", None)
        metadata.pop("canonical_sha256", None)
    register = payload.get("reopening_register", {})
    if isinstance(register, dict):
        recommendations = register.get("recommendations", [])
        if isinstance(recommendations, list):
            for item in recommendations:
                if isinstance(item, dict):
                    item.pop("recommendation_id", None)
    return payload


def test_candidate_bytes_are_deterministic():
    release = json.loads(SUCCESSOR.read_text(encoding="utf-8"))
    delta = release["delta"]
    kwargs = {
        "delta": delta,
        "version": "v1.8-det",
        "evidence_cutoff": "2026-07-29",
        "effective_as_of": "2026-07-29",
        "predecessor_sha256": "a" * 64,
        "actor": "deterministic-test",
    }
    first = _strip_nondeterministic(generate_successor_candidate(release, **kwargs))
    second = _strip_nondeterministic(generate_successor_candidate(release, **kwargs))
    assert canonical_json_bytes(first) == canonical_json_bytes(second)


def test_reconcile_reopening_register_reports_unresolved():
    candidate = generate_from_observatory_release(SUCCESSOR, version="v1.8-reopen")
    report = reconcile_reopening_register(candidate)
    assert report["counts"]["recommendations"] > 0
    assert report["counts"]["unresolved_material_recommendations"] >= 1


def test_tampered_candidate_sha256_fails_validation():
    candidate = generate_from_observatory_release(SUCCESSOR, version="v1.8-tamper")
    candidate["metadata"]["canonical_sha256"] = "0" * 64
    report = validate_successor_candidate(candidate)
    assert report["valid"] is False
    assert any(item["code"] == "CANDIDATE_SHA256_MISMATCH" for item in report["errors"])
