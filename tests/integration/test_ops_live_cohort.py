"""Ops-gated live cohort collection (skipped unless NEUROAI_LIVE_COLLECTION=1)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from neuroai_workbench.migration_ops.constants import OPS_WORKSPACE_ENV
from neuroai_workbench.shadow_refresh import LIVE_COLLECTION_ENV, SHADOW_EVALUATION_STATUS

OPS_ROOT = Path(os.environ.get(OPS_WORKSPACE_ENV, ""))
REPO = Path(__file__).resolve().parents[2]

pytestmark = [
    pytest.mark.skipif(
        not OPS_ROOT.is_dir() or not (OPS_ROOT / "01_CONFIG" / "source_monitor_registry_v1.5.json").is_file(),
        reason=f"{OPS_WORKSPACE_ENV} not configured with starter extract",
    ),
    pytest.mark.skipif(
        os.environ.get(LIVE_COLLECTION_ENV, "").strip() != "1",
        reason=f"{LIVE_COLLECTION_ENV}=1 required for live network cohort collection",
    ),
]


def test_live_reviewed_cohort_collection_writes_observed_artifacts(tmp_path: Path) -> None:
    output = tmp_path / "shadow-live"
    env = os.environ.copy()
    env[LIVE_COLLECTION_ENV] = "1"
    env[OPS_WORKSPACE_ENV] = str(OPS_ROOT)
    result = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "run_shadow_refresh.py"),
            "--ops-workspace",
            str(OPS_ROOT),
            "--workbench-root",
            str(REPO),
            "--output-root",
            str(output),
            "--run-month",
            "202608",
            "--live",
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads((output / "public_metrics_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == SHADOW_EVALUATION_STATUS
    assert summary["cohort_size"] == 25
    assert summary["network_retrieval"] == "EXECUTED_LIVE_QUARANTINE_ONLY"
    assert "live_collection_counts" in summary
    assert summary["capture_digest_count"] == len(summary.get("capture_digests", []))
    live_package = json.loads((output / "live_collection.json").read_text(encoding="utf-8"))
    assert live_package["status"] == SHADOW_EVALUATION_STATUS
    assert live_package["collector"]["handoff_enabled"] is False
    assert (output / "captures" / "quarantine").is_dir()
