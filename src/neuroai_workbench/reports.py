from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from .metrics import summarize
from .util import atomic_write_bytes, canonical_json_bytes, sha256_bytes
from .validation import validate_assessment


def _escape(value: Any) -> str:
    text = str(value if value is not None else "")
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _bullets(items: list[Any], empty: str = "None recorded.") -> str:
    values = [str(item).strip() for item in items if str(item).strip()]
    if not values:
        return empty
    return "\n".join(f"- {item}" for item in values)


def render_assessment_markdown(assessment: dict[str, Any]) -> str:
    validation = validate_assessment(assessment).to_dict()
    summary = summarize(assessment)
    metadata = assessment.get("assessment_metadata", {})
    system = assessment.get("system_profile", {})
    profile = assessment.get("profile_selection", {})
    findings = assessment.get("requirement_findings", [])
    decisions = assessment.get("decision_register", [])
    gaps = assessment.get("gap_register", [])
    claims = assessment.get("claim_register", [])
    evidence = assessment.get("evidence_register", [])
    endpoints = assessment.get("endpoint_register", [])

    lines = [
        f"# {_escape(metadata.get('title', 'NeuroAI assessment report'))}",
        "",
        "## Controlled identity",
        "",
        f"- Assessment ID: `{_escape(metadata.get('assessment_id'))}`",
        f"- Instrument: `{_escape(metadata.get('instrument_version'))}`",
        f"- Assessment status: `{_escape(metadata.get('assessment_status'))}`",
        f"- Evidence cutoff: `{_escape(metadata.get('evidence_cutoff'))}`",
        f"- Evidence freeze: `{_escape(metadata.get('evidence_freeze_id'))}`",
        f"- System: {_escape(system.get('system_name'))}",
        f"- Configuration: `{_escape(system.get('configuration_id'))}`",
        f"- Profile: `{_escape(profile.get('final_profile_id'))}`",
        f"- Target level: `{_escape(profile.get('target_conformance_level'))}`",
        "",
        "> Validation and report generation are mechanical controls. They do not establish evidentiary truth, legal authorization, clinical safety, ethical acceptability, or system conformance.",
        "",
        "## Executive determination",
        "",
    ]

    for decision in decisions:
        lines.extend([
            f"### {_escape(decision.get('decision_object_type'))}: {_escape(decision.get('decision_state'))}",
            "",
            _escape(decision.get("strongest_supported_claim")),
            "",
            "**Scope**",
            "",
            f"`{_escape(decision.get('scope'))}`",
            "",
            "**Conditions**",
            "",
            _bullets(decision.get("conditions", [])),
            "",
            "**Prohibited inferences**",
            "",
            _bullets(decision.get("prohibited_inferences", [])),
            "",
            "**Reopening triggers**",
            "",
            _bullets(decision.get("reopening_triggers", [])),
            "",
        ])

    counts = summary["counts"]
    lines.extend([
        "## Assessment state",
        "",
        "| Measure | Count |",
        "|---|---:|",
    ])
    for label, key in (
        ("Claims", "claims"),
        ("Evidence objects", "evidence_objects"),
        ("Endpoints", "endpoints"),
        ("Requirements", "requirements"),
        ("PASS", "pass"),
        ("PARTIAL", "partial"),
        ("FAIL", "fail"),
        ("NOT ASSESSED", "not_assessed"),
        ("Open gaps", "gaps"),
        ("Mechanical P0 blockers", "p0_blockers"),
    ):
        lines.append(f"| {label} | {counts.get(key, 0)} |")

    lines.extend([
        "",
        f"Mechanical validation: `{'VALID' if validation['valid'] else 'INVALID'}`. Schema issues: {len(validation['schema_issues'])}. Semantic issues: {len(validation['semantic_issues'])}.",
        "",
        "## System boundary",
        "",
        f"**Family:** {_escape(system.get('system_family'))}",
        "",
        f"**Intended uses:**\n\n{_bullets(system.get('intended_uses', []))}",
        "",
        f"**Populations:**\n\n{_bullets(system.get('populations', []))}",
        "",
        f"**Contexts:**\n\n{_bullets(system.get('contexts', []))}",
        "",
        f"**Material dependencies:**\n\n{_bullets(system.get('material_dependencies', []))}",
        "",
        f"**Unresolved identity questions:**\n\n{_bullets(system.get('unresolved_identity_questions', []))}",
        "",
        "## Claim adjudication",
        "",
        "| Claim ID | Type | Status | Strongest supported claim |",
        "|---|---|---|---|",
    ])
    for claim in claims:
        lines.append(
            f"| {_escape(claim.get('claim_id'))} | {_escape(claim.get('claim_type'))} | "
            f"{_escape(claim.get('claim_status'))} | {_escape(claim.get('strongest_supported_claim'))} |"
        )

    lines.extend([
        "",
        "## Evidence register",
        "",
        "| Evidence ID | Type | State | Title | Strongest supported claim |",
        "|---|---|---|---|---|",
    ])
    for item in evidence:
        lines.append(
            f"| {_escape(item.get('evidence_id'))} | {_escape(item.get('evidence_type'))} | "
            f"{_escape(item.get('evidence_state'))} | {_escape(item.get('title'))} | "
            f"{_escape(item.get('strongest_supported_claim'))} |"
        )

    lines.extend([
        "",
        "## Endpoint register",
        "",
        "| Endpoint ID | Endpoint | Result | Denominator IDs | Boundary |",
        "|---|---|---|---|---|",
    ])
    for endpoint in endpoints:
        lines.append(
            f"| {_escape(endpoint.get('endpoint_id'))} | {_escape(endpoint.get('endpoint'))} | "
            f"{_escape(endpoint.get('result'))} | {_escape(', '.join(endpoint.get('denominator_ids', [])))} | "
            f"{_escape('; '.join(endpoint.get('transfer_limitations', [])))} |"
        )

    by_module: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for finding in findings:
        by_module[str(finding.get("module_id", "UNRESOLVED"))].append(finding)
    lines.extend(["", "## Requirement findings", ""])
    for module_id in sorted(by_module):
        rows = by_module[module_id]
        lines.extend([
            f"### {module_id}",
            "",
            "| Requirement | Priority | Applicability | Finding | Status | Required action |",
            "|---|---|---|---|---|---|",
        ])
        for row in rows:
            lines.append(
                f"| {_escape(row.get('requirement_id'))} | {_escape(row.get('priority'))} | "
                f"{_escape(row.get('applicability'))} | {_escape(row.get('finding'))} | "
                f"{_escape(row.get('finding_status'))} | {_escape(row.get('required_action'))} |"
            )
        lines.append("")

    lines.extend([
        "## Evidence gaps",
        "",
        "| Gap ID | Priority | State | Missing evidence | Closure criterion |",
        "|---|---|---|---|---|",
    ])
    for gap in gaps:
        lines.append(
            f"| {_escape(gap.get('gap_id'))} | {_escape(gap.get('priority'))} | {_escape(gap.get('state'))} | "
            f"{_escape(gap.get('missing_evidence'))} | {_escape(gap.get('closure_criterion'))} |"
        )

    lines.extend([
        "",
        "## Validation appendix",
        "",
        f"- Assessment canonical SHA-256: `{sha256_bytes(canonical_json_bytes(assessment))}`",
        f"- Schema issues: {len(validation['schema_issues'])}",
        f"- Semantic issues: {len(validation['semantic_issues'])}",
        f"- Warnings: {len(validation['warnings'])}",
        "",
        "### Recorded limitations",
        "",
        _bullets(metadata.get("limitations", [])),
        "",
    ])
    return "\n".join(lines)


