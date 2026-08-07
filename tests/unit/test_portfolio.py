from __future__ import annotations

import copy
import csv
import json
from pathlib import Path
from typing import Any

import pytest

from neuroai_workbench import portfolio_cli
from neuroai_workbench.portfolio import (
    analyze_portfolio,
    normalize_assessment,
    normalize_status,
    render_portfolio_markdown,
    write_portfolio_outputs,
)


def _legacy(case_id: str, statuses: dict[str, str]) -> dict[str, Any]:
    return {
        "assessment_metadata": {
            "assessment_id": case_id,
            "title": f"{case_id} assessment",
            "instrument_version": "4.1.5",
            "evidence_cutoff": "2026-07-01",
        },
        "system_profile": {"system_name": f"System {case_id}"},
        "evidence_register": [{"evidence_id": "E-1"}, {"evidence_id": "E-2"}],
        "requirement_findings": [
            {
                "requirement_id": requirement_id,
                "module_id": requirement_id.split("-R")[0],
                "priority": "P0" if requirement_id.endswith("R01") else "P1",
                "finding_status": status,
                "evidence_ids": ["E-1"] if status == "PASS" else [],
                "finding": f"Finding for {requirement_id}",
            }
            for requirement_id, status in statuses.items()
        ],
        "gap_register": [
            {"gap_id": "G-1", "state": "OPEN"},
            {"gap_id": "G-2", "state": "RESOLVED"},
        ],
    }


def _current(case_id: str, statuses: dict[str, str]) -> dict[str, Any]:
    return {
        "metadata": {
            "assessment_id": case_id,
            "title": f"{case_id} current assessment",
            "instrument_version": "4.2",
            "assessment_version": "4.2.1",
            "evidence_cutoff": "2026-07-30",
        },
        "system": {"system_name": f"Current {case_id}"},
        "evidence_register": [{"evidence_id": "E-9"}],
        "requirement_findings": [
            {
                "requirement_id": requirement_id,
                "module_id": requirement_id.split("-R")[0],
                "module": f"Module {requirement_id.split('-R')[0]}",
                "priority": "P0" if requirement_id.endswith("R01") else "P1",
                "status": status,
                "evidence_ids": ["E-9"] if status == "PASS" else [],
                "gap_action": "Collect more evidence" if status != "PASS" else None,
            }
            for requirement_id, status in statuses.items()
        ],
        "gaps_and_requests": [{"gap_id": "G-9", "state": "OPEN"}],
    }


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("PASS", "PASS"),
        ("passed", "PASS"),
        ("PARTIALLY MET", "PARTIAL"),
        ("fail", "FAIL"),
        ("NOT ASSESSED", "NOT_ASSESSED"),
        ("not_assessed", "NOT_ASSESSED"),
        ("N/A", "NOT_APPLICABLE"),
        ("unknown", "UNRESOLVED"),
        (None, "UNRESOLVED"),
    ],
)
def test_normalize_status(raw: Any, expected: str) -> None:
    assert normalize_status(raw) == expected


def test_normalize_assessment_supports_legacy_without_mutation() -> None:
    raw = _legacy("LEGACY-1", {"NK-01-R01": "PASS", "NK-01-R02": "NOT ASSESSED"})
    before = copy.deepcopy(raw)
    normalized = normalize_assessment(raw, source_path="legacy.json")

    assert raw == before
    assert normalized["case_id"] == "LEGACY-1"
    assert normalized["system_name"] == "System LEGACY-1"
    assert normalized["status_counts"]["PASS"] == 1
    assert normalized["status_counts"]["NOT_ASSESSED"] == 1
    assert normalized["evidence_object_count"] == 2
    assert normalized["gap_count"] == 2
    assert normalized["open_gap_count"] == 1
    assert normalized["findings"][0]["source_status"] == "PASS"


def test_normalize_assessment_supports_current_prima_shape() -> None:
    normalized = normalize_assessment(
        _current("CURRENT-1", {"NK-03-R01": "PASS", "NK-08-R02": "PARTIAL"}),
        source_path="prima.json",
    )
    assert normalized["assessment_version"] == "4.2.1"
    assert normalized["system_name"] == "Current CURRENT-1"
    assert normalized["gap_count"] == 1
    assert normalized["findings"][1]["module"] == "Module NK-08"


def test_normalize_assessment_rejects_bad_and_duplicate_findings() -> None:
    with pytest.raises(ValueError, match="no requirement_findings"):
        normalize_assessment({"assessment_metadata": {"assessment_id": "X"}})
    raw = _legacy("DUP", {"NK-01-R01": "PASS"})
    raw["requirement_findings"].append(dict(raw["requirement_findings"][0]))
    with pytest.raises(ValueError, match="Duplicate requirement_id"):
        normalize_assessment(raw)


