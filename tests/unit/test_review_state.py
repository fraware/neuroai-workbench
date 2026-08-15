from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from neuroai_workbench.monitoring import create_change_candidate, initialize_monitoring, record_snapshot
from neuroai_workbench.review_queue import (
    claim_lease,
    initialize_review_queue,
    register_reviewer_profile,
    release_lease,
    submit_opinion,
)
from neuroai_workbench.review_state import (
    REVIEW_STATE_SNAPSHOT_VERSION,
    build_review_state_snapshot,
    verify_review_state_snapshot,
)
from neuroai_workbench.util import atomic_write_json, canonical_json_bytes, sha256_bytes
from neuroai_workbench.workspace import Workspace


def _source_record() -> dict[str, object]:
    return {
        "monitor_id": "MON-SRC-0001",
        "source_id": "SRC-0001",
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


def _resign(snapshot: dict[str, Any]) -> None:
    controlled = {key: value for key, value in snapshot.items() if key != "snapshot_sha256"}
    snapshot["snapshot_sha256"] = sha256_bytes(canonical_json_bytes(controlled))


def _review_workspace(tmp_path: Path, *, release: bool = True) -> tuple[Workspace, dict[str, Any]]:
    registry = tmp_path / "registry.json"
    atomic_write_json(registry, [_source_record()])
    workspace = Workspace.initialize(tmp_path / "workspace")
    initialize_monitoring(workspace.root, registry)
    initialize_review_queue(workspace.root, actor="tester")
    register_reviewer_profile(
        workspace.root,
        "reviewer-b",
        "Reviewer B",
        ["OBSERVER", "MONITORING_REVIEWER"],
        actor="tester",
    )
    register_reviewer_profile(
        workspace.root,
        "reviewer-a",
        "Reviewer A",
        ["MONITORING_REVIEWER"],
        actor="tester",
    )
    first = record_snapshot(workspace.root, "SRC-0001", b"alpha", media_type="text/plain")
    second = record_snapshot(workspace.root, "SRC-0001", b"beta", media_type="text/plain")
    candidate = create_change_candidate(
        workspace.root,
        "SRC-0001",
        second["snapshot_id"],
        previous_snapshot_id=first["snapshot_id"],
        summary="Synthetic review-state snapshot fixture.",
    )
    item_id = f"RQI-{candidate['candidate_id']}"
    lease = claim_lease(workspace.root, item_id, "reviewer-a", ttl_seconds=3600, actor="tester")
    opinion = submit_opinion(
        workspace.root,
        item_id,
        "reviewer-a",
        "NEEDS_EVIDENCE",
        "Verify the source transition before substantive disposition.",
        actor="tester",
    )
    release_record = None
    if release:
        release_record = release_lease(
            workspace.root,
            lease["lease"]["lease_id"],
            "reviewer-a",
            reason="RELEASED",
            actor="tester",
        )
    return workspace, {
        "candidate": candidate,
        "lease": lease,
        "opinion": opinion,
        "release": release_record,
    }


def test_snapshot_is_deterministic_content_addressed_and_complete(tmp_path: Path) -> None:
    workspace, _ = _review_workspace(tmp_path)

    first = build_review_state_snapshot(workspace.root)
    second = build_review_state_snapshot(workspace.root)

    assert first == second
    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert first["snapshot_version"] == REVIEW_STATE_SNAPSHOT_VERSION
    assert first["source_integrity"] == "VERIFIED"
    assert first["authority_profile"] == "LOCAL_READ_MODEL_NO_AUTHORITY"
    assert first["counts"] == {
        "profiles": 2,
        "queue_items": 1,
        "leases": 1,
        "lease_releases": 1,
        "opinions": 1,
    }
    assert first["event_chain"]["event_count"] >= 6
    assert len(first["event_chain"]["head_hash"]) == 64
    assert [item["profile_id"] for item in first["records"]["profiles"]] == ["reviewer-a", "reviewer-b"]
    assert "_path" not in json.dumps(first)
    assert verify_review_state_snapshot(first)["valid"] is True


def test_snapshot_is_independent_of_wall_clock_lease_activity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, _ = _review_workspace(tmp_path, release=False)
    first = build_review_state_snapshot(workspace.root)

    monkeypatch.setattr("neuroai_workbench.review_queue.utc_now", lambda: "2035-01-01T00:00:00Z")
    second = build_review_state_snapshot(workspace.root)

    assert first == second
    assert first["counts"]["leases"] == 1
    assert first["counts"]["lease_releases"] == 0


def test_builder_refuses_uninitialized_review_state(tmp_path: Path) -> None:
    workspace = Workspace.initialize(tmp_path / "workspace")
    with pytest.raises(ValueError, match="Review queue integrity verification failed"):
        build_review_state_snapshot(workspace.root)


def test_builder_refuses_stored_hash_corruption(tmp_path: Path) -> None:
    workspace, records = _review_workspace(tmp_path)
    opinion_path = Path(records["opinion"]["path"])
    opinion = json.loads(opinion_path.read_text(encoding="utf-8"))
    opinion["rationale"] = "Tampered rationale"
    atomic_write_json(opinion_path, opinion)

    with pytest.raises(ValueError, match="Review queue integrity verification failed"):
        build_review_state_snapshot(workspace.root)


def test_builder_refuses_hidden_internal_fields(tmp_path: Path) -> None:
    workspace, _ = _review_workspace(tmp_path)
    profile_path = workspace.root / "observatory" / "review_queue" / "profiles" / "reviewer-a.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile["_secret"] = "must never cross the snapshot boundary"
    atomic_write_json(profile_path, profile)

    with pytest.raises(ValueError, match="Internal field .*_secret"):
        build_review_state_snapshot(workspace.root)


def test_builder_refuses_non_object_stored_record(tmp_path: Path) -> None:
    workspace, _ = _review_workspace(tmp_path)
    malformed = workspace.root / "observatory" / "review_queue" / "profiles" / "zz-malformed.json"
    malformed.write_text("[]\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Stored review record must be a JSON object"):
        build_review_state_snapshot(workspace.root)


def test_builder_refuses_second_event_chain_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, _ = _review_workspace(tmp_path)
    monkeypatch.setattr(
        "neuroai_workbench.review_state.verify_chain",
        lambda _path: {"valid": False, "errors": ["synthetic failure"]},
    )

    with pytest.raises(ValueError, match="Review event-chain verification failed: synthetic failure"):
        build_review_state_snapshot(workspace.root)


def test_builder_fails_if_generated_snapshot_does_not_self_verify(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, _ = _review_workspace(tmp_path)
    monkeypatch.setattr(
        "neuroai_workbench.review_state.verify_review_state_snapshot",
        lambda _snapshot: {"valid": False, "errors": ["synthetic self-check failure"]},
    )

    with pytest.raises(ValueError, match="Generated review-state snapshot is invalid"):
        build_review_state_snapshot(workspace.root)


def test_verifier_rejects_non_object_and_snapshot_digest_tampering(tmp_path: Path) -> None:
    assert verify_review_state_snapshot([])["valid"] is False

    workspace, _ = _review_workspace(tmp_path)
    snapshot = build_review_state_snapshot(workspace.root)
    snapshot["snapshot_sha256"] = "0" * 64
    result = verify_review_state_snapshot(snapshot)

    assert result["valid"] is False
    assert "snapshot_sha256 mismatch" in result["errors"]


def test_verifier_rejects_schema_and_count_tampering_after_resign(tmp_path: Path) -> None:
    workspace, _ = _review_workspace(tmp_path)
    snapshot = build_review_state_snapshot(workspace.root)
    snapshot["snapshot_version"] = "2"
    snapshot["counts"]["profiles"] += 1
    _resign(snapshot)

    result = verify_review_state_snapshot(snapshot)

    assert result["valid"] is False
    assert any("schema:" in error and "snapshot_version" in error for error in result["errors"])
    assert "counts.profiles does not match records.profiles" in result["errors"]


def test_verifier_rejects_record_reordering_and_duplicates_after_resign(tmp_path: Path) -> None:
    workspace, _ = _review_workspace(tmp_path)
    snapshot = build_review_state_snapshot(workspace.root)
    snapshot["records"]["profiles"].reverse()
    duplicate = copy.deepcopy(snapshot["records"]["profiles"][0])
    snapshot["records"]["profiles"].append(duplicate)
    snapshot["counts"]["profiles"] = len(snapshot["records"]["profiles"])
    _resign(snapshot)

    result = verify_review_state_snapshot(snapshot)

    assert result["valid"] is False
    assert "records.profiles is not ordered by profile_id" in result["errors"]
    assert "records.profiles contains duplicate profile_id values" in result["errors"]


def test_verifier_rejects_internal_and_embedded_hash_tampering_after_resign(tmp_path: Path) -> None:
    workspace, _ = _review_workspace(tmp_path)
    snapshot = build_review_state_snapshot(workspace.root)
    snapshot["records"]["opinions"][0]["rationale"] = "Changed outside the stored review state"
    snapshot["records"]["opinions"][0]["_path"] = "/private/path"
    _resign(snapshot)

    result = verify_review_state_snapshot(snapshot)

    assert result["valid"] is False
    assert any("internal field is forbidden" in error for error in result["errors"])
    assert any("opinion_sha256 mismatch" in error for error in result["errors"])


def test_verifier_rejects_queue_item_schema_tampering_after_resign(tmp_path: Path) -> None:
    workspace, _ = _review_workspace(tmp_path)
    snapshot = build_review_state_snapshot(workspace.root)
    snapshot["records"]["queue_items"][0]["monitoring_record_sha256"] = "bad"
    _resign(snapshot)

    result = verify_review_state_snapshot(snapshot)

    assert result["valid"] is False
    assert any("records.queue_items[0] schema" in error for error in result["errors"])


def test_ordered_records_requires_identifier() -> None:
    from neuroai_workbench import review_state

    with pytest.raises(ValueError, match="missing required identifier"):
        review_state._ordered_records([{}], "profile_id")


def test_sanitizer_recurses_lists_and_strips_internal_path() -> None:
    from neuroai_workbench import review_state

    value = [{"_path": "/private/path", "nested": [{"value": 1}]}]
    assert review_state._sanitize(value) == [{"nested": [{"value": 1}]}]


def test_stored_records_refuses_non_mapping_normalization(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from neuroai_workbench import review_state

    root = tmp_path / "observatory" / "review_queue" / "profiles"
    root.mkdir(parents=True)
    atomic_write_json(root / "profile.json", {"profile_id": "reviewer-a"})
    monkeypatch.setattr(review_state, "_sanitize", lambda _value: [])

    with pytest.raises(ValueError, match="could not be normalized"):
        review_state._stored_records(tmp_path, "profiles")


def test_verifier_rejects_non_mapping_top_level_collections_after_resign(tmp_path: Path) -> None:
    workspace, _ = _review_workspace(tmp_path)
    snapshot = build_review_state_snapshot(workspace.root)
    snapshot["counts"] = []
    snapshot["records"] = []
    _resign(snapshot)

    result = verify_review_state_snapshot(snapshot)

    assert result["valid"] is False
    assert any("schema:" in error and "counts" in error for error in result["errors"])
    assert any("schema:" in error and "records" in error for error in result["errors"])


def test_verifier_rejects_non_list_record_category_after_resign(tmp_path: Path) -> None:
    workspace, _ = _review_workspace(tmp_path)
    snapshot = build_review_state_snapshot(workspace.root)
    snapshot["records"]["profiles"] = {}
    snapshot["counts"]["profiles"] = 0
    _resign(snapshot)

    result = verify_review_state_snapshot(snapshot)

    assert result["valid"] is False
    assert any("schema:" in error and "records.profiles" in error for error in result["errors"])


def test_verifier_rejects_scalar_record_after_resign(tmp_path: Path) -> None:
    workspace, _ = _review_workspace(tmp_path)
    snapshot = build_review_state_snapshot(workspace.root)
    snapshot["records"]["profiles"] = ["malformed"]
    snapshot["counts"]["profiles"] = 1
    _resign(snapshot)

    result = verify_review_state_snapshot(snapshot)

    assert result["valid"] is False
    assert any("schema:" in error and "records.profiles" in error for error in result["errors"])


def test_verifier_rejects_non_string_record_identifier_after_resign(tmp_path: Path) -> None:
    workspace, _ = _review_workspace(tmp_path)
    snapshot = build_review_state_snapshot(workspace.root)
    snapshot["records"]["profiles"][0]["profile_id"] = 7
    _resign(snapshot)

    result = verify_review_state_snapshot(snapshot)

    assert result["valid"] is False
    assert any("records.profiles[0] schema" in error for error in result["errors"])
