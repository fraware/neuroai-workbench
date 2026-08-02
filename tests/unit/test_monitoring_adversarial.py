from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from neuroai_workbench import monitoring
from neuroai_workbench.monitoring import (
    adjudicate_change_candidate,
    build_refresh_candidate,
    create_change_candidate,
    initialize_monitoring,
    monitoring_status,
    normalize_source_registry,
    plan_monitoring_run,
    record_snapshot,
    validate_source_registry,
)
from neuroai_workbench.util import atomic_write_json, canonical_json_bytes, load_json, sha256_bytes


def source_record(source_id: str = "SRC-0001", monitor_id: str = "MON-SRC-0001") -> dict[str, object]:
    return {
        "monitor_id": monitor_id,
        "source_id": source_id,
        "url": "https://example.org/source",
        "publisher": "Example source",
        "source_class": "REGULATORY_RECORD",
        "cadence": "WEEKLY",
        "last_successful_retrieval": "2026-07-01",
        "baseline_evidence_state": "CURRENT_SOURCE_RETRIEVED",
        "baseline_verification_state": "CURRENT_VERIFIED",
        "baseline_claim_boundary": "Human adjudication controls every substantive effect.",
        "network_access_required": True,
        "current_status": "BASELINE_REGISTERED",
        "next_action": "RETRIEVE_AND_COMPARE",
    }


def write_registry(tmp_path: Path, records: list[object] | None = None) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "registry.json"
    atomic_write_json(path, records or [source_record()])
    return path


def initialized_workspace(tmp_path: Path, records: list[object] | None = None) -> Path:
    workspace = tmp_path / "workspace"
    initialize_monitoring(workspace, write_registry(tmp_path, records))
    return workspace


def test_registry_container_and_semantic_failures() -> None:
    with pytest.raises(ValueError, match="JSON object"):
        normalize_source_registry("not-a-registry")

    record = source_record()
    malformed = {
        "metadata": {
            "title": "Broken",
            "version": "1",
            "status": "BROKEN",
            "record_count": 5,
            "boundary": "boundary",
        },
        "sources": [
            "not-an-object",
            {
                **record,
                "monitor_id": "bad/id",
                "source_id": "bad/id",
                "cadence": "HOURLY",
                "url": "https://user:secret@example.org/private",
                "last_successful_retrieval": "not-a-date",
            },
            record,
            record,
        ],
    }
    result = validate_source_registry(malformed)
    codes = {item["code"] for item in result["errors"]}
    assert result["valid"] is False
    assert {
        "INVALID_IDENTIFIER",
        "UNSUPPORTED_CADENCE",
        "INVALID_PUBLIC_URL",
        "INVALID_RETRIEVAL_DATE",
        "DUPLICATE_MONITOR_ID",
        "DUPLICATE_SOURCE_ID",
        "RECORD_COUNT_MISMATCH",
    } <= codes

    result = validate_source_registry({"metadata": {}, "sources": {}})
    assert result["valid"] is False
    assert result["counts"] == {}


