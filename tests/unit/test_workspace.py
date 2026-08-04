from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from neuroai_workbench.errors import WorkspaceError
from neuroai_workbench.util import sha256_file


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
    original_purpose = assessment["assessment_metadata"]["assessment_purpose"]
    assessment["assessment_metadata"]["assessment_purpose"] = "Controlled test purpose"
    before_sha = sha256_file(workspace.case_path("CASE-001") / "assessment.json")
    report = workspace.save_case("CASE-001", assessment, require_valid=True)
    assert report["valid"] is True
    assert report["validation_state"] == "VALID"
    assert report["persisted_as"] == "valid"
    assert report["prior_history"]["prior_assessment_sha256"] == before_sha
    recovered = workspace.load_assessment_history("CASE-001", before_sha)
    assert recovered["assessment_metadata"]["assessment_purpose"] == original_purpose
    assert (workspace.case_path("CASE-001") / "history" / "assessments" / f"{before_sha}.json").is_file()
    persistence = json.loads((workspace.case_path("CASE-001") / "persistence.json").read_text(encoding="utf-8"))
    assert persistence["validation_state"] == "VALID"
    snapshot = workspace.snapshot("CASE-001", label="freeze")
    assert snapshot["assessment_sha256"]
    assert (workspace.case_path("CASE-001") / "snapshots" / snapshot["snapshot_id"] / "assessment.json").is_file()


def test_save_optimistic_concurrency_refusal(workspace):
    assessment = workspace.create_case("CASE-001", "Example case")
    with pytest.raises(WorkspaceError, match="Optimistic concurrency"):
        workspace.save_case("CASE-001", assessment, expected_sha256="0" * 64)


def test_assessment_history_helpers_and_exclusive_records(workspace, tmp_path: Path):
    assessment = workspace.create_case("CASE-001", "Example case")
    with pytest.raises(ValueError, match="Invalid assessment history digest"):
        workspace.assessment_history_path("CASE-001", "not-a-digest")
    with pytest.raises(WorkspaceError, match="No recoverable assessment history"):
        workspace.load_assessment_history("CASE-001", "0" * 64)

    marker = workspace.case_path("CASE-001") / "exclusive.json"
    marker.write_text("{}\n", encoding="utf-8")
    with pytest.raises(WorkspaceError, match="Exclusive record already exists"):
        workspace.save_case(
            "CASE-001",
            assessment,
            exclusive_records=[(marker, {"ok": True})],
        )

    assessment["assessment_metadata"]["assessment_purpose"] = "Second save"
    first = workspace.save_case("CASE-001", assessment, require_valid=True)
    # Second save with identical prior digest reuses history file.
    assessment["assessment_metadata"]["assessment_purpose"] = "Third save"
    second = workspace.save_case(
        "CASE-001",
        assessment,
        require_valid=True,
        expected_sha256=first["after_sha256"],
        event_metadata={"note": "meta"},
        additional_events=[("CUSTOM_TEST_EVENT", {"x": 1})],
    )
    assert second["prior_history"]["prior_assessment_sha256"] == first["after_sha256"]


def test_draft_invalid_save_is_labeled(workspace):
    assessment = workspace.create_case("CASE-001", "Example case")
    assessment["requirement_findings"] = []
    report = workspace.save_case("CASE-001", assessment, require_valid=False)
    assert report["valid"] is False
    assert report["validation_state"] == "DRAFT_INVALID"
    assert report["persisted_as"] == "draft_invalid"
    persistence = json.loads((workspace.case_path("CASE-001") / "persistence.json").read_text(encoding="utf-8"))
    assert persistence["persisted_as"] == "draft_invalid"


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
