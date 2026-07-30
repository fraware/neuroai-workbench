from __future__ import annotations

import json
from pathlib import Path

from neuroai_workbench.reports import render_assessment_markdown, write_assessment_markdown

REPO = Path(__file__).resolve().parents[2]
EXAMPLE = REPO / "examples" / "assessments" / "PRIMA_Controlled_Assessment_v4.2.1.native.json"


def test_report_is_deterministic_and_bounded(tmp_path: Path) -> None:
    assessment = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    first = render_assessment_markdown(assessment)
    second = render_assessment_markdown(assessment)
    assert first == second
    assert "# PRIMA Controlled Public-Evidence Assessment" in first
    assert "CL-4" in first
    assert "do not establish evidentiary truth" in first
    assert "NK-01-R01" in first
    assert "GAP-PR-001" in first

    output = tmp_path / "report.md"
    result = write_assessment_markdown(assessment, output)
    assert output.read_text(encoding="utf-8") == first
    assert result["bytes"] == len(first.encode("utf-8"))
    assert len(result["sha256"]) == 64


def test_gap_report_is_deterministic_and_bounded() -> None:
    from neuroai_workbench.reports import render_gap_markdown

    assessment = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    first = render_gap_markdown(assessment)
    second = render_gap_markdown(assessment)
    assert first == second
    assert "Evidence-gap and closure-request report" in first
    assert "creates no disclosure duty" in first
    assert assessment["gap_register"][0]["gap_id"] in first
