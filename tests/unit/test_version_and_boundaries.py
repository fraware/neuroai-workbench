from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from neuroai_workbench import __version__
from neuroai_workbench.evidence import add_evidence_base64, add_evidence_bytes, verify_evidence_files
from neuroai_workbench.events import append_event, verify_chain
from neuroai_workbench.metrics import summarize
from neuroai_workbench.observatory import import_release, load_imported_release, load_release, validate_release
from neuroai_workbench.resource_loader import read_resource_bytes, resource_path
from neuroai_workbench.workspace import Workspace


def test_version_propagates_to_workspace_and_resources(tmp_path: Path):
    workspace = Workspace.initialize(tmp_path / "workspace")
    assert workspace.metadata["workbench_version"] == __version__
    assert resource_path("KERNEL_REQUIREMENTS_v4.2.json").is_file()
    assert len(json.loads(read_resource_bytes("KERNEL_REQUIREMENTS_v4.2.json"))) == 78


def test_metrics_summary(example_assessment):
    result = summarize(example_assessment)
    assert result["counts"]["requirements"] == 78
    assert result["mechanical_state"] in {"BLOCKED", "NO MECHANICAL P0 BLOCKER"}


def test_evidence_rejects_invalid_input_and_detects_replacement(workspace):
    workspace.create_case("CASE-001", "Evidence")
    with pytest.raises(ValueError, match="empty"):
        add_evidence_bytes(workspace, "CASE-001", "empty.txt", b"", title="Empty")
    with pytest.raises(ValueError, match="Invalid evidence filename"):
        add_evidence_bytes(workspace, "CASE-001", "..", b"x", title="Bad")
    with pytest.raises(ValueError, match="Invalid base64"):
        add_evidence_base64(workspace, "CASE-001", "bad.bin", "%%%", title="Bad")

    record = add_evidence_bytes(workspace, "CASE-001", "data.txt", b"original", title="Data", link_to_assessment=False)
    target = workspace.case_path("CASE-001") / "evidence/objects" / record["stored_filename"]
    target.write_bytes(b"replacement")
    report = verify_evidence_files(workspace, "CASE-001")
    assert report["valid"] is False
    target.unlink()
    assert verify_evidence_files(workspace, "CASE-001")["results"][0]["exists"] is False


def test_invalid_event_chain_blocks_append(tmp_path: Path):
    path = tmp_path / "events.jsonl"
    append_event(path, "CREATED", "actor", {})
    row = json.loads(path.read_text())
    row["payload"] = {"tampered": True}
    path.write_text(json.dumps(row) + "\n")
    assert verify_chain(path)["valid"] is False
    with pytest.raises(ValueError, match="Event chain is invalid"):
        append_event(path, "SECOND", "actor", {})


def test_observatory_invalid_shapes_and_import_errors(tmp_path: Path):
    with pytest.raises(ValueError, match="JSON object"):
        bad = tmp_path / "bad.json"
        bad.write_text("[]")
        load_release(bad)

    report = validate_release({})
    assert report["valid"] is False
    assert any(row["code"] == "METADATA_REQUIRED" for row in report["errors"])

    repo = Path(__file__).resolve().parents[2]
    source = repo / "examples/observatory/evidence_depth_release_v1.4.json"
    value = load_release(source)
    broken = copy.deepcopy(value)
    broken["sources"][0]["source_id"] = ""
    broken["organizations"][0]["source_ids"] = ["MISSING"]
    broken["coverage"]["v1_4_effective_counts"]["verification_rate"] = 0
    validation = validate_release(broken)
    assert validation["valid"] is False
    codes = {row["code"] for row in validation["errors"]}
    assert {"IDENTIFIER_REQUIRED", "UNRESOLVED_SOURCE_REFERENCE", "VERIFICATION_RATE_MISMATCH"} <= codes

    invalid_path = tmp_path / "invalid-release.json"
    invalid_path.write_text(json.dumps(broken))
    with pytest.raises(ValueError, match="failed validation"):
        import_release(tmp_path / "workspace", invalid_path)
    with pytest.raises(FileNotFoundError, match="Unknown observatory"):
        load_imported_release(tmp_path / "workspace", "v9")
