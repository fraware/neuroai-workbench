from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from neuroai_workbench.portfolio import analyze_portfolio
from neuroai_workbench.research_agenda import (
    build_research_agenda,
    render_research_agenda_markdown,
    write_research_agenda_outputs,
)


def _assessment(case_id: str, findings: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "title": case_id,
        "system_name": case_id,
        "status_counts": {},
        "requirement_count": len(findings),
        "evidence_object_count": 0,
        "gap_count": 0,
        "open_gap_count": 0,
        "findings": findings,
    }


def _finding(
    requirement_id: str,
    *,
    priority: str,
    status: str,
    evidence_count: int,
    action: str | None = None,
) -> dict[str, Any]:
    return {
        "requirement_id": requirement_id,
        "module_id": requirement_id.split("-R")[0],
        "module": requirement_id.split("-R")[0],
        "priority": priority,
        "status": status,
        "source_status": status,
        "evidence_count": evidence_count,
        "evidence_ids": [f"E-{index}" for index in range(evidence_count)],
        "gap_action": action,
    }


def _agenda() -> list[dict[str, Any]]:
    assessments = [
        _assessment(
            "A",
            [
                _finding("NK-08-R02", priority="P0", status="NOT_ASSESSED", evidence_count=0, action="Find source A."),
                _finding("NK-07-R01", priority="P0", status="FAIL", evidence_count=1, action="Resolve failure."),
                _finding("NK-05-R01", priority="P1", status="PARTIAL", evidence_count=0, action="Add evidence."),
            ],
        ),
        _assessment(
            "B",
            [
                _finding("NK-08-R02", priority="P0", status="NOT_ASSESSED", evidence_count=0, action="Find source B."),
                _finding("NK-07-R01", priority="P0", status="PARTIAL", evidence_count=2),
                _finding("NK-05-R01", priority="P1", status="PARTIAL", evidence_count=1),
            ],
        ),
    ]
    return build_research_agenda(assessments, analyze_portfolio(assessments))


def test_agenda_prioritizes_p0_universal_blind_spot() -> None:
    agenda = _agenda()
    assert agenda[0]["requirement_id"] == "NK-08-R02"
    assert agenda[0]["rank"] == 1
    assert agenda[0]["urgency"] == "NOW"
    assert agenda[0]["recommended_focus"] == "ESTABLISH_BASELINE_EVIDENCE"
    assert agenda[0]["universal_blind_spot"] is True
    assert agenda[0]["zero_evidence_case_ids"] == ["A", "B"]
    assert agenda[0]["recorded_gap_actions"] == [
        {"case_id": "A", "action": "Find source A."},
        {"case_id": "B", "action": "Find source B."},
    ]


def test_agenda_focuses_failures_and_partial_evidence() -> None:
    agenda = _agenda()
    failure = next(item for item in agenda if item["requirement_id"] == "NK-07-R01")
    partial = next(item for item in agenda if item["requirement_id"] == "NK-05-R01")
    assert failure["recommended_focus"] == "RESOLVE_NEGATIVE_OR_CONTRADICTORY_EVIDENCE"
    assert failure["urgency"] == "NOW"
    assert partial["recommended_focus"] == "EXPAND_DIRECT_EVIDENCE"
    assert partial["urgency"] == "HIGH"


def test_agenda_skips_common_strengths() -> None:
    assessments = [
        _assessment("A", [_finding("NK-03-R03", priority="P0", status="PASS", evidence_count=1)]),
        _assessment("B", [_finding("NK-03-R03", priority="P0", status="PASS", evidence_count=2)]),
    ]
    assert build_research_agenda(assessments, analyze_portfolio(assessments)) == []


def test_research_agenda_outputs(tmp_path: Path) -> None:
    agenda = _agenda()
    markdown = render_research_agenda_markdown(agenda)
    assert "# NeuroAI evidence collection priorities" in markdown
    assert "NK-08-R02" in markdown
    assert "Find source A." in markdown

    outputs = write_research_agenda_outputs(agenda, tmp_path)
    assert Path(outputs["json"]).is_file()
    assert Path(outputs["csv"]).is_file()
    assert Path(outputs["markdown"]).is_file()
    with Path(outputs["csv"]).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[0][0:4] == ["rank", "requirement_id", "module_id", "priority"]
    assert rows[1][1] == "NK-08-R02"