def write_assessment_markdown(assessment: dict[str, Any], output: Path) -> dict[str, Any]:
    text = render_assessment_markdown(assessment)
    atomic_write_bytes(output, text.encode("utf-8"))
    return {
        "output": str(output),
        "sha256": sha256_bytes(text.encode("utf-8")),
        "bytes": len(text.encode("utf-8")),
        "boundary": "The report is a deterministic projection of the assessment record; it creates no new finding or authority.",
    }


def render_gap_markdown(assessment: dict[str, Any]) -> str:
    validation = validate_assessment(assessment).to_dict()
    metadata = assessment.get("assessment_metadata", {})
    gaps = assessment.get("gap_register", [])
    findings = assessment.get("requirement_findings", [])
    finding_by_gap: dict[str, list[str]] = defaultdict(list)
    for finding in findings:
        gap_id = finding.get("gap_id")
        if gap_id:
            finding_by_gap[str(gap_id)].append(str(finding.get("requirement_id")))
    lines = [
        f"# Evidence-gap and closure-request report: {_escape(metadata.get('assessment_id'))}",
        "",
        (
            "> This deterministic report restates recorded gaps. It does not determine that evidence exists, "
            "creates no disclosure duty, and does not change an assessment."
        ),
        "",
        f"- Evidence cutoff: `{_escape(metadata.get('evidence_cutoff'))}`",
        f"- Assessment SHA-256: `{sha256_bytes(canonical_json_bytes(assessment))}`",
        f"- Mechanical validation: `{'VALID' if validation['valid'] else 'INVALID'}`",
        f"- Recorded gaps: {len(gaps)}",
        "",
        "| Gap | Priority | State | Related requirements | Missing evidence | Holder | Closure criterion |",
        "|---|---|---|---|---|---|---|",
    ]
    for gap in gaps:
        gap_id = str(gap.get("gap_id"))
        lines.append(
            f"| {_escape(gap_id)} | {_escape(gap.get('priority'))} | {_escape(gap.get('state'))} | "
            f"{_escape(', '.join(finding_by_gap.get(gap_id, [])))} | {_escape(gap.get('missing_evidence'))} | "
            f"{_escape(gap.get('evidence_holder'))} | {_escape(gap.get('closure_criterion'))} |"
        )
    return "\n".join(lines) + "\n"


def write_gap_markdown(assessment: dict[str, Any], output: Path) -> dict[str, Any]:
    text = render_gap_markdown(assessment)
    atomic_write_bytes(output, text.encode("utf-8"))
    return {
        "output": str(output),
        "sha256": sha256_bytes(text.encode("utf-8")),
        "bytes": len(text.encode("utf-8")),
        "boundary": "The gap report is a deterministic projection and creates no disclosure duty or assessment change.",
    }
