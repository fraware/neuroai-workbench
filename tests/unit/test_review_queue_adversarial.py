from __future__ import annotations

from pathlib import Path

import pytest

from neuroai_workbench.monitoring import create_change_candidate, initialize_monitoring, record_snapshot
from neuroai_workbench.review_queue import (
    claim_lease,
    initialize_review_queue,
    list_queue_items,
    register_reviewer_profile,
    release_lease,
    submit_opinion,
    verify_review_queue,
)
from neuroai_workbench.util import atomic_write_json, load_json


def source_record() -> dict[str, object]:
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


def setup_workspace(tmp_path: Path) -> tuple[Path, str]:
    registry = tmp_path / "registry.json"
    atomic_write_json(registry, [source_record()])
    workspace = tmp_path / "workspace"
    initialize_monitoring(workspace, registry)
    initialize_review_queue(workspace)
    register_reviewer_profile(workspace, "reviewer-a", "Reviewer A", ["MONITORING_REVIEWER"])
    register_reviewer_profile(workspace, "reviewer-b", "Reviewer B", ["MONITORING_REVIEWER"])
    first = record_snapshot(workspace, "SRC-0001", b"alpha", media_type="text/plain")
    changed = record_snapshot(workspace, "SRC-0001", b"beta", media_type="text/plain")
    candidate = create_change_candidate(
        workspace,
        "SRC-0001",
        changed["snapshot_id"],
        previous_snapshot_id=first["snapshot_id"],
    )
    item_id = f"RQI-{candidate['candidate_id']}"
    return workspace, item_id


def test_lease_steal_refused_between_profiles(tmp_path: Path) -> None:
    workspace, item_id = setup_workspace(tmp_path)
    claim_lease(workspace, item_id, "reviewer-a")
    with pytest.raises(ValueError, match="lease stealing is refused"):
        claim_lease(workspace, item_id, "reviewer-b")


def test_release_by_non_holder_refused(tmp_path: Path) -> None:
    workspace, item_id = setup_workspace(tmp_path)
    lease = claim_lease(workspace, item_id, "reviewer-a")
    lease_id = lease["lease"]["lease_id"]
    with pytest.raises(ValueError, match="cannot release lease"):
        release_lease(workspace, lease_id, "reviewer-b")


def test_duplicate_active_lease_for_same_profile_refused(tmp_path: Path) -> None:
    workspace, item_id = setup_workspace(tmp_path)
    claim_lease(workspace, item_id, "reviewer-a")
    with pytest.raises(ValueError, match="already holds an active lease"):
        claim_lease(workspace, item_id, "reviewer-a")


def test_profile_overwrite_refused(tmp_path: Path) -> None:
    workspace, _ = setup_workspace(tmp_path)
    with pytest.raises(ValueError, match="already exists with different content"):
        register_reviewer_profile(workspace, "reviewer-a", "Different Name", ["MONITORING_REVIEWER"])


def test_opinion_tamper_detected_by_verification(tmp_path: Path) -> None:
    workspace, item_id = setup_workspace(tmp_path)
    claim_lease(workspace, item_id, "reviewer-a")
    result = submit_opinion(workspace, item_id, "reviewer-a", "SUPPORT", "Initial opinion.")
    opinion_path = Path(result["path"])
    tampered = load_json(opinion_path)
    tampered["rationale"] = "Tampered rationale without hash update"
    atomic_write_json(opinion_path, tampered)
    report = verify_review_queue(workspace)
    assert report["valid"] is False
    assert any("hash mismatch" in error for error in report["errors"])


def test_multiple_opinions_are_distinct_records(tmp_path: Path) -> None:
    workspace, item_id = setup_workspace(tmp_path)
    claim_lease(workspace, item_id, "reviewer-a")
    first = submit_opinion(workspace, item_id, "reviewer-a", "SUPPORT", "First opinion.")
    release_lease(workspace, list_queue_items(workspace)[0]["active_lease"]["lease_id"], "reviewer-a")
    claim_lease(workspace, item_id, "reviewer-a")
    second = submit_opinion(workspace, item_id, "reviewer-a", "OPPOSE", "Revised view.")
    assert first["opinion"]["opinion_id"] != second["opinion"]["opinion_id"]


