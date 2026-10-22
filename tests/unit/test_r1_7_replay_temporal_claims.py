"""Synthetic source-archive tests for exact temporal statement replay."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts import r1_7_replay_temporal_claims as replay


def _fixture(path: Path, *, bad_statement: bool = False, false_adjudication: bool = False) -> dict:
    bodies = {
        "flow-fda-pma.html": b"<html><body>PMA Number P230024 Decision Date 12/08/2025</body></html>",
        "flow-september-launch.html": (
            b"<html><body>FL-100 is available in the United States from September 1, 2026.</body></html>"
        ),
        "modius-fda-denovo.html": (
            b"<html><body>De Novo Number DEN250013 Decision Date 05/08/2026 "
            b"Decision granted (DENG)</body></html>"
        ),
        "neu-2025-discontinuation.html": b"<html><body>Four named model designations</body></html>",
        "bitbrain-spanish-diadem.html": b"<html lang='es'><body>Diadem 12ch EEG</body></html>",
        "bitbrain-english-diadem.html": b"<html lang='en'><body>Diadem 12ch EEG</body></html>",
    }
    if bad_statement:
        bodies["flow-september-launch.html"] = b"<html><body>Future marketing intent only</body></html>"
    manifest = {
        "target_count": 6,
        "failures": [],
        "world_time_cutoff": "2026-09-24",
        "knowledge_time_cutoff": "2026-10-24T23:59:59Z",
        "captured": [],
    }
    expected = {}
    with ZipFile(path, "w") as archive:
        for name, body in bodies.items():
            archive.writestr(name, body)
            source = replay.REQUIRED.get(name)
            expected[name] = {
                **source,
                "expected_sha256": hashlib.sha256(body).hexdigest(),
            } if source else None
            manifest["captured"].append({
                "raw_file_name": name,
                "http_status": 200,
                "raw_sha256": hashlib.sha256(body).hexdigest(),
                "raw_bytes": len(body),
                "final_url": source["expected_url"] if source else f"https://example.invalid/{name}",
                "knowledge_observed_at": "2026-10-21T06:09:51Z",
                "source_claims_adjudicated": false_adjudication if name == "modius-fda-denovo.html" else False,
                "product_identity_or_currentness_resolved": False,
            })
        archive.writestr("capture-report.json", json.dumps(manifest))
    return {key: value for key, value in expected.items() if value is not None}


def _allow_synthetic(path: Path, monkeypatch: pytest.MonkeyPatch, expected: dict) -> None:
    monkeypatch.setattr(replay, "ARCHIVE_SHA256", hashlib.sha256(path.read_bytes()).hexdigest())
    monkeypatch.setattr(replay, "REQUIRED", expected)


def test_replay_source_hashes_and_bounded_claims(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = tmp_path / "source.zip"
    expected = _fixture(archive)
    _allow_synthetic(archive, monkeypatch, expected)
    report = replay.verify_saved_temporal_statements(archive)
    assert report["original_captured_sources_verified"] == 6
    assert len(report["narrow_source_statements_verified"]) == 3
    assert report["terminal_temporal_reviews_approved"] == 0
    assert report["canonical_product_changes"] == 0
    out = tmp_path / "replay.json"
    assert replay.main(["--archive", str(archive), "--output", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == (
        "PASS_SAVED_BYTE_INTEGRITY_AND_NARROW_STATEMENT_PRESENCE"
    )


def test_tampered_original_archive_refused(tmp_path: Path) -> None:
    archive = tmp_path / "source.zip"
    _fixture(archive)
    with pytest.raises(ValueError, match="archive digest"):
        replay.verify_saved_temporal_statements(archive)


def test_absent_original_availability_statement_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = tmp_path / "source.zip"
    expected = _fixture(archive, bad_statement=True)
    _allow_synthetic(archive, monkeypatch, expected)
    with pytest.raises(ValueError, match="original source statement absent"):
        replay.verify_saved_temporal_statements(archive)


def test_unreviewed_source_must_not_claim_adjudication(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = tmp_path / "source.zip"
    expected = _fixture(archive, false_adjudication=True)
    _allow_synthetic(archive, monkeypatch, expected)
    with pytest.raises(ValueError, match="adjudication status"):
        replay.verify_saved_temporal_statements(archive)
