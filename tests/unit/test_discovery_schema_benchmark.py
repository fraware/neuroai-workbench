"""Smoke tests for the synthetic discovery-schema validation benchmark."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "benchmark_discovery_schema_validation.py"


def test_benchmark_reports_equal_diagnostics_for_all_frozen_schemas() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--schema", "all", "--iterations", "2", "--repeats", "2"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=40,
    )
    report = json.loads(result.stdout)
    assert report["benchmark"] == "discovery-schema-compiled-validator"
    assert len(report["results"]) == 4
    for row in report["results"]:
        assert row["input"] == "synthetic-empty-object"
        assert row["diagnostics_identical"] is True
        assert row["invalid_diagnostic_count"] > 0
        assert row["iterations_per_repeat"] == 2
        assert row["repeats"] == 2
        assert row["median_uncached_microseconds_per_call"] > 0
        assert row["median_cached_microseconds_per_call"] > 0


def test_benchmark_rejects_nonpositive_iteration_count() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--iterations", "0"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode != 0
    assert "must be positive" in result.stderr