def _analysis() -> dict[str, Any]:
    cases = [
        normalize_assessment(
            _legacy(
                "A",
                {
                    "NK-01-R01": "PASS",
                    "NK-02-R01": "NOT ASSESSED",
                    "NK-03-R01": "PARTIAL",
                    "NK-04-R01": "FAIL",
                    "NK-05-R01": "PASS",
                },
            )
        ),
        normalize_assessment(
            _legacy(
                "B",
                {
                    "NK-01-R01": "PASS",
                    "NK-02-R01": "NOT ASSESSED",
                    "NK-03-R01": "PARTIAL",
                    "NK-04-R01": "PARTIAL",
                    "NK-05-R01": "PARTIAL",
                },
            )
        ),
        normalize_assessment(
            _current(
                "C",
                {
                    "NK-01-R01": "PASS",
                    "NK-02-R01": "NOT ASSESSED",
                    "NK-03-R01": "NOT ASSESSED",
                    "NK-04-R01": "PARTIAL",
                    "NK-05-R01": "PARTIAL",
                },
            )
        ),
    ]
    return analyze_portfolio(cases)


def test_analyze_portfolio_surfaces_recurrent_patterns() -> None:
    analysis = _analysis()

    assert analysis["metadata"]["case_count"] == 3
    assert analysis["metadata"]["requirement_universe_count"] == 5
    assert [item["requirement_id"] for item in analysis["common_strengths"]] == ["NK-01-R01"]
    assert [item["requirement_id"] for item in analysis["universal_blind_spots"]] == ["NK-02-R01"]

    weakness_ids = [item["requirement_id"] for item in analysis["recurrent_weaknesses"]]
    assert weakness_ids[0] == "NK-04-R01"
    nk04 = next(item for item in analysis["recurrent_weaknesses"] if item["requirement_id"] == "NK-04-R01")
    assert nk04["weak_case_count"] == 3
    assert nk04["weakness_score"] == 8
    assert nk04["status_counts"]["FAIL"] == 1
    assert any(item["pattern"] == "UNIQUE_FAIL" and item["case_id"] == "A" for item in analysis["case_outliers"])
    assert any(
        item["pattern"] == "PASS_WHERE_OTHERS_WEAK" and item["case_id"] == "A" and item["requirement_id"] == "NK-05-R01"
        for item in analysis["case_outliers"]
    )
    assert analysis["modules"][0]["weak_rate"] == 1.0


def test_analyze_portfolio_rejects_single_or_duplicate_cases() -> None:
    one = normalize_assessment(_legacy("A", {"NK-01-R01": "PASS"}))
    with pytest.raises(ValueError, match="at least two"):
        analyze_portfolio([one])
    with pytest.raises(ValueError, match="unique case_id"):
        analyze_portfolio([one, copy.deepcopy(one)])


def test_render_and_write_outputs(tmp_path: Path) -> None:
    analysis = _analysis()
    markdown = render_portfolio_markdown(analysis)
    assert "# NeuroAI portfolio analysis" in markdown
    assert "Universal blind spots" in markdown
    assert "NK-02-R01" in markdown

    outputs = write_portfolio_outputs(analysis, tmp_path / "portfolio")
    assert Path(outputs["analysis"]).is_file()
    assert Path(outputs["matrix"]).is_file()
    assert Path(outputs["summary"]).is_file()

    with Path(outputs["matrix"]).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == ["requirement_id", "module_id", "priority", "A", "B", "C"]
    nk02 = next(row for row in rows if row[0] == "NK-02-R01")
    assert nk02[3:] == ["NOT_ASSESSED", "NOT_ASSESSED", "NOT_ASSESSED"]


def test_portfolio_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(json.dumps(_legacy("A", {"NK-01-R01": "PASS", "NK-02-R01": "NOT ASSESSED"})), encoding="utf-8")
    b.write_text(json.dumps(_current("B", {"NK-01-R01": "PASS", "NK-02-R01": "PARTIAL"})), encoding="utf-8")
    output = tmp_path / "out"

    assert portfolio_cli.main([str(a), str(b), "--output-dir", str(output)]) == 0
    stdout = capsys.readouterr().out
    assert "Portfolio: 2 cases" in stdout
    assert "Top recurrent weakness: NK-02-R01" in stdout
    assert (output / "portfolio-analysis.json").is_file()
    assert (output / "portfolio-matrix.csv").is_file()
    assert (output / "portfolio-summary.md").is_file()


def test_portfolio_cli_fails_fast_for_missing_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "missing.json"
    assert portfolio_cli.main([str(missing), str(missing)]) == 2
    assert "Assessment not found" in capsys.readouterr().err
