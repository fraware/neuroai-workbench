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

from neuroai_workbench.evidence import add_evidence_bytes, verify_evidence_files
from neuroai_workbench.events import verify_chain
from neuroai_workbench.exporter import export_case_bundle
from neuroai_workbench.migration import migrate_v4_1_2
from neuroai_workbench.resource_loader import read_resource_bytes
from neuroai_workbench.server import WorkbenchHTTPServer
from neuroai_workbench.util import load_json, sha256_file, utc_now
from neuroai_workbench.validation import EXPECTED_REQUIREMENTS, validate_assessment
from neuroai_workbench.workspace import Workspace

ROOT = Path(__file__).resolve().parents[1]


def http_json(url: str):
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ci", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "verification/RELEASE_VERIFICATION_v0.1.0.json")
    args = parser.parse_args()
    checks = []

    def check(name, condition, detail=""):
        checks.append({"check_id": f"CHK-{len(checks)+1:03d}", "name": name, "status": "PASS" if condition else "FAIL", "detail": detail})
        if not condition:
            raise AssertionError(f"{name}: {detail}")

    required = [
        "README.md", "LICENSE", "NOTICE", "SECURITY.md", "THREAT_MODEL.md", "DATA_GOVERNANCE.md",
        "pyproject.toml", "src/neuroai_workbench/cli.py", "src/neuroai_workbench/server.py",
        "src/neuroai_workbench/static/index.html", "src/neuroai_workbench/resources/v4_2/UNIVERSAL_NEUROAI_ASSESSMENT_SCHEMA_v4.2.json",
    ]
    for rel in required:
        path = ROOT / rel
        check(f"Required file {rel}", path.is_file() and path.stat().st_size > 0, path.stat().st_size if path.exists() else 0)

    kernel = json.loads(read_resource_bytes("KERNEL_REQUIREMENTS_v4.2.json"))
    check("Kernel contains 78 requirements", len(kernel) == 78, len(kernel))
    check("Kernel IDs unique", len(EXPECTED_REQUIREMENTS) == 78, len(EXPECTED_REQUIREMENTS))
    blank = json.loads(read_resource_bytes("BLANK_UNIVERSAL_ASSESSMENT_INSTANCE_v4.2.json"))
    blank_report = validate_assessment(blank)
    check("Blank assessment validates", blank_report.valid, blank_report.to_dict())
    check("Blank assessment reports 52 mechanical P0 blockers", blank_report.counts["p0_blockers"] == 52, blank_report.counts)

    expected_counts = {
        "PILOT-01_BrainGate2_T15_v4.2.json": {"pass": 17, "partial": 41, "fail": 0, "not_assessed": 20, "p0_blockers": 14},
        "PILOT-02_FDA_Adaptive_DBS_v4.2.json": {"pass": 25, "partial": 41, "fail": 0, "not_assessed": 12, "p0_blockers": 9},
        "PILOT-05_Brain2Qwerty_v4.2.json": {"pass": 14, "partial": 35, "fail": 4, "not_assessed": 25, "p0_blockers": 19},
    }
    for name, counts in expected_counts.items():
        assessment = load_json(ROOT / "examples" / name)
        report = validate_assessment(assessment)
        check(f"Reference case validates: {name}", report.valid, report.to_dict())
        for key, expected in counts.items():
            check(f"Reference count {name} {key}", report.counts[key] == expected, report.counts[key])

    html_assets = [ROOT / "src/neuroai_workbench/static/index.html", ROOT / "src/neuroai_workbench/static/app.js", ROOT / "src/neuroai_workbench/static/styles.css"]
    for path in html_assets:
        text = path.read_text(encoding="utf-8")
        check(f"No remote assets in {path.name}", "https://" not in text and "http://" not in text and "//cdn" not in text.lower(), "offline-only")

    source = load_json(ROOT / "tests/fixtures/PILOT-02_v4.1.2.json")
    migrated = migrate_v4_1_2(source)
    check("Migration validates", validate_assessment(migrated).valid, migrated.get("migration_provenance"))
    check("Migration preserves historical findings", [r["finding_status"] for r in migrated["requirement_findings"]] == [r["finding_status"] for r in source["requirement_findings"]], "78 finding states")
    check("Migration preserves legacy decision", migrated["legacy_bounded_decision"] == source["bounded_decision"], "bounded decision exact")

    with tempfile.TemporaryDirectory(prefix="neuroai-release-") as tmp:
        workspace = Workspace.initialize(Path(tmp) / "workspace", name="Release verification")
        case = workspace.create_case("CASE-VERIFY", "Release verification case", actor="release-verifier")
        check("Created case validates", validate_assessment(case).valid, "CASE-VERIFY")
        evidence = add_evidence_bytes(workspace, "CASE-VERIFY", "evidence.txt", b"controlled release bytes\n", title="Release evidence", actor="release-verifier")
        check("Evidence registered", evidence["sha256"] != "", evidence)
        check("Evidence digest verifies", verify_evidence_files(workspace, "CASE-VERIFY")["valid"], evidence)
        check("Event chain verifies", verify_chain(workspace.case_path("CASE-VERIFY") / "events.jsonl")["valid"], "event chain")
        snapshot = workspace.snapshot("CASE-VERIFY", actor="release-verifier", label="release")
        check("Snapshot created", bool(snapshot["assessment_sha256"]), snapshot)
        bundle = Path(tmp) / "case.zip"
        export = export_case_bundle(workspace, "CASE-VERIFY", bundle)
        check("Controlled bundle verifies", export["validation_valid"] and export["evidence_valid"] and export["event_chain_valid"], export)
        with zipfile.ZipFile(bundle) as archive:
            check("Controlled bundle ZIP integrity", archive.testzip() is None, len(archive.namelist()))

        server = WorkbenchHTTPServer(("127.0.0.1", 0), workspace)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            check("HTTP health endpoint", http_json(base + "/api/health")["status"] == "ok", base)
            check("HTTP case endpoint", len(http_json(base + "/api/cases")["cases"]) == 1, base)
            check("HTTP validation endpoint", http_json(base + "/api/cases/CASE-VERIFY/validate")["valid"], base)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)

    compile_result = subprocess.run([sys.executable, "-m", "compileall", "-q", str(ROOT / "src")])
    check("Python compilation", compile_result.returncode == 0, compile_result.returncode)
    if not args.ci:
        pytest_result = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, text=True, capture_output=True)
        check("Pytest suite", pytest_result.returncode == 0, pytest_result.stdout + pytest_result.stderr)
        test_summary = pytest_result.stdout.strip().splitlines()[-1] if pytest_result.stdout.strip() else ""
    else:
        test_summary = "Executed separately by CI job"

    report = {
        "release": "v0.1.0",
        "generated_at": utc_now(),
        "controlled_determination": "REFERENCE WORKBENCH IMPLEMENTATION COMPLETE; SUITABLE FOR CONTROLLED LOCAL TECHNICAL PILOTS; PRODUCTION SECURITY, INSTITUTIONAL ADOPTION, SUBSTANTIVE EVIDENCE VALIDITY AND SYSTEM CONFORMANCE REMAIN OUTSIDE SOFTWARE VERIFICATION.",
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
    print(json.dumps({key: report[key] for key in ["release", "checks_total", "checks_passed", "checks_failed", "pytest"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
