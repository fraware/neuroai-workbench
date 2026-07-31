from __future__ import annotations

import os
from pathlib import Path

import pytest

from neuroai_workbench.evidence import add_evidence_bytes, verify_evidence_files
from neuroai_workbench.util import atomic_write_json, load_json, sha256_bytes
from neuroai_workbench.validation import validate_assessment


def test_add_evidence_bytes_and_link(workspace):
    workspace.create_case("CASE-001", "Example case")
    record = add_evidence_bytes(
        workspace,
        "CASE-001",
        "record.txt",
        b"controlled bytes\n",
        title="Controlled record",
        evidence_type="OTHER",
        source="Test source",
    )
    assert record["evidence_id"] == "EV-001"
    assessment = workspace.load_case("CASE-001")
    assert assessment["evidence_register"][0]["checksum"] == record["sha256"]
    assert assessment["evidence_register"][0]["access_state"] == "EVALUATION NOT EXECUTED"
    assert assessment["evidence_register"][0]["publication_or_record_state"] == "LOCAL CONTROLLED RECORD"
    assert validate_assessment(assessment).valid
    assert verify_evidence_files(workspace, "CASE-001")["valid"]


def test_duplicate_bytes_are_content_addressed(workspace):
    workspace.create_case("CASE-001", "Example case")
    first = add_evidence_bytes(workspace, "CASE-001", "a.txt", b"same", title="A")
    second = add_evidence_bytes(workspace, "CASE-001", "b.txt", b"same", title="B")
    assert first["stored_filename"] == second["stored_filename"]
    objects = list((workspace.case_path("CASE-001") / "evidence/objects").iterdir())
    assert len(objects) == 1


def test_evidence_tamper_is_detected(workspace):
    workspace.create_case("CASE-001", "Example case")
    record = add_evidence_bytes(workspace, "CASE-001", "record.txt", b"original", title="Record")
    path = workspace.case_path("CASE-001") / "evidence/objects" / record["stored_filename"]
    path.write_bytes(b"changed")
    report = verify_evidence_files(workspace, "CASE-001")
    assert not report["valid"]
    assert report["results"][0]["actual_sha256"] != report["results"][0]["expected_sha256"]


def test_empty_evidence_is_rejected(workspace):
    workspace.create_case("CASE-001", "Example case")
    try:
        add_evidence_bytes(workspace, "CASE-001", "empty.txt", b"", title="Empty")
    except ValueError as exc:
        assert "empty" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError")


def test_unlinked_evidence_ids_allocate_from_index_and_register(workspace):
    workspace.create_case("CASE-001", "Example case")
    first = add_evidence_bytes(workspace, "CASE-001", "a.txt", b"one", title="A", link_to_assessment=False)
    second = add_evidence_bytes(workspace, "CASE-001", "b.txt", b"two", title="B", link_to_assessment=False)
    assert first["evidence_id"] == "EV-001"
    assert second["evidence_id"] == "EV-002"


@pytest.mark.parametrize(
    "stored_filename",
    [
        "../assessment.json",
        "..\\assessment.json",
        "/tmp/escape.bin",
        "C:/Windows/escape.bin",
        "nested/path.bin",
    ],
)
def test_malicious_index_stored_filename_fails_verification(workspace, stored_filename: str):
    workspace.create_case("CASE-001", "Example case")
    digest = sha256_bytes(b"payload")
    case = workspace.case_path("CASE-001")
    index_path = case / "evidence" / "index.json"
    index = load_json(index_path)
    index["objects"] = [
        {
            "evidence_id": "EV-001",
            "original_filename": "payload.bin",
            "stored_filename": stored_filename,
            "sha256": digest,
            "size_bytes": 7,
            "media_type": "application/octet-stream",
            "title": "Malicious",
            "evidence_type": "OTHER",
            "source": "test",
            "added_at": "2026-07-31T00:00:00Z",
            "actor": "tester",
        }
    ]
    atomic_write_json(index_path, index)
    report = verify_evidence_files(workspace, "CASE-001")
    assert report["valid"] is False
    assert report["results"][0]["valid"] is False
    assert "error" in report["results"][0]


def test_digest_suffix_mismatch_fails_verification(workspace):
    workspace.create_case("CASE-001", "Example case")
    record = add_evidence_bytes(workspace, "CASE-001", "record.txt", b"payload", title="Record")
    case = workspace.case_path("CASE-001")
    index_path = case / "evidence" / "index.json"
    index = load_json(index_path)
    index["objects"][0]["stored_filename"] = record["sha256"] + ".exe"
    atomic_write_json(index_path, index)
    report = verify_evidence_files(workspace, "CASE-001")
    assert report["valid"] is False
    assert "digest plus permitted" in report["results"][0]["error"]


def test_symlink_escape_under_objects_fails_when_supported(workspace, tmp_path: Path):
    workspace.create_case("CASE-001", "Example case")
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"escaped-bytes")
    digest = sha256_bytes(b"escaped-bytes")
    case = workspace.case_path("CASE-001")
    objects = case / "evidence" / "objects"
    objects.mkdir(parents=True, exist_ok=True)
    link_name = digest + ".bin"
    link_path = objects / link_name
    try:
        os.symlink(outside, link_path)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Symlinks unsupported in this environment: {exc}")
    index_path = case / "evidence" / "index.json"
    index = load_json(index_path)
    index["objects"] = [
        {
            "evidence_id": "EV-001",
            "original_filename": "escape.bin",
            "stored_filename": link_name,
            "sha256": digest,
            "size_bytes": outside.stat().st_size,
            "media_type": "application/octet-stream",
            "title": "Symlink",
            "evidence_type": "OTHER",
            "source": "test",
            "added_at": "2026-07-31T00:00:00Z",
            "actor": "tester",
        }
    ]
    atomic_write_json(index_path, index)
    report = verify_evidence_files(workspace, "CASE-001")
    assert report["valid"] is False
    assert report["results"][0]["valid"] is False
