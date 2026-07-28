from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .resource_loader import read_resource_bytes
import json


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    path: str
    message: str


@dataclass(frozen=True)
class ValidationReport:
    schema_version: str
    valid: bool
    schema_issues: list[Issue]
    semantic_issues: list[Issue]
    warnings: list[Issue]
    counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "valid": self.valid,
            "schema_issues": [asdict(x) for x in self.schema_issues],
            "semantic_issues": [asdict(x) for x in self.semantic_issues],
            "warnings": [asdict(x) for x in self.warnings],
            "counts": self.counts,
            "boundary": (
                "A valid report confirms schema and configured semantic controls only. "
                "It does not establish evidentiary truth, legal authorization, ethical acceptability, or system conformance."
            ),
        }


def _load_resource(name: str) -> Any:
    return json.loads(read_resource_bytes(name).decode("utf-8"))


SCHEMA = _load_resource("UNIVERSAL_NEUROAI_ASSESSMENT_SCHEMA_v4.2.json")
KERNEL = _load_resource("KERNEL_REQUIREMENTS_v4.2.json")
EXPECTED_REQUIREMENTS = {row["Requirement_ID"] for row in KERNEL}
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


def _ids(rows: list[dict[str, Any]], key: str) -> set[str]:
    return {str(row.get(key)) for row in rows if row.get(key)}


def _duplicates(values: list[str]) -> list[str]:
    return sorted(key for key, count in Counter(values).items() if count > 1)


def semantic_issues(instance: dict[str, Any]) -> tuple[list[Issue], list[Issue]]:
    errors: list[Issue] = []
    warnings: list[Issue] = []

    findings = instance.get("requirement_findings", [])
    requirement_ids = [str(row.get("requirement_id", "")) for row in findings]
    if len(requirement_ids) != 78 or set(requirement_ids) != EXPECTED_REQUIREMENTS or _duplicates(requirement_ids):
        errors.append(Issue(
            "ERROR", "REQ-COVERAGE", "/requirement_findings",
            "requirement_findings must contain every one of the 78 v4.2 requirement IDs exactly once.",
        ))

    registers: dict[str, tuple[list[dict[str, Any]], str]] = {
        "claim": (instance.get("claim_register", []), "claim_id"),
        "evidence": (instance.get("evidence_register", []), "evidence_id"),
        "endpoint": (instance.get("endpoint_register", []), "endpoint_id"),
        "gap": (instance.get("gap_register", []), "gap_id"),
        "decision": (instance.get("decision_register", []), "decision_id"),
        "denominator": (instance.get("denominator_register", []), "denominator_id"),
        "epoch": (instance.get("configuration_epochs", []), "epoch_id"),
        "component": (instance.get("system_profile", {}).get("components", []), "component_id"),
    }
    for name, (rows, key) in registers.items():
        values = [str(row.get(key, "")) for row in rows if row.get(key)]
        dup = _duplicates(values)
        if dup:
            errors.append(Issue("ERROR", "DUPLICATE-ID", f"/{name}_register", f"Duplicate {name} IDs: {dup}"))

    evidence = _ids(instance.get("evidence_register", []), "evidence_id")
    claims = _ids(instance.get("claim_register", []), "claim_id")
    denominators = _ids(instance.get("denominator_register", []), "denominator_id")
    epochs = _ids(instance.get("configuration_epochs", []), "epoch_id")
    requirements = set(requirement_ids)

    for index, claim in enumerate(instance.get("claim_register", [])):
        missing = set(claim.get("evidence_ids", [])) - evidence
        if missing:
            errors.append(Issue("ERROR", "DANGLING-EVIDENCE", f"/claim_register/{index}/evidence_ids", f"Unknown evidence IDs: {sorted(missing)}"))

    for index, endpoint in enumerate(instance.get("endpoint_register", [])):
        missing_evidence = set(endpoint.get("source_evidence_ids", [])) - evidence
        missing_denominators = set(endpoint.get("denominator_ids", [])) - denominators
        missing_epochs = set(endpoint.get("configuration_epoch_ids", [])) - epochs
        if missing_evidence:
            errors.append(Issue("ERROR", "DANGLING-EVIDENCE", f"/endpoint_register/{index}/source_evidence_ids", f"Unknown evidence IDs: {sorted(missing_evidence)}"))
        if missing_denominators:
            errors.append(Issue("ERROR", "DANGLING-DENOMINATOR", f"/endpoint_register/{index}/denominator_ids", f"Unknown denominator IDs: {sorted(missing_denominators)}"))
        if missing_epochs:
            errors.append(Issue("ERROR", "DANGLING-EPOCH", f"/endpoint_register/{index}/configuration_epoch_ids", f"Unknown epoch IDs: {sorted(missing_epochs)}"))

    for index, finding in enumerate(findings):
        path = f"/requirement_findings/{index}"
        missing = set(finding.get("evidence_ids", [])) - evidence
        if missing:
            errors.append(Issue("ERROR", "DANGLING-EVIDENCE", path + "/evidence_ids", f"Unknown evidence IDs: {sorted(missing)}"))
        if finding.get("applicability") == "NOT APPLICABLE WITH RATIONALE" and not str(finding.get("applicability_rationale", "")).strip():
            errors.append(Issue("ERROR", "MISSING-RATIONALE", path + "/applicability_rationale", "Inapplicability requires a non-empty rationale."))
        if finding.get("finding_status") in {"PASS", "PARTIAL", "FAIL"} and not str(finding.get("finding", "")).strip():
            errors.append(Issue("ERROR", "MISSING-FINDING", path + "/finding", "A substantive finding status requires finding text."))
        if finding.get("finding_status") == "PASS" and not finding.get("evidence_ids"):
            warnings.append(Issue("WARNING", "PASS-WITHOUT-EVIDENCE", path, "PASS has no linked evidence object."))

    for index, gap in enumerate(instance.get("gap_register", [])):
        path = f"/gap_register/{index}"
        missing_req = set(gap.get("linked_requirement_ids", [])) - requirements
        missing_claim = set(gap.get("linked_claim_ids", [])) - claims
        if missing_req:
            errors.append(Issue("ERROR", "DANGLING-REQUIREMENT", path + "/linked_requirement_ids", f"Unknown requirement IDs: {sorted(missing_req)}"))
        if missing_claim:
            errors.append(Issue("ERROR", "DANGLING-CLAIM", path + "/linked_claim_ids", f"Unknown claim IDs: {sorted(missing_claim)}"))

    decisions = instance.get("decision_register", [])
    decision_types = {row.get("decision_object_type") for row in decisions}
    if "CLAIM ADJUDICATION" not in decision_types:
        errors.append(Issue("ERROR", "DECISION-SEPARATION", "/decision_register", "A CLAIM ADJUDICATION object is required."))
    if "CONFORMANCE DECISION" not in decision_types:
        errors.append(Issue("ERROR", "DECISION-SEPARATION", "/decision_register", "A CONFORMANCE DECISION object, including a blocked state, is required."))
    for index, decision in enumerate(decisions):
        path = f"/decision_register/{index}"
        if not str(decision.get("authority", "")).strip() or not str(decision.get("authority_basis", "")).strip():
            errors.append(Issue("ERROR", "DECISION-AUTHORITY", path, "Decision authority and authority basis are required."))
        if not decision.get("prohibited_inferences"):
            errors.append(Issue("ERROR", "DECISION-BOUNDARY", path + "/prohibited_inferences", "At least one prohibited inference is required."))
        if not decision.get("reopening_triggers"):
            errors.append(Issue("ERROR", "DECISION-REOPENING", path + "/reopening_triggers", "At least one reopening trigger is required."))
        unknown_evidence = set(decision.get("evidence_ids", [])) - evidence
        if unknown_evidence:
            errors.append(Issue("ERROR", "DANGLING-EVIDENCE", path + "/evidence_ids", f"Unknown evidence IDs: {sorted(unknown_evidence)}"))

    metadata = instance.get("assessment_metadata", {})
    if not str(metadata.get("evidence_freeze_id", "")).strip():
        warnings.append(Issue("WARNING", "NO-EVIDENCE-FREEZE", "/assessment_metadata/evidence_freeze_id", "No evidence freeze ID is assigned."))
    if metadata.get("assessment_status") in {"EVIDENCE FROZEN", "DECISION READY", "CLOSED"} and not str(metadata.get("evidence_freeze_id", "")).strip():
        errors.append(Issue("ERROR", "FREEZE-REQUIRED", "/assessment_metadata/evidence_freeze_id", "This assessment status requires an evidence freeze ID."))

    return errors, warnings


