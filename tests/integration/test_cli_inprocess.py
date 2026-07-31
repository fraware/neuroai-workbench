from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench import cli


def parse_stdout(capsys):
    return json.loads(capsys.readouterr().out)


def test_cli_inprocess_full_lifecycle(tmp_path: Path, capsys):
    workspace = tmp_path / "workspace"
    assert cli.main(["init", str(workspace), "--name", "In-process workspace"]) == 0
    assert parse_stdout(capsys)["metadata"]["workbench_version"] == "0.3.0.dev0"

    assert cli.main(["doctor", "--workspace", str(workspace)]) == 0
    assert parse_stdout(capsys)["cases"] == []

    assert cli.main(["case-create", str(workspace), "CASE-001", "--title", "Case one"]) == 0
    created = parse_stdout(capsys)
    assert created["assessment_metadata"]["assessment_id"] == "CASE-001"

    list_out = tmp_path / "cases.json"
    assert cli.main(["case-list", str(workspace), "--out", str(list_out)]) == 0
    assert json.loads(list_out.read_text(encoding="utf-8"))["cases"][0]["case_id"] == "CASE-001"

    show_out = tmp_path / "show.json"
    assert cli.main(["case-show", str(workspace), "CASE-001", "--out", str(show_out)]) == 0
    assessment = json.loads(show_out.read_text(encoding="utf-8"))
    assessment["assessment_metadata"]["assessment_purpose"] = "In-process test"
    replacement = tmp_path / "replacement.json"
    replacement.write_text(json.dumps(assessment), encoding="utf-8")
    assert cli.main(["case-save", str(workspace), "CASE-001", str(replacement), "--require-valid"]) == 0
    assert parse_stdout(capsys)["valid"] is True

    assert cli.main(["validate", "--workspace", str(workspace), "--case-id", "CASE-001"]) == 0
    assert parse_stdout(capsys)["valid"] is True
    assert cli.main(["summary", "--workspace", str(workspace), "--case-id", "CASE-001"]) == 0
    assert parse_stdout(capsys)["counts"]["requirements"] == 78

    assert cli.main(["snapshot", str(workspace), "CASE-001", "--label", "freeze"]) == 0
    assert parse_stdout(capsys)["assessment_sha256"]

    evidence_file = tmp_path / "evidence.txt"
    evidence_file.write_text("controlled bytes\n")
    assert (
        cli.main(
            [
                "evidence-add",
                str(workspace),
                "CASE-001",
                str(evidence_file),
                "--title",
                "Evidence",
                "--type",
                "OTHER",
                "--source",
                "TEST",
            ]
        )
        == 0
    )
    evidence = parse_stdout(capsys)
    assert evidence["evidence_id"] == "EV-001"

    assert cli.main(["evidence-verify", str(workspace), "CASE-001"]) == 0
    assert parse_stdout(capsys)["valid"] is True
    assert cli.main(["events-verify", str(workspace), "CASE-001"]) == 0
    assert parse_stdout(capsys)["valid"] is True

    bundle = tmp_path / "case.zip"
    assert cli.main(["bundle", str(workspace), "CASE-001", str(bundle)]) == 0
    assert parse_stdout(capsys)["event_chain_valid"] is True
    assert bundle.is_file()


def test_cli_import_migrate_compare_and_observatory(tmp_path: Path, capsys):
    repo = Path(__file__).resolve().parents[2]
    examples = repo / "examples" / "assessments"
    workspace = tmp_path / "workspace"
    assert cli.main(["init", str(workspace)]) == 0
    capsys.readouterr()

    example = examples / "PILOT-02_FDA_Adaptive_DBS_v4.2.json"
    assert cli.main(["case-import", str(workspace), str(example)]) == 0
    assert parse_stdout(capsys)["assessment_metadata"]["assessment_id"]

    source = repo / "tests" / "fixtures" / "PILOT-02_v4.1.2.json"
    migrated = tmp_path / "migrated.json"
    assert cli.main(["migrate", str(source), str(migrated)]) == 0
    assert parse_stdout(capsys)["sha256"]

    compare_out = tmp_path / "compare.json"
    assert (
        cli.main(
            [
                "compare",
                str(examples / "PILOT-01_BrainGate2_T15_v4.2.json"),
                str(examples / "PILOT-02_FDA_Adaptive_DBS_v4.2.json"),
                "--labels",
                "BrainGate",
                "aDBS",
                "--out",
                str(compare_out),
            ]
        )
        == 0
    )
    assert len(json.loads(compare_out.read_text(encoding="utf-8"))["cases"]) == 2

    release = repo / "examples" / "observatory" / "evidence_depth_release_v1.4.json"
    assert cli.main(["observatory-verify", str(release)]) == 0
    assert parse_stdout(capsys)["valid"] is True
    assert cli.main(["observatory-import", str(workspace), str(release)]) == 0
    parse_stdout(capsys)
    assert cli.main(["observatory-summary", "--workspace", str(workspace), "--version", "v1.4"]) == 0
    assert parse_stdout(capsys)["metadata"]["version"] == "v1.4"
    assert cli.main(["observatory-queue", "--release", str(release)]) == 0
    assert parse_stdout(capsys)["counts"]["organizations"] == 3


