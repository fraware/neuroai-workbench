"""Ops-gated shadow refresh rehearsal."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from neuroai_workbench.migration_ops.constants import OPS_WORKSPACE_ENV
from neuroai_workbench.shadow_refresh import validate_shadow_refresh_freeze_manifest

OPS_ROOT = Path(os.environ.get(OPS_WORKSPACE_ENV, ""))
REPO = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(
    not OPS_ROOT.is_dir() or not (OPS_ROOT / "01_CONFIG" / "source_monitor_registry_v1.5.json").is_file(),
    reason=f"{OPS_WORKSPACE_ENV} not configured with starter extract",
)


def test_run_shadow_refresh_script_writes_observed_artifacts(tmp_path: Path) -> None:
    output = tmp_path / "shadow-run"
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
            "--target-count",
            "25",
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (output / "cohort.json").is_file()
    assert (output / "run_results.json").is_file()
    assert (output / "public_metrics_summary.json").is_file()
    freeze = __import__("json").loads((output / "freeze_manifest.json").read_text(encoding="utf-8"))
    assert validate_shadow_refresh_freeze_manifest(freeze) == []
    assert not freeze["configuration_hashes"]["registry_sha256"].startswith("aaa")
    summary = __import__("json").loads((output / "public_metrics_summary.json").read_text(encoding="utf-8"))
    assert summary["cohort_size"] == 25
    assert summary["network_retrieval"] == "NOT_EXECUTED_OFFLINE_FIRST"
    assert summary["status"] == "SHADOW_EVALUATION_NOT_CANONICAL"
