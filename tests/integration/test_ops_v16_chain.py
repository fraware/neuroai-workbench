"""Ops-gated golden tests for v1.4 → v1.6 → v1.7 migration lineage."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from neuroai_workbench.migration_ops.constants import OPS_WORKSPACE_ENV
from neuroai_workbench.migration_ops.verification import build_migration_verification
from neuroai_workbench.observatory import validate_release
from neuroai_workbench.util import load_json, sha256_file

OPS_ROOT = Path(os.environ.get(OPS_WORKSPACE_ENV, ""))
REPO_ROOT = Path(__file__).resolve().parents[2]

REFRESH = Path("05_RELEASES/historical/CANONICAL_LIVE_REFRESH_RELEASE_v1.6.json")
DELTA = Path("05_RELEASES/historical/ADJUDICATED_DELTA_v1.6.json")
V14 = Path("05_RELEASES/historical/CANONICAL_EVIDENCE_DEPTH_AND_OBSERVATORY_RELEASE_v1.4.json")
V17 = Path("05_RELEASES/current/CANONICAL_SUCCESSOR_SNAPSHOT_v1.7.json")

pytestmark = pytest.mark.skipif(
    not OPS_ROOT.is_dir() or not (OPS_ROOT / REFRESH).is_file() or not (OPS_ROOT / DELTA).is_file(),
    reason=f"{OPS_WORKSPACE_ENV} not configured with v1.6 starter files",
)


def test_ops_v16_files_match_inventory_digests() -> None:
    assert sha256_file(OPS_ROOT / REFRESH) == "937b2fcd807392e64f946f88a89756cc91890cc6db9f98e519035725e46c7035"
    assert sha256_file(OPS_ROOT / DELTA) == "49ef4944e4dd7e5d4b3534926e41220a1493ef12d68965a7b6caa4431524b0c5"
    assert sha256_file(OPS_ROOT / V14) == "00985fa168b26c4e02df485895d728ee30191aea436b4e3956c60657e2ffc3be"
    assert sha256_file(OPS_ROOT / V17) == "9cc36aacb4c791c9830990b58e144f223925f3ad492016abaea44727b48a0b70"


def test_ops_migration_verification_unblocks_registry_and_v16() -> None:
    document = build_migration_verification(REPO_ROOT, recorded_at="2026-08-02T18:00:00Z")
    by_id = {record["inventory_id"]: record for record in document["records"]}
    assert document["summary"]["blocked"] == 0
    for inventory_id in ("INV-EXT-REG-V15", "INV-EXT-V16-REFRESH", "INV-EXT-V16-DELTA"):
        assert by_id[inventory_id]["migration_state"] == "MIGRATED"
        assert by_id[inventory_id]["access_state"] == "ACCESSIBLE"
        assert len(by_id[inventory_id]["source_sha256"]) == 64
        assert by_id[inventory_id]["lineage_digest"] != "UNKNOWN"
    assert by_id["INV-EXT-REG-V15"]["validation"]["record_count"] == 224
    # AMB-003 residual may remain inaccessible without blocking registry/v1.6.
    assert "AMB-003" in document.get("residuals", [])


def test_v17_predecessor_resolves_against_ops_v16() -> None:
    v17 = load_json(OPS_ROOT / V17)
    report = validate_release(v17)
    assert report["valid"] is True
    metadata = v17.get("metadata", {})
    assert metadata.get("predecessor") == "v1.6"
    predecessor_ref = v17.get("predecessor_reference", {})
    assert isinstance(predecessor_ref, dict)
    # Refresh + delta packages load as dicts; presence is the lineage gate for ops extract.
    assert (OPS_ROOT / REFRESH).is_file()
    assert (OPS_ROOT / DELTA).is_file()
    refresh = load_json(OPS_ROOT / REFRESH)
    delta = load_json(OPS_ROOT / DELTA)
    assert isinstance(refresh, dict) and refresh
    assert isinstance(delta, dict) and delta
