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
from neuroai_workbench.observatory_graph import build_entity
from neuroai_workbench.observatory_publication import record_s2_authorization, record_s2_publication
from neuroai_workbench.observatory_s2_release import (
    CANDIDATE_FILE_PATHS,
    OBJECT_FILES,
    S2_CANDIDATE_BOUNDARY,
)
from neuroai_workbench.release import ReleaseCompiler
from neuroai_workbench.util import canonical_json_bytes, sha256_bytes


def _json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _published_release(tmp_path: Path) -> Path:
    root = tmp_path / "published"
    records = root / "records"
    migration = root / "migration"
    records.mkdir(parents=True)
    migration.mkdir(parents=True)

    frozen = {
        "V14": "a" * 64,
        "V16": "b" * 64,
        "DELTA16": "c" * 64,
        "V17": "d" * 64,
        "PRIMA17": "e" * 64,
        "SOURCE_REGISTER14": "f" * 64,
        "MONITOR15": "0" * 64,
    }
    gate_descriptor = {
        "release_authorized": False,
        "representational_scope_complete": True,
        "workbench_compatibility_version": "0.3.0.dev0",
        "producer_workbench_commit": "1" * 40,
        "runtime_execution_pin": "2" * 40,
        "observatory_graph_schema_version": "1",
        "s2_predecessor_commit": "3" * 40,
        "inputs": frozen,
    }
    gate_descriptor_sha = sha256_bytes(canonical_json_bytes(gate_descriptor))
    gate_manifest = {"descriptor_sha256": gate_descriptor_sha, "release_authorized": False}
    gate_manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(gate_manifest))
    decision = {
        "schema_version": "1",
        "decision_type": "OBSERVATORY_V2_GATE_A_MECHANICAL_DECISION",
        "decision": "PASS_REPRESENTATIONAL_MIGRATION_MECHANICALLY_COMPLETE",
        "gate_a_complete": True,
        "release_authorized": False,
        "representational_scope_complete": True,
        "native_v2_materialization_complete": False,
        "field_proof_sha256": "4" * 64,
        "gate_a_package_manifest_sha256": gate_manifest["manifest_sha256"],
        "gate_a_package_descriptor_sha256": gate_descriptor_sha,
        "producer_workbench_commit": "1" * 40,
        "runtime_execution_pin": "2" * 40,
        "s2_predecessor_commit": "3" * 40,
        "observatory_graph_schema_version": "1",
        "boundary": "mechanical test decision",
    }
    decision["decision_sha256"] = sha256_bytes(canonical_json_bytes(decision))
    _json(migration / "gate-a-descriptor.json", gate_descriptor)
    _json(migration / "gate-a-manifest.json", gate_manifest)
    _json(migration / "gate-a-decision.json", decision)

    rows = {
        "entities.jsonl": {"object_class": "Entity", "entity_id": "ENT-API-H1", "canonical_label": "System"},
        "sources.jsonl": {
            "object_class": "Source",
            "source_id": "SRC-API-H1",
            "evidence_state": "SOURCE_STATED",
            "claim_boundary": "fixture",
        },
        "assertions.jsonl": {
            "object_class": "Assertion",
            "assertion_id": "AST-API-H1",
            "source_ids": ["SRC-API-H1"],
            "evidence_state": "SOURCE_STATED",
            "verification_state": "RETRIEVAL_VERIFIED_BYTES_ONLY",
            "review_state": "NOT_REVIEWED",
            "claim_boundary": "fixture",
            "valid_from": {"value": "2026-01-01", "precision": "DATE"},
        },
    }
    for filename in OBJECT_FILES:
        row = rows.get(filename)
        payload = b"" if row is None else (json.dumps(row, sort_keys=True) + "\n").encode("utf-8")
        (records / filename).write_bytes(payload)
    for relative in sorted(CANDIDATE_FILE_PATHS):
        path = root / relative
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n", encoding="utf-8")
    file_entries = [
        {"path": relative, "sha256": sha256_bytes((root / relative).read_bytes())}
        for relative in sorted(CANDIDATE_FILE_PATHS)
    ]
    content_sha = sha256_bytes(canonical_json_bytes(file_entries))
    candidate_id = f"OBS-V2-CAND-{content_sha[:20].upper()}"
    descriptor = {
        "schema_version": "1",
        "release_type": "OBSERVATORY_V2_S2_CANDIDATE",
        "release_tag": "test-published",
        "candidate_id": candidate_id,
        "state": "NONCANONICAL_CANDIDATE",
        "canonical_publication_state": "NOT_AUTHORIZED",
        "release_authorized": False,
        "published": False,
        "record_counts": {
            "Entity": 1,
            "Source": 1,
            "Observation": 0,
            "Assertion": 1,
            "Event": 0,
            "Relationship": 0,
            "Candidate": 0,
            "ReopeningDecision": 0,
        },
        "candidate_content_sha256": content_sha,
        "workbench_compatibility_version": "0.3.0.dev0",
        "producer_workbench_commit": "1" * 40,
        "runtime_execution_pin": "2" * 40,
        "observatory_graph_schema_version": "1",
        "s2_predecessor": {"release_tag": "prior", "commit": "3" * 40},
        "frozen_inputs": frozen,
        "migration_proof": {
            "field_proof_sha256": "4" * 64,
            "gate_a_decision_sha256": decision["decision_sha256"],
            "gate_a_manifest_sha256": gate_manifest["manifest_sha256"],
            "gate_a_descriptor_sha256": gate_descriptor_sha,
            "native_candidate_manifest_sha256": "7" * 64,
        },
        "boundary": S2_CANDIDATE_BOUNDARY,
    }
    manifest = {
        "schema_version": "1",
        "candidate_id": candidate_id,
        "candidate_content_sha256": content_sha,
        "files": file_entries,
        "descriptor_sha256": sha256_bytes(canonical_json_bytes(descriptor)),
        "release_authorized": False,
        "published": False,
        "boundary": S2_CANDIDATE_BOUNDARY,
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    _json(root / "descriptor.json", descriptor)
    _json(root / "manifest.json", manifest)
    record_s2_authorization(root, decision="AUTHORIZE", decision_rationale="Authorize API fixture.")
    record_s2_publication(
        root,
        publication_evidence={"reference": "public-ref:test:api", "sha256": manifest["manifest_sha256"]},
    )
    return root


def test_compiler_only_candidate_is_refused_by_public_loader(tmp_path: Path) -> None:
    out = tmp_path / "compiler-candidate"
    entity = build_entity(entity_id="ENT-COMPILER", entity_type="SYSTEM", canonical_label="Compiler only")
    ReleaseCompiler().build([entity], out, candidate_id="CAND-COMPILER")
    with pytest.raises(PublicObservatoryApiError, match="Invalid Observatory-v2 S2 candidate"):
        load_authorized_release(out)


def test_why_timeline_release_and_filters(tmp_path: Path) -> None:
    release_dir = _published_release(tmp_path)
    release = load_authorized_release(release_dir)
    assert release["release_authorized"] is True
    assert release["published"] is True
    assert release["canonical"] is True
    assert API_BOUNDARY in release["boundary"]

    release_body = handle_v1_get(release, "/v1/release")
    assert release_body["candidate_id"] == release["candidate_id"]
    assert release_body["release_authorized"] is True
    filtered = handle_v1_get(release, "/v1/entities", query={"id": ["ENT-API-H1"]})
    assert filtered["count"] == 1
    assert handle_v1_get(release, "/v1/entities", query={"id": ["NOPE"]})["count"] == 0

    why = handle_v1_get(release, "/v1/why", query={"id": ["AST-API-H1"]})
    assert why["why"]["evidence_state"] == "SOURCE_STATED"
    assert "SRC-API-H1" in why["provenance"]["source_ids"]
    timeline = handle_v1_get(release, "/v1/timeline", query={"id": ["AST-API-H1"]})
    assert timeline["count"] == 1

    with pytest.raises(PublicObservatoryApiError, match=r"\?id="):
        handle_v1_get(release, "/v1/why")
    with pytest.raises(PublicObservatoryApiError, match="server-configured"):
        handle_v1_get(release, "/v1/diff")
    refuse_write("GET")
    with pytest.raises(PublicObservatoryApiError, match="refused"):
        refuse_write("PATCH")


def test_http_handler_etag_and_write_refusal(tmp_path: Path) -> None:
    release_dir = _published_release(tmp_path)
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
            assert body["published"] is True
            assert body["canonical"] is True
            assert etag == etag_for_release(load_authorized_release(release_dir))
            assert response.headers.get("X-NeuroAI-API-Boundary")

        request = urllib.request.Request(f"{base}/v1/health", headers={"If-None-Match": etag}, method="GET")
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        assert error.value.code == 304

        for method in ("POST", "PUT", "DELETE"):
            req = urllib.request.Request(f"{base}/v1/entities", data=b"{}", method=method)
            try:
                urllib.request.urlopen(req)
            except urllib.error.HTTPError as error:
                assert error.code == 405
                payload = json.loads(error.read().decode("utf-8"))
                assert "refused" in payload["error"].lower()
                assert payload["boundary"] == API_BOUNDARY
            except ConnectionResetError:
                # Windows can observe a client-side reset before urllib parses the 405 response.
                # The server must still fail closed and refuse the write method.
                pass
            else:
                raise AssertionError(f"{method} unexpectedly succeeded")
    finally:
        server.shutdown()
        server.server_close()
