from __future__ import annotations

import json
from pathlib import Path

from neuroai_workbench.monitoring_cli import main
from neuroai_workbench.util import load_json

SAMPLE = Path(__file__).parents[2] / "examples" / "operations" / "SOURCE_MONITOR_REGISTRY_SAMPLE.json"


def test_registry_validate_and_invalid_input(tmp_path: Path) -> None:
    output = tmp_path / "validation.json"
    assert main(["registry-validate", str(SAMPLE), "--out", str(output)]) == 0
    assert load_json(output)["valid"] is True
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{}", encoding="utf-8")
    assert main(["registry-validate", str(invalid)]) == 1


def test_monitoring_cli_lifecycle(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    output = tmp_path / "init.json"
    assert main(["init", str(workspace), str(SAMPLE), "--out", str(output)]) == 0
    assert load_json(output)["source_count"] == 3

    plan = tmp_path / "plan.json"
    assert main(["plan", str(workspace), "--as-of", "2026-12-31", "--out", str(plan)]) == 0
    assert load_json(plan)["counts"]["due"] >= 2

    health_out = tmp_path / "health.json"
    assert main(["source-health", str(workspace), "--as-of", "2026-12-31", "--out", str(health_out)]) == 0
    health = load_json(health_out)
    assert health["counts"]["sources"] == 3
    assert health["counts"]["silent_drop"] == 0

    first_file = tmp_path / "first.txt"
    first_file.write_text("alpha\n", encoding="utf-8")
    first_out = tmp_path / "first.json"
    assert (
        main(
            [
                "snapshot",
                str(workspace),
                "SRC-SAMPLE-001",
                str(first_file),
                "--media-type",
                "text/plain",
                "--retrieved-at",
                "2026-08-02T01:00:00Z",
                "--out",
                str(first_out),
            ]
        )
        == 0
    )
    first = load_json(first_out)

    second_file = tmp_path / "second.txt"
    second_file.write_text("beta\n", encoding="utf-8")
    second_out = tmp_path / "second.json"
    assert (
        main(
            [
                "snapshot",
                str(workspace),
                "SRC-SAMPLE-001",
                str(second_file),
                "--media-type",
                "text/plain",
                "--retrieved-at",
                "2026-08-02T02:00:00Z",
                "--out",
                str(second_out),
            ]
        )
        == 0
    )
    second = load_json(second_out)

    diff = tmp_path / "diff.json"
    assert (
        main(
            [
                "diff",
                str(workspace),
                "SRC-SAMPLE-001",
                first["snapshot_id"],
                second["snapshot_id"],
                "--out",
                str(diff),
            ]
        )
        == 0
    )
    assert load_json(diff)["candidate_required"] is True

    candidate_out = tmp_path / "candidate.json"
    assert (
        main(
            [
                "candidate",
                str(workspace),
                "SRC-SAMPLE-001",
                second["snapshot_id"],
                "--previous-snapshot-id",
                first["snapshot_id"],
                "--out",
                str(candidate_out),
            ]
        )
        == 0
    )
    candidate = load_json(candidate_out)

    adjudication_out = tmp_path / "adjudication.json"
    assert (
        main(
            [
                "adjudicate",
                str(workspace),
                candidate["candidate_id"],
                "ACCEPT",
                "--rationale",
                "Controlling source changed.",
                "--change-class",
                "REGULATORY_OR_MARKET_EVENT",
                "--materiality",
                "MATERIAL",
                "--reopening-effect",
                "REVIEW_REQUIRED",
                "--out",
                str(adjudication_out),
            ]
        )
        == 0
    )
    assert load_json(adjudication_out)["decision"] == "ACCEPT"

    package_out = tmp_path / "package.json"
    assert (
        main(
            [
                "package",
                str(workspace),
                "refresh-2026-08",
                "--evidence-cutoff",
                "2026-08-02",
                "--out",
                str(package_out),
            ]
        )
        == 0
    )
    assert load_json(package_out)["package"]["counts"]["accepted"] == 1

    status_out = tmp_path / "status.json"
    assert main(["status", str(workspace), "--out", str(status_out)]) == 0
    assert load_json(status_out)["adjudication_count"] == 1


def test_cli_failure_is_controlled(tmp_path: Path, capsys) -> None:
    assert main(["status", str(tmp_path / "missing")]) == 2
    assert "Monitoring is not initialized" in capsys.readouterr().err


def test_cli_stdout_output(capsys) -> None:
    assert main(["registry-validate", str(SAMPLE)]) == 0
    value = json.loads(capsys.readouterr().out)
    assert value["valid"] is True
