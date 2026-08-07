from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any, cast

from .assessment_paths import (
    apply_field_patches,
    get_at_path,
    normalize_target_path,
    review_target_for_path,
)
from .events import append_event
from .review import assessment_edit_authority_assignments
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
DISPOSITIONS = {"ACCEPTED_AS_DRAFT", "PARTIALLY_USED", "REJECTED"}
APPLYABLE_DISPOSITIONS = frozenset({"ACCEPTED_AS_DRAFT", "PARTIALLY_USED"})
PENDING_REVIEW_STATE = "PENDING_REVIEW"
ASSISTANCE_PROPOSAL_APPLIED_EVENT = "ASSISTANCE_PROPOSAL_APPLIED"
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
            findings.append(
                {"code": code, "message": f"Prompt contains a blocked {code.lower().replace('_', ' ')} pattern."}
            )
    return findings


def _case_assistance_dir(workspace: Workspace, case_id: str) -> Path:
    case = workspace.case_path(case_id)
    if not (case / "assessment.json").is_file():
        raise ValueError(f"Unknown case {case_id!r}")
    root = case / "assistance"
    (root / "requests").mkdir(parents=True, exist_ok=True)
    (root / "responses").mkdir(parents=True, exist_ok=True)
    (root / "dispositions").mkdir(parents=True, exist_ok=True)
    (root / "applications").mkdir(parents=True, exist_ok=True)
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
            for key in (
                "system_id",
                "system_name",
                "system_family",
                "configuration_id",
                "configuration_effective_period",
            )
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
    context_findings = scan_sensitive_text(json.dumps(context, ensure_ascii=False, sort_keys=True))
    if context_findings:
        raise ValueError(
            f"Selected assistance context blocked by sensitive-data guard: "
            f"{json.dumps(context_findings, ensure_ascii=False)}"
        )
    assessment_path = workspace.case_path(case_id) / "assessment.json"
    request_id = f"AI-{uuid.uuid4().hex}"
    root = _case_assistance_dir(workspace, case_id)
    output = root / "requests" / f"{request_id}.json"
    if output.exists():
        raise ValueError(f"An assistance request already exists for {request_id}")
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
        "disclosure_policy": "ATTESTATION_PLUS_SECRET_SCAN_ONLY",
        "network_execution": "NOT_PERFORMED_BY_WORKBENCH",
        "human_authority": "REQUIRED_FOR_ANY_USE",
    }
    request["request_sha256"] = _hash_record(request, "request_sha256")
    atomic_write_json(output, request)
    append_event(
        workspace.case_path(case_id) / "events.jsonl",
        "AI_ASSISTANCE_REQUEST_CREATED",
        actor,
        {
            "request_id": request_id,
            "task_type": task_type,
            "request_sha256": request["request_sha256"],
            "assessment_sha256": request["assessment_sha256"],
        },
    )
    return {"request": request, "path": str(output)}


