from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import tarfile
import warnings
import zipfile
from pathlib import Path

import pytest

from scripts import acquire_live_v021_release
from scripts import verify_github_release_assets as release_audit

TAG = "v0.2.1"
VERSION = "0.2.1"
COMMIT = "7e60d1051a0a6a6178b7d5c39deac0b02270296d"


def _write_wheel(path: Path) -> None:
    metadata = "Metadata-Version: 2.4\nName: neuroai-workbench\nVersion: 0.2.1\n\n"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("neuroai_workbench-0.2.1.dist-info/METADATA", metadata)
        archive.writestr("neuroai_workbench-0.2.1.dist-info/RECORD", "")
        archive.writestr("neuroai_workbench/__init__.py", '__version__ = "0.2.1"\n')


def _write_sdist(path: Path) -> None:
    metadata = b"Metadata-Version: 2.4\nName: neuroai-workbench\nVersion: 0.2.1\n\n"
    with tarfile.open(path, "w:gz") as archive:
        info = tarfile.TarInfo("neuroai_workbench-0.2.1/PKG-INFO")
        info.size = len(metadata)
        archive.addfile(info, io.BytesIO(metadata))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> tuple[Path, dict, dict, dict]:
    assets = tmp_path / "assets"
    assets.mkdir()
    _write_wheel(assets / "neuroai_workbench-0.2.1-py3-none-any.whl")
    _write_sdist(assets / "neuroai_workbench-0.2.1.tar.gz")
    (assets / "neuroai-workbench-v0.2.1.bundle").write_bytes(b"synthetic bundle")
    (assets / "SBOM.spdx.json").write_text(
        json.dumps(
            {
                "spdxVersion": "SPDX-2.3",
                "dataLicense": "CC0-1.0",
                "SPDXID": "SPDXRef-DOCUMENT",
                "packages": [{"name": "neuroai-workbench"}, {"name": "jsonschema"}],
            }
        ),
        encoding="utf-8",
    )
    (assets / "RELEASE_VERIFICATION.json").write_text(
        json.dumps(
            {
                "release": TAG,
                "checks_total": 65,
                "checks_passed": 65,
                "checks_failed": 0,
                "withheld_claims": sorted(release_audit.EXPECTED_WITHHELD_CLAIMS),
            }
        ),
        encoding="utf-8",
    )
    checksummed = sorted(release_audit._expected_assets(VERSION) - {"SHA256SUMS.txt"})
    (assets / "SHA256SUMS.txt").write_text(
        "".join(f"{_sha(assets / name)}  {name}\n" for name in checksummed),
        encoding="utf-8",
    )
    names = sorted(release_audit._expected_assets(VERSION))
    body = "\n".join(
        [
            "This release does not establish scientific validity.",
            "It does not establish clinical safety or regulatory authorization.",
            "It does not establish conformance, institutional endorsement, or official UNESCO status.",
        ]
    )
    release = {
        "tagName": TAG,
        "isDraft": False,
        "isPrerelease": False,
        "url": "https://example.invalid/release",
        "body": body,
        "assets": [{"name": name, "digest": f"sha256:{_sha(assets / name)}"} for name in names],
    }
    tag = {"tag": TAG, "tag_commit": COMMIT}
    attestations = {"assets": [{"name": name, "verified": True} for name in names]}
    return assets, release, tag, attestations


def _audit(tmp_path: Path, monkeypatch, *, require_published: bool = True):
    assets, release, tag, attestations = _fixture(tmp_path)
    monkeypatch.setattr(release_audit, "_bundle_commit", lambda bundle, tag: (True, COMMIT, "synthetic"))
    report = release_audit.audit(
        assets_dir=assets,
        release=release,
        tag_record=tag,
        attestations=attestations,
        expected_tag=TAG,
        expected_commit=COMMIT,
        require_published=require_published,
    )
    return assets, release, tag, attestations, report


def test_complete_release_audit_passes(tmp_path, monkeypatch):
    _, _, _, _, report = _audit(tmp_path, monkeypatch)
    assert report["status"] == "PASS"
    assert report["checks_failed"] == 0
    assert report["observed_release_state"] == "PUBLISHED"


