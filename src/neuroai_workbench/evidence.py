from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import Any, cast

from .evidence_transactions import (
    apply_evidence_transaction,
    evidence_registration_lock,
    prepare_evidence_transaction,
    recover_evidence_transactions,
    recover_evidence_transactions_unlocked,
)
from .util import load_json, safe_join, sha256_bytes, sha256_file, utc_now
from .validation import validate_assessment
from .workspace import Workspace

_REQUIRED_INDEX_FIELDS = (
    "evidence_id",
    "original_filename",
    "stored_filename",
    "sha256",
    "size_bytes",
    "title",
)


def _index_path(case_path: Path) -> Path:
    return case_path / "evidence/index.json"


def _objects_root(case_path: Path) -> Path:
    return case_path / "evidence" / "objects"


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"


def _index_error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "message": message}
    payload.update(extra)
    return payload


def _load_evidence_index(case_path: Path) -> tuple[list[dict[str, Any]] | None, list[dict[str, Any]]]:
    """Load evidence index objects or return structured index errors.

    Distinguishes missing, unreadable, schema-invalid, and record-invalid indexes.
    An empty objects list is valid.
    """
    path = _index_path(case_path)
    if not path.is_file():
        return None, [_index_error("INDEX_MISSING", "Evidence index file is missing")]
    try:
        index = load_json(path)
    except (OSError, ValueError, TypeError) as exc:
        return None, [_index_error("INDEX_UNREADABLE", f"Evidence index could not be parsed: {exc}")]
    if not isinstance(index, dict):
        return None, [_index_error("INDEX_SCHEMA_INVALID", "Evidence index root must be a JSON object")]
    if "objects" not in index:
        return [], []
    objects = index.get("objects")
    if not isinstance(objects, list):
        return None, [
            _index_error(
                "INDEX_SCHEMA_INVALID",
                "Evidence index objects must be a list",
                path="objects",
            )
        ]
    errors: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for idx, item in enumerate(objects):
        if not isinstance(item, dict):
            errors.append(
                _index_error(
                    "INDEX_RECORD_INVALID",
                    "Evidence index record must be an object",
                    path=f"objects[{idx}]",
                )
            )
            continue
        missing = [field for field in _REQUIRED_INDEX_FIELDS if field not in item]
        if missing:
            errors.append(
                _index_error(
                    "INDEX_RECORD_INVALID",
                    f"Evidence index record missing required fields: {', '.join(missing)}",
                    path=f"objects[{idx}]",
                    fields=missing,
                )
            )
            continue
        records.append(cast(dict[str, Any], item))
    if errors:
        return None, errors
    return records, []


def list_evidence_files(workspace: Workspace, case_id: str) -> list[dict[str, Any]]:
    records, errors = _load_evidence_index(workspace.case_path(case_id))
    if errors:
        codes = ", ".join(sorted({str(item.get("code")) for item in errors}))
        raise ValueError(f"Evidence index is invalid ({codes})")
    assert records is not None
    return records


def _stored_filename_for(digest: str, original_filename: str) -> str:
    safe_name = Path(original_filename).name
    suffix = "".join(Path(safe_name).suffixes)[-24:]
    return digest + suffix


def _validate_stored_filename(record: dict[str, Any]) -> str | None:
    """Return an error message when stored_filename is unsafe or inconsistent."""
    stored = record.get("stored_filename")
    digest = record.get("sha256")
    if not isinstance(stored, str) or not stored:
        return "stored_filename missing or not a string"
    if not isinstance(digest, str) or not digest:
        return "sha256 missing or not a string"
    if Path(stored).name != stored or stored in {".", ".."}:
        return "stored_filename must be a plain basename"
    if any(sep in stored for sep in ("/", "\\", ":")):
        return "stored_filename contains path separators or drive markers"
    original = str(record.get("original_filename") or "")
    expected = _stored_filename_for(digest, original or stored)
    if stored != expected:
        return "stored_filename does not match digest plus permitted original suffix"
    return None


def _next_evidence_id(assessment: dict[str, Any], index: dict[str, Any] | None = None) -> str:
    used = {row.get("evidence_id") for row in assessment.get("evidence_register", [])}
    if index is not None:
        objects = index.get("objects", [])
        if isinstance(objects, list):
            used |= {row.get("evidence_id") for row in objects if isinstance(row, dict)}
    counter = 1
    while f"EV-{counter:03d}" in used:
        counter += 1
    return f"EV-{counter:03d}"


