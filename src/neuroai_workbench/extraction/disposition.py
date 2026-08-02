from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from neuroai_workbench.util import atomic_write_json, canonical_json_bytes, ensure_identifier, sha256_bytes, utc_now

from .contract import validate_extraction_response
from .disclosure import check_response_disclosure

EXTRACTION_DISPOSITION_SCHEMA_VERSION = "1"
DISPOSITIONS = frozenset({"ACCEPTED_AS_DRAFT", "PARTIALLY_USED", "REJECTED"})
PENDING_REVIEW_STATE = "PENDING_REVIEW"


def _hash_record(value: dict[str, Any], hash_field: str) -> str:
    controlled = {key: item for key, item in value.items() if key != hash_field}
    return sha256_bytes(canonical_json_bytes(controlled))


def _eval_root(root: Path) -> Path:
    base = root / "extraction_eval"
    for name in ("requests", "responses", "dispositions"):
        (base / name).mkdir(parents=True, exist_ok=True)
    return base


def record_extraction_request(root: Path, request: dict[str, Any], *, actor: str = "local-user") -> dict[str, Any]:
    request_id = request.get("request_id")
    if not isinstance(request_id, str):
        raise ValueError("request_id must be a string")
    ensure_identifier(request_id, "request_id")
    if request.get("request_sha256") != _hash_record(request, "request_sha256"):
        raise ValueError("Extraction request hash is invalid")

    base = _eval_root(root)
    path = base / "requests" / f"{request_id}.json"
    if path.exists():
        raise ValueError(f"An extraction request is already recorded for {request_id}")

    record = {
        "schema_version": EXTRACTION_DISPOSITION_SCHEMA_VERSION,
        "request_id": request_id,
        "recorded_at": utc_now(),
        "recorded_by": actor,
        "request": request,
        "request_sha256": request["request_sha256"],
        "boundary": "Recorded extraction request does not execute providers or mutate canonical observatory state.",
    }
    record["record_sha256"] = _hash_record(record, "record_sha256")
    atomic_write_json(path, record)
    return {"request_record": record, "path": str(path)}


def record_extraction_response(
    root: Path,
    request: dict[str, Any],
    response: dict[str, Any],
    *,
    provider: str,
    model: str,
    actor: str = "local-user",
) -> dict[str, Any]:
    request_id = request.get("request_id")
    if not isinstance(request_id, str):
        raise ValueError("request_id must be a string")
    ensure_identifier(request_id, "request_id")
    if request.get("request_sha256") != _hash_record(request, "request_sha256"):
        raise ValueError("Extraction request hash is invalid")

    validation = validate_extraction_response(response, request)
    if not validation["valid"]:
        raise ValueError(f"Extraction response failed contract validation: {json.dumps(validation['errors'])}")

    disclosure = check_response_disclosure(response)
    if not disclosure["allowed"]:
        raise ValueError(f"Extraction response failed disclosure checks: {json.dumps(disclosure['errors'])}")

    base = _eval_root(root)
    request_path = base / "requests" / f"{request_id}.json"
    if not request_path.is_file():
        raise ValueError(f"No extraction request recorded for {request_id}")

    response_path = base / "responses" / f"{request_id}.json"
    if response_path.exists():
        raise ValueError(f"An extraction response is already recorded for {request_id}")

    record = {
        "schema_version": EXTRACTION_DISPOSITION_SCHEMA_VERSION,
        "response_id": f"XRESP-{request_id}",
        "request_id": request_id,
        "request_sha256": request["request_sha256"],
        "received_at": utc_now(),
        "recorded_by": actor,
        "provider": provider,
        "model": model,
        "response": response,
        "response_sha256": sha256_bytes(canonical_json_bytes(response)),
        "disposition_state": PENDING_REVIEW_STATE,
        "boundary": "Recorded extraction output is an attributable proposal only.",
    }
    record["record_sha256"] = _hash_record(record, "record_sha256")
    atomic_write_json(response_path, record)
    return {"response_record": record, "path": str(response_path)}


