from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from neuroai_workbench import refresh_cli
from neuroai_workbench.shadow_refresh import LIVE_COLLECTION_ENV
from neuroai_workbench.util import atomic_write_json


def _package(tmp_path: Path) -> dict[str, Any]:
    output = tmp_path / "out"
    return {
        "metadata": {"mode": "live", "executed_at": "2026-08-07T20:00:00Z"},
        "status": "SHADOW_EVALUATION_NOT_CANONICAL",
        "source_outcomes": [
            {"source_id": "SRC-1", "outcome_type": "NO_CHANGE"},
            {"source_id": "SRC-2", "outcome_type": "CONTENT_CHANGED"},
            {"source_id": "SRC-3", "outcome_type": "HTTP_ERROR_UNCLASSIFIED"},
        ],
        "stats": {
            "retrieval": {
                "outcome_count": 3,
                "by_type": {
                    "NO_CHANGE": 1,
                    "CONTENT_CHANGED": 1,
                    "HTTP_ERROR_UNCLASSIFIED": 1,
                },
            }
        },
        "stage_results": {
            "collect": {"capture_digest_count": 2},
            "record_snapshot": {"count": 2},
            "create_change_candidate": {
                "count": 1,
                "candidates": [{"candidate_id": "C-1", "source_id": "SRC-2"}],
            },
            "reopening_analysis": {"recommendation_count": 1},
            "apply_delta": {
                "successor_path": str(output / "apply" / "candidate-successor.json"),
                "status": "CANDIDATE_SUCCESSOR_NOT_CANONICAL",
                "predecessor_unchanged": True,
            },
            "publications": {
                "path": str(output / "publications"),
                "products": {
                    "xlsx": str(output / "publications" / "analytical-workbook.xlsx"),
                    "html": str(output / "publications" / "dashboard.html"),
                },
                "reconciled": True,
            },
        },
        "report_path": str(output / "evaluation-cycle-report.json"),
        "assessment_mutation_performed": False,
        "canonical_successor_written": False,
    }


def test_build_update_summary_prioritizes_research_actions(tmp_path: Path) -> None:
    summary = refresh_cli.build_update_summary(_package(tmp_path))

    assert summary["sources"]["stable_count"] == 1
    assert summary["sources"]["changed_count"] == 1
    assert summary["sources"]["attention_count"] == 1
    assert summary["sources"]["changed_source_ids"] == ["SRC-2"]
    assert summary["sources"]["attention_source_ids"] == ["SRC-3"]
    assert summary["changes"]["candidate_count"] == 1
    assert summary["changes"]["assessment_impact_recommendations"] == 1
    assert summary["changes"]["assessment_mutation_performed"] is False
    assert summary["outputs"]["reconciled"] is True
    assert any("SRC-3" in item for item in summary["next_actions"])
    assert any("SRC-2" in item for item in summary["next_actions"])

    rendered = refresh_cli.render_update_summary(summary)
    assert "3 checked | 1 changed | 1 need attention" in rendered
    assert "Candidate successor:" in rendered
    assert "Generated: html, xlsx" in rendered


def test_summary_tells_operator_when_fresh_captures_need_handoff(tmp_path: Path) -> None:
    package = _package(tmp_path)
    package["stage_results"]["record_snapshot"]["count"] = 0
    summary = refresh_cli.build_update_summary(package)
    assert "Approve the successful captures" in summary["next_actions"][0]


def test_main_runs_live_cycle_with_small_team_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ops = tmp_path / "ops"
    registry = ops / "01_CONFIG" / "source_monitor_registry_v1.5.json"
    registry.parent.mkdir(parents=True)
    atomic_write_json(registry, {"sources": []})
    predecessor = tmp_path / "predecessor.json"
    atomic_write_json(predecessor, {"metadata": {"version": "v2.2"}})
    captured: dict[str, Any] = {}

    def fake_cycle(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return _package(tmp_path)

    monkeypatch.setattr(refresh_cli, "run_live_evaluation_cycle", fake_cycle)
    monkeypatch.setattr(refresh_cli, "utc_now", lambda: "2026-08-07T20:01:02Z")
    monkeypatch.delenv(LIVE_COLLECTION_ENV, raising=False)

    result = refresh_cli.main(
        [
            "--ops-workspace",
            str(ops),
            "--predecessor",
            str(predecessor),
            "--output-dir",
            str(tmp_path / "run-output"),
        ]
    )

    assert result == 0
    assert os.environ[LIVE_COLLECTION_ENV] == "1"
    assert captured["registry_path"] == registry.resolve()
    assert captured["predecessor_path"] == predecessor.resolve()
    assert captured["sample_size"] == 25
    assert captured["refresh_version"] == "v2.3.0-dev"
    assert captured["evidence_cutoff"] == "2026-08-07"
    assert captured["approve_handoff"] is True
    assert captured["as_of"] == "2026-08-07"
    assert captured["apply_id"] == "apply-v23dev-20260807t200102z"
    assert (tmp_path / "run-output" / "UPDATE_SUMMARY.json").is_file()
    assert "NeuroAI refresh complete" in capsys.readouterr().out


def test_main_json_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    ops = tmp_path / "ops"
    registry = ops / "01_CONFIG" / "source_monitor_registry_v1.5.json"
    registry.parent.mkdir(parents=True)
    atomic_write_json(registry, {"sources": []})
    predecessor = tmp_path / "predecessor.json"
    atomic_write_json(predecessor, {"metadata": {"version": "v2.2"}})
    monkeypatch.setattr(refresh_cli, "run_live_evaluation_cycle", lambda **kwargs: _package(tmp_path))

    assert (
        refresh_cli.main(
            [
                "--ops-workspace",
                str(ops),
                "--predecessor",
                str(predecessor),
                "--output-dir",
                str(tmp_path / "out-json"),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["sources"]["changed_source_ids"] == ["SRC-2"]


def test_main_fails_fast_on_missing_inputs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "missing.json"
    result = refresh_cli.main(["--predecessor", str(missing)])
    assert result == 2
    assert "NEUROAI_OPS_WORKSPACE" in capsys.readouterr().err
