from __future__ import annotations

import json
import socket
import threading
from pathlib import Path

import pytest

from neuroai_workbench.monitoring import create_change_candidate, initialize_monitoring, record_snapshot
from neuroai_workbench.review_queue import initialize_review_queue, register_reviewer_profile
from neuroai_workbench.server import WorkbenchHTTPServer
from neuroai_workbench.util import atomic_write_json
from tests.integration.test_server import REQUEST_TIMEOUT_SECONDS, wait_until_ready


def request(url, method="GET", body=None):
    import urllib.error
    import urllib.request

    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method=method, headers={"Content-Type": "application/json", "Connection": "close"}
    )
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        content_type = response.headers.get("Content-Type", "")
        raw = response.read()
    return json.loads(raw) if "application/json" in content_type else raw


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


@pytest.fixture
def monitoring_workspace(tmp_path: Path):
    registry = tmp_path / "registry.json"
    atomic_write_json(registry, [source_record()])
    from neuroai_workbench.workspace import Workspace

    workspace = Workspace.initialize(tmp_path / "workspace")
    initialize_monitoring(workspace.root, registry)
    initialize_review_queue(workspace.root, actor="tester")
    register_reviewer_profile(
        workspace.root,
        "reviewer-a",
        "Reviewer A",
        ["MONITORING_REVIEWER"],
        actor="tester",
    )
    first = record_snapshot(workspace.root, "SRC-0001", b"alpha", media_type="text/plain")
    second = record_snapshot(workspace.root, "SRC-0001", b"<script>xss</script>", media_type="text/html")
    candidate = create_change_candidate(
        workspace.root,
        "SRC-0001",
        second["snapshot_id"],
        previous_snapshot_id=first["snapshot_id"],
        summary='Change with <script>alert("x")</script> marker',
    )
    return workspace, candidate


def test_review_ui_static_and_api(monitoring_workspace):
    workspace, candidate = monitoring_workspace
    server = WorkbenchHTTPServer(("127.0.0.1", 0), workspace)
    assert isinstance(server.socket, socket.socket)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        wait_until_ready(base)
        html = request(base + "/review.html")
        assert b"Observatory monitoring review" in html
        assert b"Skip to review content" in html
        assert b'<script src="review.js"' in html

        health = request(base + "/api/review/health")
        assert health["rebuildable"] is True
        assert health["candidate_counts"]["pending"] == 1

        queue = request(base + "/api/review/queue")
        assert queue["initialized"] is True
        assert len(queue["items"]) == 1
        item_id = queue["items"][0]["item_id"]

        detail = request(base + f"/api/review/queue/{item_id}")
        assert detail["candidate"]["candidate_id"] == candidate["candidate_id"]
        assert "<script>" in detail["candidate"]["summary"]
        assert detail["capture_diff"]["available"] is True

        profiles = request(base + "/api/review/profiles")
        assert profiles["profiles"][0]["profile_id"] == "reviewer-a"

        lease = request(
            base + f"/api/review/queue/{item_id}/lease",
            "POST",
            {"reviewer_profile_id": "reviewer-a"},
        )
        assert lease["lease"]["item_id"] == item_id

        opinion = request(
            base + f"/api/review/queue/{item_id}/opinion",
            "POST",
            {
                "reviewer_profile_id": "reviewer-a",
                "position": "NEEDS_EVIDENCE",
                "rationale": "Verify hostile markup remains display-only.",
            },
        )
        assert opinion["opinion"]["position"] == "NEEDS_EVIDENCE"

        fields = request(base + "/api/review/fields")
        assert "adjudication_fields" in fields

        profile = request(
            base + "/api/review/profiles",
            "POST",
            {
                "profile_id": "reviewer-b",
                "display_name": "Reviewer B",
                "roles": ["MONITORING_REVIEWER"],
                "actor": "tester",
            },
        )
        assert profile["profile"]["profile_id"] == "reviewer-b"
        assert profile["created"] is True

        released = request(
            base + f"/api/review/leases/{lease['lease']['lease_id']}/release",
            "POST",
            {"reviewer_profile_id": "reviewer-a", "reason": "RELEASED"},
        )
        assert released["release"]["lease_id"] == lease["lease"]["lease_id"]

        # Re-claim before adjudication so lease state remains consistent with UI flow.
        lease_again = request(
            base + f"/api/review/queue/{item_id}/lease",
            "POST",
            {"reviewer_profile_id": "reviewer-a"},
        )
        assert lease_again["lease"]["item_id"] == item_id

        adjudication = request(
            base + f"/api/review/queue/{item_id}/adjudicate",
            "POST",
            {
                "decision": "DEFER",
                "rationale": "Deferred after markup-display verification; not a substantive determination.",
                "change_class": "UNCLASSIFIED",
                "materiality": "UNDETERMINED",
                "reopening_effect": "UNDETERMINED",
                "decided_by": "reviewer-a",
            },
        )
        assert adjudication["decision"] == "DEFER"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_review_queue_uninitialized_projection(tmp_path: Path):
    from neuroai_workbench.workspace import Workspace

    workspace = Workspace.initialize(tmp_path / "workspace")
    server = WorkbenchHTTPServer(("127.0.0.1", 0), workspace)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        wait_until_ready(base)
        queue = request(base + "/api/review/queue")
        assert queue["initialized"] is False
        assert queue["items"] == []
        fields = request(base + "/api/review/fields")
        assert "adjudication_fields" in fields
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