def test_initialization_and_state_integrity_fail_closed(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.json"
    atomic_write_json(invalid, [{"source_id": "ONLY"}])
    with pytest.raises(ValueError, match="Source registry is invalid"):
        initialize_monitoring(tmp_path / "invalid-workspace", invalid)

    workspace = initialized_workspace(tmp_path / "valid")
    state_path = workspace / "observatory" / "monitoring" / "state.json"
    state = load_json(state_path)
    state["registry_sha256"] = "0" * 64
    atomic_write_json(state_path, state)
    with pytest.raises(ValueError, match="registry hash"):
        monitoring_status(workspace)

    registry = load_json(workspace / "observatory" / "monitoring" / "registry" / "registry.json")
    state["registry_sha256"] = sha256_bytes(canonical_json_bytes(registry))
    state["sources"] = []
    atomic_write_json(state_path, state)
    with pytest.raises(ValueError, match="state sources"):
        plan_monitoring_run(workspace, as_of="2026-08-02")
    with pytest.raises(ValueError, match="state sources"):
        record_snapshot(workspace, "SRC-0001", b"content")


def test_plan_supports_manual_and_missing_baselines(tmp_path: Path) -> None:
    manual = {
        **source_record("SRC-0002", "MON-SRC-0002"),
        "cadence": "MANUAL",
        "last_successful_retrieval": None,
    }
    new_daily = {
        **source_record("SRC-0003", "MON-SRC-0003"),
        "cadence": "DAILY",
        "last_successful_retrieval": None,
    }
    workspace = initialized_workspace(tmp_path, [source_record(), manual, new_daily])
    plan = plan_monitoring_run(
        workspace,
        as_of=date(2026, 8, 2),
        source_ids=["SRC-0002", "SRC-0003"],
    )
    assert plan["counts"] == {"due": 1, "manual": 1, "not_due": 0}
    assert plan["manual"][0]["source_id"] == "SRC-0002"
    assert plan_monitoring_run(workspace)["as_of"]


def test_snapshot_refuses_invalid_inputs_and_tampering(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = initialized_workspace(tmp_path)
    with pytest.raises(ValueError, match="ISO-8601"):
        record_snapshot(workspace, "SRC-0001", b"content", retrieved_at="bad-time")
    with pytest.raises(ValueError, match="does not exist"):
        monitoring.record_snapshot_file(workspace, "SRC-0001", tmp_path / "missing.bin")

    snapshot = record_snapshot(workspace, "SRC-0001", b"\x00\x01", media_type="application/octet-stream")
    assert snapshot["normalized_text_sha256"] is None
    with pytest.raises(ValueError, match="Unknown snapshot"):
        monitoring.load_snapshot(workspace, "SRC-0001", "SNAP-MISSING")

    manifest_path = (
        workspace
        / "observatory"
        / "monitoring"
        / "snapshots"
        / "SRC-0001"
        / f"{snapshot['snapshot_id']}.json"
    )
    manifest = load_json(manifest_path)
    manifest["evidence_state"] = "UNSUPPORTED"
    atomic_write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="manifest is invalid"):
        monitoring.load_snapshot(workspace, "SRC-0001", snapshot["snapshot_id"])

    manifest["evidence_state"] = "RETRIEVED_BYTES_NOT_SUBSTANTIVELY_ADJUDICATED"
    atomic_write_json(manifest_path, manifest)
    (workspace / manifest["stored_path"]).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="bytes do not match"):
        monitoring.load_snapshot(workspace, "SRC-0001", snapshot["snapshot_id"])

    original_schema_errors = monitoring._schema_errors
    monkeypatch.setattr(
        monitoring,
        "_schema_errors",
        lambda value, schema: [{"code": "forced"}]
        if schema == monitoring.SNAPSHOT_SCHEMA
        else original_schema_errors(value, schema),
    )
    with pytest.raises(ValueError, match="Snapshot manifest failed validation"):
        record_snapshot(workspace, "SRC-0001", b"new")


def test_snapshot_manifest_conflict_is_immutable(tmp_path: Path) -> None:
    workspace = initialized_workspace(tmp_path)
    first = record_snapshot(
        workspace,
        "SRC-0001",
        b"same-bytes",
        media_type="text/plain",
        retrieved_at="2026-08-02T01:00:00Z",
    )
    with pytest.raises(ValueError, match="different metadata"):
        record_snapshot(
            workspace,
            "SRC-0001",
            b"same-bytes",
            media_type="text/plain",
            retrieved_at="2026-08-02T02:00:00Z",
        )
    assert first["snapshot_id"]


