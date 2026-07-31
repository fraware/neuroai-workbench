from __future__ import annotations

import json

from neuroai_workbench.events import append_event, verify_chain


def test_event_chain_valid(workspace):
    workspace.create_case("CASE-001", "Example case")
    path = workspace.case_path("CASE-001") / "events.jsonl"
    append_event(path, "TEST", "tester", {"value": 1})
    report = verify_chain(path)
    assert report["valid"]
    assert report["event_count"] == 2


def test_event_chain_detects_payload_tamper(workspace):
    workspace.create_case("CASE-001", "Example case")
    path = workspace.case_path("CASE-001") / "events.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    event = json.loads(lines[0])
    event["payload"]["case_id"] = "CHANGED"
    lines[0] = json.dumps(event)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = verify_chain(path)
    assert not report["valid"]
    assert any("event_hash mismatch" in error for error in report["errors"])


def test_event_chain_detects_truncation_link(workspace):
    workspace.create_case("CASE-001", "Example case")
    path = workspace.case_path("CASE-001") / "events.jsonl"
    append_event(path, "SECOND", "tester", {})
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text(lines[1] + "\n", encoding="utf-8")
    report = verify_chain(path)
    assert not report["valid"]
