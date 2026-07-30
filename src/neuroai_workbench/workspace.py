from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any

from . import __version__
from .errors import WorkspaceError
from .events import append_event, verify_chain
from .resource_loader import read_resource_bytes
from .util import atomic_write_json, ensure_identifier, load_json, safe_join, sha256_file, utc_now
from .validation import validate_assessment

WORKSPACE_FILE = "workspace.json"
CASE_FILE = "assessment.json"


class Workspace:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.meta_path = self.root / WORKSPACE_FILE
        self.cases_dir = self.root / "cases"

    @classmethod
    def initialize(cls, root: Path, name: str = "NeuroAI assessment workspace") -> "Workspace":
        root = root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        workspace = cls(root)
        if workspace.meta_path.exists():
            raise WorkspaceError(f"Workspace already exists at {root}")
        (root / "cases").mkdir()
        (root / "exports").mkdir()
        (root / "tmp").mkdir()
        atomic_write_json(workspace.meta_path, {
            "workspace_version": "1",
            "workbench_version": __version__,
            "name": name,
            "created_at": utc_now(),
            "instrument_version": "v4.2",
            "boundary": "This workspace stores evidence and assessment records. Software state does not establish substantive conformance.",
        })
        return workspace

    @classmethod
    def open(cls, root: Path) -> "Workspace":
        workspace = cls(root)
        if not workspace.meta_path.is_file():
            raise WorkspaceError(f"No {WORKSPACE_FILE} found at {root}")
        meta = load_json(workspace.meta_path)
        if meta.get("workspace_version") != "1":
            raise WorkspaceError(f"Unsupported workspace version: {meta.get('workspace_version')}")
        return workspace

    @property
    def metadata(self) -> dict[str, Any]:
        return load_json(self.meta_path)

    def case_path(self, case_id: str) -> Path:
        ensure_identifier(case_id, "case ID")
        return safe_join(self.cases_dir, case_id)

    def list_cases(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not self.cases_dir.exists():
            return rows
        for path in sorted(self.cases_dir.iterdir()):
            assessment_path = path / CASE_FILE
            if not path.is_dir() or not assessment_path.is_file():
                continue
            try:
                assessment = load_json(assessment_path)
                meta = assessment.get("assessment_metadata", {})
                system = assessment.get("system_profile", {})
                report = validate_assessment(assessment)
                rows.append({
                    "case_id": path.name,
                    "assessment_id": meta.get("assessment_id"),
                    "title": meta.get("title"),
                    "status": meta.get("assessment_status"),
                    "system_name": system.get("system_name"),
                    "configuration_id": system.get("configuration_id"),
                    "valid": report.valid,
                    "schema_errors": len(report.schema_issues),
                    "semantic_errors": len(report.semantic_issues),
                    "p0_blockers": report.counts.get("p0_blockers", 0),
                    "assessment_sha256": sha256_file(assessment_path),
                })
            except Exception as exc:  # preserve discoverability of a damaged case
                rows.append({"case_id": path.name, "valid": False, "error": str(exc)})
        return rows

    def create_case(self, case_id: str, title: str, actor: str = "local-user") -> dict[str, Any]:
        path = self.case_path(case_id)
        if path.exists():
            raise WorkspaceError(f"Case {case_id!r} already exists")
        (path / "evidence/objects").mkdir(parents=True)
        (path / "snapshots").mkdir()
        (path / "exports").mkdir()
        assessment = json.loads(read_resource_bytes("BLANK_UNIVERSAL_ASSESSMENT_INSTANCE_v4.2.json"))
        assessment["assessment_metadata"]["assessment_id"] = case_id
        assessment["assessment_metadata"]["title"] = title
        assessment["system_profile"]["system_id"] = f"SYSTEM-{case_id}"
        atomic_write_json(path / CASE_FILE, assessment)
        atomic_write_json(path / "evidence/index.json", {"version": "1", "objects": []})
        append_event(path / "events.jsonl", "CASE_CREATED", actor, {
            "case_id": case_id,
            "assessment_sha256": sha256_file(path / CASE_FILE),
        })
        return assessment

    def import_case(self, source: Path, case_id: str | None = None, actor: str = "local-user") -> dict[str, Any]:
        assessment = load_json(source)
        report = validate_assessment(assessment)
        if not report.valid:
            raise WorkspaceError(f"Assessment is invalid: {json.dumps(report.to_dict(), ensure_ascii=False)}")
        resolved_id = case_id or str(assessment["assessment_metadata"]["assessment_id"])
        path = self.case_path(resolved_id)
        if path.exists():
            raise WorkspaceError(f"Case {resolved_id!r} already exists")
        (path / "evidence/objects").mkdir(parents=True)
        (path / "snapshots").mkdir()
        (path / "exports").mkdir()
        atomic_write_json(path / CASE_FILE, assessment)
        atomic_write_json(path / "evidence/index.json", {"version": "1", "objects": []})
        append_event(path / "events.jsonl", "CASE_IMPORTED", actor, {
            "case_id": resolved_id,
            "source_name": source.name,
            "assessment_sha256": sha256_file(path / CASE_FILE),
        })
        return assessment

    def load_case(self, case_id: str) -> dict[str, Any]:
        path = self.case_path(case_id) / CASE_FILE
        if not path.is_file():
            raise WorkspaceError(f"Unknown case {case_id!r}")
        return load_json(path)

    def save_case(self, case_id: str, assessment: dict[str, Any], actor: str = "local-user", require_valid: bool = False) -> dict[str, Any]:
        path = self.case_path(case_id)
        if not path.is_dir():
            raise WorkspaceError(f"Unknown case {case_id!r}")
        report = validate_assessment(assessment)
        if require_valid and not report.valid:
            raise WorkspaceError("Assessment failed the required validation gate")
        target = path / CASE_FILE
        before = sha256_file(target) if target.exists() else None
        atomic_write_json(target, assessment)
        after = sha256_file(target)
        append_event(path / "events.jsonl", "ASSESSMENT_SAVED", actor, {
            "before_sha256": before,
            "after_sha256": after,
            "valid": report.valid,
            "schema_errors": len(report.schema_issues),
            "semantic_errors": len(report.semantic_issues),
        })
        return report.to_dict()

    def snapshot(self, case_id: str, actor: str = "local-user", label: str = "snapshot") -> dict[str, Any]:
        case = self.case_path(case_id)
        assessment_path = case / CASE_FILE
        if not assessment_path.is_file():
            raise WorkspaceError(f"Unknown case {case_id!r}")
        timestamp = utc_now().replace(":", "").replace("-", "")
        safe_label = ensure_identifier(label, "snapshot label")
        destination = case / "snapshots" / f"{timestamp}-{safe_label}"
        destination.mkdir(parents=True)
        shutil.copy2(assessment_path, destination / CASE_FILE)
        evidence_index = case / "evidence/index.json"
        if evidence_index.exists():
            shutil.copy2(evidence_index, destination / "evidence-index.json")
        record = {
            "snapshot_id": destination.name,
            "created_at": utc_now(),
            "assessment_sha256": sha256_file(destination / CASE_FILE),
            "event_chain": verify_chain(case / "events.jsonl"),
        }
        atomic_write_json(destination / "snapshot.json", record)
        append_event(case / "events.jsonl", "SNAPSHOT_CREATED", actor, record)
        return record

    def delete_case(self, case_id: str, confirmation: str) -> None:
        if confirmation != case_id:
            raise WorkspaceError("Deletion confirmation must exactly match the case ID")
        path = self.case_path(case_id)
        if not path.is_dir():
            raise WorkspaceError(f"Unknown case {case_id!r}")
        shutil.rmtree(path)