def test_candidate_and_adjudication_tamper_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = initialized_workspace(tmp_path)
    snapshot = record_snapshot(workspace, "SRC-0001", b"alpha", media_type="text/plain")
    candidate = create_change_candidate(workspace, "SRC-0001", snapshot["snapshot_id"], summary="Manual review")
    assert candidate["detection"]["classification"] == "MANUAL_CANDIDATE"

    with pytest.raises(ValueError, match="Unknown change candidate"):
        monitoring.load_change_candidate(workspace, "CAND-00000000000000000000000000000000")

    candidate_path = workspace / "observatory" / "monitoring" / "candidates" / f"{candidate['candidate_id']}.json"
    changed = load_json(candidate_path)
    changed["status"] = "AUTOMATICALLY_ACCEPTED"
    atomic_write_json(candidate_path, changed)
    with pytest.raises(ValueError, match="candidate is invalid"):
        monitoring.load_change_candidate(workspace, candidate["candidate_id"])

    workspace2 = initialized_workspace(tmp_path / "fresh")
    snapshot2 = record_snapshot(workspace2, "SRC-0001", b"alpha", media_type="text/plain")
    original_schema_errors = monitoring._schema_errors
    monkeypatch.setattr(
        monitoring,
        "_schema_errors",
        lambda value, schema: [{"code": "forced"}]
        if schema == monitoring.CANDIDATE_SCHEMA
        else original_schema_errors(value, schema),
    )
    with pytest.raises(ValueError, match="Change candidate failed validation"):
        create_change_candidate(workspace2, "SRC-0001", snapshot2["snapshot_id"])


def test_adjudication_rejects_invalid_inputs_and_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = initialized_workspace(tmp_path)
    snapshot = record_snapshot(workspace, "SRC-0001", b"alpha", media_type="text/plain")
    candidate = create_change_candidate(workspace, "SRC-0001", snapshot["snapshot_id"])
    cases = [
        ("INVALID", "MATERIAL", "NO_EFFECT", "r", "Unsupported adjudication decision"),
        ("REJECT", "INVALID", "NO_EFFECT", "r", "Unsupported materiality state"),
        ("REJECT", "MATERIAL", "INVALID", "r", "Unsupported reopening effect"),
        ("REJECT", "MATERIAL", "NO_EFFECT", " ", "rationale is required"),
    ]
    for decision, materiality, effect, rationale, match in cases:
        with pytest.raises(ValueError, match=match):
            adjudicate_change_candidate(
                workspace,
                candidate["candidate_id"],
                decision,
                rationale=rationale,
                materiality=materiality,
                reopening_effect=effect,
            )

    original_schema_errors = monitoring._schema_errors
    monkeypatch.setattr(
        monitoring,
        "_schema_errors",
        lambda value, schema: [{"code": "forced"}]
        if schema == monitoring.ADJUDICATION_SCHEMA
        else original_schema_errors(value, schema),
    )
    with pytest.raises(ValueError, match="adjudication failed validation"):
        adjudicate_change_candidate(
            workspace,
            candidate["candidate_id"],
            "REJECT",
            rationale="Not material.",
            materiality="NON_MATERIAL",
            reopening_effect="NO_EFFECT",
        )


def test_refresh_package_handles_unresolved_and_ignored_records(tmp_path: Path) -> None:
    workspace = initialized_workspace(tmp_path)
    snapshot = record_snapshot(workspace, "SRC-0001", b"alpha", media_type="text/plain")
    pending = create_change_candidate(workspace, "SRC-0001", snapshot["snapshot_id"])
    rejected = create_change_candidate(workspace, "SRC-0001", snapshot["snapshot_id"], summary="Second candidate")
    adjudicate_change_candidate(
        workspace,
        rejected["candidate_id"],
        "REJECT",
        rationale="No material change.",
        materiality="NON_MATERIAL",
        reopening_effect="NO_EFFECT",
    )
    candidate_dir = workspace / "observatory" / "monitoring" / "candidates"
    atomic_write_json(candidate_dir / "ignored-list.json", ["not", "a", "record"])
    result = build_refresh_candidate(workspace, "refresh-2026-09", "2026-09-01")
    assert result["package"]["counts"] == {
        "candidates": 2,
        "adjudications": 1,
        "accepted": 0,
        "unresolved": 1,
        "reopening_queue": 0,
    }
    assert result["package"]["unresolved_candidates"][0]["candidate_id"] == pending["candidate_id"]

    with pytest.raises(ValueError):
        build_refresh_candidate(workspace, "../escape", "2026-09-02")
    with pytest.raises(ValueError):
        build_refresh_candidate(workspace, "refresh-2026-10", "bad-date")
