from __future__ import annotations

import json
import re
from typing import Any

from neuroai_workbench.assistance import scan_sensitive_text

from .contract import EXTRACTION_BOUNDARY, _schema, _schema_errors

DISCLOSURE_POLICY_SCHEMA = "disclosure-policy.schema.json"
DEFAULT_POLICY_DOCUMENT = "disclosure-policy.default.json"
DEFAULT_POLICY_ID = "EXTRACTION_DEFAULT_v1"
DEFAULT_DISCLOSURE_POLICY = "FIELD_CLASSIFICATION_REQUIRED"
EXPORT_ALLOWED_CLASSES = frozenset({"PUBLIC_SYNTHETIC", "PUBLIC_SOURCE_EXCERPT"})
PROTECTED_DISCLOSURE_CLASSES = frozenset(
    {
        "PROTECTED_NEURAL",
        "PROTECTED_PARTICIPANT",
        "PROTECTED_REGULATOR",
        "PROTECTED_SECURITY",
        "PROTECTED_CLINICAL",
        "CREDENTIAL",
        "LOCAL_PATH",
    }
)
PATH_LIKE_RE = re.compile(r"(?:[A-Za-z]:[\\/]|/home/|/Users/|\\\\|file://)", re.IGNORECASE)
PROTECTED_CLASS_MARKERS = (
    re.compile(r"(?i)\bPROTECTED_(?:NEURAL|PARTICIPANT|REGULATOR|SECURITY|CLINICAL)\b"),
    re.compile(r"(?i)\bparticipant[_ -]?id\b"),
    re.compile(r"(?i)\bneural[_ -]?recording\b"),
)


def load_disclosure_policy() -> dict[str, Any]:
    return _schema(DEFAULT_POLICY_DOCUMENT)


def validate_disclosure_policy(value: Any) -> dict[str, Any]:
    errors = _schema_errors(value, DISCLOSURE_POLICY_SCHEMA)
    if isinstance(value, dict) and value.get("default_deny_protected") is not True:
        errors.append(
            {
                "code": "POLICY_INVALID",
                "path": "default_deny_protected",
                "message": "protected disclosure must remain default-deny",
            }
        )
    return {"valid": not errors, "errors": errors, "boundary": EXTRACTION_BOUNDARY}


def _scan_text(text: str) -> list[dict[str, str]]:
    findings = scan_sensitive_text(text)
    if PATH_LIKE_RE.search(text):
        findings.append({"code": "LOCAL_PATH", "message": "Text contains a blocked local path pattern."})
    for pattern in PROTECTED_CLASS_MARKERS:
        if pattern.search(text):
            findings.append(
                {
                    "code": "PROTECTED_DISCLOSURE",
                    "message": "Text contains a blocked protected-evidence marker.",
                }
            )
            break
    return findings


def check_context_disclosure(request: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    attestation = request.get("disclosure_attestation")
    if not isinstance(attestation, dict):
        errors.append(
            {
                "code": "DISCLOSURE_ATTESTATION",
                "path": "disclosure_attestation",
                "message": "disclosure attestation must be present",
            }
        )
    else:
        if attestation.get("protected_evidence_excluded") is not True:
            errors.append(
                {
                    "code": "PROTECTED_DISCLOSURE",
                    "path": "disclosure_attestation.protected_evidence_excluded",
                    "message": "protected evidence exclusion must be attested as true",
                }
            )
        if attestation.get("field_classification_complete") is not True:
            errors.append(
                {
                    "code": "DISCLOSURE_INCOMPLETE",
                    "path": "disclosure_attestation.field_classification_complete",
                    "message": "field-level disclosure classification must be complete before export",
                }
            )
    policy = load_disclosure_policy()
    allowed = set(policy.get("export_allowed_classes", []))
    excerpts = request.get("selected_excerpts", [])
    if isinstance(excerpts, list):
        for index, excerpt in enumerate(excerpts):
            if not isinstance(excerpt, dict):
                continue
            disclosure_class = excerpt.get("disclosure_class")
            if disclosure_class not in allowed:
                errors.append(
                    {
                        "code": "PROTECTED_DISCLOSURE",
                        "path": f"selected_excerpts[{index}].disclosure_class",
                        "message": f"disclosure class {disclosure_class!r} is not export-allowed",
                    }
                )
            text = excerpt.get("text")
            if isinstance(text, str):
                for finding in _scan_text(text):
                    errors.append(
                        {
                            "code": finding["code"],
                            "path": f"selected_excerpts[{index}].text",
                            "message": finding["message"],
                        }
                    )
    for finding in _scan_text(json.dumps(request, ensure_ascii=False, sort_keys=True)):
        errors.append({"code": finding["code"], "path": "$", "message": finding["message"]})
    return {
        "allowed": not errors,
        "errors": errors,
        "policy_id": policy.get("policy_id", DEFAULT_POLICY_ID),
        "boundary": (
            "Disclosure checks enforce default-deny on protected classes and obvious secret or path patterns. "
            "Passing checks does not prove that context is public, synthetic, or lawfully exportable."
        ),
    }


def check_response_disclosure(response: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    for finding in _scan_text(json.dumps(response, ensure_ascii=False, sort_keys=True)):
        errors.append({"code": finding["code"], "path": "$", "message": finding["message"]})
    return {
        "allowed": not errors,
        "errors": errors,
        "boundary": "Response disclosure checks reject obvious protected markers and secret patterns only.",
    }
