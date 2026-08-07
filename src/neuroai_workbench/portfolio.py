"""Read-only cross-case analysis for completed NeuroAI assessments."""

from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .util import atomic_write_bytes, atomic_write_json

CANONICAL_STATUSES = (
    "PASS",
    "PARTIAL",
    "FAIL",
    "NOT_ASSESSED",
    "NOT_APPLICABLE",
    "UNRESOLVED",
)
WEAK_STATUSES = frozenset({"FAIL", "NOT_ASSESSED", "PARTIAL", "UNRESOLVED"})
WEAKNESS_WEIGHTS = {
    "FAIL": 4,
    "NOT_ASSESSED": 3,
    "PARTIAL": 2,
    "UNRESOLVED": 1,
    "PASS": 0,
    "NOT_APPLICABLE": 0,
}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def normalize_status(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return "UNRESOLVED"
    token = value.strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "PASSED": "PASS",
        "PASS": "PASS",
        "PARTIAL": "PARTIAL",
        "PARTIALLY_MET": "PARTIAL",
        "FAIL": "FAIL",
        "FAILED": "FAIL",
        "NOT_ASSESSED": "NOT_ASSESSED",
        "UNASSESSED": "NOT_ASSESSED",
        "NOT_APPLICABLE": "NOT_APPLICABLE",
        "N/A": "NOT_APPLICABLE",
        "NA": "NOT_APPLICABLE",
        "UNRESOLVED": "UNRESOLVED",
        "UNKNOWN": "UNRESOLVED",
    }
    return aliases.get(token, "UNRESOLVED")


def _open_gap_count(gaps: list[Any]) -> int:
    closed_states = {"CLOSED", "RESOLVED", "COMPLETE", "COMPLETED"}
    total = 0
    for gap in gaps:
        if not isinstance(gap, dict):
            continue
        state = str(gap.get("state") or gap.get("status") or "OPEN").strip().upper().replace("-", "_").replace(" ", "_")
        if state not in closed_states:
            total += 1
    return total


def normalize_assessment(value: Any, *, source_path: str | None = None) -> dict[str, Any]:
    """Normalize historical and current completed-assessment shapes for comparison only."""
    if not isinstance(value, dict):
        raise ValueError("Assessment must be a JSON object")

    metadata = _mapping(value.get("assessment_metadata")) or _mapping(value.get("metadata"))
    system = _mapping(value.get("system_profile")) or _mapping(value.get("system"))
    raw_findings = _list(value.get("requirement_findings"))
    if not raw_findings:
        raise ValueError("Assessment has no requirement_findings")

    case_id = str(metadata.get("assessment_id") or metadata.get("id") or "").strip()
    if not case_id and source_path:
        case_id = Path(source_path).stem
    if not case_id:
        raise ValueError("Assessment is missing assessment_id")

    system_name = str(system.get("system_name") or metadata.get("title") or case_id).strip()
    title = str(metadata.get("title") or system_name or case_id).strip()
    evidence = _list(value.get("evidence_register")) or _list(value.get("sources"))
    gaps = _list(value.get("gap_register")) or _list(value.get("gaps_and_requests"))

    findings: list[dict[str, Any]] = []
    seen_requirement_ids: set[str] = set()
    for index, item in enumerate(raw_findings):
        if not isinstance(item, dict):
            raise ValueError(f"requirement_findings[{index}] must be an object")
        requirement_id = str(item.get("requirement_id") or "").strip()
        if not requirement_id:
            raise ValueError(f"requirement_findings[{index}] is missing requirement_id")
        if requirement_id in seen_requirement_ids:
            raise ValueError(f"Duplicate requirement_id {requirement_id!r} in assessment {case_id!r}")
        seen_requirement_ids.add(requirement_id)

        source_status = item.get("finding_status", item.get("status"))
        status = normalize_status(source_status)
        evidence_ids = [str(entry) for entry in _list(item.get("evidence_ids")) if entry is not None]
        findings.append(
            {
                "requirement_id": requirement_id,
                "module_id": str(item.get("module_id") or "UNRESOLVED"),
                "module": str(item.get("module") or item.get("module_id") or "UNRESOLVED"),
                "priority": str(item.get("priority") or "UNRESOLVED"),
                "source_status": source_status,
                "status": status,
                "evidence_ids": evidence_ids,
                "evidence_count": len(evidence_ids),
                "finding": item.get("finding"),
                "gap_action": item.get("required_action", item.get("gap_action")),
            }
        )

    status_counts = Counter(item["status"] for item in findings)
    return {
        "case_id": case_id,
        "title": title,
        "system_name": system_name,
        "instrument_version": metadata.get("instrument_version"),
        "assessment_version": metadata.get("assessment_version"),
        "evidence_cutoff": metadata.get("evidence_cutoff"),
        "source_path": source_path,
        "requirement_count": len(findings),
        "status_counts": {status: status_counts.get(status, 0) for status in CANONICAL_STATUSES},
        "evidence_object_count": len(evidence),
        "gap_count": len(gaps),
        "open_gap_count": _open_gap_count(gaps),
        "findings": findings,
    }