def load_assistance_request(workspace: Workspace, case_id: str, request_id: str) -> dict[str, Any]:
    ensure_identifier(request_id, "request ID")
    path = _case_assistance_dir(workspace, case_id) / "requests" / f"{request_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Unknown assistance request {request_id}")
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


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
    assessment_path = workspace.case_path(case_id) / "assessment.json"
    current_assessment_sha256 = sha256_file(assessment_path)
    if request.get("assessment_sha256") != current_assessment_sha256:
        raise ValueError(
            "Assistance request is stale: assessment_sha256 no longer matches the current assessment. "
            "Create a new assist-request against the current assessment before recording a response."
        )
    output = json.loads(response_file.read_text(encoding="utf-8"))
    assessment = workspace.load_case(case_id)
    errors = _validate_model_output(output, assessment, request)
    if errors:
        raise ValueError(f"Model output failed contract validation: {json.dumps(errors, ensure_ascii=False)}")
    output_sensitive = scan_sensitive_text(canonical_json_bytes(output).decode("utf-8"))
    if output_sensitive:
        raise ValueError(
            f"Model output blocked by sensitive-data guard: {json.dumps(output_sensitive, ensure_ascii=False)}"
        )

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
        "disposition_state": PENDING_REVIEW_STATE,
        "boundary": "Recorded model output is an attributable suggestion only and cannot modify assessment findings or decisions without human action.",
    }
    response["response_sha256"] = _hash_record(response, "response_sha256")
    root = _case_assistance_dir(workspace, case_id)
    path = root / "responses" / f"{request_id}.json"
    if path.exists():
        raise ValueError(f"A response is already recorded for {request_id}")
    atomic_write_json(path, response)
    append_event(
        workspace.case_path(case_id) / "events.jsonl",
        "AI_ASSISTANCE_RESPONSE_RECORDED",
        actor,
        {
            "request_id": request_id,
            "response_sha256": response["response_sha256"],
            "provider": provider,
            "model": model,
        },
    )
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
    request = load_assistance_request(workspace, case_id, request_id)
    assessment_path = workspace.case_path(case_id) / "assessment.json"
    if request.get("assessment_sha256") != sha256_file(assessment_path):
        raise ValueError(
            "ASSESSMENT_DRIFT: assistance request assessment_sha256 no longer matches the current assessment. "
            "Create a new assist-request before recording a disposition."
        )
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
    append_event(
        workspace.case_path(case_id) / "events.jsonl",
        "AI_ASSISTANCE_RESPONSE_DISPOSED",
        actor,
        {
            "request_id": request_id,
            "disposition": disposition,
            "disposition_sha256": record["disposition_sha256"],
        },
    )
    return {"disposition": record, "path": str(path)}


def verify_assistance_record(workspace: Workspace, case_id: str, request_id: str) -> dict[str, Any]:
    root = _case_assistance_dir(workspace, case_id)
    errors: list[str] = []
    request = load_assistance_request(workspace, case_id, request_id)
    if request.get("request_sha256") != _hash_record(request, "request_sha256"):
        errors.append("request hash mismatch")
    assessment_path = workspace.case_path(case_id) / "assessment.json"
    if request.get("assessment_sha256") != sha256_file(assessment_path):
        errors.append("ASSESSMENT_DRIFT")
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
        if disposition.get("disposition") not in DISPOSITIONS:
            errors.append("disposition is not a final allowed disposition")
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


