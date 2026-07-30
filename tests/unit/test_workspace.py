from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench.errors import WorkspaceError
from neuroai_workbench.validation import validate_assessment


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
