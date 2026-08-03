from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench.events import load_events
from neuroai_workbench.governance_scope import (
    GOVERNANCE_SCOPE_BOUNDARY,
    _hash_record,
    load_governance_scope_manifests,
    record_governance_scope_manifest,
    scope_object_for_path,
    verify_governance_scope_manifest,
    verify_governance_scope_records,
)
from neuroai_workbench.util import atomic_write_json
from neuroai_workbench.workspace import Workspace


def _workspace(tmp_path: Path) -> Workspace:
    return Workspace.initialize(tmp_path / "workspace")


def _artifacts(tmp_path: Path) -> tuple[dict[str, Path], dict[str, Path], list[dict[str, object]]]:
    public = tmp_path / "public"
    generated = tmp_path / "generated"
    archive = tmp_path / "archive"
    protected = tmp_path / "protected"
    for root in (public, generated, archive, protected):
        root.mkdir()

    files = {
        "predecessor": archive / "predecessor.json",
        "candidate": generated / "candidate.json",
        "delta": generated / "delta.json",
        "reopening": generated / "reopening.json",
        "products": generated / "products.json",
        "claims": public / "withheld-claims.json",
        "cycle": protected / "cycle-43.json",
    }
    for name, path in files.items():
        atomic_write_json(path, {"artifact": name, "status": "synthetic fixture"})

    roots = {
        "PUBLIC_GIT": public,
        "GENERATED_OUTPUT": generated,
        "ARCHIVE": archive,
    }
    bindings = {"protected-ref:cycle-43": files["cycle"]}
    objects = [
        scope_object_for_path(
            role="PREDECESSOR_RELEASE",
            label="Frozen predecessor",
            object_type="RELEASE",
            path=files["predecessor"],
            storage_boundary="ARCHIVE",
            boundary_root=archive,
            media_type="application/json",
        ),
        scope_object_for_path(
            role="SUCCESSOR_CANDIDATE",
            label="Successor candidate",
            object_type="SUCCESSOR_CANDIDATE",
            path=files["candidate"],
            storage_boundary="GENERATED_OUTPUT",
            boundary_root=generated,
        ),
        scope_object_for_path(
            role="DELTA",
            label="Non-canonical delta",
            object_type="DELTA",
            path=files["delta"],
            storage_boundary="GENERATED_OUTPUT",
            boundary_root=generated,
        ),
        scope_object_for_path(
            role="REOPENING_REGISTER",
            label="Reopening register",
            object_type="REOPENING_REGISTER",
            path=files["reopening"],
            storage_boundary="GENERATED_OUTPUT",
            boundary_root=generated,
        ),
        scope_object_for_path(
            role="PRODUCT_MANIFEST",
            label="Generated product manifest",
            object_type="PRODUCT_MANIFEST",
            path=files["products"],
            storage_boundary="GENERATED_OUTPUT",
            boundary_root=generated,
        ),
        scope_object_for_path(
            role="WITHHELD_CLAIMS",
            label="Withheld claims",
            object_type="CLAIM_SET",
            path=files["claims"],
            storage_boundary="PUBLIC_GIT",
            boundary_root=public,
        ),
        scope_object_for_path(
            role="CORE_CYCLE_EXECUTION",
            label="Protected core-cycle execution",
            object_type="CORE_CYCLE_EXECUTION",
            path=files["cycle"],
            storage_boundary="PROTECTED_WORKSPACE",
            protected_ref="cycle-43",
        ),
    ]
    return roots, bindings, objects


def _record(tmp_path: Path) -> tuple[Workspace, dict[str, Path], dict[str, Path], dict[str, object]]:
    workspace = _workspace(tmp_path)
    roots, bindings, objects = _artifacts(tmp_path)
    result = record_governance_scope_manifest(
        workspace,
        scope_label="Synthetic governance scope",
        objects=objects,
        boundary_roots=roots,
        protected_bindings=bindings,
    )
    return workspace, roots, bindings, result


def _error_codes(report: dict[str, object]) -> set[str]:
    errors = report["errors"]
    assert isinstance(errors, list)
    return {str(error.get("code")) for error in errors if isinstance(error, dict)}