def _assessment_evidence_record(
    *,
    assessment: dict[str, Any],
    evidence_id: str,
    evidence_type: str,
    title: str,
    source: str,
    digest: str,
    safe_name: str,
    stored_name: str,
    actor: str,
) -> dict[str, Any]:
    config = assessment.get("system_profile", {}).get("configuration_id", "UNRESOLVED")
    return {
        "evidence_id": evidence_id,
        "evidence_type": evidence_type,
        "title": title,
        "source": source,
        "url_or_path": f"evidence/objects/{stored_name}",
        "identifiers": {"sha256": digest, "original_filename": safe_name},
        "evidence_state": "CONTROLLED DISCOVERY RECORD",
        "system_and_version": config,
        "population": "UNRESOLVED",
        "function": "UNRESOLVED",
        "endpoint": "UNRESOLVED",
        "observation_window": "UNRESOLVED",
        "controls_or_comparators": "UNRESOLVED",
        "result_or_record_content": "File registered; substantive appraisal not executed.",
        "publication_or_record_state": "LOCAL CONTROLLED RECORD",
        "source_retrieval_state": "LOCAL BYTES PRESERVED",
        "primary_or_secondary": "UNKNOWN",
        "strongest_supported_claim": "The named file bytes were registered with the stated SHA-256 digest.",
        "prohibited_inferences": [
            "File registration does not establish substantive validity, relevance, authenticity, or conformance."
        ],
        "limitations": ["Substantive appraisal and provenance verification remain unresolved."],
        "checksum": digest,
        "access_conditions": "Local workspace access controls apply.",
        "access_state": "EVALUATION NOT EXECUTED",
        "known_holder": actor,
        "retrieval_or_authorization_required": (
            "No additional retrieval is required for the preserved bytes; appraisal remains required."
        ),
        "reproducibility_tier": "R0 NONE",
    }


