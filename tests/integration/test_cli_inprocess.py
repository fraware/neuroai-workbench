from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench import cli


def parse_stdout(capsys):
    return json.loads(capsys.readouterr().out)


def test_cli_inprocess_full_lifecycle(tmp_path: Path, capsys):
    workspace = tmp_path / "workspace"
    assert cli.main(["init", str(workspace), "--name", "In-process workspace"]) == 0
    assert parse_stdout(capsys)["metadata"]["workbench_version"] == "0.2.1"

    assert cli.main(["doctor", "--workspace", str(workspace)]) == 0
    assert parse_stdout(capsys)["cases"] == []

    assert cli.main(["case-create", str(workspace), "CASE-001", "--title", "Case one"]) == 0
    created = parse_stdout(capsys)
    assert created["assessment_metadata"]["assessment_id"] == "CASE-001"

    list_out = tmp_path / "cases.json"
    assert cli.main(["case-list", str(workspace), "--out", str(list_out)]) == 0
    assert json.loads(list_out.read_text())["cases"][0]["case_id"] == "CASE-001"

    show_out = tmp_path / "show.json"
    assert cli.main(["case-show", str(workspace), "CASE-001", "--out", str(show_out)]) == 0
    assessment = json.loads(show_out.read_text())
    assessment["assessment_metadata"]["assessment_purpose"] = "In-process test"
    replacement = tmp_path / "replacement.json"
    replacement.write_text(json.dumps(assessment))
    assert cli.main(["case-save", str(workspace), "CASE-001", str(replacement), "--require-valid"]) == 0
    assert parse_stdout(capsys)["valid"] is True

    assert cli.main(["validate", "--workspace", str(workspace), "--case-id", "CASE-001"]) == 0
    assert parse_stdout(capsys)["valid"] is True
    assert cli.main(["summary", "--workspace", str(workspace), "--case-id", "CASE-001"]) == 0
    assert parse_stdout(capsys)["counts"]["requirements"] == 78

    assert cli.main(["snapshot", str(workspace), "CASE-001", "--label", "freeze"]) == 0
    assert parse_stdout(capsys)["assessment_sha256"]

    evidence_file = tmp_path / "evidence.txt"
    evidence_file.write_text("controlled bytes\n")
    assert cli.main([
        "evidence-add", str(workspace), "CASE-001", str(evidence_file),
        "--title", "Evidence", "--type", "OTHER", "--source", "TEST",
    ]) == 0
    evidence = parse_stdout(capsys)
    assert evidence["evidence_id"] == "EV-001"

    assert cli.main(["evidence-verify", str(workspace), "CASE-001"]) == 0
    assert parse_stdout(capsys)["valid"] is True
    assert cli.main(["events-verify", str(workspace), "CASE-001"]) == 0
    assert parse_stdout(capsys)["valid"] is True

    bundle = tmp_path / "case.zip"
    assert cli.main(["bundle", str(workspace), "CASE-001", str(bundle)]) == 0
    assert parse_stdout(capsys)["event_chain_valid"] is True
    assert bundle.is_file()


def test_cli_import_migrate_compare_and_observatory(tmp_path: Path, capsys):
    repo = Path(__file__).resolve().parents[2]
    examples = repo / "examples" / "assessments"
    workspace = tmp_path / "workspace"
    assert cli.main(["init", str(workspace)]) == 0
    capsys.readouterr()

    example = examples / "PILOT-02_FDA_Adaptive_DBS_v4.2.json"
    assert cli.main(["case-import", str(workspace), str(example)]) == 0
    assert parse_stdout(capsys)["assessment_metadata"]["assessment_id"]

    source = repo / "tests" / "fixtures" / "PILOT-02_v4.1.2.json"
    migrated = tmp_path / "migrated.json"
    assert cli.main(["migrate", str(source), str(migrated)]) == 0
    assert parse_stdout(capsys)["sha256"]

    compare_out = tmp_path / "compare.json"
    assert cli.main([
        "compare",
        str(examples / "PILOT-01_BrainGate2_T15_v4.2.json"),
        str(examples / "PILOT-02_FDA_Adaptive_DBS_v4.2.json"),
        "--labels", "BrainGate", "aDBS", "--out", str(compare_out),
    ]) == 0
    assert len(json.loads(compare_out.read_text())["cases"]) == 2

    release = repo / "examples" / "observatory" / "evidence_depth_release_v1.4.json"
    assert cli.main(["observatory-verify", str(release)]) == 0
    assert parse_stdout(capsys)["valid"] is True
    assert cli.main(["observatory-import", str(workspace), str(release)]) == 0
    parse_stdout(capsys)
    assert cli.main(["observatory-summary", "--workspace", str(workspace), "--version", "v1.4"]) == 0
    assert parse_stdout(capsys)["metadata"]["version"] == "v1.4"
    assert cli.main(["observatory-queue", "--release", str(release)]) == 0
    assert parse_stdout(capsys)["counts"]["organizations"] == 3


def test_cli_failure_paths(tmp_path: Path, capsys, monkeypatch):
    assert cli.main(["validate", "--case-id", "UNKNOWN"]) == 2
    capsys.readouterr()

    repo = Path(__file__).resolve().parents[2]
    example = repo / "examples" / "assessments" / "PILOT-02_FDA_Adaptive_DBS_v4.2.json"
    assert cli.main(["compare", str(example), "--labels", "one", "two"]) == 2
    capsys.readouterr()

    workspace = tmp_path / "workspace"
    cli.main(["init", str(workspace)])
    capsys.readouterr()
    called = {}

    def fake_serve(ws, host, port, *, allow_network):
        called.update(host=host, port=port, allow_network=allow_network, root=ws.root)

    monkeypatch.setattr(cli, "serve", fake_serve)
    assert cli.main(["serve", str(workspace), "--port", "9999", "--allow-network"]) == 0
    assert called["allow_network"] is True
