#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import threading
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from neuroai_workbench import __version__
from neuroai_workbench.assistance import (
    create_assistance_request,
    dispose_assistance_response,
    record_assistance_response,
    verify_assistance_record,
)
from neuroai_workbench.events import verify_chain
from neuroai_workbench.evidence import add_evidence_bytes, verify_evidence_files
from neuroai_workbench.exchange import (
    create_exchange_request,
    record_exchange_response,
    render_exchange_markdown,
    verify_exchange_record,
)
from neuroai_workbench.exporter import export_case_bundle
from neuroai_workbench.migration import migrate_v4_1_2
from neuroai_workbench.observatory import load_release, queue_release, summarize_release, validate_release
from neuroai_workbench.programme_adapter import adapt_programme_assessment
from neuroai_workbench.reports import render_assessment_markdown, render_gap_markdown
from neuroai_workbench.resource_loader import read_resource_bytes
from neuroai_workbench.review import (
    create_review_assignment,
    dispose_review_statement,
    render_review_markdown,
    submit_review_statement,
    verify_review_records,
)
from neuroai_workbench.server import WorkbenchHTTPServer
from neuroai_workbench.util import load_json, sha256_file, utc_now
from neuroai_workbench.validation import EXPECTED_REQUIREMENTS, validate_assessment
from neuroai_workbench.workspace import Workspace

ROOT = Path(__file__).resolve().parents[1]
TAG = f"v{__version__}"


