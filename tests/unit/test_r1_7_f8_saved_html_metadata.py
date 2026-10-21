"""Synthetic network-free verification of saved F8 metadata extraction."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from scripts import r1_7_f8_saved_html_metadata as audit


def _fixture(path: Path, *, terminal: bool = False) -> None:
    """Ten synthetic attempts, eight saved pages, seven distinct byte streams."""
    sources = []
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        for index in range(10):
            frozen_context = index // 2
            name = f"synthetic-{index}.response"
            item = {
                "frozen_query_id": f"F8-EXAMPLE-{frozen_context}",
                "capture_id": f"PDC-MOCK-{frozen_context}",
                "attempted_alternative_locator": f"https://example.invalid/{index}",
                "attempted_at_utc": "2026-10-21T06:40:00+00:00",
                "source_locator_type": "SYNTHETIC_SOURCE_TEST",
                "original_frozen_outcome": "FAILED_INACCESSIBLE",
                "historical_product_claim_adjudicated": False,
                "r1_7_terminal_extraction": "UNAUTHORIZED" if terminal and index == 0 else None,
            }
            if index < 8:
                payload = (
                    b'<html lang="es"><head><title>Mock F8</title>'
                    b'<meta property="article:published_time" content="2024-07-10T12:00:00Z">'
                    b"</head><body><h1>Test Source</h1></body></html>"
                    if index in {0, 5}
                    else f"<html><head><title>Mock-{index}</title></head><body>Only a synthetic page.</body></html>".encode()
                )
                archive.writestr(name, payload)
                item.update(
                    {
                        "http_status": 200,
                        "saved_file": name,
                        "raw_bytes": len(payload),
                        "raw_sha256": hashlib.sha256(payload).hexdigest(),
                    }
                )
            else:
                item.update(
                    {
                        "failure_type": "HTTPError",
                        "failure_detail": "HTTP Error 403: Forbidden",
                    }
                )
            sources.append(item)
        archive.writestr("attempt-report.json", json.dumps({"attempts": 10, "items": sources}))


def test_exact_archive_and_metadata_accounting(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "source.zip"
    _fixture(path)
    monkeypatch.setattr(audit, "EXPECTED_ARCHIVE_SHA256", hashlib.sha256(path.read_bytes()).hexdigest())
    report = audit.audit_archive(path)
    assert report["attempted_urls"] == 10
    assert report["saved_successful_http_200"] == 8
    assert report["http_403_errors_in_recorded_exception_text"] == 2
    assert report["unique_saved_response_sha256"] == 7
    assert report["distinct_original_capture_contexts"] == 5
    assert report["scientific_disposition"] == "NONTERMINAL_OFFLINE_METADATA_EXTRACTION"
    records = report["source_metadata"]
    assert records[0]["unverified_declared_html_lang"] == "es"
    assert records[0]["unverified_date_meta"] == {"article:published_time": "2024-07-10T12:00:00Z"}
    assert records[-1]["reported_http_status"] is None
    assert records[-1]["http_403_derived_from_exception_text"] is True


def test_tampered_archive_fails_digest_check(tmp_path: Path) -> None:
    path = tmp_path / "source.zip"
    _fixture(path)
    with pytest.raises(ValueError, match="archive raw-byte SHA-256 mismatch"):
        audit.audit_archive(path)


def test_terminal_source_decision_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "source.zip"
    _fixture(path, terminal=True)
    monkeypatch.setattr(audit, "EXPECTED_ARCHIVE_SHA256", hashlib.sha256(path.read_bytes()).hexdigest())
    with pytest.raises(ValueError, match="terminal source decision"):
        audit.audit_archive(path)


def test_cli_writes_nonterminal_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "source.zip"
    output = tmp_path / "metadata.json"
    _fixture(path)
    monkeypatch.setattr(audit, "EXPECTED_ARCHIVE_SHA256", hashlib.sha256(path.read_bytes()).hexdigest())
    assert audit.main(["--archive", str(path), "--output", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["saved_successful_http_200"] == 8