def dispose_extraction_response(
    root: Path,
    request_id: str,
    disposition: str,
    notes: str,
    *,
    actor: str = "local-user",
) -> dict[str, Any]:
    ensure_identifier(request_id, "request_id")
    if disposition not in DISPOSITIONS:
        raise ValueError(f"Unsupported extraction disposition {disposition!r}")

    base = _eval_root(root)
    request_path = base / "requests" / f"{request_id}.json"
    response_path = base / "responses" / f"{request_id}.json"
    disposition_path = base / "dispositions" / f"{request_id}.json"

    if not request_path.is_file():
        raise FileNotFoundError(f"No extraction request recorded for {request_id}")
    if not response_path.is_file():
        raise FileNotFoundError(f"No extraction response recorded for {request_id}")
    if disposition_path.exists():
        raise ValueError(f"A disposition is already recorded for {request_id}")

    request_record = cast(dict[str, Any], json.loads(request_path.read_text(encoding="utf-8")))
    response_record = cast(dict[str, Any], json.loads(response_path.read_text(encoding="utf-8")))
    if response_record.get("record_sha256") != _hash_record(response_record, "record_sha256"):
        raise ValueError("Extraction response record hash is invalid")
    if response_record.get("request_sha256") != request_record.get("request_sha256"):
        raise ValueError("Extraction response does not reference the current request hash")

    record = {
        "schema_version": EXTRACTION_DISPOSITION_SCHEMA_VERSION,
        "request_id": request_id,
        "response_sha256": response_record.get("response_sha256"),
        "disposition": disposition,
        "notes": notes,
        "actor": actor,
        "recorded_at": utc_now(),
        "canonical_mutation": "NONE_PERFORMED_BY_DISPOSITION_RECORD",
        "boundary": "Disposition records human handling only; it does not mutate canonical observatory state.",
    }
    record["disposition_sha256"] = _hash_record(record, "disposition_sha256")
    atomic_write_json(disposition_path, record)
    return {"disposition": record, "path": str(disposition_path)}


def verify_extraction_records(root: Path, request_id: str) -> dict[str, Any]:
    ensure_identifier(request_id, "request_id")
    base = _eval_root(root)
    errors: list[str] = []

    request_path = base / "requests" / f"{request_id}.json"
    response_path = base / "responses" / f"{request_id}.json"
    disposition_path = base / "dispositions" / f"{request_id}.json"

    request_record: dict[str, Any] | None = None
    if request_path.is_file():
        request_record = cast(dict[str, Any], json.loads(request_path.read_text(encoding="utf-8")))
        if request_record.get("record_sha256") != _hash_record(request_record, "record_sha256"):
            errors.append("request record hash mismatch")
        request = request_record.get("request")
        if not isinstance(request, dict):
            errors.append("request payload missing")
        elif request.get("request_sha256") != request_record.get("request_sha256"):
            errors.append("request hash mismatch")

    response_record: dict[str, Any] | None = None
    if response_path.is_file():
        response_record = cast(dict[str, Any], json.loads(response_path.read_text(encoding="utf-8")))
        if response_record.get("record_sha256") != _hash_record(response_record, "record_sha256"):
            errors.append("response record hash mismatch")
        if request_record and response_record.get("request_sha256") != request_record.get("request_sha256"):
            errors.append("response does not reference the current request hash")
        response = response_record.get("response")
        if isinstance(response, dict) and request_record:
            request = request_record.get("request")
            if isinstance(request, dict):
                validation = validate_extraction_response(response, request)
                if not validation["valid"]:
                    errors.append("response contract invalid")
                if response_record.get("response_sha256") != sha256_bytes(canonical_json_bytes(response)):
                    errors.append("response content hash mismatch")

    if disposition_path.is_file():
        disposition = cast(dict[str, Any], json.loads(disposition_path.read_text(encoding="utf-8")))
        if disposition.get("disposition_sha256") != _hash_record(disposition, "disposition_sha256"):
            errors.append("disposition hash mismatch")
        if disposition.get("disposition") not in DISPOSITIONS:
            errors.append("unsupported disposition")
        if response_record is None:
            errors.append("disposition exists without response")
        elif disposition.get("response_sha256") != response_record.get("response_sha256"):
            errors.append("disposition does not reference the current response hash")

    return {
        "valid": not errors,
        "request_id": request_id,
        "request_recorded": request_path.is_file(),
        "response_recorded": response_path.is_file(),
        "disposition_recorded": disposition_path.is_file(),
        "errors": errors,
        "boundary": "Integrity verification confirms record linkage only; it does not validate substantive extraction truth.",
    }
