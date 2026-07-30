from __future__ import annotations

import json
import logging
import mimetypes
import sys
import tempfile
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

from . import __version__
from .events import load_events, verify_chain
from .evidence import add_evidence_base64, list_evidence_files, verify_evidence_files
from .exporter import export_case_bundle
from .metrics import summarize
from .resource_loader import read_resource_bytes
from .util import ensure_identifier
from .validation import validate_assessment
from .workspace import Workspace

LOGGER = logging.getLogger("neuroai_workbench.server")
MAX_JSON_BODY = 110 * 1024 * 1024


class WorkbenchHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 32

    def __init__(self, server_address: tuple[str, int], workspace: Workspace):
        super().__init__(server_address, WorkbenchRequestHandler)
        self.workspace = workspace

    def handle_error(self, request: Any, client_address: Any) -> None:
        # Windows clients often reset loopback connections after Connection: close;
        # do not treat that transport teardown as an unhandled server failure.
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, TimeoutError)):
            LOGGER.debug("Client connection closed from %s: %s", client_address, exc)
            return
        super().handle_error(request, client_address)


class WorkbenchRequestHandler(BaseHTTPRequestHandler):
    server_version = f"NeuroAIWorkbench/{__version__}"

    @property
    def workspace(self) -> Workspace:
        server = self.server
        if not isinstance(server, WorkbenchHTTPServer):
            raise TypeError("Workbench handler requires WorkbenchHTTPServer")
        return server.workspace

    def log_message(self, fmt: str, *args: Any) -> None:
        safe = " ".join(str(arg).replace("\n", " ").replace("\r", " ") for arg in args)
        LOGGER.info("%s %s", self.client_address[0], safe)

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        # Avoid Windows keep-alive races with ThreadingHTTPServer during integration tests
        # and ordinary local use; loopback binding controls remain unchanged.
        self.send_header("Connection", "close")
        self.close_connection = True
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
        )

    def _send_json(self, payload: Any, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self._security_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # Client disconnected; do not escalate into the request thread.
            return

    def _send_bytes(self, data: bytes, content_type: str, status: int = 200, filename: str | None = None) -> None:
        self.send_response(status)
        self._security_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        try:
            self.wfile.write(data)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return

    def _read_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ValueError("Invalid Content-Length") from exc
        if length <= 0:
            return {}
        if length > MAX_JSON_BODY:
            raise ValueError("Request body exceeds the configured local limit")
        data = self.rfile.read(length)
        try:
            value = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON body: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError("JSON request body must be an object")
        return value

    def _segments(self) -> list[str]:
        path = urllib.parse.urlparse(self.path).path
        return [urllib.parse.unquote(segment) for segment in path.split("/") if segment]

    def _static(self, name: str) -> None:
        if name in {"", "/"}:
            name = "index.html"
        if ".." in Path(name).parts:
            self._send_json({"error": "Invalid static path"}, HTTPStatus.BAD_REQUEST)
            return
        target = files("neuroai_workbench.static").joinpath(name)
        if not target.is_file():
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
        self._send_bytes(target.read_bytes(), content_type)

    def do_GET(self) -> None:  # noqa: N802
        try:
            segments = self._segments()
            if not segments:
                self._static("index.html")
                return
            if segments[0] != "api":
                self._static("/".join(segments))
                return
            if segments == ["api", "health"]:
                self._send_json(
                    {
                        "status": "ok",
                        "version": __version__,
                        "workspace": str(self.workspace.root),
                        "bind_boundary": "This development server is intended for local trusted use only.",
                    }
                )
                return
            if segments == ["api", "cases"]:
                self._send_json({"cases": self.workspace.list_cases()})
                return
            if segments == ["api", "resources", "kernel"]:
                self._send_bytes(
                    read_resource_bytes("KERNEL_REQUIREMENTS_v4.2.json"), "application/json; charset=utf-8"
                )
                return
            if len(segments) >= 3 and segments[:2] == ["api", "cases"]:
                case_id = ensure_identifier(segments[2], "case ID")
                if len(segments) == 4 and segments[3] == "assessment":
                    self._send_json(self.workspace.load_case(case_id))
                    return
                if len(segments) == 4 and segments[3] == "summary":
                    self._send_json(summarize(self.workspace.load_case(case_id)))
                    return
                if len(segments) == 4 and segments[3] == "validate":
                    self._send_json(validate_assessment(self.workspace.load_case(case_id)).to_dict())
                    return
                if len(segments) == 4 and segments[3] == "events":
                    case_path = self.workspace.case_path(case_id)
                    self._send_json(
                        {
                            "verification": verify_chain(case_path / "events.jsonl"),
                            "events": load_events(case_path / "events.jsonl"),
                        }
                    )
                    return
                if len(segments) == 4 and segments[3] == "evidence":
                    self._send_json(
                        {
                            "objects": list_evidence_files(self.workspace, case_id),
                            "verification": verify_evidence_files(self.workspace, case_id),
                        }
                    )
                    return
                if len(segments) == 4 and segments[3] == "bundle":
                    with tempfile.TemporaryDirectory(prefix="neuroai-bundle-") as tmp:
                        output = Path(tmp) / "controlled-bundle.zip"
                        export_case_bundle(self.workspace, case_id, output)
                        self._send_bytes(
                            output.read_bytes(),
                            "application/zip",
                            filename=f"{case_id}-controlled-bundle.zip",
                        )
                    return
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            LOGGER.exception("GET failed")
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_POST(self) -> None:  # noqa: N802
        try:
            segments = self._segments()
            body = self._read_json()
            if segments == ["api", "cases"]:
                assessment = self.workspace.create_case(
                    str(body.get("case_id", "")),
                    str(body.get("title", "Untitled NeuroAI assessment")),
                    actor=str(body.get("actor", "web-user")),
                )
                self._send_json(assessment, HTTPStatus.CREATED)
                return
            if segments == ["api", "import"]:
                assessment_value: Any = body.get("assessment")
                if not isinstance(assessment_value, dict):
                    raise ValueError("assessment must be a JSON object")
                assessment = cast(dict[str, Any], assessment_value)
                case_id = str(body.get("case_id") or assessment.get("assessment_metadata", {}).get("assessment_id", ""))
                with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
                    json.dump(assessment, handle, ensure_ascii=False)
                    handle.flush()
                    temp_path = Path(handle.name)
                try:
                    imported = self.workspace.import_case(
                        temp_path, case_id=case_id, actor=str(body.get("actor", "web-user"))
                    )
                finally:
                    temp_path.unlink(missing_ok=True)
                self._send_json(imported, HTTPStatus.CREATED)
                return
            if len(segments) >= 4 and segments[:2] == ["api", "cases"]:
                case_id = ensure_identifier(segments[2], "case ID")
                action = segments[3]
                if action == "snapshot":
                    self._send_json(
                        self.workspace.snapshot(
                            case_id, actor=str(body.get("actor", "web-user")), label=str(body.get("label", "snapshot"))
                        )
                    )
                    return
                if action == "evidence":
                    record = add_evidence_base64(
                        self.workspace,
                        case_id,
                        str(body.get("filename", "evidence.bin")),
                        str(body.get("content_base64", "")),
                        title=str(body.get("title", "Untitled evidence object")),
                        evidence_type=str(body.get("evidence_type", "OTHER")),
                        source=str(body.get("source", "LOCAL FILE")),
                        actor=str(body.get("actor", "web-user")),
                        link_to_assessment=bool(body.get("link_to_assessment", True)),
                    )
                    self._send_json(record, HTTPStatus.CREATED)
                    return
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            LOGGER.exception("POST failed")
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_PUT(self) -> None:  # noqa: N802
        try:
            segments = self._segments()
            body = self._read_json()
            if len(segments) == 4 and segments[:2] == ["api", "cases"] and segments[3] == "assessment":
                assessment = body.get("assessment")
                if not isinstance(assessment, dict):
                    raise ValueError("assessment must be a JSON object")
                report = self.workspace.save_case(
                    ensure_identifier(segments[2], "case ID"),
                    assessment,
                    actor=str(body.get("actor", "web-user")),
                    require_valid=bool(body.get("require_valid", False)),
                )
                self._send_json(report)
                return
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            LOGGER.exception("PUT failed")
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_DELETE(self) -> None:  # noqa: N802
        try:
            segments = self._segments()
            body = self._read_json()
            if len(segments) == 3 and segments[:2] == ["api", "cases"]:
                case_id = ensure_identifier(segments[2], "case ID")
                self.workspace.delete_case(case_id, str(body.get("confirmation", "")))
                self._send_json({"deleted": case_id})
                return
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            LOGGER.exception("DELETE failed")
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)


def serve(
    workspace: Workspace,
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    allow_network: bool = False,
) -> None:
    loopback_hosts = {"127.0.0.1", "localhost", "::1"}
    if host not in loopback_hosts and not allow_network:
        raise ValueError(
            "Refusing non-loopback binding without explicit --allow-network. "
            "The reference server has no authentication or TLS."
        )
    if host not in loopback_hosts:
        LOGGER.warning(
            "Non-loopback binding enabled explicitly for %s. Use only inside a separately secured environment.",
            host,
        )
    server = WorkbenchHTTPServer((host, port), workspace)
    LOGGER.info("NeuroAI Workbench listening at http://%s:%s", host, server.server_address[1])
    LOGGER.info("Workspace: %s", workspace.root)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        LOGGER.info("Stopping server")
    finally:
        server.server_close()
