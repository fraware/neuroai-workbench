from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

from .events import verify_chain
from .evidence import verify_evidence_files
from .util import atomic_write_json, sha256_file, utc_now
from .validation import validate_assessment
from .workspace import CASE_FILE, Workspace


def export_case_bundle(workspace: Workspace, case_id: str, output: Path) -> dict[str, Any]:
    case = workspace.case_path(case_id)
    if not (case / CASE_FILE).is_file():
        raise ValueError(f"Unknown case {case_id!r}")
    assessment = workspace.load_case(case_id)
    validation = validate_assessment(assessment).to_dict()
    evidence = verify_evidence_files(workspace, case_id)
    chain = verify_chain(case / "events.jsonl")
    manifest = {
        "bundle_version": "1",
        "workbench_version": "0.1.0",
        "case_id": case_id,
        "created_at": utc_now(),
        "assessment_sha256": sha256_file(case / CASE_FILE),
        "validation": validation,
        "evidence_verification": evidence,
        "event_chain_verification": chain,
        "boundary": "Bundle integrity does not establish substantive evidentiary or conformance conclusions.",
    }
    manifest_path = case / "exports" / "bundle-manifest.json"
    atomic_write_json(manifest_path, manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(case.rglob("*")):
            if path.is_file() and path != output:
                archive.write(path, arcname=f"{case_id}/{path.relative_to(case).as_posix()}")
    with zipfile.ZipFile(output) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError(f"Bundle ZIP integrity failed at {bad}")
    return {
        "output": str(output),
        "sha256": sha256_file(output),
        "size_bytes": output.stat().st_size,
        "validation_valid": validation["valid"],
        "evidence_valid": evidence["valid"],
        "event_chain_valid": chain["valid"],
    }
