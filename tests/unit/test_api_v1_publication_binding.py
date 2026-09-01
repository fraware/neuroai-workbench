from __future__ import annotations

import json

import pytest

from neuroai_workbench.api.v1 import (
    PublicObservatoryApiError,
    handle_v1_get,
    load_candidate_preview,
    load_published_release,
)
from neuroai_workbench.observatory_publication import record_s2_authorization, record_s2_publication
from neuroai_workbench.observatory_s2_release import OBJECT_FILES, S2_CANDIDATE_BOUNDARY
from neuroai_workbench.util import canonical_json_bytes, sha256_bytes


def _json(path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _candidate(root, *, release_tag: str, entity_id: str):
    records = root / "records"
    records.mkdir(parents=True, exist_ok=True)
    file_entries = []
    for filename in OBJECT_FILES:
        payload = b""
        if filename == "entities.jsonl":
            payload = f'{{"object_class":"Entity","entity_id":"{entity_id}"}}\n'.encode()
        path = records / filename
        path.write_bytes(payload)
        file_entries.append({"path": f"records/{filename}", "sha256": sha256_bytes(payload)})
    file_entries.sort(key=lambda item: item["path"])
    content_sha = sha256_bytes(canonical_json_bytes(file_entries))
    candidate_id = f"OBS-V2-CAND-{content_sha[:20].upper()}"
    descriptor = {
        "schema_version": "1",
        "release_type": "OBSERVATORY_V2_S2_CANDIDATE",
        "release_tag": release_tag,
        "candidate_id": candidate_id,
        "state": "NONCANONICAL_CANDIDATE",
        "canonical_publication_state": "NOT_AUTHORIZED",
        "release_authorized": False,
        "published": False,
        "record_counts": {
            "Entity": 1,
            "Source": 0,
            "Observation": 0,
            "Assertion": 0,
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
        "migration_proof": {
            "field_proof_sha256": "4" * 64,
            "gate_a_manifest_sha256": "5" * 64,
            "gate_a_descriptor_sha256": "6" * 64,
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
    return root


def _publish(release) -> None:
    record_s2_authorization(release, decision="AUTHORIZE", decision_rationale="Authorize exact candidate.")
    manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))
    record_s2_publication(
        release,
        publication_evidence={
            "reference": f"public-ref:github-release:{release.name}",
            "sha256": manifest["manifest_sha256"],
        },
    )


def test_candidate_preview_is_explicitly_noncanonical(tmp_path) -> None:
    release = _candidate(tmp_path / "candidate", release_tag="candidate", entity_id="ORG-1")
    preview = load_candidate_preview(release)
    assert preview["preview"] is True
    assert preview["canonical"] is False
    assert preview["release_authorized"] is False
    with pytest.raises(PublicObservatoryApiError, match="not published"):
        load_published_release(release)


def test_public_loader_requires_exact_authorization_and_publication(tmp_path) -> None:
    release = _candidate(tmp_path / "published", release_tag="published", entity_id="ORG-1")
    record_s2_authorization(release, decision="AUTHORIZE", decision_rationale="Authorize exact candidate.")
    with pytest.raises(PublicObservatoryApiError, match="not published"):
        load_published_release(release)

    manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))
    publication = record_s2_publication(
        release,
        publication_evidence={"reference": "public-ref:github-release:published", "sha256": manifest["manifest_sha256"]},
    )["publication"]
    loaded = load_published_release(release)
    assert loaded["canonical"] is True
    assert loaded["published"] is True
    assert loaded["release_authorized"] is True
    assert loaded["publication_id"] == publication["publication_id"]

    body = handle_v1_get(loaded, "/v1/entities")
    assert body["canonical"] is True
    assert body["published"] is True
    assert body["count"] == 1
    assert body["items"][0]["entity_id"] == "ORG-1"


def test_public_handler_refuses_preview_context_even_if_called_directly(tmp_path) -> None:
    release = _candidate(tmp_path / "candidate", release_tag="candidate", entity_id="ORG-1")
    preview = load_candidate_preview(release)
    with pytest.raises(PublicObservatoryApiError, match="refuses noncanonical"):
        handle_v1_get(preview, "/v1/entities")


def test_public_diff_rejects_unpublished_predecessor(tmp_path) -> None:
    current_dir = _candidate(tmp_path / "current", release_tag="current", entity_id="ORG-2")
    predecessor_dir = _candidate(tmp_path / "predecessor", release_tag="predecessor", entity_id="ORG-1")
    _publish(current_dir)
    current = load_published_release(current_dir)

    with pytest.raises(PublicObservatoryApiError, match="not published"):
        handle_v1_get(
            current,
            "/v1/diff",
            query={"predecessor": [str(predecessor_dir)]},
        )


def test_public_diff_accepts_two_published_releases(tmp_path) -> None:
    predecessor_dir = _candidate(tmp_path / "predecessor", release_tag="predecessor", entity_id="ORG-1")
    current_dir = _candidate(tmp_path / "current", release_tag="current", entity_id="ORG-2")
    _publish(predecessor_dir)
    _publish(current_dir)
    current = load_published_release(current_dir)
    body = handle_v1_get(current, "/v1/diff", query={"predecessor": [str(predecessor_dir)]})
    assert body["canonical"] is True
    assert body["predecessor_candidate_id"]
    assert body["successor_candidate_id"]