def test_cli_failure_paths(tmp_path: Path, capsys, monkeypatch):
    assert cli.main(["validate", "--case-id", "UNKNOWN"]) == 2
    capsys.readouterr()

    repo = Path(__file__).resolve().parents[2]
    example = repo / "examples" / "assessments" / "PILOT-02_FDA_Adaptive_DBS_v4.2.json"
    assert cli.main(["compare", str(example), "--labels", "one", "two"]) == 2
    capsys.readouterr()

    workspace = tmp_path / "workspace"
    cli.main(["init", str(workspace)])
    capsys.readouterr()
    called = {}

    def fake_serve(ws, host, port, *, allow_network):
        called.update(host=host, port=port, allow_network=allow_network, root=ws.root)

    monkeypatch.setattr(cli, "serve", fake_serve)
    monkeypatch.setenv("NEUROAI_ALLOW_NETWORK", "1")
    assert cli.main(["serve", str(workspace), "--port", "9999", "--allow-network"]) == 0
    assert called["allow_network"] is True
    monkeypatch.delenv("NEUROAI_ALLOW_NETWORK", raising=False)
    with pytest.raises(SystemExit, match="NEUROAI_ALLOW_NETWORK"):
        cli.main(["serve", str(workspace), "--port", "9999", "--allow-network"])


def test_cli_programme_adapter_report_assistance_and_successor(tmp_path: Path, capsys):
    repo = Path(__file__).resolve().parents[2]
    programme_source = repo / "examples" / "programme" / "PRIMA_COMPLETED_ASSESSMENT_v4.2.1.programme.json"
    successor = repo / "examples" / "observatory" / "canonical_successor_snapshot_v1.7.json"
    adapted = tmp_path / "prima-native.json"
    adapter_report = tmp_path / "adapter-report.json"

    assert cli.main(["programme-adapt", str(programme_source), str(adapted), "--report", str(adapter_report)]) == 0
    assert parse_stdout(capsys)["validation"]["valid"] is True
    assert adapted.is_file()

    report = tmp_path / "prima.md"
    assert cli.main(["report", "--assessment", str(adapted), "--output", str(report)]) == 0
    assert parse_stdout(capsys)["sha256"]
    assert "PRIMA Controlled Public-Evidence Assessment" in report.read_text(encoding="utf-8")

    workspace = tmp_path / "workspace"
    assert cli.main(["init", str(workspace)]) == 0
    capsys.readouterr()
    assert cli.main(["case-import", str(workspace), str(adapted), "--case-id", "prima"]) == 0
    capsys.readouterr()

    request_out = tmp_path / "request.json"
    assert (
        cli.main(
            [
                "assist-request",
                str(workspace),
                "prima",
                "DRAFT_FINDING",
                "--prompt",
                "Draft bounded wording for the selected requirement.",
                "--evidence-id",
                "EV-PR-001",
                "--requirement-id",
                "NK-01-R01",
                "--out",
                str(request_out),
            ]
        )
        == 0
    )
    request_id = json.loads(request_out.read_text(encoding="utf-8"))["request"]["request_id"]

    model_output = tmp_path / "model-output.json"
    model_output.write_text(
        json.dumps(
            {
                "task_type": "DRAFT_FINDING",
                "summary": "Draft supplied for human review.",
                "suggestions": [
                    {
                        "target_path": "/requirement_findings/NK-01-R01/finding",
                        "proposed_text": "The bounded public record supports the trial configuration only.",
                        "evidence_ids": ["EV-PR-001"],
                        "confidence": "MEDIUM",
                        "limitations": ["No current commercial configuration conclusion follows."],
                    }
                ],
                "warnings": ["Human review required."],
            }
        ),
        encoding="utf-8",
    )
    assert (
        cli.main(
            [
                "assist-record",
                str(workspace),
                "prima",
                request_id,
                str(model_output),
                "--provider",
                "manual",
                "--model",
                "gpt-compatible-test",
            ]
        )
        == 0
    )
    parse_stdout(capsys)
    assert (
        cli.main(
            [
                "assist-dispose",
                str(workspace),
                "prima",
                request_id,
                "REJECTED",
                "--notes",
                "Rejected during test; no assessment change.",
            ]
        )
        == 0
    )
    parse_stdout(capsys)
    assert cli.main(["assist-verify", str(workspace), "prima", request_id]) == 0
    assert parse_stdout(capsys)["valid"] is True

    assert cli.main(["observatory-verify", str(successor)]) == 0
    assert parse_stdout(capsys)["release_kind"] == "COMPACT_SUCCESSOR_SNAPSHOT"
    assert cli.main(["observatory-import", str(workspace), str(successor)]) == 0
    parse_stdout(capsys)
    assert cli.main(["observatory-summary", "--workspace", str(workspace), "--version", "v1.7"]) == 0
    assert parse_stdout(capsys)["counts"]["completed_system_assessments"] == 4


