from __future__ import annotations

import json
import threading
import urllib.request

from neuroai_workbench.server import WorkbenchHTTPServer


def request(url, method="GET", body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as response:
        content_type = response.headers.get("Content-Type", "")
        raw = response.read()
    return json.loads(raw) if "application/json" in content_type else raw


def test_http_api_and_static_ui(workspace):
    server = WorkbenchHTTPServer(("127.0.0.1", 0), workspace)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        health = request(base + "/api/health")
        assert health["status"] == "ok"
        html = request(base + "/")
        assert b"NeuroAI Evidence and Decision Workbench" in html
        created = request(base + "/api/cases", "POST", {"case_id": "CASE-001", "title": "HTTP case"})
        assert created["assessment_metadata"]["assessment_id"] == "CASE-001"
        cases = request(base + "/api/cases")
        assert cases["cases"][0]["case_id"] == "CASE-001"
        validation = request(base + "/api/cases/CASE-001/validate")
        assert validation["valid"] is True
        events = request(base + "/api/cases/CASE-001/events")
        assert events["verification"]["valid"] is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