def test_path_traversal_refused_for_controlled_paths(tmp_path: Path) -> None:
    from neuroai_workbench.util import safe_join

    workspace, _ = setup_workspace(tmp_path)
    root = workspace / "observatory" / "review_queue" / "profiles"
    with pytest.raises(ValueError, match="Path escapes controlled root"):
        safe_join(root, "..", "escape.json")
    with pytest.raises(ValueError, match="Invalid profile ID"):
        register_reviewer_profile(workspace, "bad/id", "Bad", ["OBSERVER"])


def test_stale_opinion_detected_when_candidate_changes(tmp_path: Path) -> None:
    workspace, item_id = setup_workspace(tmp_path)
    claim_lease(workspace, item_id, "reviewer-a")
    submit_opinion(workspace, item_id, "reviewer-a", "DEFER", "Waiting for registry confirmation.")
    release_lease(workspace, list_queue_items(workspace)[0]["active_lease"]["lease_id"], "reviewer-a")

    candidate_path = next((workspace / "observatory" / "monitoring" / "candidates").glob("*.json"))
    candidate = load_json(candidate_path)
    candidate["summary"] = "Updated summary after external review."
    atomic_write_json(candidate_path, candidate)

    report = verify_review_queue(workspace)
    assert any("stale" in warning for warning in report["warnings"])
    item = list_queue_items(workspace)[0]
    assert item["queue_status"] == "STALE"


def test_invalid_role_and_position_rejected(tmp_path: Path) -> None:
    workspace, item_id = setup_workspace(tmp_path)
    with pytest.raises(ValueError, match="Unsupported review queue roles"):
        register_reviewer_profile(workspace, "bad-role", "Bad", ["INSTITUTIONAL_AUTHORITY"])
    claim_lease(workspace, item_id, "reviewer-a")
    with pytest.raises(ValueError, match="Unsupported opinion position"):
        submit_opinion(workspace, item_id, "reviewer-a", "ACCEPT", "Wrong enum.")


def test_lease_ttl_bounds(tmp_path: Path) -> None:
    workspace, item_id = setup_workspace(tmp_path)
    with pytest.raises(ValueError, match="ttl_seconds"):
        claim_lease(workspace, item_id, "reviewer-a", ttl_seconds=0)
    with pytest.raises(ValueError, match="ttl_seconds"):
        claim_lease(workspace, item_id, "reviewer-a", ttl_seconds=100000)


def test_double_release_refused(tmp_path: Path) -> None:
    workspace, item_id = setup_workspace(tmp_path)
    lease = claim_lease(workspace, item_id, "reviewer-a")
    lease_id = lease["lease"]["lease_id"]
    release_lease(workspace, lease_id, "reviewer-a")
    with pytest.raises(ValueError, match="already released"):
        release_lease(workspace, lease_id, "reviewer-a")


def test_monitoring_records_unmodified_after_queue_operations(tmp_path: Path) -> None:
    workspace, item_id = setup_workspace(tmp_path)
    candidate_before = {
        path.name: path.read_bytes() for path in (workspace / "observatory" / "monitoring" / "candidates").glob("*.json")
    }
    claim_lease(workspace, item_id, "reviewer-a")
    submit_opinion(workspace, item_id, "reviewer-a", "ABSTAIN", "Insufficient context.")
    release_lease(workspace, list_queue_items(workspace)[0]["active_lease"]["lease_id"], "reviewer-a")
    candidate_after = {
        path.name: path.read_bytes() for path in (workspace / "observatory" / "monitoring" / "candidates").glob("*.json")
    }
    assert candidate_before == candidate_after
