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
    assert "0.1.0" in result.stdout
