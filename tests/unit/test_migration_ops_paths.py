from __future__ import annotations

from pathlib import Path

from neuroai_workbench.migration_ops.decisions import apply_warning_dispositions, load_migration_decisions
from neuroai_workbench.migration_ops.ops_paths import ops_workspace_root, resolve_ops_relpath


def test_ops_workspace_root_requires_existing_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("NEUROAI_OPS_WORKSPACE", raising=False)
    assert ops_workspace_root() is None
    monkeypatch.setenv("NEUROAI_OPS_WORKSPACE", str(tmp_path / "missing"))
    assert ops_workspace_root() is None
    monkeypatch.setenv("NEUROAI_OPS_WORKSPACE", str(tmp_path))
    assert ops_workspace_root() == tmp_path.resolve()


def test_resolve_ops_relpath_rejects_escape(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NEUROAI_OPS_WORKSPACE", str(tmp_path))
    target = tmp_path / "a.json"
    target.write_text("{}", encoding="utf-8")
    assert resolve_ops_relpath("a.json") == target.resolve()
    assert resolve_ops_relpath("../a.json") is None
    assert resolve_ops_relpath("C:/Windows/a.json") is None
    assert resolve_ops_relpath("missing.json") is None


def test_load_and_apply_decisions(tmp_path: Path) -> None:
    path = tmp_path / "decisions.jsonl"
    path.write_text(
        '{"decision_id":"D1","subject_id":"WARN-1","disposition":"ACCEPTED"}\n',
        encoding="utf-8",
    )
    decisions = load_migration_decisions(path)
    updated = apply_warning_dispositions(
        [{"warning_id": "WARN-1", "human_disposition": "PENDING_REVIEW"}],
        {item["subject_id"]: item for item in decisions},
    )
    assert updated[0]["human_disposition"] == "ACCEPTED"
    assert load_migration_decisions(tmp_path / "missing.jsonl") == []
