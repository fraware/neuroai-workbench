from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run(*args, check=True):
    result = subprocess.run([sys.executable, "-m", "neuroai_workbench", *args], text=True, capture_output=True)
    if check and result.returncode != 0:
        raise AssertionError(result.stderr + result.stdout)
    return result


def test_cli_workspace_lifecycle(tmp_path: Path):
    workspace = tmp_path / "workspace"
    assert run("init", str(workspace)).returncode == 0
    assert run("case-create", str(workspace), "CASE-001", "--title", "CLI case").returncode == 0
    validation = run("validate", "--workspace", str(workspace), "--case-id", "CASE-001")
    assert json.loads(validation.stdout)["valid"] is True
    summary = json.loads(run("summary", "--workspace", str(workspace), "--case-id", "CASE-001").stdout)
    assert summary["counts"]["requirements"] == 78


def test_cli_version():
    result = run("--version")
    assert "0.2.1" in result.stdout


def test_cli_observatory_commands(tmp_path: Path):
    example = Path(__file__).parents[2] / "examples" / "observatory" / "evidence_depth_release_v1.4.json"
    verify = run("observatory-verify", str(example))
    assert json.loads(verify.stdout)["valid"] is True
    summary = json.loads(run("observatory-summary", "--release", str(example)).stdout)
    assert summary["coverage"]["verification_rate"] > 0.9
    workspace = tmp_path / "workspace"
    run("init", str(workspace))
    run("observatory-import", str(workspace), str(example))
    imported = json.loads(run("observatory-summary", "--workspace", str(workspace), "--version", "v1.4").stdout)
    assert imported["metadata"]["version"] == "v1.4"
