from __future__ import annotations

import base64
import os
from pathlib import Path

import pytest

from neuroai_workbench.evidence import (
    add_evidence_base64,
    add_evidence_bytes,
    add_evidence_file,
    list_evidence_files,
    verify_evidence_files,
)
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


def test_empty_evidence_index_verifies_valid(workspace):
    workspace.create_case("CASE-001", "Example case")
    report = verify_evidence_files(workspace, "CASE-001")
    assert report["valid"] is True
    assert report["object_count"] == 0
    assert report["errors"] == []


def test_malformed_objects_map_fails_verification(workspace):
    workspace.create_case("CASE-001", "Example case")
    index_path = workspace.case_path("CASE-001") / "evidence" / "index.json"
    atomic_write_json(index_path, {"version": "1", "objects": {"EV-001": {"sha256": "abc"}}})
    report = verify_evidence_files(workspace, "CASE-001")
    assert report["valid"] is False
    assert any(item["code"] == "INDEX_SCHEMA_INVALID" for item in report["errors"])
    with pytest.raises(ValueError, match="INDEX_SCHEMA_INVALID"):
        list_evidence_files(workspace, "CASE-001")


def test_non_list_objects_fails_verification(workspace):
    workspace.create_case("CASE-001", "Example case")
    index_path = workspace.case_path("CASE-001") / "evidence" / "index.json"
    atomic_write_json(index_path, {"version": "1", "objects": "not-a-list"})
    report = verify_evidence_files(workspace, "CASE-001")
    assert report["valid"] is False
    assert report["errors"][0]["code"] == "INDEX_SCHEMA_INVALID"


def test_unreadable_index_fails_verification(workspace):
    workspace.create_case("CASE-001", "Example case")
    index_path = workspace.case_path("CASE-001") / "evidence" / "index.json"
    index_path.write_text("{not-json", encoding="utf-8")
    report = verify_evidence_files(workspace, "CASE-001")
    assert report["valid"] is False
    assert report["errors"][0]["code"] == "INDEX_UNREADABLE"


def test_missing_index_fails_verification(workspace):
    workspace.create_case("CASE-001", "Example case")
    index_path = workspace.case_path("CASE-001") / "evidence" / "index.json"
    index_path.unlink()
    report = verify_evidence_files(workspace, "CASE-001")
    assert report["valid"] is False
    assert report["errors"][0]["code"] == "INDEX_MISSING"


def test_invalid_index_record_fails_verification(workspace):
    workspace.create_case("CASE-001", "Example case")
    index_path = workspace.case_path("CASE-001") / "evidence" / "index.json"
    atomic_write_json(index_path, {"version": "1", "objects": ["not-an-object"]})
    report = verify_evidence_files(workspace, "CASE-001")
    assert report["valid"] is False
    assert report["errors"][0]["code"] == "INDEX_RECORD_INVALID"
    assert report["errors"][0]["path"] == "objects[0]"


def test_index_root_and_missing_fields_and_add_guards(workspace):
    workspace.create_case("CASE-001", "Example case")
    index_path = workspace.case_path("CASE-001") / "evidence" / "index.json"
    index_path.write_text("[]", encoding="utf-8")
    report = verify_evidence_files(workspace, "CASE-001")
    assert report["valid"] is False
    assert report["errors"][0]["code"] == "INDEX_SCHEMA_INVALID"

    atomic_write_json(index_path, {"version": "1"})
    assert verify_evidence_files(workspace, "CASE-001")["valid"] is True
    assert list_evidence_files(workspace, "CASE-001") == []

    atomic_write_json(
        index_path,
        {"version": "1", "objects": [{"evidence_id": "EV-001", "title": "incomplete"}]},
    )
    report = verify_evidence_files(workspace, "CASE-001")
    assert report["valid"] is False
    assert report["errors"][0]["code"] == "INDEX_RECORD_INVALID"

    with pytest.raises(ValueError, match="empty"):
        add_evidence_bytes(workspace, "CASE-001", "x.txt", b"", title="Empty")
    with pytest.raises(ValueError, match="Invalid evidence filename"):
        add_evidence_bytes(workspace, "CASE-001", "..", b"data", title="Bad")
    with pytest.raises(ValueError, match="Invalid base64"):
        add_evidence_base64(workspace, "CASE-001", "x.txt", "@@@", title="Bad")

    # Restore a usable index then exercise base64 happy path and missing object bytes.
    atomic_write_json(index_path, {"version": "1", "objects": []})
    record = add_evidence_base64(
        workspace,
        "CASE-001",
        "note.txt",
        base64.b64encode(b"hello").decode("ascii"),
        title="Note",
    )
    object_path = workspace.case_path("CASE-001") / "evidence" / "objects" / record["stored_filename"]
    object_path.unlink()
    report = verify_evidence_files(workspace, "CASE-001")
    assert report["valid"] is False
    assert report["results"][0]["exists"] is False

    # Non-string stored_filename / sha256 after a valid add.
    atomic_write_json(index_path, {"version": "1", "objects": []})
    record = add_evidence_bytes(workspace, "CASE-001", "a.txt", b"abc", title="A")
    index = load_json(index_path)
    index["objects"][0]["stored_filename"] = None
    atomic_write_json(index_path, index)
    report = verify_evidence_files(workspace, "CASE-001")
    assert report["valid"] is False
    assert "stored_filename" in report["results"][0]["error"]

    index["objects"][0]["stored_filename"] = record["stored_filename"]
    index["objects"][0]["sha256"] = None
    atomic_write_json(index_path, index)
    report = verify_evidence_files(workspace, "CASE-001")
    assert report["valid"] is False
    assert "sha256" in report["results"][0]["error"]


