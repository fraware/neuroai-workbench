from __future__ import annotations

from pathlib import Path

import pytest

from neuroai_workbench.delta import compile_delta_from_workspace
from neuroai_workbench.monitoring import (
    adjudicate_change_candidate,
    build_refresh_candidate,
    create_change_candidate,
    initialize_monitoring,
    record_snapshot,
)
from neuroai_workbench.util import atomic_write_json, load_json

FIXTURES = Path(__file__).parents[1] / "fixtures" / "delta"
PREDECESSOR = FIXTURES / "synthetic_predecessor_release.json"


def _small_registry() -> list[dict[str, object]]:
    boundary = "Synthetic monitoring boundary."
    return [
        {
            "monitor_id": "MON-SRC-0001",
            "source_id": "SRC-0001",
            "url": "https://example.org/regulatory",
            "publisher": "Example regulator",
            "source_class": "REGULATORY_RECORD",
            "cadence": "WEEKLY",
            "last_successful_retrieval": "2026-07-01",
            "baseline_evidence_state": "CURRENT_SOURCE_RETRIEVED",
            "baseline_verification_state": "CURRENT_VERIFIED",
            "baseline_claim_boundary": boundary,
            "network_access_required": True,
            "current_status": "BASELINE_REGISTERED",
            "next_action": "RETRIEVE_AND_COMPARE",
        }
    ]


def test_compile_delta_from_workspace_end_to_end(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    registry_path = tmp_path / "registry.json"
    atomic_write_json(registry_path, _small_registry())
    initialize_monitoring(workspace, registry_path, actor="tester")

    first = record_snapshot(workspace, "SRC-0001", b"alpha", media_type="text/plain")
    changed = record_snapshot(workspace, "SRC-0001", b"beta", media_type="text/plain")
    candidate = create_change_candidate(
        workspace,
        "SRC-0001",
        changed["snapshot_id"],
        previous_snapshot_id=first["snapshot_id"],
        actor="tester",
    )
    adjudicate_change_candidate(
        workspace,
        candidate["candidate_id"],
        "ACCEPT",
        rationale="Synthetic acceptance for delta compile test.",
        change_class="REGULATORY_OR_MARKET_EVENT",
        materiality="MATERIAL",
        reopening_effect="NO_EFFECT",
        actor="tester",
    )
    build_refresh_candidate(workspace, "refresh-delta-test", "2026-08-02", actor="tester")

    result = compile_delta_from_workspace(
        workspace,
        "refresh-delta-test",
        PREDECESSOR,
        predecessor_release_id="v1.0-synthetic",
        actor="tester",
    )
    assert result["delta"]["metadata"]["status"] == "NON_CANONICAL"
    delta_path = workspace / result["path"]
    assert delta_path.is_file()
    stored = load_json(delta_path)
    assert stored["metadata"]["delta_id"] == result["delta"]["metadata"]["delta_id"]

    with pytest.raises(ValueError, match="Refusing to overwrite"):
        compile_delta_from_workspace(
            workspace,
            "refresh-delta-test",
            PREDECESSOR,
            predecessor_release_id="v1.0-synthetic",
        )


def test_compile_delta_from_workspace_with_operation_specs(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    registry_path = tmp_path / "registry.json"
    atomic_write_json(registry_path, _small_registry())
    initialize_monitoring(workspace, registry_path, actor="tester")
    first = record_snapshot(workspace, "SRC-0001", b"alpha", media_type="text/plain")
    changed = record_snapshot(workspace, "SRC-0001", b"beta", media_type="text/plain")
    candidate = create_change_candidate(
        workspace,
        "SRC-0001",
        changed["snapshot_id"],
        previous_snapshot_id=first["snapshot_id"],
    )
    adjudicate_change_candidate(
        workspace,
        candidate["candidate_id"],
        "ACCEPT",
        rationale="Field update required.",
        change_class="FIELD_UPDATE",
        materiality="NON_MATERIAL",
        reopening_effect="NO_EFFECT",
    )
    build_refresh_candidate(workspace, "refresh-specs", "2026-08-02")
    specs_path = tmp_path / "specs.json"
    atomic_write_json(
        specs_path,
        {
            candidate["candidate_id"]: [
                {
                    "operation_type": "UPDATE_FIELD_WITH_PREDECESSOR",
                    "target_section": "sources",
                    "record_id_field": "source_id",
                    "record_id": "SRC-0001",
                    "field": "baseline_verification_state",
                    "before_value": "CURRENT_VERIFIED",
                    "after_value": "CURRENT_PARTIAL",
                }
            ]
        },
    )
    result = compile_delta_from_workspace(
        workspace,
        "refresh-specs",
        PREDECESSOR,
        predecessor_release_id="v1.0-synthetic",
        operation_specs_path=specs_path,
    )
    assert result["delta"]["operations"][0]["operation_type"] == "UPDATE_FIELD_WITH_PREDECESSOR"


def test_compile_delta_from_workspace_rejects_invalid_specs(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    registry_path = tmp_path / "registry.json"
    atomic_write_json(registry_path, _small_registry())
    initialize_monitoring(workspace, registry_path)
    build_refresh_candidate(workspace, "refresh-bad-specs", "2026-08-02")
    specs_path = tmp_path / "bad-specs.json"
    atomic_write_json(specs_path, ["not-a-map"])
    with pytest.raises(ValueError, match="operation_specs must be a JSON object"):
        compile_delta_from_workspace(
            workspace,
            "refresh-bad-specs",
            PREDECESSOR,
            predecessor_release_id="v1.0-synthetic",
            operation_specs_path=specs_path,
        )


def test_compile_delta_from_workspace_rejects_invalid_predecessor(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    registry_path = tmp_path / "registry.json"
    atomic_write_json(registry_path, _small_registry())
    initialize_monitoring(workspace, registry_path)
    build_refresh_candidate(workspace, "refresh-bad-pred", "2026-08-02")
    bad_predecessor = tmp_path / "bad.json"
    atomic_write_json(bad_predecessor, ["not-a-release"])
    with pytest.raises(ValueError, match="Predecessor release must be a JSON object"):
        compile_delta_from_workspace(
            workspace,
            "refresh-bad-pred",
            bad_predecessor,
            predecessor_release_id="v1.0-synthetic",
        )


def test_compile_delta_from_workspace_rejects_missing_package(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    registry_path = tmp_path / "registry.json"
    atomic_write_json(registry_path, _small_registry())
    initialize_monitoring(workspace, registry_path, actor="tester")
    with pytest.raises(ValueError, match="No refresh package found"):
        compile_delta_from_workspace(
            workspace,
            "missing-version",
            PREDECESSOR,
            predecessor_release_id="v1.0-synthetic",
        )
