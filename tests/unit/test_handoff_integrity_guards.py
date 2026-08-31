from __future__ import annotations

from pathlib import Path

import pytest

from neuroai_workbench.collector.handoff import (
    HandoffBlockedError,
    _persist_successor,
    _write_lineage,
    approve_quarantine_record,
    prepare_monitoring_handoff,
    reject_quarantine_record,
)
from neuroai_workbench.collector.ids import new_quarantine_id
from neuroai_workbench.collector.quarantine import (
    build_quarantine_record,
    persist_quarantine_record,
    write_quarantine_bytes,
)
from neuroai_workbench.util import atomic_write_json, load_json, sha256_bytes


def _pending_record(tmp_path: Path, *, filename: str = "page.html") -> dict:
    root = tmp_path / "quarantine"
    data = b"<html>fixture</html>"
    relative = f"objects/{filename}"
    write_quarantine_bytes(root, relative, data)
    result_id = "CRES-" + ("a" * 32)
    record = build_quarantine_record(
        result_id=result_id,
        source_id="SRC-1",
        monitor_id="MON-1",
        captured_at="2026-08-01T00:00:00Z",
        content_sha256=sha256_bytes(data),
        size_bytes=len(data),
        original_filename=filename,
        quarantine_path=relative,
        collector_version="0.0.0-test",
        configuration_hash="a" * 64,
    )
    persist_quarantine_record(root, record)
    atomic_write_json(
        root / "results" / f"{result_id}.json",
        {
            "result_id": result_id,
            "source_id": "SRC-1",
            "monitor_id": "MON-1",
            "media_type": "text/html",
            "sha256": sha256_bytes(data),
            "size_bytes": len(data),
            "quarantine_path": relative,
        },
    )
    return record


def test_persist_successor_refuses_overwrite_and_lineage_drift(tmp_path: Path) -> None:
    predecessor = _pending_record(tmp_path)
    root = tmp_path / "quarantine"
    approved = approve_quarantine_record(
        root, str(predecessor["quarantine_id"]), approved_by="reviewer", rationale="ok"
    )
    with pytest.raises(HandoffBlockedError, match="overwrite"):
        _persist_successor(root, predecessor, approved)

    drifted = dict(approved)
    drifted["quarantine_id"] = new_quarantine_id()
    _write_lineage(root, str(predecessor["quarantine_id"]), "OTHER", ["OTHER"])
    with pytest.raises(HandoffBlockedError, match="lineage tip"):
        _persist_successor(root, predecessor, drifted)


def test_reject_approve_guards_and_lineage_extension(tmp_path: Path) -> None:
    pending = _pending_record(tmp_path)
    root = tmp_path / "quarantine"
    qid = str(pending["quarantine_id"])

    rejected = reject_quarantine_record(root, qid, rejected_by="reviewer", rejection_reason="bad capture")
    assert rejected["approval_state"] == "REJECTED"
    with pytest.raises(HandoffBlockedError, match="cannot be approved"):
        approve_quarantine_record(root, qid, approved_by="reviewer")

    pending2 = _pending_record(tmp_path, filename="page2.html")
    qid2 = str(pending2["quarantine_id"])
    approved = approve_quarantine_record(root, qid2, approved_by="reviewer", rationale="ship")
    with pytest.raises(HandoffBlockedError, match="already approved"):
        approve_quarantine_record(root, str(approved["quarantine_id"]), approved_by="reviewer")

    successor = dict(approved)
    successor["quarantine_id"] = new_quarantine_id()
    successor["predecessor_quarantine_id"] = approved["quarantine_id"]
    successor["root_quarantine_id"] = approved.get("root_quarantine_id") or qid2
    extended = _persist_successor(root, approved, successor)
    lineage = load_json(root / "lineage" / f"{extended['root_quarantine_id']}.json")
    assert lineage["chain"][-1] == extended["quarantine_id"]
    assert lineage["chain"][-2] == approved["quarantine_id"]


def test_prepare_handoff_guards_and_success(tmp_path: Path) -> None:
    pending = _pending_record(tmp_path)
    root = tmp_path / "quarantine"
    qid = str(pending["quarantine_id"])
    with pytest.raises(HandoffBlockedError, match="Quarantine approval is required"):
        prepare_monitoring_handoff(root, qid)

    approved = approve_quarantine_record(root, qid, approved_by="reviewer", rationale="ship")
    with pytest.raises(HandoffBlockedError, match="Only pending"):
        reject_quarantine_record(root, qid, rejected_by="reviewer", rejection_reason="late")

    payload = prepare_monitoring_handoff(root, str(approved["quarantine_id"]))
    assert payload.sha256 == approved["sha256"]
    assert payload.result_id == approved["result_id"]
    assert payload.as_dict()["handoff_state"] == "READY_FOR_MONITORING_SNAPSHOT"

    bytes_path = root / str(approved["quarantine_path"])
    bytes_path.unlink()
    with pytest.raises(HandoffBlockedError, match="bytes missing"):
        prepare_monitoring_handoff(root, str(approved["quarantine_id"]))