def test_add_rejects_corrupt_index_and_colon_filename(workspace, monkeypatch):
    workspace.create_case("CASE-001", "Example case")
    index_path = workspace.case_path("CASE-001") / "evidence" / "index.json"
    index_path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        add_evidence_bytes(workspace, "CASE-001", "a.txt", b"data", title="A")
    atomic_write_json(index_path, {"version": "1", "objects": "bad"})
    with pytest.raises(ValueError, match="objects must be a list"):
        add_evidence_bytes(workspace, "CASE-001", "a.txt", b"data", title="A")
    atomic_write_json(index_path, {"version": "1"})
    add_evidence_bytes(workspace, "CASE-001", "a.txt", b"data", title="A")

    digest = sha256_bytes(b"payload")
    index = load_json(index_path)
    index["objects"] = [
        {
            "evidence_id": "EV-COL",
            "original_filename": "payload.bin",
            "stored_filename": f"{digest}:ads",
            "sha256": digest,
            "size_bytes": 7,
            "media_type": "application/octet-stream",
            "title": "Colon",
            "evidence_type": "OTHER",
            "source": "test",
            "added_at": "2026-07-31T00:00:00Z",
            "actor": "tester",
        }
    ]
    atomic_write_json(index_path, index)
    report = verify_evidence_files(workspace, "CASE-001")
    assert report["valid"] is False
    assert any(
        "separator" in (row.get("error") or "") or "basename" in (row.get("error") or "") for row in report["results"]
    )

    # Symlink escape (resolved outside objects root).
    link_name = digest + ".bin"
    index["objects"][0]["stored_filename"] = link_name
    atomic_write_json(index_path, index)
    objects_root = workspace.case_path("CASE-001") / "evidence" / "objects"
    (objects_root / link_name).write_bytes(b"payload")

    import neuroai_workbench.evidence as evidence_mod

    real_safe_join = evidence_mod.safe_join

    class EscapePath:
        def __init__(self, real: Path):
            self._real = real

        def is_symlink(self) -> bool:
            return True

        def resolve(self) -> Path:
            return Path.cwd() / "outside-of-objects.bin"

        def is_file(self) -> bool:
            return False

        def exists(self) -> bool:
            return True

        def relative_to(self, other: Path) -> Path:
            return Path("evidence/objects") / link_name

    def fake_safe_join(root: Path, name: str) -> Path:
        joined = real_safe_join(root, name)
        if name == link_name:
            return EscapePath(joined)  # type: ignore[return-value]
        return joined

    monkeypatch.setattr(evidence_mod, "safe_join", fake_safe_join)
    report = verify_evidence_files(workspace, "CASE-001")
    assert report["valid"] is False
    assert "symlink escapes" in report["results"][0]["error"]


def test_add_evidence_file_and_limit_and_symlink_oserror(workspace, tmp_path: Path, monkeypatch):
    workspace.create_case("CASE-001", "Example case")
    source = tmp_path / "from-disk.txt"
    source.write_bytes(b"from-disk")
    record = add_evidence_file(workspace, "CASE-001", source, title="From disk")
    assert record["original_filename"] == "from-disk.txt"
    with pytest.raises(ValueError, match="100 MiB"):
        add_evidence_bytes(workspace, "CASE-001", "huge.bin", b"x" * (100 * 1024 * 1024 + 1), title="Huge")

    # Force the symlink OSError branch without requiring OS symlink support.
    digest = sha256_bytes(b"link-target")
    case = workspace.case_path("CASE-001")
    index_path = case / "evidence" / "index.json"
    index = load_json(index_path)
    link_name = digest + ".bin"
    index["objects"] = [
        {
            "evidence_id": "EV-SYM",
            "original_filename": "link.bin",
            "stored_filename": link_name,
            "sha256": digest,
            "size_bytes": 11,
            "media_type": "application/octet-stream",
            "title": "Symlink",
            "evidence_type": "OTHER",
            "source": "test",
            "added_at": "2026-07-31T00:00:00Z",
            "actor": "tester",
        }
    ]
    atomic_write_json(index_path, index)
    fake = case / "evidence" / "objects" / link_name
    fake.write_bytes(b"link-target")

    class FakePath:
        def __init__(self, real: Path):
            self._real = real

        def is_symlink(self) -> bool:
            return True

        def resolve(self):
            raise OSError("boom")

        def is_file(self) -> bool:
            return False

        def exists(self) -> bool:
            return True

        def relative_to(self, _other: Path) -> Path:
            return Path("evidence/objects") / link_name

    import neuroai_workbench.evidence as evidence_mod

    real_safe_join = evidence_mod.safe_join

    def fake_safe_join(root: Path, name: str) -> Path:
        joined = real_safe_join(root, name)
        if name == link_name:
            return FakePath(joined)  # type: ignore[return-value]
        return joined

    monkeypatch.setattr(evidence_mod, "safe_join", fake_safe_join)
    report = verify_evidence_files(workspace, "CASE-001")
    assert report["valid"] is False
    assert "symlink could not be resolved" in report["results"][0]["error"]


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