def _priority_rank(value: str) -> int:
    token = value.upper()
    if token == "P0":
        return 0
    if token == "P1":
        return 1
    if token == "P2":
        return 2
    return 9


def _status_counts(statuses: list[str]) -> dict[str, int]:
    counts = Counter(statuses)
    return {status: counts.get(status, 0) for status in CANONICAL_STATUSES}


def analyze_portfolio(assessments: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute cross-case requirement and module patterns from normalized assessments."""
    if len(assessments) < 2:
        raise ValueError("Portfolio analysis requires at least two assessments")
    case_ids = [str(item.get("case_id") or "") for item in assessments]
    if any(not case_id for case_id in case_ids):
        raise ValueError("Every normalized assessment requires case_id")
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("Portfolio analysis requires unique case_id values")

    by_requirement: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    module_findings: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for assessment in assessments:
        case_id = str(assessment["case_id"])
        for finding in _list(assessment.get("findings")):
            if not isinstance(finding, dict):
                continue
            requirement_id = str(finding.get("requirement_id") or "")
            module_id = str(finding.get("module_id") or "UNRESOLVED")
            by_requirement[requirement_id].append((case_id, finding))
            module_findings[module_id].append((case_id, finding))

    matrix: list[dict[str, Any]] = []
    recurrent_weaknesses: list[dict[str, Any]] = []
    common_strengths: list[dict[str, Any]] = []
    universal_blind_spots: list[dict[str, Any]] = []
    case_outliers: list[dict[str, Any]] = []

    for requirement_id, entries in sorted(by_requirement.items()):
        first = entries[0][1]
        status_by_case = {case_id: str(finding.get("status") or "UNRESOLVED") for case_id, finding in entries}
        statuses = [status_by_case.get(case_id, "MISSING") for case_id in case_ids]
        present_statuses = [status for status in statuses if status != "MISSING"]
        weak_cases = [case_id for case_id in case_ids if status_by_case.get(case_id) in WEAK_STATUSES]
        weakness_score = sum(WEAKNESS_WEIGHTS.get(status_by_case.get(case_id, "UNRESOLVED"), 1) for case_id in case_ids)
        evidence_by_case = {
            case_id: int(finding.get("evidence_count") or 0)
            for case_id, finding in entries
        }
        row = {
            "requirement_id": requirement_id,
            "module_id": first.get("module_id"),
            "module": first.get("module"),
            "priority": first.get("priority"),
            "status_by_case": {case_id: status_by_case.get(case_id, "MISSING") for case_id in case_ids},
            "evidence_count_by_case": {case_id: evidence_by_case.get(case_id, 0) for case_id in case_ids},
            "present_case_count": len(entries),
            "weak_case_count": len(weak_cases),
            "weakness_score": weakness_score,
        }
        matrix.append(row)

        if weak_cases:
            recurrent_weaknesses.append(
                {
                    **row,
                    "weak_cases": weak_cases,
                    "status_counts": _status_counts(present_statuses),
                }
            )
        if len(entries) == len(case_ids) and present_statuses and all(status == "PASS" for status in present_statuses):
            common_strengths.append(row)
        if len(entries) == len(case_ids) and present_statuses and all(status == "NOT_ASSESSED" for status in present_statuses):
            universal_blind_spots.append(row)

        for case_id in case_ids:
            own = status_by_case.get(case_id)
            others = [status_by_case.get(other) for other in case_ids if other != case_id and status_by_case.get(other)]
            if own == "PASS" and others and all(status in WEAK_STATUSES for status in others):
                case_outliers.append(
                    {
                        "case_id": case_id,
                        "requirement_id": requirement_id,
                        "module_id": first.get("module_id"),
                        "priority": first.get("priority"),
                        "status": own,
                        "pattern": "PASS_WHERE_OTHERS_WEAK",
                        "other_statuses": others,
                    }
                )
            elif own == "FAIL" and others and all(status != "FAIL" for status in others):
                case_outliers.append(
                    {
                        "case_id": case_id,
                        "requirement_id": requirement_id,
                        "module_id": first.get("module_id"),
                        "priority": first.get("priority"),
                        "status": own,
                        "pattern": "UNIQUE_FAIL",
                        "other_statuses": others,
                    }
                )

    recurrent_weaknesses.sort(
        key=lambda item: (
            -int(item["weak_case_count"]),
            -int(item["weakness_score"]),
            _priority_rank(str(item.get("priority") or "")),
            str(item["requirement_id"]),
        )
    )
    common_strengths.sort(key=lambda item: (_priority_rank(str(item.get("priority") or "")), str(item["requirement_id"])))
    universal_blind_spots.sort(
        key=lambda item: (_priority_rank(str(item.get("priority") or "")), str(item["requirement_id"]))
    )

    modules: list[dict[str, Any]] = []
    for module_id, entries in sorted(module_findings.items()):
        statuses = [str(finding.get("status") or "UNRESOLVED") for _, finding in entries]
        counts = _status_counts(statuses)
        total = len(statuses)
        weak = sum(counts.get(status, 0) for status in WEAK_STATUSES)
        modules.append(
            {
                "module_id": module_id,
                "module": next((finding.get("module") for _, finding in entries if finding.get("module")), module_id),
                "finding_count": total,
                "status_counts": counts,
                "pass_rate": round(counts["PASS"] / total, 4) if total else 0.0,
                "weak_rate": round(weak / total, 4) if total else 0.0,
            }
        )
    modules.sort(key=lambda item: (-float(item["weak_rate"]), str(item["module_id"])))

    aggregate_statuses: list[str] = []
    for assessment in assessments:
        for finding in _list(assessment.get("findings")):
            if isinstance(finding, dict):
                aggregate_statuses.append(str(finding.get("status") or "UNRESOLVED"))

    cases = [
        {
            key: assessment.get(key)
            for key in (
                "case_id",
                "title",
                "system_name",
                "instrument_version",
                "assessment_version",
                "evidence_cutoff",
                "source_path",
                "requirement_count",
                "status_counts",
                "evidence_object_count",
                "gap_count",
                "open_gap_count",
            )
        }
        for assessment in assessments
    ]

    return {
        "metadata": {
            "title": "NeuroAI cross-case assessment portfolio analysis",
            "case_count": len(cases),
            "requirement_universe_count": len(matrix),
            "read_only": True,
        },
        "cases": cases,
        "portfolio_status_counts": _status_counts(aggregate_statuses),
        "modules": modules,
        "recurrent_weaknesses": recurrent_weaknesses,
        "universal_blind_spots": universal_blind_spots,
        "common_strengths": common_strengths,
        "case_outliers": case_outliers,
        "requirement_matrix": matrix,
    }


def render_portfolio_markdown(analysis: dict[str, Any], *, top: int = 20) -> str:
    metadata = _mapping(analysis.get("metadata"))
    cases = [item for item in _list(analysis.get("cases")) if isinstance(item, dict)]
    weaknesses = [item for item in _list(analysis.get("recurrent_weaknesses")) if isinstance(item, dict)]
    blind_spots = [item for item in _list(analysis.get("universal_blind_spots")) if isinstance(item, dict)]
    strengths = [item for item in _list(analysis.get("common_strengths")) if isinstance(item, dict)]
    modules = [item for item in _list(analysis.get("modules")) if isinstance(item, dict)]

    lines = [
        "# NeuroAI portfolio analysis",
        "",
        f"Cases: {metadata.get('case_count', 0)}  ",
        f"Requirement universe: {metadata.get('requirement_universe_count', 0)}",
        "",
        "## Cases",
        "",
        "| Case | System | PASS | PARTIAL | FAIL | Not assessed | Open gaps | Evidence objects |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for case in cases:
        counts = _mapping(case.get("status_counts"))
        lines.append(
            "| {case} | {system} | {passed} | {partial} | {failed} | {not_assessed} | {gaps} | {evidence} |".format(
                case=case.get("case_id"),
                system=case.get("system_name"),
                passed=counts.get("PASS", 0),
                partial=counts.get("PARTIAL", 0),
                failed=counts.get("FAIL", 0),
                not_assessed=counts.get("NOT_ASSESSED", 0),
                gaps=case.get("open_gap_count", 0),
                evidence=case.get("evidence_object_count", 0),
            )
        )

    lines.extend(["", "## Modules with the highest weak-rate", ""])
    for item in modules[:10]:
        lines.append(
            f"- **{item.get('module_id')}** — weak rate {float(item.get('weak_rate', 0)):.1%}; "
            f"pass rate {float(item.get('pass_rate', 0)):.1%}."
        )

    lines.extend(["", "## Recurrent weak requirements", ""])
    for item in weaknesses[:top]:
        counts = _mapping(item.get("status_counts"))
        lines.append(
            f"- **{item.get('requirement_id')}** ({item.get('module_id')}, {item.get('priority')}): "
            f"weak in {item.get('weak_case_count')}/{metadata.get('case_count')} cases; "
            f"PASS {counts.get('PASS', 0)}, PARTIAL {counts.get('PARTIAL', 0)}, "
            f"FAIL {counts.get('FAIL', 0)}, NOT_ASSESSED {counts.get('NOT_ASSESSED', 0)}."
        )

    lines.extend(["", "## Universal blind spots", ""])
    if blind_spots:
        for item in blind_spots:
            lines.append(f"- **{item.get('requirement_id')}** ({item.get('module_id')}, {item.get('priority')})")
    else:
        lines.append("None detected.")

    lines.extend(["", "## Common strengths", ""])
    if strengths:
        for item in strengths:
            lines.append(f"- **{item.get('requirement_id')}** ({item.get('module_id')}, {item.get('priority')})")
    else:
        lines.append("None detected.")

    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "This is a descriptive comparison of recorded assessment findings. It does not rescore or mutate source assessments.",
            "",
        ]
    )
    return "\n".join(lines)


def write_portfolio_outputs(analysis: dict[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "portfolio-analysis.json"
    csv_path = output_dir / "portfolio-matrix.csv"
    markdown_path = output_dir / "portfolio-summary.md"
    atomic_write_json(json_path, analysis)

    cases = [str(item.get("case_id")) for item in _list(analysis.get("cases")) if isinstance(item, dict)]
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["requirement_id", "module_id", "priority", *cases])
    for item in _list(analysis.get("requirement_matrix")):
        if not isinstance(item, dict):
            continue
        statuses = _mapping(item.get("status_by_case"))
        writer.writerow(
            [
                item.get("requirement_id"),
                item.get("module_id"),
                item.get("priority"),
                *[statuses.get(case_id, "MISSING") for case_id in cases],
            ]
        )
    atomic_write_bytes(csv_path, buffer.getvalue().encode("utf-8"))
    atomic_write_bytes(markdown_path, render_portfolio_markdown(analysis).encode("utf-8"))
    return {
        "analysis": str(json_path),
        "matrix": str(csv_path),
        "summary": str(markdown_path),
    }