def validate_assessment(instance: dict[str, Any]) -> ValidationReport:
    schema_issues = [
        Issue(
            "ERROR",
            "SCHEMA",
            "/" + "/".join(str(part) for part in error.absolute_path),
            error.message,
        )
        for error in sorted(VALIDATOR.iter_errors(instance), key=lambda item: list(item.absolute_path))
    ]
    semantic, warnings = semantic_issues(instance)
    statuses = Counter(row.get("finding_status") for row in instance.get("requirement_findings", []))
    applicability = Counter(row.get("applicability") for row in instance.get("requirement_findings", []))
    p0_blockers = sum(
        1
        for row in instance.get("requirement_findings", [])
        if row.get("priority") == "P0"
        and (
            row.get("applicability") == "UNCERTAIN — RESOLUTION REQUIRED"
            or (row.get("applicability") == "APPLICABLE" and row.get("finding_status") in {"FAIL", "NOT ASSESSED"})
        )
    )
    counts = {
        "claims": len(instance.get("claim_register", [])),
        "evidence_objects": len(instance.get("evidence_register", [])),
        "endpoints": len(instance.get("endpoint_register", [])),
        "gaps": len(instance.get("gap_register", [])),
        "decisions": len(instance.get("decision_register", [])),
        "requirements": len(instance.get("requirement_findings", [])),
        "applicable": applicability.get("APPLICABLE", 0),
        "uncertain": applicability.get("UNCERTAIN — RESOLUTION REQUIRED", 0),
        "not_applicable": applicability.get("NOT APPLICABLE WITH RATIONALE", 0),
        "pass": statuses.get("PASS", 0),
        "partial": statuses.get("PARTIAL", 0),
        "fail": statuses.get("FAIL", 0),
        "not_assessed": statuses.get("NOT ASSESSED", 0),
        "p0_blockers": p0_blockers,
    }
    return ValidationReport(
        schema_version="v4.2",
        valid=not schema_issues and not semantic,
        schema_issues=schema_issues,
        semantic_issues=semantic,
        warnings=warnings,
        counts=counts,
    )
