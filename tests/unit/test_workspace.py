from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from neuroai_workbench.errors import WorkspaceError


def test_create_and_list_case(workspace):
    assessment = workspace.create_case("CASE-001", "Example case")
    assert assessment["assessment_metadata"]["assessment_id"] == "CASE-001"
    rows = workspace.list_cases()
    assert len(rows) == 1
    assert rows[0]["case_id"] == "CASE-001"
    assert rows[0]["valid"] is True


def test_duplicate_case_is_rejected(workspace):
    workspace.create_case("CASE-001", "Example case")
    with pytest.raises(WorkspaceError):
        workspace.create_case("CASE-001", "Duplicate")


def test_invalid_case_identifier_is_rejected(workspace):
    with pytest.raises(ValueError):
        workspace.create_case("../escape", "Bad")


def test_import_valid_example(workspace, example_assessment, tmp_path: Path):
    path = tmp_path / "assessment.json"
    path.write_text(json.dumps(example_assessment), encoding="utf-8")
    imported = workspace.import_case(path)
    case_id = imported["assessment_metadata"]["assessment_id"]
    assert workspace.load_case(case_id) == example_assessment


def test_import_invalid_example_is_rejected(workspace, example_assessment, tmp_path: Path):
    example_assessment["requirement_findings"] = []
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(example_assessment), encoding="utf-8")
    with pytest.raises(WorkspaceError):
        workspace.import_case(path)


def test_save_and_snapshot(workspace):
    assessment = workspace.create_case("CASE-001", "Example case")
    assessment["assessment_metadata"]["assessment_purpose"] = "Controlled test purpose"
    report = workspace.save_case("CASE-001", assessment, require_valid=True)
    assert report["valid"] is True
    snapshot = workspace.snapshot("CASE-001", label="freeze")
    assert snapshot["assessment_sha256"]
    assert (workspace.case_path("CASE-001") / "snapshots" / snapshot["snapshot_id"] / "assessment.json").is_file()


def test_delete_requires_exact_confirmation(workspace):
    workspace.create_case("CASE-001", "Example case")
    with pytest.raises(WorkspaceError):
        workspace.delete_case("CASE-001", "wrong")
    workspace.delete_case("CASE-001", "CASE-001")
    assert workspace.list_cases() == []


def test_workspace_open_and_version_guards(tmp_path: Path):
    from neuroai_workbench.workspace import Workspace

    with pytest.raises(WorkspaceError, match="No workspace.json"):
        Workspace.open(tmp_path / "missing")

    workspace = Workspace.initialize(tmp_path / "workspace")
    with pytest.raises(WorkspaceError, match="already exists"):
        Workspace.initialize(workspace.root)

    metadata = workspace.metadata
    metadata["workspace_version"] = "999"
    workspace.meta_path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(WorkspaceError, match="Unsupported workspace version"):
        Workspace.open(workspace.root)


def test_workspace_unknown_case_operations_and_validation_gate(workspace, example_assessment):
    with pytest.raises(WorkspaceError, match="Unknown case"):
        workspace.load_case("UNKNOWN")
    with pytest.raises(WorkspaceError, match="Unknown case"):
        workspace.save_case("UNKNOWN", example_assessment)
    with pytest.raises(WorkspaceError, match="Unknown case"):
        workspace.snapshot("UNKNOWN")
    with pytest.raises(WorkspaceError, match="Unknown case"):
        workspace.delete_case("UNKNOWN", "UNKNOWN")

    workspace.create_case("CASE-001", "Example case")
    invalid = json.loads(json.dumps(example_assessment))
    invalid["requirement_findings"] = []
    with pytest.raises(WorkspaceError, match="validation gate"):
        workspace.save_case("CASE-001", invalid, require_valid=True)


def test_list_cases_preserves_damaged_case_and_missing_cases_directory(workspace):
    workspace.create_case("CASE-001", "Example case")
    case_file = workspace.case_path("CASE-001") / "assessment.json"
    case_file.write_text("{not-json", encoding="utf-8")
    rows = workspace.list_cases()
    assert rows[0]["case_id"] == "CASE-001"
    assert rows[0]["valid"] is False
    assert rows[0]["error"]

    shutil.rmtree(workspace.cases_dir)
    assert workspace.list_cases() == []


def test_import_duplicate_and_snapshot_without_evidence_index(workspace, example_assessment, tmp_path: Path):
    source = tmp_path / "assessment.json"
    source.write_text(json.dumps(example_assessment), encoding="utf-8")
    imported = workspace.import_case(source, case_id="CASE-IMPORTED")
    assert imported["assessment_metadata"]["assessment_id"]
    with pytest.raises(WorkspaceError, match="already exists"):
        workspace.import_case(source, case_id="CASE-IMPORTED")

    evidence_index = workspace.case_path("CASE-IMPORTED") / "evidence/index.json"
    evidence_index.unlink()
    snapshot = workspace.snapshot("CASE-IMPORTED", label="no-evidence-index")
    snapshot_dir = workspace.case_path("CASE-IMPORTED") / "snapshots" / snapshot["snapshot_id"]
    assert not (snapshot_dir / "evidence-index.json").exists()
