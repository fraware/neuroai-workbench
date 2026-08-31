"""Public observatory read API (/v1) substrate.

Serves immutable release artifacts only. This package is not an extension of the
local unauthenticated case ThreadingHTTPServer.
"""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..observatory_graph.temporal_compiler import predecessor_successor_diff
from ..util import load_json, sha256_bytes

API_BOUNDARY = (
    "Public /v1 responses are read-only projections of release directories. "
    "No write endpoint mutates canonical state. Caching/ETag keys bind to immutable "
    "release digests. This API is not the local case server and is not institutional SSO."
)

API_VERSION = "v1"

OBJECT_ROUTES = {
    "/v1/entities": "entities.jsonl",
    "/v1/sources": "sources.jsonl",
    "/v1/observations": "observations.jsonl",
    "/v1/assertions": "assertions.jsonl",
    "/v1/events": "events.jsonl",
    "/v1/relationships": "relationships.jsonl",
    "/v1/candidates": "candidates.jsonl",
    "/v1/reopening-decisions": "reopening-decisions.jsonl",
}

ID_FIELDS = (
    "entity_id",
    "source_id",
    "observation_id",
    "assertion_id",
    "event_id",
    "relationship_id",
    "candidate_id",
    "reopening_decision_id",
)


class PublicObservatoryApiError(ValueError):
    pass


def load_authorized_release(release_dir: Path) -> dict[str, Any]:
    """Load a release directory. Authorization is recorded, never inferred by this API."""
    descriptor_path = release_dir / "descriptor.json"
    manifest_path = release_dir / "manifest.json"
    if not descriptor_path.is_file() or not manifest_path.is_file():
        raise PublicObservatoryApiError("Release directory requires descriptor.json and manifest.json")
    descriptor = load_json(descriptor_path)
    manifest = load_json(manifest_path)
    if not isinstance(descriptor, dict) or not isinstance(manifest, dict):
        raise PublicObservatoryApiError("Release descriptor and manifest must be objects")
    return {
        "release_dir": release_dir,
        "descriptor": descriptor,
        "manifest": manifest,
        "manifest_sha256": str(manifest.get("manifest_sha256") or ""),
        "release_authorized": bool(descriptor.get("release_authorized") is True),
        "candidate_id": descriptor.get("candidate_id"),
        "boundary": API_BOUNDARY,
    }


def release_context(release: dict[str, Any]) -> dict[str, Any]:
    descriptor = release["descriptor"]
    return {
        "api_version": API_VERSION,
        "candidate_id": descriptor.get("candidate_id"),
        "package_version": descriptor.get("package_version"),
        "producer_commit": descriptor.get("producer_commit"),
        "runtime_execution_pin": descriptor.get("runtime_execution_pin"),
        "manifest_sha256": release.get("manifest_sha256"),
        "etag": etag_for_release(release),
        "release_authorized": bool(descriptor.get("release_authorized") is True),
        "mechanical_verification": descriptor.get("mechanical_verification"),
        "rebuildable_from_release_artifacts": True,
        "boundary": API_BOUNDARY,
    }


def etag_for_release(release: dict[str, Any]) -> str:
    digest = release.get("manifest_sha256") or sha256_bytes(b"missing-manifest")
    return f'W/"{API_VERSION}-{digest}"'


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _all_records(release: dict[str, Any]) -> list[dict[str, Any]]:
    records_root = Path(release["release_dir"]) / "records"
    rows: list[dict[str, Any]] = []
    for filename in OBJECT_ROUTES.values():
        rows.extend(read_jsonl(records_root / filename))
    return rows


def _object_id(row: dict[str, Any]) -> str | None:
    for field in ID_FIELDS:
        value = row.get(field)
        if isinstance(value, str) and value:
            return value
    return None


def _filter_by_id(rows: list[dict[str, Any]], object_id: str) -> list[dict[str, Any]]:
    return [row for row in rows if object_id == _object_id(row) or object_id in {row.get(field) for field in ID_FIELDS}]


def _why_provenance(release: dict[str, Any], object_id: str) -> dict[str, Any]:
    rows = _filter_by_id(_all_records(release), object_id)
    if not rows:
        raise PublicObservatoryApiError(f"Unknown object id {object_id!r} in this release")
    primary = rows[0]
    source_ids = list(
        primary.get("source_ids") or ([] if primary.get("source_id") is None else [primary.get("source_id")])
    )
    observation_ids = list(primary.get("observation_ids") or [])
    return {
        "object_id": object_id,
        "object_class": primary.get("object_class"),
        "why": {
            "evidence_state": primary.get("evidence_state"),
            "verification_state": primary.get("verification_state"),
            "review_state": primary.get("review_state"),
            "claim_boundary": primary.get("claim_boundary"),
            "prohibited_inferences": primary.get("prohibited_inferences") or [],
        },
        "provenance": {
            "source_ids": source_ids,
            "observation_ids": observation_ids,
            "canonical_sha256": primary.get("canonical_sha256"),
            "release_manifest_sha256": release.get("manifest_sha256"),
        },
        "items": rows,
    }