def _normalize_field_patches(field_patches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(field_patches, list) or not field_patches:
        raise ValueError("Explicit field_patches are required; acceptance is not application")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, patch in enumerate(field_patches):
        if not isinstance(patch, dict):
            raise ValueError(f"field_patches[{index}] must be an object")
        path = normalize_target_path(str(patch.get("target_path", "")))
        if path in seen:
            raise ValueError(f"Duplicate field patch for {path}")
        seen.add(path)
        if "value" not in patch:
            raise ValueError(f"field_patches[{index}] requires value")
        normalized.append({"target_path": path, "value": patch["value"]})
    return normalized


def apply_assistance_proposal(
    workspace: Workspace,
    case_id: str,
    request_id: str,
    *,
    actor: str,
    expected_assessment_sha256: str,
    field_patches: list[dict[str, Any]],
    require_valid: bool = True,
) -> dict[str, Any]:
    """Apply an exactly bound human-disposed proposal through ordinary ``save_case``."""
    ensure_identifier(request_id, "request ID")
    ensure_identifier(actor, "actor ID")
    if not expected_assessment_sha256 or not isinstance(expected_assessment_sha256, str):
        raise ValueError("expected_assessment_sha256 is required")
    patches = _normalize_field_patches(field_patches)

    root = _case_assistance_dir(workspace, case_id)
    application_path = root / "applications" / f"{request_id}.json"
    if application_path.exists():
        raise ValueError(f"Assistance proposal {request_id} has already been applied")

    request = load_assistance_request(workspace, case_id, request_id)
    if request.get("request_sha256") != _hash_record(request, "request_sha256"):
        raise ValueError("Assistance request hash is invalid")

    response_path = root / "responses" / f"{request_id}.json"
    if not response_path.is_file():
        raise FileNotFoundError(f"No response recorded for {request_id}")
    response = json.loads(response_path.read_text(encoding="utf-8"))
    if response.get("response_sha256") != _hash_record(response, "response_sha256"):
        raise ValueError("Assistance response hash is invalid")

    disposition_path = root / "dispositions" / f"{request_id}.json"
    if not disposition_path.is_file():
        raise ValueError(f"No disposition recorded for {request_id}; acceptance is required before apply")
    disposition = json.loads(disposition_path.read_text(encoding="utf-8"))
    if disposition.get("disposition_sha256") != _hash_record(disposition, "disposition_sha256"):
        raise ValueError("Assistance disposition hash is invalid")
    if disposition.get("response_sha256") != response.get("response_sha256"):
        raise ValueError("Disposition does not reference the current response hash")
    disposition_value = disposition.get("disposition")
    if disposition_value not in APPLYABLE_DISPOSITIONS:
        raise ValueError(
            f"Disposition {disposition_value!r} cannot be applied; "
            "only ACCEPTED_AS_DRAFT or PARTIALLY_USED may be applied with explicit field patches"
        )

    assessment_path = workspace.case_path(case_id) / "assessment.json"
    current_sha = sha256_file(assessment_path)
    if current_sha != expected_assessment_sha256:
        raise ValueError("Stale assessment: expected_assessment_sha256 does not match the current assessment")
    if request.get("assessment_sha256") != current_sha:
        raise ValueError(
            "ASSESSMENT_DRIFT: assistance request assessment_sha256 no longer matches the current assessment"
        )

    suggestions = response.get("output", {}).get("suggestions")
    if not isinstance(suggestions, list) or not suggestions:
        raise ValueError("Assistance response suggestions are missing")
    normalized_suggestions: list[tuple[str, Any]] = []
    for index, item in enumerate(suggestions):
        if not isinstance(item, dict) or not item.get("target_path") or "proposed_text" not in item:
            raise ValueError(f"Assistance suggestion {index} is malformed")
        normalized_suggestions.append((normalize_target_path(str(item["target_path"])), item["proposed_text"]))
    if len(set(normalized_suggestions)) != len(normalized_suggestions):
        raise ValueError("Assistance response contains duplicate path/text suggestions")

    selected_indices: set[int] = set()
    for patch in patches:
        matches = [
            index
            for index, suggestion in enumerate(normalized_suggestions)
            if suggestion == (patch["target_path"], patch["value"])
        ]
        if len(matches) != 1:
            raise ValueError(
                f"Field patch is not exactly bound to one accepted proposal suggestion: {patch['target_path']}"
            )
        selected_indices.add(matches[0])
    if len(selected_indices) != len(patches):
        raise ValueError("Multiple field patches select the same assistance suggestion")
    all_indices = set(range(len(normalized_suggestions)))
    if disposition_value == "ACCEPTED_AS_DRAFT" and selected_indices != all_indices:
        raise ValueError("ACCEPTED_AS_DRAFT must apply every accepted suggestion exactly")
    if disposition_value == "PARTIALLY_USED" and selected_indices == all_indices:
        raise ValueError("PARTIALLY_USED must apply a non-empty proper subset of accepted suggestions")

    request_path = root / "requests" / f"{request_id}.json"
    proposal_bytes_before = request_path.read_bytes()
    response_bytes_before = response_path.read_bytes()
    disposition_bytes_before = disposition_path.read_bytes()

    assessment = workspace.load_case(case_id)
    authority_targets = [review_target_for_path(assessment, patch["target_path"]) for patch in patches]
    authority_assignments = assessment_edit_authority_assignments(workspace, case_id, actor, authority_targets)
    authority_digests = {str(item["assignment_id"]): str(item["assignment_sha256"]) for item in authority_assignments}

    patches_for_record: list[dict[str, Any]] = []
    for patch in patches:
        before_value = get_at_path(assessment, patch["target_path"])
        patches_for_record.append(
            {
                "target_path": patch["target_path"],
                "expected_value": before_value,
                "value": patch["value"],
                "before_value_sha256": sha256_bytes(canonical_json_bytes(before_value)),
                "after_value_sha256": sha256_bytes(canonical_json_bytes(patch["value"])),
            }
        )
    patched = apply_field_patches(assessment, patches)
    planned_bytes = json.dumps(patched, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    planned_after = sha256_bytes(planned_bytes)
    applied_at = utc_now()
    application: dict[str, Any] = {
        "schema_version": ASSISTANCE_SCHEMA_VERSION,
        "application_id": f"APP-{request_id}",
        "request_id": request_id,
        "request_sha256": request["request_sha256"],
        "response_sha256": response["response_sha256"],
        "disposition": disposition_value,
        "disposition_sha256": disposition["disposition_sha256"],
        "actor": actor,
        "authority_assignments": authority_digests,
        "applied_at": applied_at,
        "field_patches": patches_for_record,
        "before_assessment_sha256": current_sha,
        "after_assessment_sha256": planned_after,
        "assessment_mutation": "ORDINARY_SAVE_CASE",
        "model_invocation": "NONE",
        "authority_profile": "LOCAL_UNAUTHENTICATED_ATTRIBUTION",
        "authority_boundary": (
            "Active local decision-role records authorize this workflow edit only. "
            "They do not authenticate identity or establish institutional or release authority."
        ),
    }
    application["application_sha256"] = _hash_record(application, "application_sha256")
    event_metadata = {
        "proposal_kind": "ASSISTANCE",
        "proposal_id": request_id,
        "proposal_sha256": request["request_sha256"],
        "disposition_sha256": disposition["disposition_sha256"],
        "response_sha256": response["response_sha256"],
        "disposition": disposition_value,
        "applied_paths": [item["target_path"] for item in patches_for_record],
        "authority_assignments": authority_digests,
        "model_invocation": "NONE",
        "before_assessment_sha256": current_sha,
        "after_assessment_sha256": planned_after,
        "application_sha256": application["application_sha256"],
    }

    def revalidate_authority() -> None:
        current = assessment_edit_authority_assignments(workspace, case_id, actor, authority_targets)
        current_digests = {str(item["assignment_id"]): str(item["assignment_sha256"]) for item in current}
        for assignment_id, digest in authority_digests.items():
            if current_digests.get(assignment_id) != digest:
                raise ValueError("Assessment-edit authority changed before persistence")
        current_assessment = workspace.load_case(case_id)
        for patch in patches_for_record:
            if get_at_path(current_assessment, patch["target_path"]) != patch["expected_value"]:
                raise ValueError(f"Field value changed before persistence: {patch['target_path']}")

    save_result = workspace.save_case(
        case_id,
        patched,
        actor=actor,
        require_valid=require_valid,
        expected_sha256=expected_assessment_sha256,
        event_metadata=event_metadata,
        additional_events=[(ASSISTANCE_PROPOSAL_APPLIED_EVENT, event_metadata)],
        exclusive_records=[(application_path, application)],
        precondition=revalidate_authority,
    )
    if save_result.get("after_sha256") != planned_after:
        raise RuntimeError("Assessment digest after ordinary save did not match the planned apply digest")
    if request_path.read_bytes() != proposal_bytes_before:
        raise RuntimeError("Assistance request bytes changed during apply")
    if response_path.read_bytes() != response_bytes_before:
        raise RuntimeError("Assistance response bytes changed during apply")
    if disposition_path.read_bytes() != disposition_bytes_before:
        raise RuntimeError("Assistance disposition bytes changed during apply")
    return {
        "application": application,
        "path": str(application_path),
        "save": save_result,
        "boundary": (
            "Assistance disposition remains separate from assessment authority. "
            "This record links an ordinary assessment edit to a human-accepted proposal."
        ),
    }
