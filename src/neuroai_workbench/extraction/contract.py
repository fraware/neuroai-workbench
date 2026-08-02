from __future__ import annotations

import json
import re
from importlib.resources import files
from typing import Any, cast

from jsonschema import Draft202012Validator

from neuroai_workbench.util import canonical_json_bytes, sha256_bytes

EXTRACTION_RESOURCE_PACKAGE = "neuroai_workbench.resources.extraction"
EXTRACTION_SCHEMA_VERSION = "1"
REQUEST_SCHEMA = "extraction-request.schema.json"
RESPONSE_SCHEMA = "extraction-response.schema.json"
DISCLOSURE_POLICY_SCHEMA = "disclosure-policy.schema.json"
BENCHMARK_MANIFEST_SCHEMA = "benchmark-manifest.schema.json"
TASK_TYPES = frozenset({"EXTRACT_OBSERVATORY_SIGNALS", "EXTRACT_ENTITY_MENTIONS", "EXTRACT_EVENT_SIGNALS"})
FIELD_TYPES = frozenset(
    {
        "ENTITY_MENTION",
        "DATE",
        "EVENT_TYPE",
        "RELATIONSHIP",
        "CHANGE_CLASS",
        "REOPENING_RELEVANCE",
        "REVIEW_QUESTION",
        "MISSING_EVIDENCE",
    }
)
CONFIDENCE_VALUES = frozenset({"LOW", "MEDIUM", "HIGH"})
EXTRACTION_BOUNDARY = (
    "Extraction output proposes structured observatory change records from selected source excerpts only. "
    "It does not establish source authenticity, legal status, scientific validity, clinical benefit, safety, "
    "conformance, canonical mutation, or release authority."
)
PROMPT_INJECTION_MARKERS = (
    re.compile(r"(?i)\bignore (?:all )?(?:previous|prior) instructions\b"),
    re.compile(r"(?i)\bsystem prompt\b"),
    re.compile(r"(?i)\b(?:run|execute|invoke|call)\s+(?:tool|function|browser|code)\b"),
    re.compile(r"(?i)\b(?:browse|fetch|download|curl|wget)\s+(?:the|this|that|a)\s+(?:url|page|site)\b"),
)