def _timeline(release: dict[str, Any], object_id: str | None) -> dict[str, Any]:
    rows = _all_records(release)
    if object_id:
        rows = [
            row
            for row in rows
            if object_id == _object_id(row)
            or object_id in set(row.get("source_ids") or [])
            or object_id in set(row.get("observation_ids") or [])
            or object_id == row.get("source_id")
            or object_id in set(row.get("supersedes_assertion_ids") or [])
        ]
    events: list[dict[str, Any]] = []
    for row in rows:
        for field in ("observed_at", "valid_from", "valid_until", "occurred_at"):
            value = row.get(field)
            if value is None:
                continue
            events.append(
                {
                    "object_id": _object_id(row),
                    "object_class": row.get("object_class"),
                    "time_field": field,
                    "time_value": value,
                }
            )
    events.sort(key=lambda item: json.dumps(item.get("time_value"), sort_keys=True, default=str))
    return {"object_id": object_id, "events": events, "count": len(events)}


def _diff_against_predecessor(release: dict[str, Any], predecessor_dir: Path) -> dict[str, Any]:
    predecessor = load_authorized_release(predecessor_dir)
    current_rows = _all_records(release)
    predecessor_rows = _all_records(predecessor)
    diff = predecessor_successor_diff(predecessor_rows, current_rows)
    return {
        "predecessor_candidate_id": predecessor.get("candidate_id"),
        "predecessor_manifest_sha256": predecessor.get("manifest_sha256"),
        "successor_candidate_id": release.get("candidate_id"),
        "successor_manifest_sha256": release.get("manifest_sha256"),
        **diff,
    }


def handle_v1_get(release: dict[str, Any], path: str, *, query: dict[str, list[str]] | None = None) -> dict[str, Any]:
    """Return a JSON-serializable body for a /v1 GET. Raises on unknown routes."""
    query = query or {}
    context = release_context(release)
    if path in {"/v1", "/v1/", "/v1/health"}:
        return {
            "status": "ok",
            "read_only": True,
            "writes_supported": False,
            **context,
        }
    if path == "/v1/release":
        return {
            "descriptor": release["descriptor"],
            "manifest": dict(release["manifest"]),
            **context,
        }
    records_root = Path(release["release_dir"]) / "records"
    if path in OBJECT_ROUTES:
        rows = read_jsonl(records_root / OBJECT_ROUTES[path])
        id_values = query.get("id") or []
        object_id = id_values[0] if id_values else ""
        if object_id:
            rows = _filter_by_id(rows, object_id)
        return {"items": rows, "count": len(rows), **context}
    if path in {"/v1/why", "/v1/provenance"}:
        id_values = query.get("id") or []
        if not id_values or not id_values[0].strip():
            raise PublicObservatoryApiError("/v1/why and /v1/provenance require ?id=")
        body = _why_provenance(release, id_values[0].strip())
        return {**body, **context}
    if path == "/v1/timeline":
        id_values = query.get("id") or []
        timeline_object_id: str | None = id_values[0].strip() if id_values and id_values[0].strip() else None
        body = _timeline(release, timeline_object_id)
        return {**body, **context}
    if path == "/v1/diff":
        predecessor_values = query.get("predecessor") or []
        if not predecessor_values or not predecessor_values[0].strip():
            raise PublicObservatoryApiError("/v1/diff requires ?predecessor=<release_dir>")
        predecessor_dir = Path(predecessor_values[0].strip())
        if not predecessor_dir.is_dir():
            raise PublicObservatoryApiError("predecessor release directory not found")
        body = _diff_against_predecessor(release, predecessor_dir)
        return {**body, **context}
    if path.startswith("/v1/"):
        raise PublicObservatoryApiError(f"Unknown /v1 route {path}")
    raise PublicObservatoryApiError("Public observatory API only serves /v1/*")


def refuse_write(method: str) -> None:
    if method.upper() not in {"GET", "HEAD", "OPTIONS"}:
        raise PublicObservatoryApiError(
            f"Write method {method!r} is refused. Canonical state is immutable release artifacts only."
        )


class PublicObservatoryV1Handler(BaseHTTPRequestHandler):
    """Minimal read-only handler bound to one release directory.

    Not institutional auth. Not the local case API.
    """

    release_dir: Path

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def _release(self) -> dict[str, Any]:
        return load_authorized_release(self.release_dir)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            release = self._release()
            if_none_match = self.headers.get("If-None-Match")
            etag = etag_for_release(release)
            if if_none_match and if_none_match == etag:
                self.send_response(HTTPStatus.NOT_MODIFIED)
                self.send_header("ETag", etag)
                self.end_headers()
                return
            body = handle_v1_get(release, parsed.path, query=parse_qs(parsed.query))
            payload = json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", "public, max-age=0, must-revalidate")
            self.send_header("X-NeuroAI-API-Boundary", API_BOUNDARY[:200])
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except PublicObservatoryApiError as exc:
            payload = json.dumps({"error": str(exc), "boundary": API_BOUNDARY}, ensure_ascii=False).encode("utf-8")
            self.send_response(HTTPStatus.BAD_REQUEST)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    def do_POST(self) -> None:  # noqa: N802
        self._refuse_write()

    def do_PUT(self) -> None:  # noqa: N802
        self._refuse_write()

    def do_DELETE(self) -> None:  # noqa: N802
        self._refuse_write()

    def _refuse_write(self) -> None:
        payload = json.dumps(
            {
                "error": "Write methods are refused. Canonical state is immutable release artifacts only.",
                "boundary": API_BOUNDARY,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Allow", "GET, HEAD, OPTIONS")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def make_v1_server(release_dir: Path, host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    handler = type(
        "BoundPublicObservatoryV1Handler",
        (PublicObservatoryV1Handler,),
        {"release_dir": Path(release_dir)},
    )
    return ThreadingHTTPServer((host, port), handler)
