"""Offline synthetic tests for the bounded four-paper R1.7 archive replay."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from neuroai_workbench.release_a_r1_route_execution_ledger import canonical_sha256
from scripts.r1_7_replay_literature_archive import (
    EXPECTED_PMIDS,
    ArchivedLiteratureError,
    replay_archive,
)


def _fixture(tmp_path: Path) -> tuple[Path, str]:
    """Synthesize public-free JSON and XML with matching frozen-style receipts."""
    path = tmp_path / "synthetic-evidence.zip"
    files: dict[str, bytes] = {}
    acquisitions = []
    for n, pmid in enumerate(EXPECTED_PMIDS):
        capture = f"SYNTHETIC-CAPTURE-{n}"
        work = f"SYNTHETIC-WORK-{n}"
        query = f"SYNTHETIC-QUERY-{n}"
        xml = f"<article><article-id>{pmid}</article-id></article>".encode()
        raw_sha = hashlib.sha256(xml).hexdigest()
        url = f"https://example.invalid/{pmid}/fullTextXML"
        timestamp = "2026-10-21T04:19:31Z"
        request = {"method": "GET", "locator": url, "request_context": {"query_or_seed_id": query}}
        response = {
            "retrieval_status": "RETRIEVED",
            "content_type": "application/xml",
            "encoding": "utf-8",
            "final_locator": url,
            "response_metadata": {"status_code": 200, "raw_sha256": raw_sha},
        }
        reference = f"SYNTHETIC-EVIDENCE-{n}"
        artifact = {
            "artifact_schema_id": "R1_ROUTE_EVIDENCE_ARTIFACT_v1.0",
            "evidence_ref": reference,
            "capture_id": capture,
            "query_or_seed_id": query,
            "source_locator": url,
            "knowledge_observed_at": timestamp,
            "retrieval_request": request,
            "response_context": response,
            "content_representation": "BASE64_BYTES",
            "content": base64.b64encode(xml).decode("ascii"),
        }
        evidence = {
            "evidence_ref": reference,
            "sha256": canonical_sha256(artifact),
            "capture_id": capture,
            "query_or_seed_id": query,
            "source_locator": url,
            "knowledge_observed_at": timestamp,
            "evidence_role": "RECORD_EXTRACTION",
            "supported_propositions": ["RECORD_EXTRACTION_UNRESOLVED"],
        }
        record = {
            "work_item_id": work,
            "execution_route": "LITERATURE_RECORD_EXTRACTION",
            "completion_state": "RECORD_EXTRACTION_UNRESOLVED",
            "work_item_completion_claimed": False,
            "covered_capture_ids": [capture],
            "extracted_leads": [],
            "review_state": "MACHINE_PROVISIONAL",
            "evidence": [evidence],
        }
        record["execution_record_id"] = "R1ROUTE-" + canonical_sha256(record)
        entry = {"route_execution_record": record, "supersedes_ledger_entry_ids": []}
        entry["ledger_entry_id"] = "R1LEDGER-" + canonical_sha256(entry)
        acquisitions.append(
            {
                "pmid": pmid,
                "capture_id": capture,
                "work_item_id": work,
                "raw_sha256": raw_sha,
                "bytes": len(xml),
            }
        )
        prefix = f"pmid-{pmid}"
        files[f"{prefix}-fulltext.xml"] = xml
        files[f"{prefix}-decision.json"] = json.dumps(
            {
                "capture_id": capture,
                "completion_state": "RECORD_EXTRACTION_UNRESOLVED",
                "extracted_candidate_keys": [],
                "knowledge_observed_at": timestamp,
                "retrieval_request": request,
                "response_context": response,
            }
        ).encode()
        files[f"{prefix}-evidence-bundle.json"] = json.dumps(
            {
                "pmid": pmid,
                "capture_id": capture,
                "raw_snapshot_sha256": raw_sha,
                "ledger_entry": entry,
                "evidence_archive": {reference: artifact},
                "derived_state": {
                    "completed_work_item_count": 0,
                    "pending_work_item_count": 192,
                    "unresolved_barrier_work_item_count": 1,
                },
            }
        ).encode()
    files["acquisition-report.json"] = json.dumps(
        {
            "expected": 4,
            "failures": [],
            "results": acquisitions,
        }
    ).encode()
    files["nonterminal-mentions.json"] = b'{"papers": []}'
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        for filename, data in sorted(files.items()):
            archive.writestr(filename, data)
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def _bounded_state(entries: list[dict], *, evidence_archive: dict) -> dict:
    """Test adapter; repository ledger semantic validation is separately tested."""
    assert len(entries) == 4 and len(evidence_archive) == 4
    return {
        "frozen_work_item_count": 192,
        "frozen_capture_count": 247,
        "ledger_entry_count": len(entries),
        "completed_work_item_count": 0,
        "pending_work_item_count": 192,
        "unresolved_barrier_work_item_count": 4,
        "active_extracted_lead_count": 0,
    }


def test_archive_replay_is_reproducible_and_nonterminal(tmp_path: Path) -> None:
    path, digest = _fixture(tmp_path)
    first = replay_archive(path, expected_archive_sha256=digest, state_builder=_bounded_state)
    assert first == replay_archive(path, expected_archive_sha256=digest, state_builder=_bounded_state)
    assert first["original_source_receipts_replayed"] == 4
    assert first["literature_work_items_without_direct_bundle_receipt"] == 17
    assert first["completed_work_item_count"] == 0
    assert first["pending_work_item_count"] == 192
    assert {r["pmid"] for r in first["receipts"]} == set(EXPECTED_PMIDS)
    assert "content" not in json.dumps(first)  # no archived XML in output


def test_modified_zip_is_rejected_before_analysis(tmp_path: Path) -> None:
    path, digest = _fixture(tmp_path)
    path.write_bytes(path.read_bytes() + b"modified archive")
    with pytest.raises(ArchivedLiteratureError, match="ZIP byte digest"):
        replay_archive(path, expected_archive_sha256=digest, state_builder=_bounded_state)


@pytest.mark.parametrize("tamper", ["raw", "terminal", "scope", "provenance"])
def test_adversarial_archived_bundle_changes_fail_closed(tmp_path: Path, tamper: str) -> None:
    path, _ = _fixture(tmp_path)
    with ZipFile(path) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    pmid = EXPECTED_PMIDS[0]
    prefix = f"pmid-{pmid}"
    if tamper == "raw":
        members[f"{prefix}-fulltext.xml"] += b"<unreported-change/>"
    elif tamper == "terminal":
        name = f"{prefix}-decision.json"
        doc = json.loads(members[name])
        doc["completion_state"] = "RECORD_EXTRACTED_ZERO_OFFERING_LEADS"
        members[name] = json.dumps(doc).encode()
    elif tamper == "scope":
        name = f"{prefix}-evidence-bundle.json"
        doc = json.loads(members[name])
        doc["ledger_entry"]["route_execution_record"]["execution_route"] = "SOURCE_SURFACE_RESOLUTION"
        members[name] = json.dumps(doc).encode()
    else:
        name = f"{prefix}-evidence-bundle.json"
        doc = json.loads(members[name])
        artifact = next(iter(doc["evidence_archive"].values()))
        artifact["retrieval_request"]["request_context"]["query_or_seed_id"] = "wrong-seed"
        members[name] = json.dumps(doc).encode()
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for name, data in sorted(members.items()):
            archive.writestr(name, data)
    new_digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ArchivedLiteratureError):
        replay_archive(path, expected_archive_sha256=new_digest, state_builder=_bounded_state)


def test_forged_completion_state_from_semantic_replayer_fails_closed(tmp_path: Path) -> None:
    path, digest = _fixture(tmp_path)

    def invalid(entries: list, *, evidence_archive: dict) -> dict:
        result = _bounded_state(entries, evidence_archive=evidence_archive)
        result["completed_work_item_count"] = 1
        return result

    with pytest.raises(ArchivedLiteratureError, match="nonterminal"):
        replay_archive(path, expected_archive_sha256=digest, state_builder=invalid)