def _schema(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(EXTRACTION_RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8")),
    )


def _schema_errors(value: Any, schema_name: str) -> list[dict[str, str]]:
    validator = Draft202012Validator(_schema(schema_name))
    return [
        {
            "code": "SCHEMA_ERROR",
            "path": ".".join(str(part) for part in error.absolute_path) or "$",
            "message": error.message,
        }
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    ]


def _excerpt_index(request: dict[str, Any]) -> dict[str, dict[str, Any]]:
    excerpts = request.get("selected_excerpts", [])
    if not isinstance(excerpts, list):
        return {}
    return {
        item["excerpt_id"]: item
        for item in excerpts
        if isinstance(item, dict) and isinstance(item.get("excerpt_id"), str)
    }


def _validate_citation(citation: Any, *, prefix: str, excerpts: dict[str, dict[str, Any]]) -> list[str]:
    if not isinstance(citation, dict):
        return [f"{prefix}.citation must be an object"]
    excerpt_id = citation.get("excerpt_id")
    if not isinstance(excerpt_id, str):
        return [f"{prefix}.citation.excerpt_id must be a string"]
    excerpt = excerpts.get(excerpt_id)
    if excerpt is None:
        return [f"{prefix}.citation references unknown excerpt_id {excerpt_id!r}"]
    errors: list[str] = []
    if citation.get("excerpt_sha256") != excerpt.get("excerpt_sha256"):
        errors.append(f"{prefix}.citation.excerpt_sha256 does not match the request excerpt")
    supporting = citation.get("supporting_text")
    excerpt_text = excerpt.get("text")
    if not isinstance(supporting, str) or not supporting.strip():
        errors.append(f"{prefix}.citation.supporting_text must be a non-empty string")
    elif isinstance(excerpt_text, str) and supporting not in excerpt_text:
        errors.append(f"{prefix}.citation.supporting_text is not contained in the cited excerpt")
    start, end = citation.get("start_offset"), citation.get("end_offset")
    if not isinstance(start, int) or not isinstance(end, int) or end <= start:
        errors.append(f"{prefix}.citation offsets must be integers with end_offset > start_offset")
    elif isinstance(excerpt_text, str):
        if start < 0 or end > len(excerpt_text):
            errors.append(f"{prefix}.citation offsets fall outside the cited excerpt")
        elif isinstance(supporting, str) and excerpt_text[start:end] != supporting:
            errors.append(f"{prefix}.citation offsets do not match supporting_text")
    return errors


def validate_extraction_request(value: Any) -> dict[str, Any]:
    errors = _schema_errors(value, REQUEST_SCHEMA)
    if isinstance(value, dict) and value.get("task_type") not in TASK_TYPES:
        errors.append(
            {
                "code": "UNSUPPORTED_TASK",
                "path": "task_type",
                "message": f"task_type must be one of {sorted(TASK_TYPES)}",
            }
        )
    return {"valid": not errors, "errors": errors, "boundary": EXTRACTION_BOUNDARY}


def validate_extraction_response(value: Any, request: dict[str, Any] | None = None) -> dict[str, Any]:
    errors = _schema_errors(value, RESPONSE_SCHEMA)
    if not isinstance(value, dict):
        return {"valid": False, "errors": errors, "boundary": EXTRACTION_BOUNDARY}
    if request is not None:
        if value.get("request_id") != request.get("request_id"):
            errors.append(
                {
                    "code": "REQUEST_MISMATCH",
                    "path": "request_id",
                    "message": "response request_id does not match the extraction request",
                }
            )
        if value.get("request_sha256") != request.get("request_sha256"):
            errors.append(
                {
                    "code": "REQUEST_HASH_MISMATCH",
                    "path": "request_sha256",
                    "message": "response request_sha256 does not match the extraction request",
                }
            )
        if value.get("task_type") != request.get("task_type"):
            errors.append(
                {
                    "code": "TASK_MISMATCH",
                    "path": "task_type",
                    "message": "response task_type does not match the extraction request",
                }
            )
    excerpts = _excerpt_index(request) if isinstance(request, dict) else {}
    proposed_fields = value.get("proposed_fields")
    if isinstance(proposed_fields, list):
        for index, field in enumerate(proposed_fields):
            prefix = f"proposed_fields[{index}]"
            if not isinstance(field, dict):
                errors.append({"code": "INVALID_FIELD", "path": prefix, "message": "must be an object"})
                continue
            if field.get("confidence") not in CONFIDENCE_VALUES:
                errors.append(
                    {
                        "code": "INVALID_CONFIDENCE",
                        "path": f"{prefix}.confidence",
                        "message": "confidence must be LOW, MEDIUM, or HIGH",
                    }
                )
                continue
            if field.get("field_type") not in FIELD_TYPES:
                errors.append(
                    {
                        "code": "INVALID_FIELD_TYPE",
                        "path": f"{prefix}.field_type",
                        "message": f"field_type must be one of {sorted(FIELD_TYPES)}",
                    }
                )
            if "value" not in field:
                errors.append(
                    {
                        "code": "CITATION_REQUIRED",
                        "path": f"{prefix}.value",
                        "message": "proposed field must include a value",
                    }
                )
            for message in _validate_citation(field.get("citation"), prefix=prefix, excerpts=excerpts):
                errors.append({"code": "CITATION_REQUIRED", "path": f"{prefix}.citation", "message": message})
    abstentions = value.get("abstentions", [])
    if isinstance(abstentions, list):
        for index, abstention in enumerate(abstentions):
            prefix = f"abstentions[{index}]"
            if not isinstance(abstention, dict):
                errors.append({"code": "INVALID_ABSTENTION", "path": prefix, "message": "must be an object"})
                continue
            if not isinstance(abstention.get("abstention_reason"), str) or not abstention.get("abstention_reason"):
                errors.append(
                    {
                        "code": "ABSTENTION_REASON_REQUIRED",
                        "path": f"{prefix}.abstention_reason",
                        "message": "abstention_reason must be a non-empty string",
                    }
                )
            if abstention.get("field_type") not in FIELD_TYPES:
                errors.append(
                    {
                        "code": "INVALID_FIELD_TYPE",
                        "path": f"{prefix}.field_type",
                        "message": f"field_type must be one of {sorted(FIELD_TYPES)}",
                    }
                )
    return {"valid": not errors, "errors": errors, "boundary": EXTRACTION_BOUNDARY}


def scan_prompt_injection(text: str) -> list[dict[str, str]]:
    for pattern in PROMPT_INJECTION_MARKERS:
        if pattern.search(text):
            return [
                {
                    "code": "PROMPT_INJECTION",
                    "message": "Source excerpt contains an untrusted instruction-like pattern.",
                }
            ]
    return []


def compute_excerpt_sha256(text: str) -> str:
    return sha256_bytes(canonical_json_bytes({"text": text}))


def contract_sha256() -> str:
    payload = {
        "request_schema": _schema(REQUEST_SCHEMA),
        "response_schema": _schema(RESPONSE_SCHEMA),
        "disclosure_policy_schema": _schema(DISCLOSURE_POLICY_SCHEMA),
        "benchmark_manifest_schema": _schema(BENCHMARK_MANIFEST_SCHEMA),
    }
    return sha256_bytes(canonical_json_bytes(payload))
