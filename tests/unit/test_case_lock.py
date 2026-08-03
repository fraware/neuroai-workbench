from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Event
from typing import Any

from neuroai_workbench import evidence as evidence_module
from neuroai_workbench import workspace as workspace_module
from neuroai_workbench.case_lock import case_mutation_lock, case_mutation_lock_path
from neuroai_workbench.evidence import add_evidence_bytes


def _assert_call_blocks_on_case_lock(
    case_path: Path,
    monkeypatch,
    module: Any,
    call: Callable[[], Any],
) -> Any:
    attempted = Event()
    real_lock = case_mutation_lock

    @contextmanager
    def observed_lock(path: Path) -> Iterator[dict[str, Any]]:
        attempted.set()
        with real_lock(path) as owner:
            yield owner

    monkeypatch.setattr(module, "case_mutation_lock", observed_lock)
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        with real_lock(case_path):
            future = executor.submit(call)
            assert attempted.wait(timeout=2)
            time.sleep(0.05)
            assert not future.done()
        return future.result(timeout=5)
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


def test_case_lock_lives_outside_case_directory(workspace):
    workspace.create_case("CASE-001", "Example case")
    case_path = workspace.case_path("CASE-001")
    lock_path = case_mutation_lock_path(case_path)
    assert lock_path.parent == workspace.cases_dir / ".case-locks"
    assert case_path not in lock_path.parents


def test_assessment_save_uses_case_mutation_lock(workspace, monkeypatch):
    workspace.create_case("CASE-001", "Example case")
    case_path = workspace.case_path("CASE-001")
    assessment = workspace.load_case("CASE-001")
    result = _assert_call_blocks_on_case_lock(
        case_path,
        monkeypatch,
        workspace_module,
        lambda: workspace.save_case("CASE-001", assessment, actor="save-worker"),
    )
    assert result["validation_state"] in {"VALID", "DRAFT_INVALID"}


def test_snapshot_uses_case_mutation_lock(workspace, monkeypatch):
    workspace.create_case("CASE-001", "Example case")
    case_path = workspace.case_path("CASE-001")
    record = _assert_call_blocks_on_case_lock(
        case_path,
        monkeypatch,
        workspace_module,
        lambda: workspace.snapshot("CASE-001", actor="snapshot-worker", label="locked-snapshot"),
    )
    assert record["snapshot_id"].endswith("-locked-snapshot")


def test_evidence_registration_uses_case_mutation_lock(workspace, monkeypatch):
    workspace.create_case("CASE-001", "Example case")
    case_path = workspace.case_path("CASE-001")
    record = _assert_call_blocks_on_case_lock(
        case_path,
        monkeypatch,
        evidence_module,
        lambda: add_evidence_bytes(
            workspace,
            "CASE-001",
            "record.txt",
            b"controlled",
            title="Controlled record",
            actor="evidence-worker",
        ),
    )
    assert record["evidence_id"] == "EV-001"


def test_delete_uses_external_case_lock_without_recreating_case(workspace, monkeypatch):
    workspace.create_case("CASE-001", "Example case")
    case_path = workspace.case_path("CASE-001")
    lock_path = case_mutation_lock_path(case_path)
    _assert_call_blocks_on_case_lock(
        case_path,
        monkeypatch,
        workspace_module,
        lambda: workspace.delete_case("CASE-001", "CASE-001"),
    )
    assert not case_path.exists()
    assert not lock_path.exists()
