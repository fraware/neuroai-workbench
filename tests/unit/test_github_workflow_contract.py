from __future__ import annotations

import shutil
from pathlib import Path

from scripts.check_github_workflow_contract import validate

ROOT = Path(__file__).resolve().parents[2]
_CONTRACT_FILES = (
    ".github/required-checks.json",
    ".github/workflows/ci.yml",
    ".github/workflows/codeql.yml",
    ".github/workflows/dependency-review.yml",
    ".github/workflows/observatory-monitor-plan.yml",
    ".github/workflows/release.yml",
)


def _copy_contract(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    for relative in _CONTRACT_FILES:
        source = ROOT / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return root


def _replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_repository_workflow_contract_passes():
    assert validate(ROOT) == []


def test_unknown_workflow_fails_closed(tmp_path):
    root = _copy_contract(tmp_path)
    unknown = root / ".github/workflows/unknown.yml"
    unknown.write_text("name: Unknown\non: [pull_request]\njobs: {}\n", encoding="utf-8")
    assert any("Unaudited workflow files" in error for error in validate(root))


def test_mutable_action_reference_is_rejected(tmp_path):
    root = _copy_contract(tmp_path)
    workflow = root / ".github/workflows/ci.yml"
    _replace(
        workflow,
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
        "actions/checkout@v7",
    )
    assert any("not pinned to a 40-character commit SHA" in error for error in validate(root))


def test_pull_request_secret_dependency_is_rejected(tmp_path):
    root = _copy_contract(tmp_path)
    workflow = root / ".github/workflows/ci.yml"
    workflow.write_text(
        workflow.read_text(encoding="utf-8") + "\n# ${{ secrets.REPOSITORY_TOKEN }}\n",
        encoding="utf-8",
    )
    assert any("references repository secrets" in error for error in validate(root))


def test_permission_escalation_is_rejected(tmp_path):
    root = _copy_contract(tmp_path)
    workflow = root / ".github/workflows/dependency-review.yml"
    _replace(workflow, "  contents: read", "  contents: write")
    assert any("permissions" in error and "contract" in error for error in validate(root))


def test_job_and_required_check_name_drift_is_rejected(tmp_path):
    root = _copy_contract(tmp_path)
    workflow = root / ".github/workflows/codeql.yml"
    _replace(workflow, "    name: codeql", "    name: code-scanning")
    errors = validate(root)
    assert any("job 'analyze' name" in error for error in errors)


def test_unsafe_pr_trigger_is_rejected(tmp_path):
    root = _copy_contract(tmp_path)
    workflow = root / ".github/workflows/ci.yml"
    workflow.write_text(
        workflow.read_text(encoding="utf-8").replace("  pull_request:\n", "  pull_request_target:\n", 1),
        encoding="utf-8",
    )
    errors = validate(root)
    assert any("forbidden workflow marker" in error for error in errors)
    assert any("pull_request trigger is required" in error for error in errors)


def test_scheduled_workflow_trigger_drift_is_rejected(tmp_path):
    root = _copy_contract(tmp_path)
    workflow = root / ".github/workflows/observatory-monitor-plan.yml"
    _replace(workflow, '    - cron: "17 6 * * 1"', '    - cron: "0 0 * * *"')
    assert any("required trigger marker missing" in error for error in validate(root))
