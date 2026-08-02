from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from neuroai_workbench.monitoring import (
    adjudicate_change_candidate,
    create_change_candidate,
    initialize_monitoring,
    record_snapshot,
)
from neuroai_workbench.review_queue import (
    _hash_record,
    _parse_timestamp,
    claim_lease,
    get_queue_item,
    initialize_review_queue,
    list_queue_items,
    load_item_opinions,
    load_reviewer_profiles,
    rebuild_queue_projection,
    register_reviewer_profile,
    release_lease,
    render_queue_markdown,
    review_queue_status,
    submit_opinion,
    verify_review_queue,
)
from neuroai_workbench.util import atomic_write_json, load_json


def source_record(source_id: str = "SRC-0001") -> dict[str, object]:
    return {
        "monitor_id": "MON-SRC-0001",
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


def write_registry(tmp_path: Path) -> Path:
    path = tmp_path / "registry.json"
    atomic_write_json(path, [source_record()])
    return path


def setup_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    initialize_monitoring(workspace, write_registry(tmp_path))
    initialize_review_queue(workspace, actor="tester")
    return workspace


def create_candidate(workspace: Path) -> dict[str, object]:
    first = record_snapshot(workspace, "SRC-0001", b"alpha", media_type="text/plain")
    changed = record_snapshot(workspace, "SRC-0001", b"beta", media_type="text/plain")
    return create_change_candidate(
        workspace,
        "SRC-0001",
        changed["snapshot_id"],
        previous_snapshot_id=first["snapshot_id"],
        actor="detector",
    )


def register_profiles(workspace: Path) -> None:
    register_reviewer_profile(workspace, "reviewer-a", "Reviewer A", ["MONITORING_REVIEWER"], actor="admin")
    register_reviewer_profile(workspace, "reviewer-b", "Reviewer B", ["ADJUDICATION_REVIEWER"], actor="admin")


def test_initialize_requires_monitoring(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    with pytest.raises(ValueError, match="Monitoring must be initialized"):
        initialize_review_queue(workspace)


def test_register_profile_and_status(tmp_path: Path) -> None:
    workspace = setup_workspace(tmp_path)
    result = register_reviewer_profile(
        workspace,
        "reviewer-a",
        "Reviewer A",
        ["MONITORING_REVIEWER", "OBSERVER"],
        actor="admin",
    )
    assert result["created"] is True
    again = register_reviewer_profile(
        workspace,
        "reviewer-a",
        "Reviewer A",
        ["MONITORING_REVIEWER", "OBSERVER"],
        actor="admin",
    )
    assert again["created"] is False
    status = review_queue_status(workspace)
    assert status["initialized"] is True
    assert status["profile_count"] == 1


def test_projection_from_candidates_and_adjudications(tmp_path: Path) -> None:
    workspace = setup_workspace(tmp_path)
    candidate = create_candidate(workspace)
    items = rebuild_queue_projection(workspace)
    assert len(items) == 1
    assert items[0]["item_id"] == f"RQI-{candidate['candidate_id']}"
    assert items[0]["queue_status"] == "OPEN"

    adjudicate_change_candidate(
        workspace,
        candidate["candidate_id"],
        "REJECT",
        rationale="Non-material wording change only.",
        actor="reviewer",
    )
    items = rebuild_queue_projection(workspace)
    assert items[0]["queue_status"] == "ADJUDICATED"
    assert items[0]["adjudication_decision"] == "REJECT"


def test_list_queue_items_enriches_leases_and_opinions(tmp_path: Path) -> None:
    workspace = setup_workspace(tmp_path)
    create_candidate(workspace)
    register_profiles(workspace)
    item = list_queue_items(workspace)[0]
    claim_lease(workspace, item["item_id"], "reviewer-a", actor="reviewer-a")
    submit_opinion(
        workspace,
        item["item_id"],
        "reviewer-a",
        "NEEDS_EVIDENCE",
        "Need the exact capture provenance.",
    )
    enriched = list_queue_items(workspace, persist_projection=True)[0]
    assert enriched["active_lease"]["reviewer_profile_id"] == "reviewer-a"
    assert enriched["opinion_count"] == 1
    assert list((workspace / "observatory" / "review_queue" / "projections").glob("*.json"))


def test_full_lifecycle_is_non_mutating(tmp_path: Path) -> None:
    workspace = setup_workspace(tmp_path)
    candidate = create_candidate(workspace)
    candidate_path = workspace / "observatory" / "monitoring" / "candidates" / f"{candidate['candidate_id']}.json"
    before = candidate_path.read_bytes()
    register_profiles(workspace)
    item = get_queue_item(workspace, f"RQI-{candidate['candidate_id']}")
    lease = claim_lease(workspace, item["item_id"], "reviewer-a")
    submit_opinion(
        workspace,
        item["item_id"],
        "reviewer-a",
        "OPPOSE",
        "The detected change may be formatting-only.",
    )
    release_lease(workspace, lease["lease"]["lease_id"], "reviewer-a")

    report = verify_review_queue(workspace)
    assert report["valid"] is True
    assert report["counts"]["opinions"] == 1
    assert report["counts"]["disagreements"] == 1
    assert candidate_path.read_bytes() == before

    markdown = render_queue_markdown(workspace)
    assert "OPPOSE" in markdown
    assert "reviewer-a" in markdown


def test_multiple_opinions_preserved(tmp_path: Path) -> None:
    workspace = setup_workspace(tmp_path)
    create_candidate(workspace)
    register_profiles(workspace)
    item = list_queue_items(workspace)[0]

    claim_lease(workspace, item["item_id"], "reviewer-a")
    submit_opinion(workspace, item["item_id"], "reviewer-a", "SUPPORT", "Looks material.")
    release_lease(workspace, list_queue_items(workspace)[0]["active_lease"]["lease_id"], "reviewer-a")

    claim_lease(workspace, item["item_id"], "reviewer-b")
    submit_opinion(workspace, item["item_id"], "reviewer-b", "OPPOSE", "Likely duplicate capture.")
    release_lease(workspace, list_queue_items(workspace)[0]["active_lease"]["lease_id"], "reviewer-b")

    opinions = load_item_opinions(workspace, item["item_id"])
    assert len(opinions) == 2
    assert {item["position"] for item in opinions} == {"SUPPORT", "OPPOSE"}


def test_projection_rebuild_is_idempotent(tmp_path: Path) -> None:
    workspace = setup_workspace(tmp_path)
    create_candidate(workspace)
    first = rebuild_queue_projection(workspace)
    second = rebuild_queue_projection(workspace)
    assert first == second


def test_profiles_are_loaded_with_hashes(tmp_path: Path) -> None:
    workspace = setup_workspace(tmp_path)
    register_reviewer_profile(workspace, "reviewer-a", "Reviewer A", ["OBSERVER"])
    profiles = load_reviewer_profiles(workspace)
    assert len(profiles) == 1
    assert profiles[0]["profile_sha256"] == _hash_record(profiles[0], "profile_sha256")


def test_get_queue_item_unknown_raises(tmp_path: Path) -> None:
    workspace = setup_workspace(tmp_path)
    with pytest.raises(ValueError, match="Unknown review queue item"):
        get_queue_item(workspace, "RQI-CAND-deadbeeffeeddeadbeefdeadbeef00")


def test_submit_opinion_requires_active_lease(tmp_path: Path) -> None:
    workspace = setup_workspace(tmp_path)
    create_candidate(workspace)
    register_profiles(workspace)
    item = list_queue_items(workspace)[0]
    with pytest.raises(ValueError, match="must hold an active lease"):
        submit_opinion(workspace, item["item_id"], "reviewer-a", "DEFER", "Need more context.")


def test_expired_lease_ignored_and_reclaim_allowed(tmp_path: Path) -> None:
    workspace = setup_workspace(tmp_path)
    create_candidate(workspace)
    register_profiles(workspace)
    item = list_queue_items(workspace)[0]
    lease = claim_lease(workspace, item["item_id"], "reviewer-a", ttl_seconds=1)
    lease_record = load_json(
        workspace / "observatory" / "review_queue" / "leases" / f"{lease['lease']['lease_id']}.json"
    )
    expired = (
        (_parse_timestamp(str(lease_record["expires_at"])) - timedelta(seconds=2)).isoformat().replace("+00:00", "Z")
    )
    lease_record["expires_at"] = expired
    lease_record["lease_sha256"] = _hash_record(lease_record, "lease_sha256")
    atomic_write_json(
        workspace / "observatory" / "review_queue" / "leases" / f"{lease['lease']['lease_id']}.json",
        lease_record,
    )
    new_lease = claim_lease(workspace, item["item_id"], "reviewer-b")
    assert new_lease["lease"]["reviewer_profile_id"] == "reviewer-b"
