"""Ops-gated entity benchmark (≥60 annotated cases)."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from neuroai_workbench.entities.benchmark import run_blinded_benchmark
from neuroai_workbench.migration_ops.constants import OPS_WORKSPACE_ENV
from tests.unit.test_entity_resolver import seed_entity_workspace

OPS_ROOT = Path(os.environ.get(OPS_WORKSPACE_ENV, ""))
BENCH = Path("evaluation/entity/RESOLUTION_BENCHMARK_OPS_GE60.json")

pytestmark = pytest.mark.skipif(
    not OPS_ROOT.is_dir() or not (OPS_ROOT / BENCH).is_file(),
    reason=f"{OPS_WORKSPACE_ENV} missing ops entity benchmark ≥60",
)


def test_ops_entity_benchmark_ge60_digest_and_metrics(tmp_path: Path) -> None:
    path = OPS_ROOT / BENCH
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert len(digest) == 64
    workspace = seed_entity_workspace(tmp_path)
    report = run_blinded_benchmark(workspace, actor="ops-entity", benchmark_path=path)
    assert report["counts"]["total"] >= 60
    assert "precision" in report["metrics"]
    assert "false_merge_count" in report["metrics"]
