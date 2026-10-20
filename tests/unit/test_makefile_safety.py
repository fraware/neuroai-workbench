"""Regression tests: development Makefile must preserve user-controlled data."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(shutil.which("make") is None, reason="make executable is unavailable")


def _copy_makefile(tmp_path: Path) -> None:
    """Test actual Make targets in an isolated scratch directory."""
    shutil.copyfile(ROOT / "Makefile", tmp_path / "Makefile")


@pytest.mark.parametrize("existing_target", ["directory", "dangling_symlink"])
def test_demo_refuses_to_overwrite_existing_workspace(tmp_path: Path, existing_target: str) -> None:
    """Demo preparation must never delete an existing workspace or symlink."""
    _copy_makefile(tmp_path)
    workspace = tmp_path / "workspaces" / "demo"
    workspace.parent.mkdir()
    if existing_target == "directory":
        workspace.mkdir()
        sentinel = workspace / "evidence.bin"
        sentinel.write_bytes(b"controlled-local-evidence")
    else:
        workspace.symlink_to(tmp_path / "unavailable-target", target_is_directory=True)

    result = subprocess.run(
        ["make", "-f", "Makefile", "demo", f"WORKSPACE={workspace}"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )

    assert result.returncode != 0
    assert "Refusing to overwrite" in result.stderr
    if existing_target == "directory":
        assert sentinel.read_bytes() == b"controlled-local-evidence"
    else:
        assert workspace.is_symlink()


def test_clean_removes_only_disposable_build_state(tmp_path: Path) -> None:
    """Clean removes reproducible outputs while retaining workspaces and reports."""
    _copy_makefile(tmp_path)
    workspace = tmp_path / "workspaces" / "research-case"
    workspace.mkdir(parents=True)
    evidence = workspace / "observation.bin"
    evidence.write_bytes(b"must-not-delete")

    report_dir = tmp_path / "artifacts"
    report_dir.mkdir()
    report = report_dir / "research-report.json"
    report.write_text('{"status": "noncanonical"}', encoding="utf-8")

    for directory in ("src", "scripts", "tests", "build", "dist", ".pytest_cache", "htmlcov"):
        (tmp_path / directory).mkdir()
    (tmp_path / "src" / "__pycache__").mkdir()
    (tmp_path / "src" / "__pycache__" / "example.pyc").write_bytes(b"cache")
    (tmp_path / "tests" / "example.pyc").write_bytes(b"cache")

    result = subprocess.run(
        ["make", "-f", "Makefile", "clean"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )

    assert result.returncode == 0, result.stderr
    assert evidence.read_bytes() == b"must-not-delete"
    assert report.read_text(encoding="utf-8") == '{"status": "noncanonical"}'
    for directory in ("build", "dist", ".pytest_cache", "htmlcov", "src/__pycache__"):
        assert not (tmp_path / directory).exists()
    assert not (tmp_path / "tests" / "example.pyc").exists()
