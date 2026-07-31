from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any, cast

from .events import append_event
from .util import atomic_write_bytes, atomic_write_json, load_json, safe_join, sha256_bytes, sha256_file, utc_now
from .workspace import Workspace


def _index_path(case_path: Path) -> Path:
    return case_path / "evidence/index.json"


def _objects_root(case_path: Path) -> Path:
    return case_path / "evidence" / "objects"


def list_evidence_files(workspace: Workspace, case_id: str) -> list[dict[str, Any]]:
    index = load_json(_index_path(workspace.case_path(case_id)))
    objects = index.get("objects", [])
    if not isinstance(objects, list):
        return []
    return cast(list[dict[str, Any]], objects)


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
        used |= {row.get("evidence_id") for row in index.get("objects", [])}
    counter = 1
    while f"EV-{counter:03d}" in used:
        counter += 1
    return f"EV-{counter:03d}"


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
    if not target.exists():
        atomic_write_bytes(target, data)
    index_path = _index_path(case)
    index = load_json(index_path)
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
    index.setdefault("objects", []).append(record)
    atomic_write_json(index_path, index)

    if link_to_assessment:
        config = assessment.get("system_profile", {}).get("configuration_id", "UNRESOLVED")
        assessment.setdefault("evidence_register", []).append(
            {
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
                "retrieval_or_authorization_required": "No additional retrieval is required for the preserved bytes; appraisal remains required.",
                "reproducibility_tier": "R0 NONE",
            }
        )
        workspace.save_case(case_id, assessment, actor=actor)

    append_event(case / "events.jsonl", "EVIDENCE_ADDED", actor, record)
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
    records = list_evidence_files(workspace, case_id)
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
        # Refuse to follow symlinks that escape the objects root.
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
        "boundary": "Digest verification establishes byte identity only; it does not establish evidence quality or authenticity.",
    }