def _assessment_commit_state(
    assessment: dict[str, Any],
    *,
    before_sha256: str,
    actor: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    report = validate_assessment(assessment)
    validation_state = "VALID" if report.valid else "DRAFT_INVALID"
    persisted_as = "valid" if report.valid else "draft_invalid"
    after_sha256 = sha256_bytes(_json_bytes(assessment))
    persistence = {
        "validation_state": validation_state,
        "persisted_as": persisted_as,
        "require_valid": False,
        "assessment_sha256": after_sha256,
        "updated_at": utc_now(),
        "actor": actor,
        "boundary": (
            "validation_state records schema/semantic gate outcome only; "
            "it does not establish substantive truth or conformance."
        ),
    }
    event = {
        "before_sha256": before_sha256,
        "after_sha256": after_sha256,
        "valid": report.valid,
        "validation_state": validation_state,
        "persisted_as": persisted_as,
        "schema_errors": len(report.schema_issues),
        "semantic_errors": len(report.semantic_issues),
    }
    return persistence, event


def recover_evidence_registrations(
    workspace: Workspace,
    case_id: str,
    *,
    actor: str = "evidence-recovery",
) -> list[dict[str, Any]]:
    return recover_evidence_transactions(workspace.case_path(case_id), actor=actor)


def add_evidence_bytes(
    workspace: Workspace,
    case_id: str,
    filename: str,
    data: bytes,
    *,
    title: str,
    evidence_type: str = "OTHER",
    source: str = "LOCAL FILE",
    actor: str = "local-user",
    link_to_assessment: bool = True,
) -> dict[str, Any]:
    if not data:
        raise ValueError("Evidence file is empty")
    if len(data) > 100 * 1024 * 1024:
        raise ValueError("Evidence file exceeds the 100 MiB local limit")
    safe_name = Path(filename).name
    if safe_name in {"", ".", ".."}:
        raise ValueError("Invalid evidence filename")

    digest = sha256_bytes(data)
    case = workspace.case_path(case_id)
    objects_root = _objects_root(case)
    objects_root.mkdir(parents=True, exist_ok=True)
    stored_name = _stored_filename_for(digest, safe_name)
    try:
        target = safe_join(objects_root, stored_name)
    except ValueError as exc:
        raise ValueError("Evidence object path escapes the controlled objects root") from exc
    if target.is_symlink():
        raise ValueError("Evidence object path must not be a symlink")

    with evidence_registration_lock(case):
        recover_evidence_transactions_unlocked(case, actor=actor)
        if target.is_file() and sha256_file(target) != digest:
            raise ValueError("Existing content-addressed evidence object has a digest mismatch")

        index_path = _index_path(case)
        index = load_json(index_path)
        if not isinstance(index, dict):
            raise ValueError("Evidence index root must be a JSON object")
        if "objects" not in index:
            index["objects"] = []
        if not isinstance(index.get("objects"), list):
            raise ValueError("Evidence index objects must be a list")

        assessment_path = case / "assessment.json"
        assessment = workspace.load_case(case_id)
        evidence_id = _next_evidence_id(assessment, index)
        record = {
            "evidence_id": evidence_id,
            "original_filename": safe_name,
            "stored_filename": stored_name,
            "sha256": digest,
            "size_bytes": len(data),
            "media_type": mimetypes.guess_type(safe_name)[0] or "application/octet-stream",
            "title": title,
            "evidence_type": evidence_type,
            "source": source,
            "added_at": utc_now(),
            "actor": actor,
        }
        desired_index = dict(index)
        desired_index["objects"] = list(index["objects"]) + [record]

        desired_assessment: dict[str, Any] | None = None
        desired_persistence: dict[str, Any] | None = None
        assessment_event: dict[str, Any] | None = None
        if link_to_assessment:
            desired_assessment = json.loads(json.dumps(assessment))
            desired_assessment.setdefault("evidence_register", []).append(
                _assessment_evidence_record(
                    assessment=assessment,
                    evidence_id=evidence_id,
                    evidence_type=evidence_type,
                    title=title,
                    source=source,
                    digest=digest,
                    safe_name=safe_name,
                    stored_name=stored_name,
                    actor=actor,
                )
            )
            desired_persistence, assessment_event = _assessment_commit_state(
                desired_assessment,
                before_sha256=sha256_file(assessment_path),
                actor=actor,
            )

        transaction_path = prepare_evidence_transaction(
            case,
            data=data,
            record=record,
            desired_index=desired_index,
            desired_assessment=desired_assessment,
            desired_persistence=desired_persistence,
            assessment_event=assessment_event,
        )
        apply_evidence_transaction(case, transaction_path, actor=actor)
        return record


def add_evidence_file(workspace: Workspace, case_id: str, path: Path, **kwargs: Any) -> dict[str, Any]:
    return add_evidence_bytes(workspace, case_id, path.name, path.read_bytes(), **kwargs)


def add_evidence_base64(
    workspace: Workspace, case_id: str, filename: str, content_b64: str, **kwargs: Any
) -> dict[str, Any]:
    try:
        data = base64.b64decode(content_b64, validate=True)
    except Exception as exc:
        raise ValueError("Invalid base64 evidence content") from exc
    return add_evidence_bytes(workspace, case_id, filename, data, **kwargs)


def verify_evidence_files(workspace: Workspace, case_id: str) -> dict[str, Any]:
    case = workspace.case_path(case_id)
    objects_root = _objects_root(case)
    records, index_errors = _load_evidence_index(case)
    if index_errors:
        return {
            "valid": False,
            "object_count": 0,
            "results": [],
            "errors": index_errors,
            "boundary": "Digest verification establishes byte identity only; it does not establish evidence quality or authenticity.",
        }
    assert records is not None
    results: list[dict[str, Any]] = []
    for record in records:
        filename_error = _validate_stored_filename(record)
        path_display = f"evidence/objects/{record.get('stored_filename', '')}"
        if filename_error:
            results.append(
                {
                    "evidence_id": record.get("evidence_id"),
                    "path": path_display,
                    "exists": False,
                    "expected_sha256": record.get("sha256"),
                    "actual_sha256": None,
                    "valid": False,
                    "error": filename_error,
                }
            )
            continue
        try:
            path = safe_join(objects_root, str(record["stored_filename"]))
        except ValueError:
            results.append(
                {
                    "evidence_id": record.get("evidence_id"),
                    "path": path_display,
                    "exists": False,
                    "expected_sha256": record.get("sha256"),
                    "actual_sha256": None,
                    "valid": False,
                    "error": "stored_filename escapes the controlled objects root",
                }
            )
            continue
        if path.is_symlink():
            try:
                resolved = path.resolve()
                if objects_root.resolve() not in resolved.parents and resolved != objects_root.resolve():
                    results.append(
                        {
                            "evidence_id": record.get("evidence_id"),
                            "path": str(path.relative_to(case)),
                            "exists": False,
                            "expected_sha256": record.get("sha256"),
                            "actual_sha256": None,
                            "valid": False,
                            "error": "symlink escapes the controlled objects root",
                        }
                    )
                    continue
            except OSError:
                results.append(
                    {
                        "evidence_id": record.get("evidence_id"),
                        "path": str(path.relative_to(case)),
                        "exists": False,
                        "expected_sha256": record.get("sha256"),
                        "actual_sha256": None,
                        "valid": False,
                        "error": "symlink could not be resolved safely",
                    }
                )
                continue
        exists = path.is_file()
        actual = sha256_file(path) if exists else None
        results.append(
            {
                "evidence_id": record["evidence_id"],
                "path": str(path.relative_to(case)) if exists or path.exists() else path_display,
                "exists": exists,
                "expected_sha256": record["sha256"],
                "actual_sha256": actual,
                "valid": exists and actual == record["sha256"],
            }
        )
    return {
        "valid": all(row["valid"] for row in results),
        "object_count": len(results),
        "results": results,
        "errors": [],
        "boundary": "Digest verification establishes byte identity only; it does not establish evidence quality or authenticity.",
    }
