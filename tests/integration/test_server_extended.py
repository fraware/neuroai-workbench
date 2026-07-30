from __future__ import annotations

import base64
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from neuroai_workbench import __version__
from neuroai_workbench.server import WorkbenchHTTPServer, serve


def request(url: str, method: str = "GET", body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            raw = response.read()
            return response.status, response.headers, raw
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers, exc.read()


@pytest.fixture
def live_server(workspace):
    server = WorkbenchHTTPServer(("127.0.0.1", 0), workspace)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", workspace
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def json_body(raw: bytes):
    return json.loads(raw)


def test_all_http_routes_and_errors(live_server, example_assessment):
    base, workspace = live_server
    status, headers, raw = request(base + "/api/health")
    assert status == 200
    assert json_body(raw)["version"] == __version__
    assert headers["X-Frame-Options"] == "DENY"

    assert request(base + "/styles.css")[0] == 200
    assert request(base + "/missing.css")[0] == 404
    assert request(base + "/api/resources/kernel")[0] == 200
    assert request(base + "/api/unknown")[0] == 404

    status, _, raw = request(base + "/api/cases", "POST", {"case_id": "CASE-001", "title": "HTTP case"})
    assert status == 201
    assessment = json_body(raw)

    for route in ("assessment", "summary", "validate", "events", "evidence"):
        assert request(base + f"/api/cases/CASE-001/{route}")[0] == 200
    status, headers, bundle = request(base + "/api/cases/CASE-001/bundle")
    assert status == 200 and bundle.startswith(b"PK")
    assert "attachment" in headers["Content-Disposition"]

    status, _, raw = request(base + "/api/cases/CASE-001/snapshot", "POST", {"label": "freeze"})
    assert status == 200 and json_body(raw)["assessment_sha256"]

    status, _, raw = request(base + "/api/cases/CASE-001/evidence", "POST", {
        "filename": "evidence.txt",
        "content_base64": base64.b64encode(b"bytes").decode(),
        "title": "Evidence",
    })
    assert status == 201 and json_body(raw)["evidence_id"] == "EV-001"

    assessment["assessment_metadata"]["assessment_purpose"] = "Updated over HTTP"
    status, _, raw = request(base + "/api/cases/CASE-001/assessment", "PUT", {"assessment": assessment})
    assert status == 200 and json_body(raw)["valid"] is True

    imported = json.loads(json.dumps(example_assessment))
    imported["assessment_metadata"]["assessment_id"] = "CASE-IMPORTED"
    status, _, raw = request(base + "/api/import", "POST", {"assessment": imported})
    assert status == 201 and json_body(raw)["assessment_metadata"]["assessment_id"] == "CASE-IMPORTED"

    assert request(base + "/api/import", "POST", {"assessment": "bad"})[0] == 400
    assert request(base + "/api/cases/CASE-001/evidence", "POST", {"content_base64": "%%%", "title": "Bad"})[0] == 400
    assert request(base + "/api/cases/CASE-001/assessment", "PUT", {"assessment": "bad"})[0] == 400
    assert request(base + "/api/nope", "POST", {})[0] == 404
    assert request(base + "/api/nope", "PUT", {})[0] == 404
    assert request(base + "/api/nope", "DELETE", {})[0] == 404

    assert request(base + "/api/cases/CASE-001", "DELETE", {"confirmation": "wrong"})[0] == 400
    assert request(base + "/api/cases/CASE-001", "DELETE", {"confirmation": "CASE-001"})[0] == 200
    assert not workspace.case_path("CASE-001").exists()


def test_network_binding_requires_explicit_opt_in(workspace, monkeypatch):
    with pytest.raises(ValueError, match="Refusing non-loopback"):
        serve(workspace, host="0.0.0.0", port=0)

    class FakeServer:
        server_address = ("0.0.0.0", 1234)

        def __init__(self, address, ws):
            self.address = address
            self.workspace = ws

        def serve_forever(self, poll_interval):
            raise KeyboardInterrupt

        def server_close(self):
            self.closed = True

    monkeypatch.setattr("neuroai_workbench.server.WorkbenchHTTPServer", FakeServer)
    serve(workspace, host="0.0.0.0", port=1234, allow_network=True)
