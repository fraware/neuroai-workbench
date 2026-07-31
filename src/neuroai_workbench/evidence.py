from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any, cast

from .events import append_event
from .util import atomic_write_json, load_json, sha256_bytes, sha256_file, utc_now
from .workspace import Workspace


def _index_path(case_path: Path) -> Path:
    return case_path / "evidence/index.json"


def list_evidence_files(workspace: Workspace, case_id: str) -> list[dict[str, Any]]:
    index = load_json(_index_path(workspace.case_path(case_id)))
    objects = index.get("objects", [])
    if not isinstance(objects, list):
        return []
    return cast(list[dict[str, Any]], objects)


def _next_evidence_id(assessment: dict[str, Any]) -> str:
    used = {row.get("evidence_id") for row in assessment.get("evidence_register", [])}
    index = 1
    while f"EV-{index:03d}" in used:
        index += 1
    return f"EV-{index:03d}"


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
    suffix = "".join(Path(safe_name).suffixes)[-24:]
    stored_name = digest + suffix
    target = case / "evidence/objects" / stored_name
    if not target.exists():
        target.write_bytes(data)
    index_path = _index_path(case)
    index = load_json(index_path)
    assessment = workspace.load_case(case_id)
    evidence_id = _next_evidence_id(assessment)
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
                "access_state": "CONTROLLED PUBLIC EXTRACT",
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
    records = list_evidence_files(workspace, case_id)
    results: list[dict[str, Any]] = []
    for record in records:
        path = case / "evidence/objects" / record["stored_filename"]
        exists = path.is_file()
        actual = sha256_file(path) if exists else None
        results.append(
            {
                "evidence_id": record["evidence_id"],
                "path": str(path.relative_to(case)),
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
