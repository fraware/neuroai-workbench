from __future__ import annotations

import json
from pathlib import Path

from neuroai_workbench.events import append_event
from neuroai_workbench.governance_legacy import diagnose_legacy_governance_bindings
from neuroai_workbench.util import atomic_write_json
from neuroai_workbench.workspace import Workspace


def _workspace(tmp_path: Path) -> Workspace:
    return Workspace.initialize(tmp_path / "workspace")


def _scope(workspace: Workspace, scope_id: str = "GOVSCOPE-LEGACY") -> Path:
    root = workspace.root / "governance" / "scopes"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{scope_id}.json"
    atomic_write_json(path, {"scope_id": scope_id, "manifest_sha256": "a" * 64})
    return path


def test_legacy_exact_event_binding_is_classified_without_rewrite(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    path = _scope(workspace)
    original = path.read_bytes()
    append_event(
        workspace.root / "events.jsonl",
        "GOVERNANCE_SCOPE_RECORDED",
        "local-test",
        {"scope_id": "GOVSCOPE-LEGACY", "manifest_sha256": "a" * 64},
    )

    report = diagnose_legacy_governance_bindings(workspace)

    assert report["valid"] is True
    assert report["counts"]["LEGACY_BOUND"] == 1
    assert report["counts"]["TRANSACTION_BOUND"] == 0
    assert report["release_authorization_performed"] is False
    assert path.read_bytes() == original


def test_transaction_envelope_classifies_new_record(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _scope(workspace, "GOVSCOPE-TXN")
    append_event(
        workspace.root / "events.jsonl",
        "GOVERNANCE_SCOPE_RECORDED",
        "local-test",
        {
            "scope_id": "GOVSCOPE-TXN",
            "manifest_sha256": "a" * 64,
            "transaction_id": "GOVTXN-example",
        },
    )

    report = diagnose_legacy_governance_bindings(workspace)

    assert report["valid"] is True
    assert report["counts"]["TRANSACTION_BOUND"] == 1


def test_record_without_exact_event_binding_is_an_orphan(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _scope(workspace)
    append_event(workspace.root / "events.jsonl", "UNRELATED", "local-test", {"value": 1})

    report = diagnose_legacy_governance_bindings(workspace)

    assert report["valid"] is False
    assert report["counts"]["ORPHAN"] == 1
    assert "no exact event binding" in report["errors"][0]


def test_duplicate_exact_bindings_are_ambiguous(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _scope(workspace)
    payload = {"scope_id": "GOVSCOPE-LEGACY", "manifest_sha256": "a" * 64}
    append_event(workspace.root / "events.jsonl", "GOVERNANCE_SCOPE_RECORDED", "local-test", payload)
    append_event(workspace.root / "events.jsonl", "GOVERNANCE_SCOPE_RECORDED", "local-test", payload)

    report = diagnose_legacy_governance_bindings(workspace)

    assert report["valid"] is False
    assert report["counts"]["AMBIGUOUS"] == 1


def test_invalid_record_shape_fails_closed(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    root = workspace.root / "governance" / "opinions"
    root.mkdir(parents=True)
    (root / "broken.json").write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    append_event(workspace.root / "events.jsonl", "UNRELATED", "local-test", {})

    report = diagnose_legacy_governance_bindings(workspace)

    assert report["valid"] is False
    assert report["counts"]["INVALID_RECORD"] == 1


def test_invalid_event_chain_blocks_diagnosis(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    append_event(workspace.root / "events.jsonl", "UNRELATED", "local-test", {})
    with (workspace.root / "events.jsonl").open("ab") as handle:
        handle.write(b"corruption\n")

    report = diagnose_legacy_governance_bindings(workspace)

    assert report["valid"] is False
    assert report["records"] == []
    assert "diagnosis is blocked" in report["errors"][0]
