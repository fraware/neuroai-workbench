from __future__ import annotations

import json
import socket
import threading
import time
import urllib.error
import urllib.request

from neuroai_workbench.server import WorkbenchHTTPServer

# Windows under load can need longer than a tight timeout for ThreadingHTTPServer
# accept + first response; keep loopback-only and do not weaken binding controls.
REQUEST_TIMEOUT_SECONDS = 60.0
READY_TIMEOUT_SECONDS = 15.0


def wait_until_ready(base: str, timeout: float = READY_TIMEOUT_SECONDS) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(base + "/api/health", timeout=1.0) as response:
                if response.status == 200:
                    return
        except (TimeoutError, urllib.error.URLError, ConnectionError, OSError) as exc:
            last_error = exc
            time.sleep(0.05)
    raise TimeoutError(f"Server not ready at {base} within {timeout}s: {last_error}")


def request(url, method="GET", body=None, attempts: int = 3):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method=method, headers={"Content-Type": "application/json", "Connection": "close"}
    )
    # Retries are only safe for idempotent reads; POSTs may have already committed.
    max_attempts = attempts if method.upper() in {"GET", "HEAD"} else 1
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                content_type = response.headers.get("Content-Type", "")
                raw = response.read()
            return json.loads(raw) if "application/json" in content_type else raw
        except (TimeoutError, ConnectionError, OSError) as exc:
            last_error = exc
            time.sleep(0.1 * (attempt + 1))
    raise TimeoutError(f"Request failed after {max_attempts} attempts for {method} {url}: {last_error}")


def test_http_api_and_static_ui(workspace):
    server = WorkbenchHTTPServer(("127.0.0.1", 0), workspace)
    # Confirm the listening socket is bound before clients race the acceptor thread.
    assert isinstance(server.socket, socket.socket)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        wait_until_ready(base)
        health = request(base + "/api/health")
        assert health["status"] == "ok"
        catalog = request(base + "/api/presentation/catalog?locale=fr-FR")
        assert catalog["translation_scope"] == "PRESENTATION_ONLY"
        assert catalog["locale"] == "en"
        assert catalog["resolution"]["source"] == "query"
        assert catalog["resolution"]["fallback_used"] is True
        assert catalog["messages"]["assessment.shell_title"] == "NeuroAI Evidence and Decision Workbench"
        assert len(catalog["catalog_sha256"]) == 64
        assert workspace.list_cases() == []
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
