from __future__ import annotations

from pathlib import Path

import pytest

from neuroai_workbench.collector import LocalContentAddressedAdapter
from neuroai_workbench.monitoring import initialize_monitoring, record_snapshot
from neuroai_workbench.util import atomic_write_json, load_json
from tests.unit.test_collector_schemas import CONFIG_HASH
from tests.unit.test_monitoring import small_registry


def _adapter(tmp_path: Path, allowlisted: Path) -> LocalContentAddressedAdapter:
    return LocalContentAddressedAdapter(
        quarantine_root=tmp_path / "quarantine",
        allowlisted_roots=(allowlisted,),
        collector_version="0.3.0.dev0-collector",
        configuration_hash=CONFIG_HASH,
    )


def test_local_adapter_ingests_allowlisted_file_then_snapshot(tmp_path: Path) -> None:
    allowlisted = tmp_path / "allowlisted"
    allowlisted.mkdir()
    source_file = allowlisted / "controlled.json"
    source_file.write_text('{"fixture": true}\n', encoding="utf-8")

    records = small_registry()
    records.append(
        {
            "monitor_id": "MON-SRC-LOCAL",
            "source_id": "SRC-LOCAL",
            "url": "controlled-inputs/controlled.json",
            "publisher": "Controlled project input",
            "source_class": "CONTROLLED_LOCAL_INPUT",
            "cadence": "QUARTERLY",
            "last_successful_retrieval": "2026-07-29",
            "baseline_evidence_state": "PUBLIC_RESEARCH_ARTIFACT",
            "baseline_verification_state": "CURRENT_VERIFIED",
            "baseline_claim_boundary": "Local ingest proves byte identity only.",
            "network_access_required": False,
            "current_status": "BASELINE_REGISTERED",
            "next_action": "MIGRATE_TO_CONTENT_ADDRESSED_OBJECT",
        }
    )
    registry_path = tmp_path / "registry.json"
    atomic_write_json(registry_path, records)
    workspace = tmp_path / "workspace"
    initialize_monitoring(workspace, registry_path, actor="tester")

    adapter = _adapter(tmp_path, allowlisted)
    ingest = adapter.ingest_file(
        source_id="SRC-LOCAL",
        monitor_id="MON-SRC-LOCAL",
        source_path=source_file,
        media_type="application/json",
    )
    assert ingest["adapter_id"] == "local-content-addressed"
    assert (tmp_path / "quarantine" / ingest["quarantine_path"]).is_file()

    # Snapshot recording stays on the monitoring side (collector must not call it).
    data = Path(ingest["bytes_path"]).read_bytes()
    snapshot = record_snapshot(
        workspace,
        "SRC-LOCAL",
        data,
        media_type="application/json",
        retrieved_at="2026-08-02T12:00:00Z",
        retrieval_url=str(source_file),
        original_filename=str(ingest["original_filename"]),
        actor="local-adapter",
    )
    assert snapshot["sha256"] == ingest["sha256"]
    state = load_json(workspace / "observatory" / "monitoring" / "state.json")
    assert state["sources"]["SRC-LOCAL"]["last_snapshot_id"] == snapshot["snapshot_id"]


def test_local_adapter_refuses_path_outside_allowlist(tmp_path: Path) -> None:
    allowlisted = tmp_path / "allowlisted"
    allowlisted.mkdir()
    outside = tmp_path / "outside" / "secret.json"
    outside.parent.mkdir()
    outside.write_text("{}", encoding="utf-8")
    adapter = _adapter(tmp_path, allowlisted)
    with pytest.raises(ValueError, match="outside allowlisted roots"):
        adapter.ingest_file(
            source_id="SRC-LOCAL",
            monitor_id="MON-SRC-LOCAL",
            source_path=outside,
        )
