from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


def compare_assessments(cases: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    matrix: dict[str, dict[str, Any]] = defaultdict(dict)
    summaries: list[dict[str, Any]] = []
    for case_id, assessment in cases:
        findings = assessment.get("requirement_findings", [])
        status = Counter(row.get("finding_status") for row in findings)
        summaries.append({
            "case_id": case_id,
            "assessment_id": assessment.get("assessment_metadata", {}).get("assessment_id"),
            "system_name": assessment.get("system_profile", {}).get("system_name"),
            "profile": assessment.get("profile_selection", {}).get("final_profile_id"),
            "target_level": assessment.get("profile_selection", {}).get("target_conformance_level"),
            "status_counts": dict(status),
        })
        for row in findings:
            matrix[row["requirement_id"]][case_id] = {
                "module_id": row.get("module_id"),
                "priority": row.get("priority"),
                "applicability": row.get("applicability"),
                "finding_status": row.get("finding_status"),
                "evidence_access_state": row.get("evidence_access_state"),
            }
    common_pass: list[str] = []
    common_partial: list[str] = []
    universal_voids: list[str] = []
    for requirement_id, values in matrix.items():
        rows = list(values.values())
        if len(rows) != len(cases):
            continue
        statuses = [row["finding_status"] for row in rows]
        if all(status == "PASS" for status in statuses):
            common_pass.append(requirement_id)
        if all(status == "PARTIAL" for status in statuses):
            common_partial.append(requirement_id)
        if all(row["priority"] == "P0" and row["applicability"] == "APPLICABLE" and row["finding_status"] == "NOT ASSESSED" for row in rows):
            universal_voids.append(requirement_id)
    return {
        "case_count": len(cases),
        "cases": summaries,
        "requirement_matrix": dict(sorted(matrix.items())),
        "common_pass": sorted(common_pass),
        "common_partial": sorted(common_partial),
        "universal_p0_evidence_voids": sorted(universal_voids),
        "boundary": "Cross-case aggregation preserves source finding states and does not create a new conformance decision.",
    }
