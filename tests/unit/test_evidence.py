from __future__ import annotations

from neuroai_workbench.evidence import add_evidence_bytes, verify_evidence_files
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