def test_tampered_asset_fails_checksum_github_digest_and_spdx(tmp_path, monkeypatch):
    assets, release, tag, attestations = _fixture(tmp_path)
    monkeypatch.setattr(release_audit, "_bundle_commit", lambda bundle, tag: (True, COMMIT, "synthetic"))
    (assets / "SBOM.spdx.json").write_text("{}", encoding="utf-8")
    report = release_audit.audit(
        assets_dir=assets,
        release=release,
        tag_record=tag,
        attestations=attestations,
        expected_tag=TAG,
        expected_commit=COMMIT,
        require_published=True,
    )
    failed = {item["name"] for item in report["checks"] if item["status"] == "FAIL"}
    assert "Checksum SBOM.spdx.json" in failed
    assert "GitHub asset digest SBOM.spdx.json" in failed
    assert "SPDX format identity" in failed


def test_missing_attestation_fails_inventory_and_asset_check(tmp_path, monkeypatch):
    assets, release, tag, attestations = _fixture(tmp_path)
    attestations["assets"].pop()
    monkeypatch.setattr(release_audit, "_bundle_commit", lambda bundle, tag: (True, COMMIT, "synthetic"))
    report = release_audit.audit(
        assets_dir=assets,
        release=release,
        tag_record=tag,
        attestations=attestations,
        expected_tag=TAG,
        expected_commit=COMMIT,
        require_published=True,
    )
    assert report["status"] == "FAIL"
    assert any(item["name"] == "Attestation result inventory" and item["status"] == "FAIL" for item in report["checks"])


def test_draft_release_fails_only_when_publication_is_required(tmp_path, monkeypatch):
    assets, release, tag, attestations = _fixture(tmp_path)
    release["isDraft"] = True
    monkeypatch.setattr(release_audit, "_bundle_commit", lambda bundle, tag: (True, COMMIT, "synthetic"))
    strict = release_audit.audit(
        assets_dir=assets,
        release=release,
        tag_record=tag,
        attestations=attestations,
        expected_tag=TAG,
        expected_commit=COMMIT,
        require_published=True,
    )
    recorded = release_audit.audit(
        assets_dir=assets,
        release=release,
        tag_record=tag,
        attestations=attestations,
        expected_tag=TAG,
        expected_commit=COMMIT,
        require_published=False,
    )
    assert strict["status"] == "FAIL"
    assert recorded["status"] == "PASS"
    assert recorded["observed_release_state"] == "DRAFT"


def test_release_verification_claim_drift_is_rejected(tmp_path, monkeypatch):
    assets, release, tag, attestations = _fixture(tmp_path)
    verification_path = assets / "RELEASE_VERIFICATION.json"
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    verification["checks_failed"] = 1
    verification["withheld_claims"].pop()
    verification_path.write_text(json.dumps(verification), encoding="utf-8")
    monkeypatch.setattr(release_audit, "_bundle_commit", lambda bundle, tag: (True, COMMIT, "synthetic"))
    report = release_audit.audit(
        assets_dir=assets,
        release=release,
        tag_record=tag,
        attestations=attestations,
        expected_tag=TAG,
        expected_commit=COMMIT,
        require_published=True,
    )
    failed = {item["name"] for item in report["checks"] if item["status"] == "FAIL"}
    assert "Release verification checks all pass" in failed
    assert "Release verification preserves withheld claims" in failed


def test_live_v021_release_and_attestations():
    if os.getenv("GITHUB_ACTIONS") != "true":
        pytest.skip("live release audit runs only in GitHub Actions")
    if os.getenv("GITHUB_HEAD_REF") != "agent/verify-v0.2.1-release":
        pytest.skip("live release audit is restricted to the dedicated verification branch")
    if sys.version_info[:2] != (3, 13):
        pytest.skip("live release audit executes once on Python 3.13")

    try:
        report = acquire_live_v021_release.acquire_and_audit()
    except Exception as exc:  # noqa: BLE001 - audit boundary converts acquisition failures into evidence
        report = {
            "schema_version": 1,
            "release": TAG,
            "status": "FAIL",
            "checks_total": 1,
            "checks_passed": 0,
            "checks_failed": 1,
            "checks": [{"name": "Live acquisition", "status": "FAIL", "detail": str(exc)}],
        }
    warnings.warn(
        "LIVE_V021_AUDIT_JSON=" + json.dumps(report, ensure_ascii=False, separators=(",", ":")),
        UserWarning,
        stacklevel=1,
    )
    assert report["status"] == "PASS", json.dumps(report, ensure_ascii=False, indent=2)
