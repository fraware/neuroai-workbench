from __future__ import annotations

from collections import Counter
from typing import Any


def summarize(instance: dict[str, Any]) -> dict[str, Any]:
    findings = instance.get("requirement_findings", [])
    status = Counter(row.get("finding_status") for row in findings)
    applicability = Counter(row.get("applicability") for row in findings)
    p0 = [
        row["requirement_id"]
        for row in findings
        if row.get("priority") == "P0"
        and (
            row.get("applicability") == "UNCERTAIN — RESOLUTION REQUIRED"
            or (row.get("applicability") == "APPLICABLE" and row.get("finding_status") in {"FAIL", "NOT ASSESSED"})
        )
    ]
    decision_types = Counter(row.get("decision_object_type") for row in instance.get("decision_register", []))
    metadata = instance.get("assessment_metadata", {})
    system = instance.get("system_profile", {})
    profile = instance.get("profile_selection", {})
    return {
        "assessment_id": metadata.get("assessment_id"),
        "title": metadata.get("title"),
        "assessment_status": metadata.get("assessment_status"),
        "evidence_cutoff": metadata.get("evidence_cutoff"),
        "evidence_freeze_id": metadata.get("evidence_freeze_id"),
        "system_id": system.get("system_id"),
        "system_name": system.get("system_name"),
        "configuration_id": system.get("configuration_id"),
        "profile_id": profile.get("final_profile_id"),
        "target_level": profile.get("target_conformance_level"),
        "counts": {
            "claims": len(instance.get("claim_register", [])),
            "evidence_objects": len(instance.get("evidence_register", [])),
            "endpoints": len(instance.get("endpoint_register", [])),
            "gaps": len(instance.get("gap_register", [])),
            "decisions": len(instance.get("decision_register", [])),
            "requirements": len(findings),
            "applicable": applicability.get("APPLICABLE", 0),
            "uncertain": applicability.get("UNCERTAIN — RESOLUTION REQUIRED", 0),
            "not_applicable": applicability.get("NOT APPLICABLE WITH RATIONALE", 0),
            "pass": status.get("PASS", 0),
            "partial": status.get("PARTIAL", 0),
            "fail": status.get("FAIL", 0),
            "not_assessed": status.get("NOT ASSESSED", 0),
            "p0_blockers": len(p0),
        },
        "p0_blocker_ids": p0,
        "decision_types": dict(decision_types),
        "mechanical_state": "BLOCKED" if p0 else "NO MECHANICAL P0 BLOCKER",
        "boundary": "Mechanical state is not a substantive conformance decision.",
    }
