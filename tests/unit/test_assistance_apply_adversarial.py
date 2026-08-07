from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench.assistance import (
    _hash_record,
    apply_assistance_proposal,
    create_assistance_request,
    dispose_assistance_response,
    record_assistance_response,
)
from neuroai_workbench.review import create_review_assignment
from neuroai_workbench.util import canonical_json_bytes, sha256_bytes, sha256_file

REPO = Path(__file__).resolve().parents[2]
PRIMA = REPO / "examples" / "assessments" / "PRIMA_Controlled_Assessment_v4.2.1.native.json"
TARGET = "/requirement_findings/NK-01-R01/finding"
SECOND_TARGET = "/requirement_findings/NK-01-R01/strongest_supported_claim"
TEXT = "Exact accepted proposal text."
SECOND_TEXT = "Exact accepted bounded claim."


def _suggestion(path: str, text: str) -> dict[str, object]:
    return {
        "target_path": path,
        "proposed_text": text,
        "evidence_ids": ["EV-PR-001"],
        "confidence": "HIGH",
        "limitations": [],
    }


def _prepare(workspace, tmp_path: Path, *, disposition: str = "ACCEPTED_AS_DRAFT") -> tuple[str, str]:
    workspace.import_case(PRIMA, case_id="prima")
    create_review_assignment(
        workspace,
        "prima",
        "lead-1",
        "LEAD_ASSESSOR",
        ["FINDING:NK-01-R01"],
        actor="assigner-1",
    )
    request = create_assistance_request(
        workspace,
        "prima",
        "DRAFT_FINDING",
        "Draft bounded finding text.",
        requirement_ids=["NK-01-R01"],
        actor="requester-1",
    )["request"]
    output_path = tmp_path / "output.json"
    output_path.write_text(
        json.dumps(
            {
                "task_type": "DRAFT_FINDING",
                "summary": "Bounded proposal.",
                "suggestions": [_suggestion(TARGET, TEXT)],
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )
    record_assistance_response(
        workspace,
        "prima",
        request["request_id"],
        output_path,
        provider="fixture",
        model="fixture",
        actor="recorder-1",
    )
    dispose_assistance_response(
        workspace,
        "prima",
        request["request_id"],
        disposition,
        "Human disposition.",
        actor="reviewer-1",
    )
    return request["request_id"], sha256_file(workspace.case_path("prima") / "assessment.json")


def _paths(workspace, request_id: str) -> tuple[Path, Path, Path]:
    root = workspace.case_path("prima") / "assistance"
    return (
        root / "requests" / f"{request_id}.json",
        root / "responses" / f"{request_id}.json",
        root / "dispositions" / f"{request_id}.json",
    )


def _write_hashed(path: Path, record: dict[str, object], hash_field: str) -> dict[str, object]:
    record[hash_field] = _hash_record(record, hash_field)
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def _rewrite_response_output(workspace, request_id: str, output: dict[str, object]) -> None:
    _request_path, response_path, disposition_path = _paths(workspace, request_id)
    response = json.loads(response_path.read_text(encoding="utf-8"))
    response["output"] = output
    response["output_sha256"] = sha256_bytes(canonical_json_bytes(output))
    response = _write_hashed(response_path, response, "response_sha256")
    disposition = json.loads(disposition_path.read_text(encoding="utf-8"))
    disposition["response_sha256"] = response["response_sha256"]
    _write_hashed(disposition_path, disposition, "disposition_sha256")


def _apply(workspace, request_id: str, before_sha: str, patches=None):
    return apply_assistance_proposal(
        workspace,
        "prima",
        request_id,
        actor="lead-1",
        expected_assessment_sha256=before_sha,
        field_patches=patches if patches is not None else [{"target_path": TARGET, "value": TEXT}],
    )


def test_assistance_apply_requires_expected_assessment_digest(workspace, tmp_path: Path) -> None:
    request_id, _before_sha = _prepare(workspace, tmp_path)
    with pytest.raises(ValueError, match="expected_assessment_sha256"):
        _apply(workspace, request_id, "")


@pytest.mark.parametrize(
    ("patches", "message"),
    [
        ([], "Explicit field_patches"),
        (["bad"], "must be an object"),
        ([{"target_path": TARGET}], "requires value"),
        (
            [
                {"target_path": TARGET, "value": TEXT},
                {"target_path": TARGET, "value": TEXT},
            ],
            "Duplicate field patch",
        ),
    ],
)
def test_assistance_apply_rejects_malformed_patch_plans(workspace, tmp_path: Path, patches, message: str) -> None:
    request_id, before_sha = _prepare(workspace, tmp_path)
    with pytest.raises(ValueError, match=message):
        _apply(workspace, request_id, before_sha, patches)


def test_load_assistance_request_refuses_unknown_request(workspace) -> None:
    workspace.import_case(PRIMA, case_id="prima")
    from neuroai_workbench.assistance import load_assistance_request

    with pytest.raises(FileNotFoundError, match="Unknown assistance request"):
        load_assistance_request(workspace, "prima", "AI-UNKNOWN")


def test_assistance_apply_refuses_request_hash_tamper(workspace, tmp_path: Path) -> None:
    request_id, before_sha = _prepare(workspace, tmp_path)
    request_path, _response_path, _disposition_path = _paths(workspace, request_id)
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["actor"] = "tampered"
    request_path.write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="request hash"):
        _apply(workspace, request_id, before_sha)


def test_assistance_apply_refuses_missing_response(workspace, tmp_path: Path) -> None:
    request_id, before_sha = _prepare(workspace, tmp_path)
    _request_path, response_path, _disposition_path = _paths(workspace, request_id)
    response_path.unlink()
    with pytest.raises(FileNotFoundError, match="No response"):
        _apply(workspace, request_id, before_sha)


def test_assistance_apply_refuses_response_hash_tamper(workspace, tmp_path: Path) -> None:
    request_id, before_sha = _prepare(workspace, tmp_path)
    _request_path, response_path, _disposition_path = _paths(workspace, request_id)
    response = json.loads(response_path.read_text(encoding="utf-8"))
    response["provider"] = "tampered"
    response_path.write_text(json.dumps(response, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="response hash"):
        _apply(workspace, request_id, before_sha)


def test_assistance_apply_refuses_missing_disposition(workspace, tmp_path: Path) -> None:
    request_id, before_sha = _prepare(workspace, tmp_path)
    _request_path, _response_path, disposition_path = _paths(workspace, request_id)
    disposition_path.unlink()
    with pytest.raises(ValueError, match="No disposition"):
        _apply(workspace, request_id, before_sha)


def test_assistance_apply_refuses_disposition_hash_tamper(workspace, tmp_path: Path) -> None:
    request_id, before_sha = _prepare(workspace, tmp_path)
    _request_path, _response_path, disposition_path = _paths(workspace, request_id)
    disposition = json.loads(disposition_path.read_text(encoding="utf-8"))
    disposition["notes"] = "tampered"
    disposition_path.write_text(json.dumps(disposition, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="disposition hash"):
        _apply(workspace, request_id, before_sha)


def test_assistance_apply_refuses_disposition_response_mismatch(workspace, tmp_path: Path) -> None:
    request_id, before_sha = _prepare(workspace, tmp_path)
    _request_path, _response_path, disposition_path = _paths(workspace, request_id)
    disposition = json.loads(disposition_path.read_text(encoding="utf-8"))
    disposition["response_sha256"] = "0" * 64
    _write_hashed(disposition_path, disposition, "disposition_sha256")
    with pytest.raises(ValueError, match="does not reference"):
        _apply(workspace, request_id, before_sha)


def test_assistance_apply_refuses_rejected_disposition(workspace, tmp_path: Path) -> None:
    request_id, before_sha = _prepare(workspace, tmp_path, disposition="REJECTED")
    with pytest.raises(ValueError, match="cannot be applied"):
        _apply(workspace, request_id, before_sha)


def test_assistance_apply_refuses_stale_expected_digest(workspace, tmp_path: Path) -> None:
    request_id, _before_sha = _prepare(workspace, tmp_path)
    with pytest.raises(ValueError, match="Stale assessment"):
        _apply(workspace, request_id, "0" * 64)


def test_assistance_apply_refuses_request_assessment_drift(workspace, tmp_path: Path) -> None:
    request_id, before_sha = _prepare(workspace, tmp_path)
    request_path, response_path, disposition_path = _paths(workspace, request_id)
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["assessment_sha256"] = "0" * 64
    request = _write_hashed(request_path, request, "request_sha256")
    response = json.loads(response_path.read_text(encoding="utf-8"))
    response["request_sha256"] = request["request_sha256"]
    response = _write_hashed(response_path, response, "response_sha256")
    disposition = json.loads(disposition_path.read_text(encoding="utf-8"))
    disposition["response_sha256"] = response["response_sha256"]
    _write_hashed(disposition_path, disposition, "disposition_sha256")
    with pytest.raises(ValueError, match="ASSESSMENT_DRIFT"):
        _apply(workspace, request_id, before_sha)


@pytest.mark.parametrize(
    ("output", "message"),
    [
        (
            {"task_type": "DRAFT_FINDING", "summary": "x", "suggestions": [], "warnings": []},
            "suggestions are missing",
        ),
        (
            {"task_type": "DRAFT_FINDING", "summary": "x", "suggestions": [{}], "warnings": []},
            "suggestion 0 is malformed",
        ),
        (
            {
                "task_type": "DRAFT_FINDING",
                "summary": "x",
                "suggestions": [_suggestion(TARGET, TEXT), _suggestion(TARGET, TEXT)],
                "warnings": [],
            },
            "duplicate path/text suggestions",
        ),
    ],
)
def test_assistance_apply_revalidates_suggestion_shape(workspace, tmp_path: Path, output, message: str) -> None:
    request_id, before_sha = _prepare(workspace, tmp_path)
    _rewrite_response_output(workspace, request_id, output)
    with pytest.raises(ValueError, match=message):
        _apply(workspace, request_id, before_sha)


def test_assistance_apply_detects_authority_change_inside_save(workspace, tmp_path: Path, monkeypatch) -> None:
    request_id, before_sha = _prepare(workspace, tmp_path)
    import neuroai_workbench.assistance as module

    real = module.assessment_edit_authority_assignments
    calls = 0

    def changed(*args, **kwargs):
        nonlocal calls
        calls += 1
        records = real(*args, **kwargs)
        if calls > 1:
            records = [dict(records[0], assignment_sha256="0" * 64)]
        return records

    monkeypatch.setattr(module, "assessment_edit_authority_assignments", changed)
    with pytest.raises(ValueError, match="authority changed"):
        _apply(workspace, request_id, before_sha)


def test_assistance_apply_detects_field_change_inside_save(workspace, tmp_path: Path, monkeypatch) -> None:
    request_id, before_sha = _prepare(workspace, tmp_path)
    original_save = workspace.save_case

    def changed(*args, **kwargs):
        current = workspace.load_case("prima")
        current["requirement_findings"][0]["finding"] = "concurrent change"
        from neuroai_workbench.util import atomic_write_json

        atomic_write_json(workspace.case_path("prima") / "assessment.json", current)
        return original_save(*args, **kwargs)

    monkeypatch.setattr(workspace, "save_case", changed)
    with pytest.raises(ValueError, match="Field value changed"):
        _apply(workspace, request_id, before_sha)


def test_assistance_apply_detects_post_save_digest_mismatch(workspace, tmp_path: Path, monkeypatch) -> None:
    request_id, before_sha = _prepare(workspace, tmp_path)
    original_save = workspace.save_case

    def changed(*args, **kwargs):
        result = original_save(*args, **kwargs)
        return dict(result, after_sha256="0" * 64)

    monkeypatch.setattr(workspace, "save_case", changed)
    with pytest.raises(RuntimeError, match="planned apply digest"):
        _apply(workspace, request_id, before_sha)


@pytest.mark.parametrize("source", ["request", "response", "disposition"])
def test_assistance_apply_detects_source_mutation_after_save(
    workspace, tmp_path: Path, monkeypatch, source: str
) -> None:
    request_id, before_sha = _prepare(workspace, tmp_path)
    request_path, response_path, disposition_path = _paths(workspace, request_id)
    source_path = {"request": request_path, "response": response_path, "disposition": disposition_path}[source]
    original_save = workspace.save_case

    def changed(*args, **kwargs):
        result = original_save(*args, **kwargs)
        source_path.write_bytes(source_path.read_bytes() + b" ")
        return result

    monkeypatch.setattr(workspace, "save_case", changed)
    with pytest.raises(RuntimeError, match=f"Assistance {source} bytes changed"):
        _apply(workspace, request_id, before_sha)
