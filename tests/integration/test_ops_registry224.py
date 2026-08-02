"""Ops-gated integration tests for the full 224-source registry.

Skip unless NEUROAI_OPS_WORKSPACE points at an extracted Operations Starter root.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from neuroai_workbench.migration_ops.constants import OPS_WORKSPACE_ENV
from neuroai_workbench.monitoring import (
    build_source_health_report,
    initialize_monitoring,
    load_source_registry,
    plan_monitoring_run,
    validate_source_registry,
)

OPS_ROOT = Path(os.environ.get(OPS_WORKSPACE_ENV, ""))
REGISTRY_REL = Path("01_CONFIG/source_monitor_registry_v1.5.json")

pytestmark = pytest.mark.skipif(
    not OPS_ROOT.is_dir() or not (OPS_ROOT / REGISTRY_REL).is_file(),
    reason=f"{OPS_WORKSPACE_ENV} not configured with starter extract",
)


def test_full_registry_validates_224_sources(tmp_path: Path) -> None:
    registry = load_source_registry(OPS_ROOT / REGISTRY_REL)
    result = validate_source_registry(registry)
    assert result["valid"] is True
    assert result["counts"]["sources"] == 224
    assert any(item["code"] == "NON_PORTABLE_LOCAL_REFERENCE" for item in result["warnings"])


def test_plan_and_health_cover_all_monitor_ids(tmp_path: Path) -> None:
    workspace = tmp_path / "ops-workspace"
    init = initialize_monitoring(workspace, OPS_ROOT / REGISTRY_REL, actor="ops-integration")
    assert init["source_count"] == 224

    plan = plan_monitoring_run(workspace, as_of="2026-08-02")
    planned_monitor_ids = {item["monitor_id"] for bucket in ("due", "manual", "not_due") for item in plan[bucket]}
    registry = load_source_registry(OPS_ROOT / REGISTRY_REL)
    expected_monitor_ids = {str(item["monitor_id"]) for item in registry["sources"]}
    assert planned_monitor_ids == expected_monitor_ids
    assert plan["counts"]["due"] + plan["counts"]["manual"] + plan["counts"]["not_due"] == 224

    local_ids = {
        str(item["source_id"])
        for item in registry["sources"]
        if item.get("source_class") == "CONTROLLED_LOCAL_INPUT" or item.get("network_access_required") is False
    }
    assert local_ids == {"SRC-14-045", "SRC-14-046", "SRC-14-047"}
    due_ids = {item["source_id"] for item in plan["due"]}
    manual_ids = {item["source_id"] for item in plan["manual"]}
    assert local_ids.isdisjoint(due_ids)
    assert local_ids.issubset(manual_ids)
    assert all(
        item.get("manual_reason") == "CONTROLLED_LOCAL_OR_NO_NETWORK"
        for item in plan["manual"]
        if item["source_id"] in local_ids
    )

    # When cadence would mark locals due, they must still stay in manual.
    plan_due_window = plan_monitoring_run(workspace, as_of="2026-10-28")
    due_later = {item["source_id"] for item in plan_due_window["due"]}
    assert local_ids.isdisjoint(due_later)
    assert local_ids.issubset({item["source_id"] for item in plan_due_window["manual"]})

    health = build_source_health_report(workspace, as_of="2026-08-02", plan=plan)
    assert health["counts"]["sources"] == 224
    assert health["counts"]["silent_drop"] == 0
    assert health["silent_drop_source_ids"] == []
    assert health["counts"]["due"] == plan["counts"]["due"]
    assert health["counts"]["manual"] == plan["counts"]["manual"]
    assert health["counts"]["not_due"] == plan["counts"]["not_due"]
    health_monitor_ids = {item["monitor_id"] for item in health["sources"]}
    assert health_monitor_ids == expected_monitor_ids
