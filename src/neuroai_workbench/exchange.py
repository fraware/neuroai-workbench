from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .assistance import scan_sensitive_text
from .events import append_event, verify_chain
from .util import atomic_write_json, canonical_json_bytes, ensure_identifier, sha256_bytes, sha256_file, utc_now
from .workspace import Workspace

EXCHANGE_SCHEMA_VERSION = "1"
RESPONSE_STATES = {
    "PENDING",
    "DECLINED",
    "NOT_HELD",
    "UNKNOWN",
    "AVAILABLE_UNDER_CONDITIONS",
    "PROVIDED_OUT_OF_BAND",
}
PUBLIC_URL_RE = re.compile(r"^https?://", re.IGNORECASE)
PATH_LIKE_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|/|\\\\|file:)", re.IGNORECASE)


def _hash_record(value: dict[str, Any], hash_field: str) -> str:
    controlled = {key: item for key, item in value.items() if key != hash_field and not key.startswith("_")}
    return sha256_bytes(canonical_json_bytes(controlled))


def _exchange_root(workspace: Workspace, case_id: str) -> Path:
    case = workspace.case_path(case_id)
    if not (case / "assessment.json").is_file():
        raise ValueError(f"Unknown case {case_id!r}")
    root = case / "exchanges"
    (root / "requests").mkdir(parents=True, exist_ok=True)
    (root / "responses").mkdir(parents=True, exist_ok=True)
    return root