def test_record_and_verify_governance_scope(tmp_path: Path) -> None:
    workspace, roots, bindings, result = _record(tmp_path)
    manifest = result["manifest"]
    assert isinstance(manifest, dict)
    assert manifest["manifest_sha256"] == _hash_record(manifest)
    assert manifest["release_authorization_performed"] is False
    assert manifest["boundary"] == GOVERNANCE_SCOPE_BOUNDARY
    assert result["verification"]["valid"] is True

    records = load_governance_scope_manifests(workspace)
    assert len(records) == 1
    report = verify_governance_scope_records(
        workspace,
        boundary_roots=roots,
        protected_bindings=bindings,
    )
    assert report["valid"] is True
    assert report["event_chain_valid"] is True
    assert report["counts"]["scope_manifests"] == 1
    assert report["release_authorization_performed"] is False

    events = load_events(workspace.root / "events.jsonl")
    assert events[-1]["action"] == "GOVERNANCE_SCOPE_RECORDED"
    assert events[-1]["payload"]["scope_id"] == manifest["scope_id"]
    assert events[-1]["payload"]["manifest_sha256"] == manifest["manifest_sha256"]
    assert Path(str(result["path"])).is_file()


def test_referenced_object_tampering_and_missing_files_are_detected(tmp_path: Path) -> None:
    workspace, roots, bindings, result = _record(tmp_path)
    manifest = result["manifest"]
    candidate = roots["GENERATED_OUTPUT"] / "candidate.json"
    atomic_write_json(candidate, {"artifact": "tampered"})
    report = verify_governance_scope_manifest(
        manifest,
        boundary_roots=roots,
        protected_bindings=bindings,
    )
    assert "REFERENCED_OBJECT_SHA256_MISMATCH" in _error_codes(report)

    candidate.unlink()
    report = verify_governance_scope_records(
        workspace,
        boundary_roots=roots,
        protected_bindings=bindings,
    )
    assert report["valid"] is False
    scope_errors = report["scopes"][0]["errors"]
    assert any(error.get("code") == "REFERENCED_OBJECT_MISSING" for error in scope_errors)


def test_manifest_tampering_is_detected(tmp_path: Path) -> None:
    _, roots, bindings, result = _record(tmp_path)
    manifest = json.loads(json.dumps(result["manifest"]))
    manifest["scope_label"] = "Tampered label"
    report = verify_governance_scope_manifest(
        manifest,
        boundary_roots=roots,
        protected_bindings=bindings,
    )
    assert "MANIFEST_SHA256_MISMATCH" in _error_codes(report)


def test_duplicate_missing_and_substituted_roles_are_detected(tmp_path: Path) -> None:
    _, roots, bindings, result = _record(tmp_path)
    manifest = json.loads(json.dumps(result["manifest"]))
    predecessor = next(item for item in manifest["objects"] if item["role"] == "PREDECESSOR_RELEASE")
    predecessor["role"] = "DELTA"
    predecessor["object_type"] = "RELEASE"
    manifest["manifest_sha256"] = _hash_record(manifest)
    report = verify_governance_scope_manifest(
        manifest,
        boundary_roots=roots,
        protected_bindings=bindings,
    )
    codes = _error_codes(report)
    assert "DUPLICATE_LOGICAL_ROLES" in codes
    assert "REQUIRED_ROLES_MISSING" in codes
    assert "ROLE_OBJECT_TYPE_MISMATCH" in codes


def test_protected_locator_and_binding_fail_closed(tmp_path: Path) -> None:
    _, roots, bindings, result = _record(tmp_path)
    manifest = result["manifest"]
    report = verify_governance_scope_manifest(
        manifest,
        boundary_roots=roots,
        protected_bindings={},
    )
    assert "OBJECT_REFERENCE_INVALID" in _error_codes(report)
    assert any("No protected binding supplied" in error.get("message", "") for error in report["errors"])

    leaked = json.loads(json.dumps(manifest))
    protected = next(item for item in leaked["objects"] if item["storage_boundary"] == "PROTECTED_WORKSPACE")
    protected["locator"] = "protected/private/cycle-43.json"
    leaked["manifest_sha256"] = _hash_record(leaked)
    report = verify_governance_scope_manifest(
        leaked,
        boundary_roots=roots,
        protected_bindings=bindings,
    )
    assert "OBJECT_REFERENCE_INVALID" in _error_codes(report)


def test_public_path_traversal_is_rejected(tmp_path: Path) -> None:
    _, roots, bindings, result = _record(tmp_path)
    manifest = json.loads(json.dumps(result["manifest"]))
    public = next(item for item in manifest["objects"] if item["storage_boundary"] == "PUBLIC_GIT")
    public["locator"] = "../withheld-claims.json"
    manifest["manifest_sha256"] = _hash_record(manifest)
    report = verify_governance_scope_manifest(
        manifest,
        boundary_roots=roots,
        protected_bindings=bindings,
    )
    assert "OBJECT_REFERENCE_INVALID" in _error_codes(report)


