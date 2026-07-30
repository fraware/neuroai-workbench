from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .events import append_event
from .util import atomic_write_json, canonical_json_bytes, ensure_identifier, sha256_bytes, sha256_file, utc_now
from .validation import validate_assessment
from .workspace import Workspace

ASSISTANCE_SCHEMA_VERSION = "1"
TASK_TYPES = {
    "SUMMARIZE_EVIDENCE",
    "DRAFT_FINDING",
    "IDENTIFY_GAPS",
    "CHECK_CONSISTENCY",
    "DRAFT_REPORT_SECTION",
}
DISPOSITIONS = {"ACCEPTED_AS_DRAFT", "PARTIALLY_USED", "REJECTED", "PENDING_REVIEW"}
SENSITIVE_PATTERNS = (
    ("PRIVATE_KEY", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("AWS_ACCESS_KEY", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("JWT", re.compile(r"\beyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b")),
    ("API_SECRET", re.compile(r"(?i)\b(?:api[_ -]?key|secret|password|token)\s*[:=]\s*[^\s]{8,}")),
    ("US_SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
)


def _hash_record(value: dict[str, Any], hash_field: str) -> str:
    controlled = {key: item for key, item in value.items() if key != hash_field}
    return sha256_bytes(canonical_json_bytes(controlled))


def scan_sensitive_text(text: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for code, pattern in SENSITIVE_PATTERNS:
        if pattern.search(text):
            findings.append({"code": code, "message": f"Prompt contains a blocked {code.lower().replace('_', ' ')} pattern."})
    return findings


def _case_assistance_dir(workspace: Workspace, case_id: str) -> Path:
    case = workspace.case_path(case_id)
    if not (case / "assessment.json").is_file():
        raise ValueError(f"Unknown case {case_id!r}")
    root = case / "assistance"
    (root / "requests").mkdir(parents=True, exist_ok=True)
    (root / "responses").mkdir(parents=True, exist_ok=True)
    (root / "dispositions").mkdir(parents=True, exist_ok=True)
    return root


def _selected_context(
    assessment: dict[str, Any], evidence_ids: list[str], requirement_ids: list[str]
) -> dict[str, Any]:
    known_evidence = {item.get("evidence_id"): item for item in assessment.get("evidence_register", [])}
    known_findings = {item.get("requirement_id"): item for item in assessment.get("requirement_findings", [])}
    missing_evidence = sorted(set(evidence_ids) - set(known_evidence))
    missing_requirements = sorted(set(requirement_ids) - set(known_findings))
    if missing_evidence:
        raise ValueError(f"Unknown evidence IDs: {', '.join(missing_evidence)}")
    if missing_requirements:
        raise ValueError(f"Unknown requirement IDs: {', '.join(missing_requirements)}")

    return {
        "assessment_metadata": assessment.get("assessment_metadata", {}),
        "system_identity": {
            key: assessment.get("system_profile", {}).get(key)
            for key in ("system_id", "system_name", "system_family", "configuration_id", "configuration_effective_period")
        },
        "selected_evidence": [
            {
                "evidence_id": item.get("evidence_id"),
                "evidence_type": item.get("evidence_type"),
                "title": item.get("title"),
                "evidence_state": item.get("evidence_state"),
                "strongest_supported_claim": item.get("strongest_supported_claim"),
                "limitations": item.get("limitations", []),
                "prohibited_inferences": item.get("prohibited_inferences", []),
            }
            for evidence_id in evidence_ids
            for item in [known_evidence[evidence_id]]
        ],
        "selected_findings": [
            {
                "requirement_id": item.get("requirement_id"),
                "priority": item.get("priority"),
                "applicability": item.get("applicability"),
                "finding_status": item.get("finding_status"),
                "finding": item.get("finding"),
                "evidence_ids": item.get("evidence_ids", []),
                "strongest_supported_claim": item.get("strongest_supported_claim"),
                "prohibited_inferences": item.get("prohibited_inferences", []),
                "evidence_gap": item.get("evidence_gap"),
                "required_action": item.get("required_action"),
            }
            for requirement_id in requirement_ids
            for item in [known_findings[requirement_id]]
        ],
    }


def create_assistance_request(
    workspace: Workspace,
    case_id: str,
    task_type: str,
    prompt: str,
    *,
    evidence_ids: list[str] | None = None,
    requirement_ids: list[str] | None = None,
    actor: str = "local-user",
) -> dict[str, Any]:
    if task_type not in TASK_TYPES:
        raise ValueError(f"Unsupported task type {task_type!r}")
    prompt = prompt.strip()
    if not prompt:
        raise ValueError("Prompt must not be empty")
    sensitive = scan_sensitive_text(prompt)
    if sensitive:
        raise ValueError(f"Prompt blocked by sensitive-data guard: {json.dumps(sensitive, ensure_ascii=False)}")

    assessment = workspace.load_case(case_id)
    validation = validate_assessment(assessment).to_dict()
    context = _selected_context(assessment, evidence_ids or [], requirement_ids or [])
    assessment_path = workspace.case_path(case_id) / "assessment.json"
    seed = canonical_json_bytes({
        "case_id": case_id,
        "task_type": task_type,
        "prompt": prompt,
        "assessment_sha256": sha256_file(assessment_path),
        "context": context,
    })
    request_id = f"AI-{utc_now().replace(':', '').replace('-', '')}-{sha256_bytes(seed)[:12]}"
    request = {
        "schema_version": ASSISTANCE_SCHEMA_VERSION,
        "request_id": request_id,
        "created_at": utc_now(),
        "case_id": case_id,
        "task_type": task_type,
        "actor": actor,
        "assessment_sha256": sha256_file(assessment_path),
        "assessment_validation_valid": validation["valid"],
        "context": context,
        "context_sha256": sha256_bytes(canonical_json_bytes(context)),
        "prompt": prompt,
        "required_output_contract": {
            "type": "object",
            "required": ["task_type", "summary", "suggestions", "warnings"],
            "suggestion_required": ["target_path", "proposed_text", "evidence_ids", "confidence", "limitations"],
            "confidence_values": ["LOW", "MEDIUM", "HIGH"],
        },
        "model_instructions": [
            "Use only the supplied context and identify every supporting evidence ID.",
            "Preserve system, configuration, population, endpoint, jurisdiction, and evidence-cutoff boundaries.",
            "Do not infer scientific truth from schema validity.",
            "Do not convert unavailable evidence into failure.",
            "Do not collapse capability, authorization, deployment, and conformance.",
            "Return suggestions only. Do not claim to modify the assessment or exercise decision authority.",
        ],
        "data_attestation": "PUBLIC_OR_SYNTHETIC_STRUCTURED_CONTEXT_ONLY",
        "network_execution": "NOT_PERFORMED_BY_WORKBENCH",
        "human_authority": "REQUIRED_FOR_ANY_USE",
    }
    request["request_sha256"] = _hash_record(request, "request_sha256")
    root = _case_assistance_dir(workspace, case_id)
    output = root / "requests" / f"{request_id}.json"
    atomic_write_json(output, request)
    append_event(workspace.case_path(case_id) / "events.jsonl", "AI_ASSISTANCE_REQUEST_CREATED", actor, {
        "request_id": request_id,
        "task_type": task_type,
        "request_sha256": request["request_sha256"],
        "assessment_sha256": request["assessment_sha256"],
    })
    return {"request": request, "path": str(output)}


def load_assistance_request(workspace: Workspace, case_id: str, request_id: str) -> dict[str, Any]:
    ensure_identifier(request_id, "request ID")
    path = _case_assistance_dir(workspace, case_id) / "requests" / f"{request_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Unknown assistance request {request_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_model_output(output: Any, assessment: dict[str, Any], request: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(output, dict):
        return ["Model output must be a JSON object"]
    if output.get("task_type") != request.get("task_type"):
        errors.append("task_type does not match request")
    if not isinstance(output.get("summary"), str) or not output.get("summary", "").strip():
        errors.append("summary must be a non-empty string")
    suggestions = output.get("suggestions")
    if not isinstance(suggestions, list):
        errors.append("suggestions must be a list")
        suggestions = []
    if not isinstance(output.get("warnings"), list):
        errors.append("warnings must be a list")

    evidence_ids = {item.get("evidence_id") for item in assessment.get("evidence_register", [])}
    for index, suggestion in enumerate(suggestions):
        prefix = f"suggestions[{index}]"
        if not isinstance(suggestion, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in ("target_path", "proposed_text"):
            if not isinstance(suggestion.get(field), str) or not suggestion.get(field, "").strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")
        refs = suggestion.get("evidence_ids")
        if not isinstance(refs, list) or not all(isinstance(item, str) for item in refs):
            errors.append(f"{prefix}.evidence_ids must be a string list")
        else:
            unknown = sorted(set(refs) - evidence_ids)
            if unknown:
                errors.append(f"{prefix}.evidence_ids contains unknown IDs: {', '.join(unknown)}")
        if suggestion.get("confidence") not in {"LOW", "MEDIUM", "HIGH"}:
            errors.append(f"{prefix}.confidence must be LOW, MEDIUM, or HIGH")
        if not isinstance(suggestion.get("limitations"), list):
            errors.append(f"{prefix}.limitations must be a list")
    return errors


def record_assistance_response(
    workspace: Workspace,
    case_id: str,
    request_id: str,
    response_file: Path,
    *,
    provider: str,
    model: str,
    actor: str = "local-user",
) -> dict[str, Any]:
    request = load_assistance_request(workspace, case_id, request_id)
    if request.get("request_sha256") != _hash_record(request, "request_sha256"):
        raise ValueError("Assistance request hash is invalid")
    output = json.loads(response_file.read_text(encoding="utf-8"))
    assessment = workspace.load_case(case_id)
    errors = _validate_model_output(output, assessment, request)
    if errors:
        raise ValueError(f"Model output failed contract validation: {json.dumps(errors, ensure_ascii=False)}")

    response = {
        "schema_version": ASSISTANCE_SCHEMA_VERSION,
        "response_id": f"RESP-{request_id}",
        "request_id": request_id,
        "request_sha256": request["request_sha256"],
        "received_at": utc_now(),
        "recorded_by": actor,
        "provider": provider,
        "model": model,
        "output": output,
        "output_sha256": sha256_bytes(canonical_json_bytes(output)),
        "contract_valid": True,
        "disposition_state": "PENDING_REVIEW",
        "boundary": "Recorded model output is an attributable suggestion only and cannot modify assessment findings or decisions without human action.",
    }
    response["response_sha256"] = _hash_record(response, "response_sha256")
    root = _case_assistance_dir(workspace, case_id)
    path = root / "responses" / f"{request_id}.json"
    if path.exists():
        raise ValueError(f"A response is already recorded for {request_id}")
    atomic_write_json(path, response)
    append_event(workspace.case_path(case_id) / "events.jsonl", "AI_ASSISTANCE_RESPONSE_RECORDED", actor, {
        "request_id": request_id,
        "response_sha256": response["response_sha256"],
        "provider": provider,
        "model": model,
    })
    return {"response": response, "path": str(path)}


def dispose_assistance_response(
    workspace: Workspace,
    case_id: str,
    request_id: str,
    disposition: str,
    notes: str,
    *,
    actor: str = "local-user",
) -> dict[str, Any]:
    if disposition not in DISPOSITIONS:
        raise ValueError(f"Unsupported disposition {disposition!r}")
    root = _case_assistance_dir(workspace, case_id)
    response_path = root / "responses" / f"{request_id}.json"
    if not response_path.is_file():
        raise FileNotFoundError(f"No response recorded for {request_id}")
    response = json.loads(response_path.read_text(encoding="utf-8"))
    if response.get("response_sha256") != _hash_record(response, "response_sha256"):
        raise ValueError("Assistance response hash is invalid")
    record = {
        "schema_version": ASSISTANCE_SCHEMA_VERSION,
        "request_id": request_id,
        "response_sha256": response["response_sha256"],
        "disposition": disposition,
        "notes": notes,
        "actor": actor,
        "recorded_at": utc_now(),
        "assessment_mutation": "NONE_PERFORMED_BY_DISPOSITION_RECORD",
    }
    record["disposition_sha256"] = _hash_record(record, "disposition_sha256")
    path = root / "dispositions" / f"{request_id}.json"
    if path.exists():
        raise ValueError(f"A disposition is already recorded for {request_id}")
    atomic_write_json(path, record)
    append_event(workspace.case_path(case_id) / "events.jsonl", "AI_ASSISTANCE_RESPONSE_DISPOSED", actor, {
        "request_id": request_id,
        "disposition": disposition,
        "disposition_sha256": record["disposition_sha256"],
    })
    return {"disposition": record, "path": str(path)}


def verify_assistance_record(workspace: Workspace, case_id: str, request_id: str) -> dict[str, Any]:
    root = _case_assistance_dir(workspace, case_id)
    errors: list[str] = []
    request = load_assistance_request(workspace, case_id, request_id)
    if request.get("request_sha256") != _hash_record(request, "request_sha256"):
        errors.append("request hash mismatch")
    assessment = workspace.load_case(case_id)
    response_path = root / "responses" / f"{request_id}.json"
    disposition_path = root / "dispositions" / f"{request_id}.json"
    response: dict[str, Any] | None = None
    if response_path.exists():
        response = json.loads(response_path.read_text(encoding="utf-8"))
        if response.get("response_sha256") != _hash_record(response, "response_sha256"):
            errors.append("response hash mismatch")
        if response.get("request_sha256") != request.get("request_sha256"):
            errors.append("response does not reference the current request hash")
        if response.get("output_sha256") != sha256_bytes(canonical_json_bytes(response.get("output"))):
            errors.append("model output hash mismatch")
        errors.extend(_validate_model_output(response.get("output"), assessment, request))
    if disposition_path.exists():
        disposition = json.loads(disposition_path.read_text(encoding="utf-8"))
        if disposition.get("disposition_sha256") != _hash_record(disposition, "disposition_sha256"):
            errors.append("disposition hash mismatch")
        if response is None:
            errors.append("disposition exists without response")
        elif disposition.get("response_sha256") != response.get("response_sha256"):
            errors.append("disposition does not reference the current response hash")
    return {
        "valid": not errors,
        "request_id": request_id,
        "response_recorded": response_path.exists(),
        "disposition_recorded": disposition_path.exists(),
        "errors": errors,
        "boundary": "Integrity verification confirms record linkage only; it does not validate the model's substantive suggestions.",
    }
