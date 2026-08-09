from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from neuroai_workbench import data_cli


def _assessment() -> dict[str, Any]:
    return {
        "assessment_metadata": {"assessment_id": "CLI-ASSESSMENT", "title": "CLI assessment"},
        "system_profile": {"system_name": "CLI System"},
        "evidence_register": [
            {"evidence_id": "EV-1", "title": "Exact URL", "url_or_path": "https://example.org/source"},
            {"evidence_id": "EV-2", "title": "Outside", "url_or_path": "https://outside.example/source"},
        ],
        "requirement_findings": [
            {"requirement_id": "NK-01-R01", "finding_status": "PASS", "evidence_ids": ["EV-1"]},
            {"requirement_id": "NK-01-R02", "finding_status": "PARTIAL", "evidence_ids": ["EV-2"]},
        ],
    }


def test_crosswalk_cli_accepts_composed_json_and_jsonl_source_universe(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps({"sources": [{"source_id": "SRC-1", "title": "Exact", "url": "https://example.org/source/"}]}),
        encoding="utf-8",
    )
    supplemental = tmp_path / "supplemental.jsonl"
    supplemental.write_text(
        json.dumps({"source_id": "SRC-2", "title": "Supplemental", "url": "https://example.org/second"}) + "\n",
        encoding="utf-8",
    )
    assessment = tmp_path / "assessment.json"
    assessment.write_text(json.dumps(_assessment()), encoding="utf-8")
    output = tmp_path / "out"

    assert (
        data_cli.main(
            [
                "crosswalk",
                "--source-universe",
                str(baseline),
                "--source-universe",
                str(supplemental),
                "--assessment",
                str(assessment),
                "--output-dir",
                str(output),
            ]
        )
        == 0
    )
    stdout = capsys.readouterr().out
    assert "Evidence crosswalk: 2 current sources" in stdout
    assert "Matched: 1" in stdout
    assert "unresolved: 1" in stdout
    assert "registration candidates: 1" in stdout
    assert (output / "evidence-crosswalk.json").is_file()
    assert (output / "evidence-crosswalk.csv").is_file()
    assert (output / "evidence-crosswalk.md").is_file()


def test_crosswalk_cli_json_mode_prints_complete_payload(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "source.json"
    source.write_text(json.dumps([{"source_id": "SRC-1", "url": "https://example.org/source"}]), encoding="utf-8")
    assessment = tmp_path / "assessment.json"
    assessment.write_text(json.dumps(_assessment()), encoding="utf-8")

    assert (
        data_cli.main(
            [
                "crosswalk",
                "--source-universe",
                str(source),
                "--assessment",
                str(assessment),
                "--output-dir",
                str(tmp_path / "out"),
                "--json",
            ]
        )
        == 0
    )
    stdout = capsys.readouterr().out
    assert '"crosswalk_state": "EXACT_URL"' in stdout
    assert '"source_registration_candidate": true' in stdout


def test_crosswalk_cli_rejects_invalid_jsonl(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "bad.jsonl"
    source.write_text('{"source_id":"SRC-1"}\nnot-json\n', encoding="utf-8")
    assessment = tmp_path / "assessment.json"
    assessment.write_text(json.dumps(_assessment()), encoding="utf-8")
    assert (
        data_cli.main(
            [
                "crosswalk",
                "--source-universe",
                str(source),
                "--assessment",
                str(assessment),
            ]
        )
        == 2
    )
    assert "Invalid JSONL" in capsys.readouterr().err


def test_crosswalk_cli_rejects_missing_source_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assessment = tmp_path / "assessment.json"
    assessment.write_text(json.dumps(_assessment()), encoding="utf-8")
    assert (
        data_cli.main(
            [
                "crosswalk",
                "--source-universe",
                str(tmp_path / "missing.json"),
                "--assessment",
                str(assessment),
            ]
        )
        == 2
    )
    assert "Input not found" in capsys.readouterr().err
