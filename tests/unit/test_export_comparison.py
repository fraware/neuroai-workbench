from __future__ import annotations

import json
import zipfile
from pathlib import Path

from neuroai_workbench.comparison import compare_assessments
from neuroai_workbench.exporter import export_case_bundle


def test_export_controlled_bundle(workspace, tmp_path: Path):
    workspace.create_case("CASE-001", "Example case")
    output = tmp_path / "case.zip"
    result = export_case_bundle(workspace, "CASE-001", output)
    assert result["validation_valid"]
    assert result["event_chain_valid"]
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
    assert "CASE-001/assessment.json" in names
    assert "CASE-001/exports/bundle-manifest.json" in names


def test_three_pilot_comparison_has_expected_common_controls():
    root = Path(__file__).resolve().parents[2] / "examples" / "assessments"
    paths = sorted(root.glob("*.json"))
    cases = [(path.stem, json.loads(path.read_text(encoding="utf-8"))) for path in paths]
    report = compare_assessments(cases)
    assert report["case_count"] == 3
    assert report["common_pass"] == ["NK-01-R03", "NK-01-R04", "NK-03-R03", "NK-03-R06"]
    assert set(report["universal_p0_evidence_voids"]) == {
        "NK-05-R03",
        "NK-06-R03",
        "NK-08-R02",
        "NK-08-R04",
        "NK-09-R03",
        "NK-09-R04",
    }
