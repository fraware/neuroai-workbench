from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import neuroai_workbench.api.v1 as api_module
from neuroai_workbench.api.v1 import (
    API_BOUNDARY,
    OBJECT_ROUTES,
    PublicObservatoryApiError,
    etag_for_release,
    handle_v1_get,
    load_candidate_preview,
    load_published_release,
    make_v1_server,
    read_jsonl,
    refuse_write,
    release_context,
)


def _json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _loader_files(root: Path) -> None:
    _json(
        root / "descriptor.json",
        {
            "candidate_id": "OBS-V2-CAND-TEST",
            "release_tag": "test",
            "workbench_compatibility_version": "0.3.0.dev0",
            "producer_workbench_commit": "1" * 40,
            "runtime_execution_pin": "2" * 40,
            "observatory_graph_schema_version": "1",
        },
    )
    _json(root / "manifest.json", {"manifest_sha256": "3" * 64})


def _projection_release(root: Path) -> dict:
    records = root / "records"
    records.mkdir(parents=True, exist_ok=True)
    for filename in OBJECT_ROUTES.values():
        (records / filename).write_text("", encoding="utf-8")

    entities = [
        {
            "object_class": "Entity",
            "entity_id": "ENT-1",
            "source_ids": ["SRC-1"],
            "observation_ids": ["OBS-1"],
            "evidence_state": "OBSERVED",
            "verification_state": "VERIFIED",
            "review_state": "REVIEWED",
            "claim_boundary": "Entity boundary",
            "prohibited_inferences": ["No clinical inference"],
            "canonical_sha256": "a" * 64,
            "valid_from": {"value": "2026", "precision": "YEAR"},
        }
    ]
    sources = [
        {
            "object_class": "Source",
            "source_id": "SRC-1",
            "observed_at": {"value": "2026-08-01", "precision": "DATE"},
            "canonical_sha256": "b" * 64,
        }
    ]
    observations = [
        {
            "object_class": "Observation",
            "observation_id": "OBS-1",
            "source_id": "SRC-1",
            "observed_at": {"value": "2026-08-02T10:00:00Z", "precision": "TIMESTAMP"},
        }
    ]
    assertions = [
        {
            "object_class": "Assertion",
            "assertion_id": "ASR-1",
            "source_ids": ["SRC-1"],
            "observation_ids": ["OBS-1"],
            "valid_until": {"value": "2026-12-31", "precision": "DATE"},
            "supersedes_assertion_ids": ["ASR-OLD"],
        }
    ]
    events = [
        {
            "object_class": "Event",
            "event_id": "EV-1",
            "source_ids": ["SRC-1"],
            "occurred_at": {"value": "2026-07-01", "precision": "DATE"},
        }
    ]
    decisions = [
        {
            "object_class": "ReopeningDecision",
            "reopening_decision_id": "RD-1",
            "decided_at": {"value": "2026-08-03", "precision": "DATE"},
        }
    ]
    payloads = {
        "entities.jsonl": entities,
        "sources.jsonl": sources,
        "observations.jsonl": observations,
        "assertions.jsonl": assertions,
        "events.jsonl": events,
        "reopening-decisions.jsonl": decisions,
    }
    for filename, rows in payloads.items():
        (records / filename).write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
    return {
        "release_dir": root,
        "descriptor": {
            "candidate_id": "OBS-V2-CAND-PUBLISHED",
            "release_tag": "published",
            "workbench_compatibility_version": "0.3.0.dev0",
            "producer_workbench_commit": "1" * 40,
            "runtime_execution_pin": "2" * 40,
            "observatory_graph_schema_version": "1",
        },
        "manifest": {"manifest_sha256": "3" * 64},
        "manifest_sha256": "3" * 64,
        "candidate_id": "OBS-V2-CAND-PUBLISHED",
        "release_authorized": True,
        "published": True,
        "canonical": True,
        "preview": False,
        "authorization_id": "OBSAUTH-1",
        "authorization_sha256": "4" * 64,
        "publication_id": "OBSPUB-1",
        "publication_sha256": "5" * 64,
        "boundary": API_BOUNDARY,
    }