def test_release_authorization_flag_is_prohibited(tmp_path: Path) -> None:
    _, roots, bindings, result = _record(tmp_path)
    manifest = json.loads(json.dumps(result["manifest"]))
    manifest["release_authorization_performed"] = True
    manifest["manifest_sha256"] = _hash_record(manifest)
    report = verify_governance_scope_manifest(
        manifest,
        boundary_roots=roots,
        protected_bindings=bindings,
    )
    assert "RELEASE_AUTHORIZATION_PROHIBITED" in _error_codes(report)
    assert report["valid"] is False


def test_scope_reference_builder_rejects_invalid_inputs(tmp_path: Path) -> None:
    path = tmp_path / "object.json"
    atomic_write_json(path, {"object": "fixture"})
    missing = tmp_path / "missing.json"

    with pytest.raises(ValueError, match="does not exist"):
        scope_object_for_path(
            role="DELTA",
            label="Delta",
            object_type="DELTA",
            path=missing,
            storage_boundary="GENERATED_OUTPUT",
            boundary_root=tmp_path,
        )
    with pytest.raises(ValueError, match="requires object_type"):
        scope_object_for_path(
            role="DELTA",
            label="Delta",
            object_type="RELEASE",
            path=path,
            storage_boundary="GENERATED_OUTPUT",
            boundary_root=tmp_path,
        )
    with pytest.raises(ValueError, match="label must not be empty"):
        scope_object_for_path(
            role="DELTA",
            label=" ",
            object_type="DELTA",
            path=path,
            storage_boundary="GENERATED_OUTPUT",
            boundary_root=tmp_path,
        )
    with pytest.raises(ValueError, match="require protected_ref"):
        scope_object_for_path(
            role="CORE_CYCLE_EXECUTION",
            label="Cycle",
            object_type="CORE_CYCLE_EXECUTION",
            path=path,
            storage_boundary="PROTECTED_WORKSPACE",
        )
    with pytest.raises(ValueError, match="require boundary_root"):
        scope_object_for_path(
            role="DELTA",
            label="Delta",
            object_type="DELTA",
            path=path,
            storage_boundary="GENERATED_OUTPUT",
        )
    with pytest.raises(ValueError, match="valid only"):
        scope_object_for_path(
            role="DELTA",
            label="Delta",
            object_type="DELTA",
            path=path,
            storage_boundary="GENERATED_OUTPUT",
            boundary_root=tmp_path,
            protected_ref="not-allowed",
        )
    with pytest.raises(ValueError, match="escapes"):
        scope_object_for_path(
            role="DELTA",
            label="Delta",
            object_type="DELTA",
            path=path,
            storage_boundary="GENERATED_OUTPUT",
            boundary_root=tmp_path / "other-root",
        )


def test_record_refuses_invalid_scope_and_existing_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class _FixedUUID:
        hex = "a" * 32

    monkeypatch.setattr("neuroai_workbench.governance_scope.uuid4", lambda: _FixedUUID())
    workspace = _workspace(tmp_path)
    roots, bindings, objects = _artifacts(tmp_path)
    record_governance_scope_manifest(
        workspace,
        scope_label="Fixed scope",
        objects=objects,
        boundary_roots=roots,
        protected_bindings=bindings,
    )
    with pytest.raises(ValueError, match="already exists"):
        record_governance_scope_manifest(
            workspace,
            scope_label="Fixed scope",
            objects=objects,
            boundary_roots=roots,
            protected_bindings=bindings,
        )
    with pytest.raises(ValueError, match="label must not be empty"):
        record_governance_scope_manifest(
            workspace,
            scope_label=" ",
            objects=objects,
            boundary_roots=roots,
            protected_bindings=bindings,
        )


def test_record_verification_detects_duplicate_scope_and_event_failure(tmp_path: Path) -> None:
    workspace, roots, bindings, result = _record(tmp_path)
    manifest = result["manifest"]
    duplicate_path = workspace.root / "governance" / "scopes" / "duplicate.json"
    atomic_write_json(duplicate_path, manifest)

    report = verify_governance_scope_records(
        workspace,
        boundary_roots=roots,
        protected_bindings=bindings,
    )
    assert report["valid"] is False
    assert any("duplicate scope_id" in error for error in report["errors"])

    events_path = workspace.root / "events.jsonl"
    events_path.write_text("{}\n", encoding="utf-8")
    report = verify_governance_scope_records(
        workspace,
        boundary_roots=roots,
        protected_bindings=bindings,
    )
    assert report["valid"] is False
    assert any("matching GOVERNANCE_SCOPE_RECORDED event is missing" in error for error in report["errors"])
    assert report["event_chain_valid"] is False


