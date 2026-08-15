from __future__ import annotations

import json
import socket
import threading
from pathlib import Path

from neuroai_workbench.monitoring import initialize_monitoring
from neuroai_workbench.review_queue import initialize_review_queue
from neuroai_workbench.server import WorkbenchHTTPServer
from neuroai_workbench.util import atomic_write_json
from neuroai_workbench.workspace import Workspace
from tests.integration.test_server import REQUEST_TIMEOUT_SECONDS, wait_until_ready


def _request(url: str) -> dict[str, object]:
    import urllib.request

    request = urllib.request.Request(url, method="GET", headers={"Connection": "close"})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        assert "application/json" in response.headers.get("Content-Type", "")
        return json.loads(response.read())


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


def test_review_snapshot_route_is_read_only_and_deterministic(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    atomic_write_json(registry, [_source_record()])
    workspace = Workspace.initialize(tmp_path / "workspace")
    initialize_monitoring(workspace.root, registry)
    initialize_review_queue(workspace.root, actor="tester")

    server = WorkbenchHTTPServer(("127.0.0.1", 0), workspace)
    assert isinstance(server.socket, socket.socket)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        wait_until_ready(base)
        first = _request(base + "/api/review/snapshot")
        second = _request(base + "/api/review/snapshot")

        assert first == second
        assert first["snapshot_version"] == "1"
        assert first["source_integrity"] == "VERIFIED"
        assert first["authority_profile"] == "LOCAL_READ_MODEL_NO_AUTHORITY"
        assert first["counts"] == {
            "profiles": 0,
            "queue_items": 0,
            "leases": 0,
            "lease_releases": 0,
            "opinions": 0,
        }
        assert first["records"] == {
            "profiles": [],
            "queue_items": [],
            "leases": [],
            "lease_releases": [],
            "opinions": [],
        }
        assert len(str(first["snapshot_sha256"])) == 64
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
