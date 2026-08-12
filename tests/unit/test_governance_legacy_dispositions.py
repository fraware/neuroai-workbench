from __future__ import annotations

from pathlib import Path

from neuroai_workbench.events import append_event
from neuroai_workbench.governance_legacy import diagnose_legacy_governance_bindings
from neuroai_workbench.util import atomic_write_json
from neuroai_workbench.workspace import Workspace


def test_owner_disposition_legacy_binding_uses_issue_111_storage(tmp_path: Path) -> None:
    workspace = Workspace.initialize(tmp_path / "workspace")
    root = workspace.root / "governance" / "owner-dispositions"
    root.mkdir(parents=True)
    record = {
        "disposition_id": "GOVDISP-legacy",
        "disposition_sha256": "a" * 64,
    }
    path = root / "GOVDISP-legacy.json"
    atomic_write_json(path, record)
    append_event(
        workspace.root / "events.jsonl",
        "GOVERNANCE_OWNER_DISPOSITION_RECORDED",
        "local-test",
        {
            "disposition_id": record["disposition_id"],
            "disposition_sha256": record["disposition_sha256"],
        },
    )

    report = diagnose_legacy_governance_bindings(workspace)

    assert report["valid"] is True
    assert report["counts"]["LEGACY_BOUND"] == 1
    assert report["records"][0]["record_type"] == "OWNER-DISPOSITION"
    assert report["records"][0]["record_id"] == "GOVDISP-legacy"
