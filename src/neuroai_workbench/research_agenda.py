"""Turn cross-case assessment patterns into a lightweight research priority queue."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from .util import atomic_write_bytes, atomic_write_json


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _priority_rank(priority: Any) -> int:
    return {"P0": 0, "P1": 1, "P2": 2}.get(str(priority or "").upper(), 9)


def _finding_index(assessments: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    index: dict[str, dict[str, dict[str, Any]]] = {}
    for assessment in assessments:
        case_id = str(assessment.get("case_id") or "")
        if not case_id:
            continue
        for finding in _list(assessment.get("findings")):
            if not isinstance(finding, dict):
                continue
            requirement_id = str(finding.get("requirement_id") or "")
            if requirement_id:
                index.setdefault(requirement_id, {})[case_id] = finding
    return index


def _focus(statuses: list[str], zero_evidence_cases: int) -> str:
    present = [status for status in statuses if status != "MISSING"]
    if present and all(status == "NOT_ASSESSED" for status in present):
        return "ESTABLISH_BASELINE_EVIDENCE"
    if "FAIL" in present:
        return "RESOLVE_NEGATIVE_OR_CONTRADICTORY_EVIDENCE"
    if zero_evidence_cases:
        return "EXPAND_DIRECT_EVIDENCE"
    return "CLOSE_PARTIAL_EVIDENCE"


def build_research_agenda(
    assessments: list[dict[str, Any]],
    analysis: dict[str, Any],
) -> list[dict[str, Any]]:
    """Rank evidence work without inventing a scalar conformance score.

    Ordering is lexicographic and intentionally transparent: P0 before P1/P2,
    universal blind spots first within a priority, then recurrence, missing direct
    evidence, recorded weakness severity, and requirement ID for stability.
    """
    cases = [str(item.get("case_id")) for item in _list(analysis.get("cases")) if isinstance(item, dict)]
    findings = _finding_index(assessments)
    agenda: list[dict[str, Any]] = []

    for row in _list(analysis.get("requirement_matrix")):
        if not isinstance(row, dict) or int(row.get("weak_case_count") or 0) <= 0:
            continue
        requirement_id = str(row.get("requirement_id") or "")
        statuses = _mapping(row.get("status_by_case"))
        evidence = _mapping(row.get("evidence_count_by_case"))
        status_values = [str(statuses.get(case_id, "MISSING")) for case_id in cases]
        universal_blind_spot = bool(status_values) and all(status == "NOT_ASSESSED" for status in status_values)
        zero_evidence_case_ids = [case_id for case_id in cases if int(evidence.get(case_id) or 0) == 0]

        recorded_actions: list[dict[str, str]] = []
        for case_id in cases:
            finding = findings.get(requirement_id, {}).get(case_id)
            if not finding:
                continue
            action = finding.get("gap_action")
            if isinstance(action, str) and action.strip():
                recorded_actions.append({"case_id": case_id, "action": action.strip()})

        priority = str(row.get("priority") or "UNRESOLVED")
        weak_case_count = int(row.get("weak_case_count") or 0)
        if priority.upper() == "P0" and (universal_blind_spot or weak_case_count == len(cases)):
            urgency = "NOW"
        elif priority.upper() == "P0" or (priority.upper() == "P1" and weak_case_count == len(cases)):
            urgency = "HIGH"
        else:
            urgency = "NORMAL"

        agenda.append(
            {
                "requirement_id": requirement_id,
                "module_id": row.get("module_id"),
                "module": row.get("module"),
                "priority": priority,
                "urgency": urgency,
                "recommended_focus": _focus(status_values, len(zero_evidence_case_ids)),
                "universal_blind_spot": universal_blind_spot,
                "weak_case_count": weak_case_count,
                "case_count": len(cases),
                "zero_evidence_case_count": len(zero_evidence_case_ids),
                "zero_evidence_case_ids": zero_evidence_case_ids,
                "weakness_score": int(row.get("weakness_score") or 0),
                "status_by_case": {case_id: statuses.get(case_id, "MISSING") for case_id in cases},
                "evidence_count_by_case": {case_id: int(evidence.get(case_id) or 0) for case_id in cases},
                "recorded_gap_actions": recorded_actions,
            }
        )

    agenda.sort(
        key=lambda item: (
            _priority_rank(item.get("priority")),
            not bool(item.get("universal_blind_spot")),
            -int(item.get("weak_case_count") or 0),
            -int(item.get("zero_evidence_case_count") or 0),
            -int(item.get("weakness_score") or 0),
            str(item.get("requirement_id") or ""),
        )
    )
    for rank, item in enumerate(agenda, start=1):
        item["rank"] = rank
    return agenda


def render_research_agenda_markdown(agenda: list[dict[str, Any]], *, top: int = 25) -> str:
    lines = [
        "# NeuroAI evidence collection priorities",
        "",
        "This queue turns recorded cross-case assessment gaps into a practical research agenda. It is not a system score.",
        "",
        "| Rank | Requirement | Module | Priority | Urgency | Focus | Weak cases | Zero-evidence cases |",
        "| ---: | --- | --- | --- | --- | --- | ---: | ---: |",
    ]
    for item in agenda[:top]:
        lines.append(
            f"| {item.get('rank')} | {item.get('requirement_id')} | {item.get('module_id')} | "
            f"{item.get('priority')} | {item.get('urgency')} | {item.get('recommended_focus')} | "
            f"{item.get('weak_case_count')}/{item.get('case_count')} | {item.get('zero_evidence_case_count')} |"
        )
        actions = _list(item.get("recorded_gap_actions"))
        if actions:
            lines.append("")
            lines.append(f"**Recorded actions for {item.get('requirement_id')}:**")
            for action in actions:
                if isinstance(action, dict):
                    lines.append(f"- {action.get('case_id')}: {action.get('action')}")
            lines.append("")
    lines.extend(
        [
            "",
            "Ordering rule: requirement priority, universal blind-spot status, cross-case recurrence, zero-evidence cases, recorded weakness severity, then requirement ID.",
            "",
        ]
    )
    return "\n".join(lines)


def write_research_agenda_outputs(agenda: list[dict[str, Any]], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "evidence-priorities.json"
    csv_path = output_dir / "evidence-priorities.csv"
    markdown_path = output_dir / "evidence-priorities.md"
    atomic_write_json(json_path, {"priorities": agenda, "count": len(agenda)})

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "rank",
            "requirement_id",
            "module_id",
            "priority",
            "urgency",
            "recommended_focus",
            "weak_case_count",
            "case_count",
            "zero_evidence_case_count",
            "zero_evidence_case_ids",
        ]
    )
    for item in agenda:
        writer.writerow(
            [
                item.get("rank"),
                item.get("requirement_id"),
                item.get("module_id"),
                item.get("priority"),
                item.get("urgency"),
                item.get("recommended_focus"),
                item.get("weak_case_count"),
                item.get("case_count"),
                item.get("zero_evidence_case_count"),
                ";".join(str(value) for value in _list(item.get("zero_evidence_case_ids"))),
            ]
        )
    atomic_write_bytes(csv_path, buffer.getvalue().encode("utf-8"))
    atomic_write_bytes(markdown_path, render_research_agenda_markdown(agenda).encode("utf-8"))
    return {"json": str(json_path), "csv": str(csv_path), "markdown": str(markdown_path)}
