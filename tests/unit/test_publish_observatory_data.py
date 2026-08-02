from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from neuroai_workbench.publish.data import build_publish_plan, publish_release, verify_publish_staging

ROOT = Path(__file__).resolve().parents[2]
SCAFFOLD = ROOT / "templates" / "neuroai-observatory-data"


def test_build_publish_plan_requires_synthetic_fixtures(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Approved synthetic fixtures missing"):
        build_publish_plan(release_tag="data-v0.0.1-test", staging_root=tmp_path, fixture_dir=tmp_path)


def test_dry_run_publish_verifies_manifest_without_writing_staging(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    report = publish_release(
        build_publish_plan(
            release_tag="data-v0.0.1-bootstrap",
            staging_root=staging,
            target=SCAFFOLD,
            dry_run=True,
        ),
        target=SCAFFOLD,
    )
    assert report["dry_run"] is True
    assert report["manifest_verified"] is True
    assert report["manifest_errors"] == []
    assert not staging.exists()
    assert "withheld_claims" in report["descriptor"]
    assert report["boundary"].startswith("Manifest verification confirms")


def test_publish_writes_and_verifies_staging_tree(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    plan = build_publish_plan(
        release_tag="data-v0.0.1-bootstrap",
        staging_root=staging,
        target=SCAFFOLD,
    )
    report = publish_release(plan, target=SCAFFOLD)
    assert report["manifest_verified"] is True
    assert (staging / "fixtures" / "synthetic_source_registry.json").is_file()
    manifest = staging / "releases" / "data-v0.0.1-bootstrap" / "SHA256SUMS.txt"
    descriptor = staging / "releases" / "data-v0.0.1-bootstrap" / "release-descriptor.json"
    assert manifest.is_file()
    assert descriptor.is_file()

    verify = verify_publish_staging(plan, target=SCAFFOLD)
    assert verify["manifest_verified"] is True
    assert verify["descriptor_verified"] is True


def test_publish_cli_dry_run_exits_zero() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "publish_observatory_data.py"),
            "--staging",
            str(ROOT / "artifacts" / "publish-dry-run"),
            "--release-tag",
            "data-v0.0.1-bootstrap",
            "--target",
            str(SCAFFOLD),
            "--dry-run",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["manifest_verified"] is True


def test_publish_is_deterministic_for_fixture_hashes(tmp_path: Path) -> None:
    staging_a = tmp_path / "a"
    staging_b = tmp_path / "b"
    plan_a = build_publish_plan(release_tag="data-v0.0.1-bootstrap", staging_root=staging_a, target=SCAFFOLD)
    plan_b = build_publish_plan(release_tag="data-v0.0.1-bootstrap", staging_root=staging_b, target=SCAFFOLD)
    report_a = publish_release(plan_a, target=SCAFFOLD)
    report_b = publish_release(plan_b, target=SCAFFOLD)
    assert report_a["fixtures_sha256"] == report_b["fixtures_sha256"]
    manifest_a = (staging_a / "releases" / "data-v0.0.1-bootstrap" / "SHA256SUMS.txt").read_text(encoding="utf-8")
    manifest_b = (staging_b / "releases" / "data-v0.0.1-bootstrap" / "SHA256SUMS.txt").read_text(encoding="utf-8")
    assert manifest_a == manifest_b


def test_authorized_public_release_set_requires_ops_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from neuroai_workbench.migration_ops.constants import OPS_WORKSPACE_ENV
    from neuroai_workbench.publish.data import AUTHORIZED_PUBLIC_RELEASE_SET

    monkeypatch.delenv(OPS_WORKSPACE_ENV, raising=False)
    with pytest.raises(FileNotFoundError, match=OPS_WORKSPACE_ENV):
        build_publish_plan(
            release_tag="data-v0.1.0-public-governing",
            staging_root=tmp_path / "staging",
            target=SCAFFOLD,
            release_set=AUTHORIZED_PUBLIC_RELEASE_SET,
        )


def test_authorized_public_release_set_publishes_from_explicit_ops(tmp_path: Path) -> None:
    from neuroai_workbench.publish.data import AUTHORIZED_PUBLIC_RELEASE_SET

    ops = tmp_path / "ops"
    (ops / "01_CONFIG").mkdir(parents=True)
    (ops / "05_RELEASES" / "historical").mkdir(parents=True)
    (ops / "05_RELEASES" / "current").mkdir(parents=True)
    mapping = {
        "01_CONFIG/source_monitor_registry_v1.5.json": {"sources": []},
        "05_RELEASES/historical/CANONICAL_EVIDENCE_DEPTH_AND_OBSERVATORY_RELEASE_v1.4.json": {
            "metadata": {"version": "v1.4"}
        },
        "05_RELEASES/historical/CANONICAL_LIVE_REFRESH_RELEASE_v1.6.json": {"metadata": {"version": "v1.6"}},
        "05_RELEASES/historical/ADJUDICATED_DELTA_v1.6.json": {"delta_id": "DELTA-V16"},
        "05_RELEASES/current/CANONICAL_SUCCESSOR_SNAPSHOT_v1.7.json": {
            "metadata": {"version": "v1.7", "predecessor": "v1.6"}
        },
    }
    for rel, payload in mapping.items():
        (ops / rel).write_text(json.dumps(payload), encoding="utf-8")

    staging = tmp_path / "staging"
    plan = build_publish_plan(
        release_tag="data-v0.1.0-public-governing",
        staging_root=staging,
        target=SCAFFOLD,
        release_set=AUTHORIZED_PUBLIC_RELEASE_SET,
        ops_workspace=ops,
    )
    report = publish_release(plan, target=SCAFFOLD)
    assert report["manifest_verified"] is True
    assert report["descriptor"]["release_set"] == AUTHORIZED_PUBLIC_RELEASE_SET
    records = staging / "releases" / "data-v0.1.0-public-governing" / "records"
    assert (records / "source_monitor_registry_v1.5.json").is_file()
    assert (records / "canonical_successor_snapshot_v1.7.json").is_file()
    assert (records / "public_disposition_summary.json").is_file()
    assert any("UNESCO" in claim for claim in report["descriptor"]["withheld_claims"])
    verify = verify_publish_staging(plan, target=SCAFFOLD)
    assert verify["manifest_verified"] is True
    assert verify["descriptor_verified"] is True