def test_scope_without_protected_object_warns_but_remains_valid(tmp_path: Path) -> None:
    _, roots, _, result = _record(tmp_path)
    manifest = json.loads(json.dumps(result["manifest"]))
    manifest["objects"] = [item for item in manifest["objects"] if item["storage_boundary"] != "PROTECTED_WORKSPACE"]
    manifest["manifest_sha256"] = _hash_record(manifest)
    report = verify_governance_scope_manifest(manifest, boundary_roots=roots)
    assert report["valid"] is True
    assert report["warnings"] == ["No protected object is bound in this governance scope."]


def test_extended_fail_closed_validation_paths(tmp_path: Path) -> None:
    _, roots, bindings, result = _record(tmp_path)
    manifest = result["manifest"]
    path = tmp_path / "fixture.json"
    atomic_write_json(path, {"fixture": True})

    with pytest.raises(ValueError, match="Unsupported governance scope role"):
        scope_object_for_path(
            role="UNKNOWN",
            label="Unknown",
            object_type="DELTA",
            path=path,
            storage_boundary="GENERATED_OUTPUT",
            boundary_root=tmp_path,
        )
    with pytest.raises(ValueError, match="identify a file below"):
        scope_object_for_path(
            role="DELTA",
            label="Delta",
            object_type="DELTA",
            path=path,
            storage_boundary="GENERATED_OUTPUT",
            boundary_root=path,
        )

    mutations = [
        ("sha256", "invalid"),
        ("storage_boundary", "UNKNOWN"),
        ("locator", ""),
        ("locator", "protected-ref:leak"),
        ("locator", "nested\\object.json"),
        ("locator", "nested//object.json"),
    ]
    for field, value in mutations:
        candidate = json.loads(json.dumps(manifest))
        target = next(item for item in candidate["objects"] if item["role"] == "WITHHELD_CLAIMS")
        target[field] = value
        candidate["manifest_sha256"] = _hash_record(candidate)
        report = verify_governance_scope_manifest(
            candidate,
            boundary_roots=roots,
            protected_bindings=bindings,
        )
        assert report["valid"] is False
        assert "OBJECT_REFERENCE_INVALID" in _error_codes(report)

    report = verify_governance_scope_manifest(
        manifest,
        boundary_roots={"PUBLIC_GIT": roots["PUBLIC_GIT"], "ARCHIVE": roots["ARCHIVE"]},
        protected_bindings=bindings,
    )
    assert "OBJECT_REFERENCE_INVALID" in _error_codes(report)
    assert any("No verification root supplied" in error.get("message", "") for error in report["errors"])

    malformed = json.loads(json.dumps(manifest))
    malformed["objects"] = {}
    malformed["manifest_sha256"] = _hash_record(malformed)
    report = verify_governance_scope_manifest(malformed, boundary_roots=roots, protected_bindings=bindings)
    assert "REQUIRED_ROLES_MISSING" in _error_codes(report)

    non_object = json.loads(json.dumps(manifest))
    non_object["objects"][0] = "invalid-object-reference"
    non_object["manifest_sha256"] = _hash_record(non_object)
    report = verify_governance_scope_manifest(non_object, boundary_roots=roots, protected_bindings=bindings)
    assert "OBJECT_REFERENCE_INVALID" in _error_codes(report)

    unsupported = json.loads(json.dumps(manifest))
    target = next(item for item in unsupported["objects"] if item["role"] == "WITHHELD_CLAIMS")
    target["role"] = "UNKNOWN"
    unsupported["manifest_sha256"] = _hash_record(unsupported)
    report = verify_governance_scope_manifest(unsupported, boundary_roots=roots, protected_bindings=bindings)
    assert "UNSUPPORTED_OBJECT_ROLE" in _error_codes(report)


def test_invalid_record_non_object_file_and_corrupt_event_log(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    roots, bindings, objects = _artifacts(tmp_path)
    with pytest.raises(ValueError, match="failed verification"):
        record_governance_scope_manifest(
            workspace,
            scope_label="Incomplete scope",
            objects=[item for item in objects if item["role"] != "PREDECESSOR_RELEASE"],
            boundary_roots=roots,
            protected_bindings=bindings,
        )

    scopes = workspace.root / "governance" / "scopes"
    scopes.mkdir(parents=True, exist_ok=True)
    atomic_write_json(scopes / "non-object.json", ["ignored non-object record"])
    assert load_governance_scope_manifests(workspace) == []

    result = record_governance_scope_manifest(
        workspace,
        scope_label="Valid scope",
        objects=objects,
        boundary_roots=roots,
        protected_bindings=bindings,
    )
    assert result["verification"]["valid"] is True
    (workspace.root / "events.jsonl").write_text("{invalid-json\n", encoding="utf-8")
    report = verify_governance_scope_records(
        workspace,
        boundary_roots=roots,
        protected_bindings=bindings,
    )
    assert report["valid"] is False
    assert any("event log load failed" in error for error in report["errors"])