def http_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=5) as response:
        value = json.loads(response.read())
    if not isinstance(value, dict):
        raise TypeError("expected JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ci", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/RELEASE_VERIFICATION.json")
    args = parser.parse_args()
    checks: list[dict[str, Any]] = []

    def check(name: str, condition: bool, detail: Any = "") -> None:
        checks.append(
            {
                "check_id": f"CHK-{len(checks) + 1:03d}",
                "name": name,
                "status": "PASS" if condition else "FAIL",
                "detail": detail,
            }
        )
        if not condition:
            raise AssertionError(f"{name}: {detail}")

    required = [
        "AGENTS.md",
        "README.md",
        "LICENSE",
        "NOTICE",
        "SECURITY.md",
        "THREAT_MODEL.md",
        "DATA_GOVERNANCE.md",
        "pyproject.toml",
        ".github/CODEOWNERS",
        ".cursor/environment.json",
        "docs/architecture/overview.md",
        "docs/governance/evidence-boundary.md",
        "docs/reference/evidence-exchange.md",
        "docs/reference/observatory.md",
        "docs/reference/review.md",
        "docs/operations/cursor-engineering-handoff.md",
        "src/neuroai_workbench/cli.py",
        "src/neuroai_workbench/server.py",
        "src/neuroai_workbench/programme_adapter.py",
        "src/neuroai_workbench/assistance.py",
        "src/neuroai_workbench/exchange.py",
        "src/neuroai_workbench/reports.py",
        "src/neuroai_workbench/review.py",
        "src/neuroai_workbench/static/index.html",
        "src/neuroai_workbench/resources/v4_2/UNIVERSAL_NEUROAI_ASSESSMENT_SCHEMA_v4.2.json",
        "examples/observatory/evidence_depth_release_v1.4.json",
        "examples/observatory/canonical_successor_snapshot_v1.7.json",
        "examples/programme/PRIMA_COMPLETED_ASSESSMENT_v4.2.1.programme.json",
        "examples/assessments/PRIMA_Controlled_Assessment_v4.2.1.native.json",
    ]
    for rel in required:
        path = ROOT / rel
        check(
            f"Required file {rel}",
            path.is_file() and path.stat().st_size > 0,
            path.stat().st_size if path.exists() else 0,
        )

    for script in ("scripts/check_repository_hygiene.py", "scripts/check_version_consistency.py"):
        result = subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT, text=True, capture_output=True)
        check(f"Gate {script}", result.returncode == 0, result.stdout + result.stderr)

    kernel = json.loads(read_resource_bytes("KERNEL_REQUIREMENTS_v4.2.json"))
    check("Kernel contains 78 requirements", len(kernel) == 78, len(kernel))
    check("Kernel IDs unique", len(EXPECTED_REQUIREMENTS) == 78, len(EXPECTED_REQUIREMENTS))
    blank = json.loads(read_resource_bytes("BLANK_UNIVERSAL_ASSESSMENT_INSTANCE_v4.2.json"))
    blank_report = validate_assessment(blank)
    check("Blank assessment validates", blank_report.valid, blank_report.to_dict())
    check(
        "Blank assessment reports 52 mechanical P0 blockers",
        blank_report.counts["p0_blockers"] == 52,
        blank_report.counts,
    )

    expected_counts = {
        "PILOT-01_BrainGate2_T15_v4.2.json": {
            "pass": 17,
            "partial": 41,
            "fail": 0,
            "not_assessed": 20,
            "p0_blockers": 14,
        },
        "PILOT-02_FDA_Adaptive_DBS_v4.2.json": {
            "pass": 25,
            "partial": 41,
            "fail": 0,
            "not_assessed": 12,
            "p0_blockers": 9,
        },
        "PILOT-05_Brain2Qwerty_v4.2.json": {
            "pass": 14,
            "partial": 35,
            "fail": 4,
            "not_assessed": 25,
            "p0_blockers": 19,
        },
        "PRIMA_Controlled_Assessment_v4.2.1.native.json": {
            "pass": 15,
            "partial": 42,
            "fail": 0,
            "not_assessed": 21,
            "p0_blockers": 11,
        },
    }
    for name, counts in expected_counts.items():
        assessment = load_json(ROOT / "examples/assessments" / name)
        report = validate_assessment(assessment)
        check(f"Reference case validates: {name}", report.valid, report.to_dict())
        for key, expected in counts.items():
            check(f"Reference count {name} {key}", report.counts[key] == expected, report.counts[key])

    observatory_release = load_release(ROOT / "examples/observatory/evidence_depth_release_v1.4.json")
    observatory_report = validate_release(observatory_release)
    check("Observatory example validates", observatory_report["valid"], observatory_report)
    observatory_summary = summarize_release(observatory_release)
    check(
        "Observatory verification rate above 90 percent",
        observatory_summary["coverage"]["verification_rate"] >= 0.90,
        observatory_summary["coverage"],
    )
    observatory_queue = queue_release(observatory_release)
    check(
        "Observatory unresolved organization queue preserved",
        observatory_queue["counts"]["organizations"] == 3,
        observatory_queue,
    )

    successor_release = load_release(ROOT / "examples/observatory/canonical_successor_snapshot_v1.7.json")
    successor_report = validate_release(successor_release)
    check("Compact v1.7 successor validates", successor_report["valid"], successor_report)
    check(
        "Compact v1.7 successor preserves four completed assessments",
        successor_report["counts"].get("completed_system_assessments") == 4,
        successor_report["counts"],
    )
    successor_queue = queue_release(successor_release)
    check(
        "Compact successor retains open reopening conditions",
        any(
            item.get("object") == "PRIMA observatory system record"
            for item in successor_queue.get("reopening_queue", [])
        ),
        successor_queue,
    )

    programme_source = load_json(ROOT / "examples/programme/PRIMA_COMPLETED_ASSESSMENT_v4.2.1.programme.json")
    adapted = adapt_programme_assessment(programme_source)
    check("PRIMA programme adapter validates", adapted.report["validation"]["valid"], adapted.report)
    checked_in_prima = load_json(ROOT / "examples/assessments/PRIMA_Controlled_Assessment_v4.2.1.native.json")
    check("PRIMA checked-in projection is deterministic", adapted.assessment == checked_in_prima, adapted.report)
    prima_markdown = render_assessment_markdown(checked_in_prima)
    prima_gap_markdown = render_gap_markdown(checked_in_prima)
    check(
        "Deterministic report preserves decision boundary",
        "They do not establish evidentiary truth" in prima_markdown and "CL-4" in prima_markdown,
        len(prima_markdown),
    )
    check(
        "Deterministic gap report preserves closure boundary",
        "creates no disclosure duty" in prima_gap_markdown and "GAP-PR-001" in prima_gap_markdown,
        len(prima_gap_markdown),
    )

    html_assets = [
        ROOT / "src/neuroai_workbench/static/index.html",
        ROOT / "src/neuroai_workbench/static/app.js",
        ROOT / "src/neuroai_workbench/static/styles.css",
    ]
    for path in html_assets:
        text = path.read_text(encoding="utf-8")
        check(
            f"No remote assets in {path.name}",
            "https://" not in text and "http://" not in text and "//cdn" not in text.lower(),
            "offline-only",
        )

    source = load_json(ROOT / "tests/fixtures/PILOT-02_v4.1.2.json")
    migrated = migrate_v4_1_2(source)
    check("Migration validates", validate_assessment(migrated).valid, migrated.get("migration_provenance"))
    check(
        "Migration preserves historical findings",
        [row["finding_status"] for row in migrated["requirement_findings"]]
        == [row["finding_status"] for row in source["requirement_findings"]],
        "78 finding states",
    )
    check(
        "Migration preserves legacy decision",
        migrated["legacy_bounded_decision"] == source["bounded_decision"],
        "bounded decision exact",
    )

    with tempfile.TemporaryDirectory(prefix="neuroai-release-") as tmp:
        workspace = Workspace.initialize(Path(tmp) / "workspace", name="Release verification")
        check(
            "Workspace records package version",
            workspace.metadata["workbench_version"] == __version__,
            workspace.metadata,
        )
        case = workspace.create_case("CASE-VERIFY", "Release verification case", actor="release-verifier")
        check("Created case validates", validate_assessment(case).valid, "CASE-VERIFY")
        evidence = add_evidence_bytes(
            workspace,
            "CASE-VERIFY",
            "evidence.txt",
            b"controlled release bytes\n",
            title="Release evidence",
            actor="release-verifier",
        )
        check("Evidence registered", evidence["sha256"] != "", evidence)
        check("Evidence digest verifies", verify_evidence_files(workspace, "CASE-VERIFY")["valid"], evidence)
        check(
            "Event chain verifies",
            verify_chain(workspace.case_path("CASE-VERIFY") / "events.jsonl")["valid"],
            "event chain",
        )
        snapshot = workspace.snapshot("CASE-VERIFY", actor="release-verifier", label="release")
        check("Snapshot created", bool(snapshot["assessment_sha256"]), snapshot)
        bundle = Path(tmp) / "case.zip"
        export = export_case_bundle(workspace, "CASE-VERIFY", bundle)
        check(
            "Controlled bundle verifies",
            export["validation_valid"] and export["evidence_valid"] and export["event_chain_valid"],
            export,
        )
        with zipfile.ZipFile(bundle) as archive:
            check("Controlled bundle ZIP integrity", archive.testzip() is None, len(archive.namelist()))

        server = WorkbenchHTTPServer(("127.0.0.1", 0), workspace)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            health = http_json(base + "/api/health")
            check("HTTP health endpoint", health["status"] == "ok", base)
            check("HTTP version endpoint", health["version"] == __version__, health)
            check("HTTP case endpoint", len(http_json(base + "/api/cases")["cases"]) == 1, base)
            check("HTTP validation endpoint", http_json(base + "/api/cases/CASE-VERIFY/validate")["valid"], base)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        workspace.import_case(
            ROOT / "examples/assessments/PRIMA_Controlled_Assessment_v4.2.1.native.json",
            case_id="PRIMA-VERIFY",
            actor="release-verifier",
        )
        before_assistance = sha256_file(workspace.case_path("PRIMA-VERIFY") / "assessment.json")
        request = create_assistance_request(
            workspace,
            "PRIMA-VERIFY",
            "DRAFT_FINDING",
            "Draft bounded wording for NK-01-R01 using only the selected evidence.",
            evidence_ids=["EV-PR-001"],
            requirement_ids=["NK-01-R01"],
            actor="release-verifier",
        )["request"]
        response_path = Path(tmp) / "model-output.json"
        response_path.write_text(
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
                            "limitations": ["No current commercial configuration or conformance conclusion follows."],
                        }
                    ],
                    "warnings": ["Human review required."],
                }
            ),
            encoding="utf-8",
        )
        record_assistance_response(
            workspace,
            "PRIMA-VERIFY",
            request["request_id"],
            response_path,
            provider="release-verification",
            model="provider-neutral-test",
            actor="release-verifier",
        )
        dispose_assistance_response(
            workspace,
            "PRIMA-VERIFY",
            request["request_id"],
            "REJECTED",
            "Verification-only response; no assessment mutation.",
            actor="release-verifier",
        )
        assistance_report = verify_assistance_record(workspace, "PRIMA-VERIFY", request["request_id"])
        check("Controlled model-assistance record verifies", assistance_report["valid"], assistance_report)
        check(
            "Model-assistance lifecycle does not mutate assessment",
            sha256_file(workspace.case_path("PRIMA-VERIFY") / "assessment.json") == before_assistance,
            before_assistance,
        )
        before_review = sha256_file(workspace.case_path("PRIMA-VERIFY") / "assessment.json")
        create_review_assignment(
            workspace,
            "PRIMA-VERIFY",
            "domain-reviewer",
            "DOMAIN_REVIEWER",
            ["FINDING:NK-01-R01"],
            actor="lead-assessor",
        )
        create_review_assignment(
            workspace,
            "PRIMA-VERIFY",
            "lead-assessor",
            "LEAD_ASSESSOR",
            ["ASSESSMENT:*"],
            actor="lead-assessor",
        )
        review_statement = submit_review_statement(
            workspace,
            "PRIMA-VERIFY",
            "domain-reviewer",
            "FINDING",
            "NK-01-R01",
            "DISAGREE",
            "The wording should remain bounded to the assessed configuration.",
            evidence_ids=["EV-PR-001"],
        )["statement"]
        dispose_review_statement(
            workspace,
            "PRIMA-VERIFY",
            review_statement["statement_id"],
            "PARTIALLY_ACCEPTED",
            "Record the disagreement; any assessment edit remains a separate human action.",
            actor="lead-assessor",
        )
        review_report = verify_review_records(workspace, "PRIMA-VERIFY")
        check("Collaborative review record verifies", review_report["valid"], review_report)
        check(
            "Review lifecycle does not mutate assessment",
            sha256_file(workspace.case_path("PRIMA-VERIFY") / "assessment.json") == before_review,
            before_review,
        )
        review_markdown = render_review_markdown(workspace, "PRIMA-VERIFY")
        check(
            "Review report preserves disagreement and disposition",
            "DISAGREE" in review_markdown and "PARTIALLY_ACCEPTED" in review_markdown,
            len(review_markdown),
        )
        before_exchange = sha256_file(workspace.case_path("PRIMA-VERIFY") / "assessment.json")
        exchange_request = create_exchange_request(
            workspace,
            "PRIMA-VERIFY",
            ["EV-PR-001"],
            recipient="PRIMA evidence custodian",
            purpose="Request controlled access metadata for the unresolved evidence gap.",
            requested_materials=["Access procedure and immutable digest"],
            gap_ids=["GAP-PR-001"],
            disclosure_constraints=["No participant-level data through the workbench."],
            actor="lead-assessor",
        )["request"]
        record_exchange_response(
            workspace,
            "PRIMA-VERIFY",
            exchange_request["request_id"],
            "AVAILABLE_UNDER_CONDITIONS",
            holder="PRIMA evidence custodian",
            conditions=["Independent review agreement required"],
            materials=[
                {
                    "evidence_id": "EV-PR-001",
                    "holder_reference": "custodian-record-2026-001",
                    "sha256": "a" * 64,
                }
            ],
            notes="Evidence remains with the holder.",
            actor="lead-assessor",
        )
        exchange_report = verify_exchange_record(workspace, "PRIMA-VERIFY", exchange_request["request_id"])
        check("Protected-evidence metadata exchange verifies", exchange_report["valid"], exchange_report)
        check(
            "Protected-evidence exchange does not mutate assessment",
            sha256_file(workspace.case_path("PRIMA-VERIFY") / "assessment.json") == before_exchange,
            before_exchange,
        )
        exchange_markdown = render_exchange_markdown(workspace, "PRIMA-VERIFY", exchange_request["request_id"])
        check(
            "Exchange report preserves no-byte and no-receipt boundaries",
            "does not include evidence bytes" in exchange_markdown
            and "AVAILABLE_UNDER_CONDITIONS" in exchange_markdown,
            len(exchange_markdown),
        )

    compile_result = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", str(ROOT / "src"), str(ROOT / "scripts")]
    )
    check("Python compilation", compile_result.returncode == 0, compile_result.returncode)
    if not args.ci:
        pytest_result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")},
        )
        check("Pytest suite", pytest_result.returncode == 0, pytest_result.stdout + pytest_result.stderr)
        test_summary = pytest_result.stdout.strip().splitlines()[-1] if pytest_result.stdout.strip() else ""
    else:
        test_summary = "Executed separately by CI job"

    report = {
        "release": TAG,
        "generated_at": utc_now(),
        "controlled_determination": (
            "REPOSITORY STABILIZATION VERIFIED FOR CONTROLLED LOCAL TECHNICAL PILOTS; PRODUCTION SECURITY, "
            "INSTITUTIONAL ADOPTION, SUBSTANTIVE EVIDENCE VALIDITY, REGULATORY AUTHORIZATION AND SYSTEM "
            "CONFORMANCE REMAIN OUTSIDE SOFTWARE VERIFICATION."
        ),
        "instrument_version": "v4.2",
        "normative_requirements": 78,
        "semantic_change_from_v0_2_0": False,
        "checks_total": len(checks),
        "checks_passed": sum(row["status"] == "PASS" for row in checks),
        "checks_failed": sum(row["status"] == "FAIL" for row in checks),
        "pytest": test_summary,
        "reference_cases": list(expected_counts),
        "withheld_claims": [
            "UNESCO endorsement or official-methodology status",
            "Legal or regulatory authorization",
            "Clinical safety or effectiveness",
            "Production-grade cybersecurity",
            "Evidence authenticity or methodological adequacy",
            "Completed system conformance",
        ],
        "checks": checks,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {key: report[key] for key in ["release", "checks_total", "checks_passed", "checks_failed", "pytest"]},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
