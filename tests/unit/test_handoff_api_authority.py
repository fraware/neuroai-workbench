"""Authority-boundary tests for the public observatory /v1 API substrate."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from neuroai_workbench.api import (
    API_BOUNDARY,
    PublicObservatoryApiError,
    etag_for_release,
    handle_v1_get,
    load_authorized_release,
    make_v1_server,
    refuse_write,
)
from neuroai_workbench.observatory_graph import (
    GRAPH_BOUNDARY,
    KIND_RESOLVED_ENTITY_REFERENCE,
    build_assertion,
    build_entity,
    build_observation,
    build_source,
)
from neuroai_workbench.release import ReleaseCompiler
from neuroai_workbench.temporal import TIME_VALUE_BOUNDARY


def _resolved(entity_id: str) -> dict[str, str]:
    return {"kind": KIND_RESOLVED_ENTITY_REFERENCE, "entity_id": entity_id, "boundary": GRAPH_BOUNDARY}


def _ts(value: str = "2026-08-31T12:00:00Z") -> dict[str, str | None]:
    return {"value": value, "precision": "TIMESTAMP", "boundary": TIME_VALUE_BOUNDARY}


def _date(value: str = "2026-08-01") -> dict[str, str | None]:
    return {"value": value, "precision": "DATE", "boundary": TIME_VALUE_BOUNDARY}


def _build_release(tmp_path: Path) -> Path:
    entity = build_entity(entity_id="ENT-API-H1", entity_type="SYSTEM", canonical_label="System")
    source = build_source(
        source_id="SRC-API-H1",
        source_class="REGISTRY",
        title="Source",
        publisher="Pub",
        canonical_url_or_reference="https://example.test/src",
        publication_or_record_date=_date(),
    )
    observation = build_observation(
        observation_id="OBS-API-H1",
        source_id="SRC-API-H1",
        observed_at=_ts(),
        retrieval_method="HTTP_GET",
        retrieval_outcome="RETRIEVED",
        requested_locator="https://example.test/src",
        content_sha256="a" * 64,
    )
    assertion = build_assertion(
        assertion_id="AST-API-H1",
        subject=_resolved("ENT-API-H1"),
        predicate="STATUS",
        value="ACTIVE",
        evidence_state="SOURCE_STATED",
        verification_state="RETRIEVAL_VERIFIED_BYTES_ONLY",
        review_state="NOT_REVIEWED",
        claim_boundary="fixture",
        valid_from=_date("2026-01-01"),
        valid_until=_date("2026-12-31"),
        observed_at=_ts(),
        source_ids=["SRC-API-H1"],
        observation_ids=["OBS-API-H1"],
    )
    out = tmp_path / "release"
    ReleaseCompiler().build(
        [entity, source, observation, assertion],
        out,
        candidate_id="CAND-API-H1",
    )
    return out


def test_load_authorized_release_guards(tmp_path: Path) -> None:
    with pytest.raises(PublicObservatoryApiError, match="descriptor.json"):
        load_authorized_release(tmp_path / "missing")
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "descriptor.json").write_text("[]", encoding="utf-8")
    (bad / "manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(PublicObservatoryApiError, match="objects"):
        load_authorized_release(bad)


def test_why_timeline_release_and_filters(tmp_path: Path) -> None:
    release_dir = _build_release(tmp_path)
    release = load_authorized_release(release_dir)
    assert release["release_authorized"] is False
    assert API_BOUNDARY in release["boundary"]

    release_body = handle_v1_get(release, "/v1/release")
    assert release_body["descriptor"]["candidate_id"] == "CAND-API-H1"
    assert release_body["release_authorized"] is False

    filtered = handle_v1_get(release, "/v1/entities", query={"id": ["ENT-API-H1"]})
    assert filtered["count"] == 1
    empty = handle_v1_get(release, "/v1/entities", query={"id": ["NOPE"]})
    assert empty["count"] == 0

    why = handle_v1_get(release, "/v1/why", query={"id": ["AST-API-H1"]})
    assert why["object_id"] == "AST-API-H1"
    assert "SOURCE_STATED" == why["why"]["evidence_state"]
    assert "SRC-API-H1" in why["provenance"]["source_ids"]
    provenance = handle_v1_get(release, "/v1/provenance", query={"id": ["OBS-API-H1"]})
    assert provenance["object_id"] == "OBS-API-H1"

    with pytest.raises(PublicObservatoryApiError, match=r"\?id="):
        handle_v1_get(release, "/v1/why", query={})
    with pytest.raises(PublicObservatoryApiError, match="Unknown object"):
        handle_v1_get(release, "/v1/why", query={"id": ["MISSING"]})

    timeline = handle_v1_get(release, "/v1/timeline", query={"id": ["AST-API-H1"]})
    assert timeline["count"] >= 1
    assert all(item["object_id"] for item in timeline["events"])
    entity_timeline = handle_v1_get(release, "/v1/timeline", query={"id": ["ENT-API-H1"]})
    assert "events" in entity_timeline

    with pytest.raises(PublicObservatoryApiError, match="predecessor"):
        handle_v1_get(release, "/v1/diff", query={})
    with pytest.raises(PublicObservatoryApiError, match="not found"):
        handle_v1_get(release, "/v1/diff", query={"predecessor": [str(tmp_path / "nope")]})

    refuse_write("GET")
    with pytest.raises(PublicObservatoryApiError, match="refused"):
        refuse_write("PATCH")


def test_http_handler_etag_and_write_refusal(tmp_path: Path) -> None:
    release_dir = _build_release(tmp_path)
    server = make_v1_server(release_dir, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        base = f"http://{host}:{port}"
        with urllib.request.urlopen(f"{base}/v1/health") as response:
            body = json.loads(response.read().decode("utf-8"))
            etag = response.headers.get("ETag")
            assert body["read_only"] is True
            assert body["writes_supported"] is False
            assert "ThreadingHTTPServer" not in body["boundary"]
            assert "institutional" not in body["boundary"].lower() or "not institutional" in body["boundary"].lower()
            assert etag == etag_for_release(load_authorized_release(release_dir))
            assert response.headers.get("X-NeuroAI-API-Boundary")

        request = urllib.request.Request(
            f"{base}/v1/health",
            headers={"If-None-Match": etag},
            method="GET",
        )
        try:
            urllib.request.urlopen(request)
            raise AssertionError("expected 304")
        except urllib.error.HTTPError as exc:
            assert exc.code == 304

        for method in ("POST", "PUT", "DELETE"):
            req = urllib.request.Request(f"{base}/v1/entities", data=b"{}", method=method)
            try:
                urllib.request.urlopen(req)
                raise AssertionError(f"expected write refusal for {method}")
            except urllib.error.HTTPError as exc:
                assert exc.code == 405
                payload = json.loads(exc.read().decode("utf-8"))
                assert "refused" in payload["error"].lower()
                assert payload["boundary"] == API_BOUNDARY

        bad = urllib.request.Request(f"{base}/v1/nope")
        try:
            urllib.request.urlopen(bad)
            raise AssertionError("expected 400")
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
            payload = json.loads(exc.read().decode("utf-8"))
            assert "error" in payload
    finally:
        server.shutdown()
        server.server_close()


def test_empty_jsonl_and_blank_lines(tmp_path: Path) -> None:
    release_dir = _build_release(tmp_path)
    records = release_dir / "records" / "candidates.jsonl"
    records.write_text("\n\n", encoding="utf-8")
    release = load_authorized_release(release_dir)
    body = handle_v1_get(release, "/v1/candidates")
    assert body["count"] == 0
    assert body["items"] == []
