#!/usr/bin/env python3
"""Build the static v2.3.0-dev canonical checkpoint from governing inputs.

The checkpoint preserves original governing JSON bytes, registers every artifact by
SHA-256, adds only explicitly declared supplemental workbook-derived records, and
verifies cross-release and assessment invariants. It does not refresh any source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

BOUNDARY = (
    "Static canonical checkpoint imported from the preserved v2.2.0 programme corpus. "
    "No source refresh, new finding, or silent semantic upgrade is performed."
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def copy_governing(
    src: Path,
    dst: Path,
    family: str,
    registry: list[dict[str, Any]],
) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    registry.append(
        {
            "family": family,
            "source_path": str(src),
            "canonical_path": str(dst),
            "size_bytes": dst.stat().st_size,
            "sha256": sha256_file(dst),
            "byte_preserved": sha256_file(src) == sha256_file(dst),
        }
    )


def assessment_counts(document: dict[str, Any]) -> dict[str, int]:
    if "assessment_metadata" in document:
        return {
            "findings": len(document.get("requirement_findings", [])),
            "claims": len(document.get("claim_register", [])),
            "evidence": len(document.get("evidence_register", [])),
            "endpoints": len(document.get("endpoint_register", [])),
            "gaps": len(document.get("gap_register", [])),
        }
    return {
        "findings": len(document.get("requirement_findings", [])),
        "claims": len(document.get("claims", [])),
        "evidence": len(document.get("evidence_register", [])),
        "endpoints": len(document.get("endpoints", [])),
        "gaps": len(document.get("gaps_and_requests", [])),
    }


def status_counts(document: dict[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in document.get("requirement_findings", []):
        if not isinstance(row, dict):
            continue
        status = row.get("normalized_status") or row.get("finding_status") or row.get("status") or "UNRESOLVED"
        counts[str(status)] += 1
    return dict(sorted(counts.items()))


def add_check(
    checks: list[dict[str, Any]],
    check_id: str,
    expected: Any,
    observed: Any,
    detail: str = "",
) -> None:
    checks.append(
        {
            "check_id": check_id,
            "expected": expected,
            "observed": observed,
            "status": "PASS" if expected == observed else "FAIL",
            "detail": detail,
        }
    )


def governing_mappings() -> list[tuple[str, str, str]]:
    return [
        (
            "01_Programme_Overview/CANONICAL_PROGRAMME_ASSET_REGISTER_v2.0.0.json",
            "programme/asset_register_v2.0.0.json",
            "PROGRAMME",
        ),
        (
            "01_Programme_Overview/CURRENT_PROGRAMME_STATE_v2.0.0.json",
            "programme/state_v2.0.0.json",
            "PROGRAMME",
        ),
        (
            "02_Global_Landscape_and_Observatory/CANONICAL_EVIDENCE_DEPTH_AND_OBSERVATORY_RELEASE_v1.4.json",
            "observatory/releases/v1.4/full_release.json",
            "OBSERVATORY",
        ),
        (
            "02_Global_Landscape_and_Observatory/SOURCE_REGISTER_v1.4.json",
            "observatory/releases/v1.4/source_register.json",
            "OBSERVATORY",
        ),
        (
            "02_Global_Landscape_and_Observatory/SOURCE_MONITOR_REGISTRY_v1.5.json",
            "observatory/releases/v1.5/source_monitor_registry.json",
            "OBSERVATORY",
        ),
        (
            "02_Global_Landscape_and_Observatory/CANONICAL_LIVE_REFRESH_RELEASE_v1.6.json",
            "observatory/releases/v1.6/live_refresh.json",
            "OBSERVATORY",
        ),
        (
            "02_Global_Landscape_and_Observatory/ADJUDICATED_DELTA_v1.6.json",
            "observatory/releases/v1.6/adjudicated_delta.json",
            "OBSERVATORY",
        ),
        (
            "02_Global_Landscape_and_Observatory/CANONICAL_SUCCESSOR_SNAPSHOT_v1.6.json",
            "observatory/releases/v1.6/successor_snapshot.json",
            "OBSERVATORY",
        ),
        (
            "02_Global_Landscape_and_Observatory/CANONICAL_SUCCESSOR_SNAPSHOT_v1.7.json",
            "observatory/releases/v1.7/successor_snapshot.json",
            "OBSERVATORY",
        ),
        (
            "02_Global_Landscape_and_Observatory/PRIMA_OBSERVATORY_SUCCESSOR_DELTA_v1.7.json",
            "observatory/releases/v1.7/prima_delta.json",
            "OBSERVATORY",
        ),
        (
            "03_Current_Assessment_Instrument/KERNEL_REQUIREMENTS_v4.2.json",
            "normative/v4.2/kernel_requirements.json",
            "NORMATIVE",
        ),
        (
            "03_Current_Assessment_Instrument/MINIMUM_EVIDENCE_STANDARD_v4.2.json",
            "normative/v4.2/minimum_evidence_standard.json",
            "NORMATIVE",
        ),
        (
            "03_Current_Assessment_Instrument/UNIVERSAL_NEUROAI_ASSESSMENT_SCHEMA_v4.2.json",
            "normative/v4.2/assessment_schema.json",
            "NORMATIVE",
        ),
        (
            "04_Completed_Assessments/01_Brain2Qwerty_v4.1.3/PILOT-05_COMPLETED_ASSESSMENT_v4.1.3.json",
            "assessments/brain2qwerty/v4.1.3/assessment.json",
            "ASSESSMENT",
        ),
        (
            "04_Completed_Assessments/02_FDA_Adaptive_DBS_v4.1.4/PILOT-02_COMPLETED_ASSESSMENT_v4.1.4.json",
            "assessments/fda-adaptive-dbs/v4.1.4/assessment.json",
            "ASSESSMENT",
        ),
        (
            "04_Completed_Assessments/03_BrainGate2_T15_v4.1.5/PILOT-01_COMPLETED_ASSESSMENT_v4.1.5.json",
            "assessments/braingate2-t15/v4.1.5/assessment.json",
            "ASSESSMENT",
        ),
        (
            "04_Completed_Assessments/04_PRIMA_v4.2.1_and_Observatory_v1.7/PRIMA_COMPLETED_ASSESSMENT_v4.2.1.json",
            "assessments/prima/v4.2.1/assessment.json",
            "ASSESSMENT",
        ),
        (
            "05_Comparative_Findings/CROSS_CASE_COMPARISON_v4.1.6.json",
            "comparison/v4.1.6/cross_case_comparison.json",
            "COMPARISON",
        ),
        (
            "05_Comparative_Findings/MINIMUM_EVIDENCE_STANDARD_v4.1.6.json",
            "comparison/v4.1.6/minimum_evidence_standard.json",
            "COMPARISON",
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--governing-root", type=Path, required=True)
    parser.add_argument("--phase1-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workbench-commit", default="UNRESOLVED")
    args = parser.parse_args()

    if args.output.exists():
        shutil.rmtree(args.output)
    args.output.mkdir(parents=True)

    governing_root = args.governing_root
    output = args.output
    artifacts: list[dict[str, Any]] = []

    for source_relative, target_relative, family in governing_mappings():
        source = governing_root / source_relative
        if not source.is_file():
            raise FileNotFoundError(source)
        copy_governing(source, output / target_relative, family, artifacts)

    supplemental = {
        "Implementation_Indicators": "implementation/implementation_indicators.json",
        "Recommendation_Crosswalk": "implementation/recommendation_crosswalk.json",
        "Outreach_Contacts": "operations/outreach_contacts_checkpoint.json",
    }
    exports = args.phase1_output / "canonical_sheet_exports"
    for sheet, target_relative in supplemental.items():
        source = next(exports.glob(f"*_{sheet}.json"))
        document = load_json(source)
        derived = {
            "metadata": {
                "title": f"{sheet} v2.2 checkpoint import",
                "source_export_sha256": sha256_file(source),
                "row_count": len(document.get("rows", [])),
                "status": "STATIC_CHECKPOINT_IMPORT",
                "boundary": BOUNDARY,
            },
            "records": document.get("rows", []),
        }
        derived["metadata"]["canonical_sha256"] = canonical_hash(derived)
        target = output / target_relative
        write_json(target, derived)
        artifacts.append(
            {
                "family": "SUPPLEMENTAL_CHECKPOINT",
                "source_path": str(source),
                "canonical_path": str(target),
                "size_bytes": target.stat().st_size,
                "sha256": sha256_file(target),
                "byte_preserved": False,
            }
        )

    checks: list[dict[str, Any]] = []
    v14 = load_json(output / "observatory/releases/v1.4/full_release.json")
    registry = load_json(output / "observatory/releases/v1.5/source_monitor_registry.json")
    v16 = load_json(output / "observatory/releases/v1.6/live_refresh.json")
    delta_v16 = load_json(output / "observatory/releases/v1.6/adjudicated_delta.json")
    v17 = load_json(output / "observatory/releases/v1.7/successor_snapshot.json")

    add_check(checks, "V14-ORGANIZATIONS", 223, len(v14.get("organizations", [])))
    add_check(checks, "V14-SOURCES", 224, len(v14.get("sources", [])))
    registry_count = len(registry) if isinstance(registry, list) else len(registry.get("sources", []))
    add_check(checks, "REGISTRY-SOURCES", 224, registry_count)
    add_check(checks, "V16-NEW-SOURCES", 12, len(v16.get("new_sources", [])))
    add_check(checks, "V16-CANDIDATES", 9, len(v16.get("change_candidates", [])))
    delta_total = sum(len(value) for value in delta_v16.values() if isinstance(value, list))
    add_check(checks, "V16-DELTA-RECORDS", 9, delta_total)
    add_check(
        checks,
        "V17-PREDECESSOR",
        "v1.6",
        v17.get("metadata", {}).get("predecessor"),
    )
    add_check(
        checks,
        "V17-SOURCE-EFFECTIVE-COUNT",
        248,
        v17.get("successor_effective_counts", {}).get("source_records"),
    )

    assessment_expectations = {
        "brain2qwerty/v4.1.3": {
            "findings": 78,
            "claims": 8,
            "evidence": 10,
            "endpoints": 6,
            "gaps": 12,
        },
        "fda-adaptive-dbs/v4.1.4": {
            "findings": 78,
            "claims": 10,
            "evidence": 15,
            "endpoints": 8,
            "gaps": 12,
        },
        "braingate2-t15/v4.1.5": {
            "findings": 78,
            "claims": 12,
            "evidence": 12,
            "endpoints": 13,
            "gaps": 14,
        },
        "prima/v4.2.1": {
            "findings": 78,
            "claims": 14,
            "evidence": 15,
            "endpoints": 11,
            "gaps": 22,
        },
    }
    assessment_summary: list[dict[str, Any]] = []
    for key, expected in assessment_expectations.items():
        document = load_json(output / f"assessments/{key}/assessment.json")
        observed = assessment_counts(document)
        for metric, value in expected.items():
            add_check(checks, f"ASSESSMENT-{key}-{metric}", value, observed[metric])
        assessment_summary.append(
            {
                "assessment": key,
                **observed,
                "statuses": status_counts(document),
            }
        )

    preserved_or_declared = sum(
        1 for artifact in artifacts if artifact["byte_preserved"] or artifact["family"] == "SUPPLEMENTAL_CHECKPOINT"
    )
    add_check(
        checks,
        "ARTIFACT-BYTE-PRESERVATION",
        len(artifacts),
        preserved_or_declared,
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    state = {
        "metadata": {
            "title": "NeuroAI v2.3.0-dev static canonical checkpoint",
            "checkpoint_id": "NEUROAI-V2.3.0-DEV-STATIC-IMPORT-001",
            "source_checkpoint": "v2.2.0",
            "status": "PASS" if not failures else "FAIL",
            "workbench_commit_observed": args.workbench_commit,
            "boundary": BOUNDARY,
        },
        "observatory_lineage": ["v1.4", "v1.5", "v1.6", "v1.7"],
        "assessment_summary": assessment_summary,
        "artifact_count": len(artifacts),
        "check_count": len(checks),
        "pass_count": len(checks) - len(failures),
        "fail_count": len(failures),
        "next_phase": "CURRENT_STATE_REFRESH_DELTA",
    }
    state["metadata"]["checkpoint_sha256"] = canonical_hash(state)
    write_json(output / "programme/canonical_checkpoint_state.json", state)
    write_json(
        output / "verification/checks.json",
        {"checks": checks, "failures": failures, "boundary": BOUNDARY},
    )

    manifest_files = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            manifest_files.append(
                {
                    "path": str(path.relative_to(output)).replace(os.sep, "/"),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    manifest = {
        "metadata": {
            "title": "NeuroAI v2.3.0-dev static canonical checkpoint manifest",
            "file_count": len(manifest_files),
            "status": state["metadata"]["status"],
            "boundary": BOUNDARY,
        },
        "governing_artifacts": artifacts,
        "files": manifest_files,
    }
    manifest["metadata"]["manifest_sha256"] = canonical_hash(manifest)
    write_json(output / "manifest.json", manifest)

    (output / "README.md").write_text(
        "# NeuroAI v2.3.0-dev static canonical checkpoint\n\n"
        f"Status: **{state['metadata']['status']}**\n\n"
        "This directory preserves the current governing JSON corpus in a structured "
        "canonical layout and verifies inherited observatory and assessment counts. "
        "It is an import checkpoint, not a refreshed successor.\n",
        encoding="utf-8",
    )
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