def test_cli_review_workflow_and_gap_report(tmp_path: Path, capsys):
    repo = Path(__file__).resolve().parents[2]
    assessment = repo / "examples" / "assessments" / "PRIMA_Controlled_Assessment_v4.2.1.native.json"
    workspace = tmp_path / "workspace"
    assert cli.main(["init", str(workspace)]) == 0
    capsys.readouterr()
    assert cli.main(["case-import", str(workspace), str(assessment), "--case-id", "prima-review"]) == 0
    capsys.readouterr()

    assert (
        cli.main(
            [
                "review-assign",
                str(workspace),
                "prima-review",
                "reviewer-1",
                "DOMAIN_REVIEWER",
                "--scope",
                "FINDING:NK-01-R01",
                "--actor",
                "lead-1",
            ]
        )
        == 0
    )
    assert parse_stdout(capsys)["assignment"]["role"] == "DOMAIN_REVIEWER"
    assert (
        cli.main(
            [
                "review-assign",
                str(workspace),
                "prima-review",
                "lead-1",
                "LEAD_ASSESSOR",
                "--scope",
                "ASSESSMENT:*",
                "--actor",
                "assigner-1",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        cli.main(
            [
                "review-submit",
                str(workspace),
                "prima-review",
                "reviewer-1",
                "FINDING",
                "NK-01-R01",
                "DISAGREE",
                "--rationale",
                "The claim should remain bounded to the assessed configuration.",
                "--evidence-id",
                "EV-PR-001",
                "--proposed-change",
                "Narrow the finding wording.",
            ]
        )
        == 0
    )
    statement_id = parse_stdout(capsys)["statement"]["statement_id"]
    assert (
        cli.main(
            [
                "review-dispose",
                str(workspace),
                "prima-review",
                statement_id,
                "PARTIALLY_ACCEPTED",
                "--rationale",
                "Record the disagreement and review the assessment separately.",
                "--actor",
                "lead-1",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert cli.main(["review-verify", str(workspace), "prima-review"]) == 0
    assert parse_stdout(capsys)["valid"] is True

    review_report = tmp_path / "review.md"
    assert cli.main(["review-report", str(workspace), "prima-review", "--output", str(review_report)]) == 0
    assert parse_stdout(capsys)["sha256"]
    assert "PARTIALLY_ACCEPTED" in review_report.read_text(encoding="utf-8")

    gap_report = tmp_path / "gaps.md"
    assert cli.main(["gap-report", "--assessment", str(assessment), "--output", str(gap_report)]) == 0
    assert parse_stdout(capsys)["sha256"]
    assert "Evidence-gap and closure-request report" in gap_report.read_text(encoding="utf-8")


def test_cli_protected_evidence_exchange(tmp_path: Path, capsys):
    repo = Path(__file__).resolve().parents[2]
    assessment = repo / "examples" / "assessments" / "PRIMA_Controlled_Assessment_v4.2.1.native.json"
    workspace = tmp_path / "workspace"
    assert cli.main(["init", str(workspace)]) == 0
    capsys.readouterr()
    assert cli.main(["case-import", str(workspace), str(assessment), "--case-id", "prima-exchange"]) == 0
    capsys.readouterr()

    assert (
        cli.main(
            [
                "exchange-create",
                str(workspace),
                "prima-exchange",
                "--evidence-id",
                "EV-PR-001",
                "--gap-id",
                "GAP-PR-001",
                "--recipient",
                "PRIMA evidence custodian",
                "--purpose",
                "Request controlled access metadata.",
                "--requested-material",
                "Access procedure and immutable file digest",
                "--constraint",
                "No participant-level data should be transmitted through the workbench.",
                "--actor",
                "lead-1",
            ]
        )
        == 0
    )
    request = parse_stdout(capsys)["request"]
    request_id = request["request_id"]
    assert request["evidence_bytes_included"] is False

    materials = tmp_path / "materials.json"
    materials.write_text(
        json.dumps(
            [
                {
                    "evidence_id": "EV-PR-001",
                    "holder_reference": "custodian-record-2026-001",
                    "sha256": "b" * 64,
                }
            ]
        ),
        encoding="utf-8",
    )
    assert (
        cli.main(
            [
                "exchange-record",
                str(workspace),
                "prima-exchange",
                request_id,
                "AVAILABLE_UNDER_CONDITIONS",
                "--holder",
                "PRIMA evidence custodian",
                "--condition",
                "Independent review agreement required",
                "--materials-json",
                str(materials),
                "--notes",
                "Evidence remains with the holder.",
                "--actor",
                "lead-1",
            ]
        )
        == 0
    )
    assert parse_stdout(capsys)["response"]["evidence_bytes_received"] is False
    assert cli.main(["exchange-verify", str(workspace), "prima-exchange", request_id]) == 0
    assert parse_stdout(capsys)["valid"] is True

    report = tmp_path / "exchange.md"
    assert cli.main(["exchange-report", str(workspace), "prima-exchange", request_id, "--output", str(report)]) == 0
    assert parse_stdout(capsys)["sha256"]
    assert "metadata and holder representations only" in report.read_text(encoding="utf-8")