def _clean_text(value: str, field: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{field} must not be empty")
    findings = scan_sensitive_text(value)
    if findings:
        codes = ", ".join(item["code"] for item in findings)
        raise ValueError(f"{field} contains blocked sensitive patterns: {codes}")
    return value


def _public_url(value: Any) -> str | None:
    if isinstance(value, str) and PUBLIC_URL_RE.match(value.strip()):
        return value.strip()
    return None


def _assessment_index(assessment: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    evidence = {
        str(item.get("evidence_id")): item
        for item in assessment.get("evidence_register", [])
        if item.get("evidence_id")
    }
    gaps = {
        str(item.get("gap_id")): item
        for item in assessment.get("gap_register", [])
        if item.get("gap_id")
    }
    return evidence, gaps


def _related_requirements(assessment: dict[str, Any], evidence_id: str) -> list[str]:
    related: set[str] = set()
    for finding in assessment.get("requirement_findings", []):
        refs = finding.get("evidence_ids", [])
        if evidence_id in refs:
            related.add(str(finding.get("requirement_id")))
    return sorted(related)


def _evidence_metadata(assessment: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    evidence_id = str(item.get("evidence_id"))
    metadata = {
        "evidence_id": evidence_id,
        "title": item.get("title"),
        "evidence_type": item.get("evidence_type"),
        "evidence_state": item.get("evidence_state"),
        "publication_or_record_state": item.get("publication_or_record_state"),
        "access_state": item.get("access_state"),
        "known_holder": item.get("known_holder"),
        "retrieval_or_authorization_required": item.get("retrieval_or_authorization_required"),
        "system_and_version": item.get("system_and_version"),
        "population": item.get("population"),
        "endpoint": item.get("endpoint"),
        "observation_window": item.get("observation_window"),
        "reproducibility_tier": item.get("reproducibility_tier"),
        "limitations": item.get("limitations", []),
        "related_requirement_ids": _related_requirements(assessment, evidence_id),
    }
    public_url = _public_url(item.get("url_or_path"))
    if public_url:
        metadata["public_url"] = public_url
    return metadata


def _gap_metadata(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "gap_id": item.get("gap_id"),
        "priority": item.get("priority"),
        "state": item.get("state"),
        "missing_evidence": item.get("missing_evidence"),
        "request_text": item.get("request_text"),
        "closure_criterion": item.get("closure_criterion"),
        "evidence_access_state": item.get("evidence_access_state"),
        "linked_requirement_ids": item.get("linked_requirement_ids", []),
        "linked_claim_ids": item.get("linked_claim_ids", []),
    }


def create_exchange_request(
    workspace: Workspace,
    case_id: str,
    evidence_ids: list[str],
    *,
    recipient: str,
    purpose: str,
    requested_materials: list[str],
    gap_ids: list[str] | None = None,
    authorized_use: str = "ASSESSMENT_REVIEW_ONLY",
    disclosure_constraints: list[str] | None = None,
    actor: str = "local-user",
) -> dict[str, Any]:
    ensure_identifier(actor, "actor ID")
    recipient = _clean_text(recipient, "recipient")
    purpose = _clean_text(purpose, "purpose")
    authorized_use = _clean_text(authorized_use, "authorized use")
    if not evidence_ids:
        raise ValueError("At least one evidence ID is required")
    if not requested_materials:
        raise ValueError("At least one requested material is required")
    requested_materials = [_clean_text(value, "requested material") for value in requested_materials]
    disclosure_constraints = [
        _clean_text(value, "disclosure constraint") for value in (disclosure_constraints or [])
    ]

    assessment = workspace.load_case(case_id)
    evidence, gaps = _assessment_index(assessment)
    selected_evidence_ids = sorted(set(evidence_ids))
    unknown_evidence = sorted(set(selected_evidence_ids) - set(evidence))
    if unknown_evidence:
        raise ValueError(f"Unknown evidence IDs: {', '.join(unknown_evidence)}")
    selected_gap_ids = sorted(set(gap_ids or []))
    unknown_gaps = sorted(set(selected_gap_ids) - set(gaps))
    if unknown_gaps:
        raise ValueError(f"Unknown gap IDs: {', '.join(unknown_gaps)}")

    assessment_path = workspace.case_path(case_id) / "assessment.json"
    created_at = utc_now()
    seed = canonical_json_bytes({
        "case_id": case_id,
        "evidence_ids": selected_evidence_ids,
        "gap_ids": selected_gap_ids,
        "recipient": recipient,
        "purpose": purpose,
        "created_at": created_at,
        "assessment_sha256": sha256_file(assessment_path),
    })
    request_id = f"EX-{created_at.replace(':', '').replace('-', '')}-{sha256_bytes(seed)[:12]}"
    request = {
        "schema_version": EXCHANGE_SCHEMA_VERSION,
        "request_id": request_id,
        "case_id": case_id,
        "assessment_id": assessment.get("assessment_metadata", {}).get("assessment_id"),
        "assessment_sha256": sha256_file(assessment_path),
        "created_at": created_at,
        "created_by": actor,
        "recipient": recipient,
        "purpose": purpose,
        "authorized_use": authorized_use,
        "requested_materials": requested_materials,
        "disclosure_constraints": disclosure_constraints,
        "selected_evidence_metadata": [
            _evidence_metadata(assessment, evidence[evidence_id]) for evidence_id in selected_evidence_ids
        ],
        "related_gaps": [_gap_metadata(gaps[gap_id]) for gap_id in selected_gap_ids],
        "evidence_bytes_included": False,
        "local_paths_included": False,
        "credentials_included": False,
        "receipt_state": "NOT_REQUESTED_FROM_WORKBENCH",
        "boundary": (
            "This metadata request does not prove that the recipient holds the requested material, "
            "create a disclosure duty, grant access, or register evidence bytes."
        ),
    }
    request["request_sha256"] = _hash_record(request, "request_sha256")
    root = _exchange_root(workspace, case_id)
    output = root / "requests" / f"{request_id}.json"
    if output.exists():
        raise ValueError(f"An identical exchange request already exists for this timestamp: {request_id}")
    atomic_write_json(output, request)
    append_event(
        workspace.case_path(case_id) / "events.jsonl",
        "PROTECTED_EVIDENCE_METADATA_REQUEST_CREATED",
        actor,
        {
            "request_id": request_id,
            "evidence_ids": selected_evidence_ids,
            "gap_ids": selected_gap_ids,
            "request_sha256": request["request_sha256"],
        },
    )
    return {"request": request, "path": str(output)}


def load_exchange_request(workspace: Workspace, case_id: str, request_id: str) -> dict[str, Any]:
    ensure_identifier(request_id, "request ID")
    path = _exchange_root(workspace, case_id) / "requests" / f"{request_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Unknown evidence exchange request {request_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def record_exchange_response(
    workspace: Workspace,
    case_id: str,
    request_id: str,
    response_state: str,
    *,
    holder: str,
    conditions: list[str] | None = None,
    materials: list[dict[str, Any]] | None = None,
    notes: str | None = None,
    actor: str = "local-user",
) -> dict[str, Any]:
    ensure_identifier(actor, "actor ID")
    if response_state not in RESPONSE_STATES:
        raise ValueError(f"Unsupported exchange response state {response_state!r}")
    holder = _clean_text(holder, "holder")
    conditions = [_clean_text(value, "condition") for value in (conditions or [])]
    notes = _clean_text(notes, "notes") if notes is not None else None

    request = load_exchange_request(workspace, case_id, request_id)
    if request.get("request_sha256") != _hash_record(request, "request_sha256"):
        raise ValueError("Evidence exchange request hash is invalid")

    materials = materials or []
    if response_state == "PROVIDED_OUT_OF_BAND" and not materials:
        raise ValueError("PROVIDED_OUT_OF_BAND requires at least one material reference")
    if materials and response_state not in {"AVAILABLE_UNDER_CONDITIONS", "PROVIDED_OUT_OF_BAND"}:
        raise ValueError(f"Response state {response_state} cannot include material references")

    normalized_materials: list[dict[str, Any]] = []
    requested_ids = {
        str(item.get("evidence_id")) for item in request.get("selected_evidence_metadata", [])
    }
    for index, item in enumerate(materials):
        if not isinstance(item, dict):
            raise ValueError(f"materials[{index}] must be an object")
        evidence_id = str(item.get("evidence_id", ""))
        if evidence_id not in requested_ids:
            raise ValueError(f"materials[{index}] references unrequested evidence ID {evidence_id!r}")
        holder_reference = _clean_text(str(item.get("holder_reference", "")), "holder reference")
        if PATH_LIKE_RE.match(holder_reference):
            raise ValueError("holder reference must not contain a local path or file URI")
        digest = item.get("sha256")
        if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise ValueError(f"materials[{index}].sha256 must be a lowercase SHA-256 hex digest")
        normalized_materials.append({
            "evidence_id": evidence_id,
            "holder_reference": holder_reference,
            "sha256": digest,
            "bytes_received_by_workbench": False,
            "verification_state": "NOT_VERIFIED_BY_WORKBENCH",
        })

    root = _exchange_root(workspace, case_id)
    output = root / "responses" / f"{request_id}.json"
    if output.exists():
        raise ValueError(f"A response is already recorded for {request_id}")
    response = {
        "schema_version": EXCHANGE_SCHEMA_VERSION,
        "request_id": request_id,
        "request_sha256": request["request_sha256"],
        "response_state": response_state,
        "holder": holder,
        "conditions": conditions,
        "materials": normalized_materials,
        "notes": notes,
        "recorded_at": utc_now(),
        "recorded_by": actor,
        "evidence_bytes_received": False,
        "assessment_mutation": "NONE_PERFORMED_BY_EXCHANGE_RESPONSE",
        "boundary": (
            "This response records a holder representation or out-of-band reference only. "
            "It does not establish custody, authenticity, completeness, admissibility, or evidentiary weight."
        ),
    }
    response["response_sha256"] = _hash_record(response, "response_sha256")
    atomic_write_json(output, response)
    append_event(
        workspace.case_path(case_id) / "events.jsonl",
        "PROTECTED_EVIDENCE_METADATA_RESPONSE_RECORDED",
        actor,
        {
            "request_id": request_id,
            "response_state": response_state,
            "response_sha256": response["response_sha256"],
        },
    )
    return {"response": response, "path": str(output)}


def verify_exchange_record(workspace: Workspace, case_id: str, request_id: str) -> dict[str, Any]:
    root = _exchange_root(workspace, case_id)
    request = load_exchange_request(workspace, case_id, request_id)
    errors: list[str] = []
    warnings: list[str] = []
    if request.get("request_sha256") != _hash_record(request, "request_sha256"):
        errors.append("request hash mismatch")
    if request.get("evidence_bytes_included") is not False:
        errors.append("request does not preserve the no-evidence-bytes boundary")
    if request.get("local_paths_included") is not False:
        errors.append("request does not preserve the no-local-paths boundary")
    for item in request.get("selected_evidence_metadata", []):
        if "url_or_path" in item:
            errors.append("request metadata contains a prohibited url_or_path field")
        public_url = item.get("public_url")
        if public_url is not None and not _public_url(public_url):
            errors.append("request metadata contains a non-public URL")

    response_path = root / "responses" / f"{request_id}.json"
    response: dict[str, Any] | None = None
    if response_path.exists():
        response = json.loads(response_path.read_text(encoding="utf-8"))
        if response.get("response_sha256") != _hash_record(response, "response_sha256"):
            errors.append("response hash mismatch")
        if response.get("request_sha256") != request.get("request_sha256"):
            errors.append("response does not reference the current request hash")
        if response.get("response_state") not in RESPONSE_STATES:
            errors.append("response has unsupported state")
        if response.get("evidence_bytes_received") is not False:
            errors.append("response does not preserve the no-evidence-bytes boundary")
        for item in response.get("materials", []):
            if item.get("bytes_received_by_workbench") is not False:
                errors.append("material record claims bytes were received by the workbench")
            holder_reference = item.get("holder_reference")
            if isinstance(holder_reference, str) and PATH_LIKE_RE.match(holder_reference):
                errors.append("material record contains a local path or file URI")
            if item.get("verification_state") != "NOT_VERIFIED_BY_WORKBENCH":
                errors.append("material record overstates workbench verification")
    else:
        warnings.append("no exchange response recorded")

    assessment_sha256 = sha256_file(workspace.case_path(case_id) / "assessment.json")
    if request.get("assessment_sha256") != assessment_sha256:
        warnings.append("assessment has changed since the request was created")
    event_report = verify_chain(workspace.case_path(case_id) / "events.jsonl")
    if not event_report["valid"]:
        errors.extend(f"event chain: {error}" for error in event_report["errors"])
    return {
        "valid": not errors,
        "request_id": request_id,
        "response_recorded": response is not None,
        "response_state": response.get("response_state") if response else None,
        "errors": errors,
        "warnings": warnings,
        "event_chain_valid": event_report["valid"],
        "boundary": (
            "Exchange-record integrity verifies metadata linkage only; it does not establish disclosure duties, "
            "evidence receipt, authenticity, completeness, or decision weight."
        ),
    }


def render_exchange_markdown(workspace: Workspace, case_id: str, request_id: str) -> str:
    request = load_exchange_request(workspace, case_id, request_id)
    verification = verify_exchange_record(workspace, case_id, request_id)
    response_path = _exchange_root(workspace, case_id) / "responses" / f"{request_id}.json"
    response = json.loads(response_path.read_text(encoding="utf-8")) if response_path.exists() else None
    lines = [
        f"# Protected-evidence metadata exchange: {request_id}",
        "",
        (
            "> This report contains metadata and holder representations only. It does not include evidence bytes, "
            "create a disclosure duty, establish receipt, or assign evidentiary weight."
        ),
        "",
        f"- Case: `{case_id}`",
        f"- Recipient: {request.get('recipient')}",
        f"- Purpose: {request.get('purpose')}",
        f"- Integrity: `{'VALID' if verification['valid'] else 'INVALID'}`",
        f"- Response: `{verification['response_state'] or 'NOT_RECORDED'}`",
        "",
        "## Requested evidence metadata",
        "",
        "| Evidence | Type | Access state | Known holder | Related requirements |",
        "|---|---|---|---|---|",
    ]
    for item in request.get("selected_evidence_metadata", []):
        lines.append(
            f"| {item.get('evidence_id')} | {item.get('evidence_type')} | {item.get('access_state')} | "
            f"{item.get('known_holder')} | {', '.join(item.get('related_requirement_ids', []))} |"
        )
    lines.extend(["", "## Requested materials", ""])
    lines.extend(f"- {value}" for value in request.get("requested_materials", []))
    if response:
        lines.extend([
            "",
            "## Recorded response",
            "",
            f"- Holder: {response.get('holder')}",
            f"- State: `{response.get('response_state')}`",
            f"- Conditions: {', '.join(response.get('conditions', [])) or 'None recorded'}",
            f"- Notes: {response.get('notes') or 'None recorded'}",
        ])
    if verification["errors"]:
        lines.extend(["", "## Integrity errors", ""])
        lines.extend(f"- {value}" for value in verification["errors"])
    if verification["warnings"]:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {value}" for value in verification["warnings"])
    return "\n".join(lines) + "\n"