def test_candidate_loader_file_and_verifier_guards(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(api_module, "verify_observatory_v2_s2_candidate", lambda path: ["bad candidate"])
    with pytest.raises(PublicObservatoryApiError, match="Invalid Observatory-v2 S2 candidate"):
        load_candidate_preview(tmp_path)

    monkeypatch.setattr(api_module, "verify_observatory_v2_s2_candidate", lambda path: [])
    with pytest.raises(PublicObservatoryApiError, match="requires descriptor.json"):
        load_candidate_preview(tmp_path)

    _json(tmp_path / "descriptor.json", [])
    _json(tmp_path / "manifest.json", {})
    with pytest.raises(PublicObservatoryApiError, match="must be objects"):
        load_candidate_preview(tmp_path)

    _loader_files(tmp_path)
    preview = load_candidate_preview(tmp_path)
    assert preview["candidate_id"] == "OBS-V2-CAND-TEST"
    assert preview["preview"] is True
    assert preview["canonical"] is False


def test_published_loader_requires_valid_binding_and_exact_governance_ids(tmp_path, monkeypatch) -> None:
    _loader_files(tmp_path)
    monkeypatch.setattr(api_module, "verify_observatory_v2_s2_candidate", lambda path: ["bad"])
    with pytest.raises(PublicObservatoryApiError, match="Invalid Observatory-v2 S2 candidate"):
        load_published_release(tmp_path)

    monkeypatch.setattr(api_module, "verify_observatory_v2_s2_candidate", lambda path: [])
    monkeypatch.setattr(
        api_module,
        "verify_s2_publication_binding",
        lambda path: {"valid": False, "errors": ["not published"]},
    )
    with pytest.raises(PublicObservatoryApiError, match="not published"):
        load_published_release(tmp_path)

    monkeypatch.setattr(api_module, "verify_s2_publication_binding", lambda path: {"valid": True, "errors": []})
    with pytest.raises(PublicObservatoryApiError, match="exact governance identities"):
        load_published_release(tmp_path)

    monkeypatch.setattr(
        api_module,
        "verify_s2_publication_binding",
        lambda path: {
            "valid": True,
            "errors": [],
            "authorization_id": "OBSAUTH-1",
            "authorization_sha256": "4" * 64,
            "publication_id": "OBSPUB-1",
            "publication_sha256": "5" * 64,
        },
    )
    release = load_published_release(tmp_path)
    assert release["canonical"] is True
    assert release["authorization_id"] == "OBSAUTH-1"
    assert release["publication_id"] == "OBSPUB-1"


def test_release_context_etag_and_jsonl_edges(tmp_path) -> None:
    release = _projection_release(tmp_path / "release")
    context = release_context(release)
    assert context["package_version"] == "0.3.0.dev0"
    assert context["producer_commit"] == "1" * 40
    assert context["canonical"] is True
    assert context["etag"] == etag_for_release(release)

    fallback = {
        "descriptor": {"package_version": "legacy", "producer_commit": "legacy-commit"},
        "manifest_sha256": "",
    }
    fallback_context = release_context(fallback)
    assert fallback_context["package_version"] == "legacy"
    assert fallback_context["producer_commit"] == "legacy-commit"
    assert fallback_context["etag"] == etag_for_release(fallback)

    assert read_jsonl(tmp_path / "missing.jsonl") == []
    path = tmp_path / "mixed.jsonl"
    path.write_text('\n[]\n{"entity_id":"ENT-X"}\n', encoding="utf-8")
    assert read_jsonl(path) == [{"entity_id": "ENT-X"}]


def test_projection_routes_filters_provenance_and_timeline(tmp_path) -> None:
    release = _projection_release(tmp_path / "release")
    health = handle_v1_get(release, "/v1/health")
    assert health["status"] == "ok"
    assert health["read_only"] is True
    assert handle_v1_get(release, "/v1")["status"] == "ok"
    assert handle_v1_get(release, "/v1/")["status"] == "ok"

    release_body = handle_v1_get(release, "/v1/release")
    assert release_body["descriptor"]["candidate_id"] == "OBS-V2-CAND-PUBLISHED"
    assert release_body["manifest"] == release["manifest"]

    entities = handle_v1_get(release, "/v1/entities")
    assert entities["count"] == 1
    assert handle_v1_get(release, "/v1/entities", query={"id": ["ENT-1"]})["count"] == 1
    assert handle_v1_get(release, "/v1/entities", query={"id": ["ENT-NONE"]})["count"] == 0
    for route in OBJECT_ROUTES:
        body = handle_v1_get(release, route)
        assert "items" in body and "count" in body

    why = handle_v1_get(release, "/v1/why", query={"id": ["ENT-1"]})
    assert why["object_class"] == "Entity"
    assert why["provenance"]["source_ids"] == ["SRC-1"]
    assert why["provenance"]["observation_ids"] == ["OBS-1"]
    assert why["why"]["prohibited_inferences"] == ["No clinical inference"]

    source = handle_v1_get(release, "/v1/provenance", query={"id": ["SRC-1"]})
    assert source["provenance"]["source_ids"] == ["SRC-1"]
    with pytest.raises(PublicObservatoryApiError, match=r"require \?id="):
        handle_v1_get(release, "/v1/why")
    with pytest.raises(PublicObservatoryApiError, match="Unknown object id"):
        handle_v1_get(release, "/v1/why", query={"id": ["UNKNOWN"]})

    timeline = handle_v1_get(release, "/v1/timeline")
    assert timeline["count"] == 6
    filtered = handle_v1_get(release, "/v1/timeline", query={"id": ["SRC-1"]})
    assert filtered["object_id"] == "SRC-1"
    assert filtered["count"] >= 4
    empty_filter = handle_v1_get(release, "/v1/timeline", query={"id": ["   "]})
    assert empty_filter["object_id"] is None


def test_projection_refuses_bad_context_routes_and_writes(tmp_path) -> None:
    release = _projection_release(tmp_path / "release")
    bad = dict(release)
    bad["published"] = False
    with pytest.raises(PublicObservatoryApiError, match="refuses noncanonical"):
        handle_v1_get(bad, "/v1/health")
    with pytest.raises(PublicObservatoryApiError, match="Unknown /v1 route"):
        handle_v1_get(release, "/v1/unknown")
    with pytest.raises(PublicObservatoryApiError, match="only serves /v1"):
        handle_v1_get(release, "/other")
    with pytest.raises(PublicObservatoryApiError, match="server-configured"):
        handle_v1_get(release, "/v1/diff")

    refuse_write("GET")
    refuse_write("HEAD")
    refuse_write("OPTIONS")
    with pytest.raises(PublicObservatoryApiError, match="Write method"):
        refuse_write("PATCH")


def test_http_handler_success_etag_error_and_all_write_refusals(tmp_path, monkeypatch) -> None:
    release = _projection_release(tmp_path / "release")
    monkeypatch.setattr(api_module, "load_published_release", lambda path: release)
    server = make_v1_server(tmp_path / "release", host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        base = f"http://{host}:{port}"
        with urllib.request.urlopen(f"{base}/v1/health") as response:
            assert response.status == 200
            etag = response.headers["ETag"]
            body = json.loads(response.read())
            assert body["status"] == "ok"
            assert response.headers["X-NeuroAI-API-Boundary"] == API_BOUNDARY[:200]

        request = urllib.request.Request(f"{base}/v1/health", headers={"If-None-Match": etag})
        with pytest.raises(urllib.error.HTTPError) as not_modified:
            urllib.request.urlopen(request)
        assert not_modified.value.code == 304
        assert not_modified.value.headers["ETag"] == etag
        not_modified.value.close()

        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(f"{base}/v1/unknown")
        assert error.value.code == 400
        error.value.close()

        for method in ("POST", "PUT", "DELETE"):
            request = urllib.request.Request(f"{base}/v1/health", data=b"{}", method=method)
            with pytest.raises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(request)
            assert error.value.code == 405
            assert error.value.headers["Allow"] == "GET, HEAD, OPTIONS"
            error.value.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
