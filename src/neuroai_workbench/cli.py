from __future__ import annotations

import argparse
import json
import logging
import sys
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any

from . import __version__
from .comparison import compare_assessments
from .evidence import add_evidence_file, verify_evidence_files
from .events import verify_chain
from .exporter import export_case_bundle
from .metrics import summarize
from .migration import migrate_file
from .observatory import import_release, load_imported_release, load_release, queue_release, summarize_release, validate_release
from .server import serve
from .util import atomic_write_json, sha256_file
from .validation import validate_assessment
from .workspace import Workspace


def emit(value: Any, output: Path | None = None) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def _workspace(path: str) -> Workspace:
    return Workspace.open(Path(path))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neuroai-workbench",
        description="Offline-first evidence and decision workbench for the v4.2 universal NeuroAI assessment instrument.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--log-level", default="WARNING", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="Initialize an empty workspace")
    p.add_argument("workspace")
    p.add_argument("--name", default="NeuroAI assessment workspace")

    p = sub.add_parser("doctor", help="Check the runtime and an optional workspace")
    p.add_argument("--workspace")

    p = sub.add_parser("serve", help="Run the local web application")
    p.add_argument("workspace")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)

    p = sub.add_parser("case-create", help="Create a blank v4.2 case")
    p.add_argument("workspace")
    p.add_argument("case_id")
    p.add_argument("--title", required=True)
    p.add_argument("--actor", default="cli-user")

    p = sub.add_parser("case-import", help="Import a valid v4.2 assessment")
    p.add_argument("workspace")
    p.add_argument("assessment")
    p.add_argument("--case-id")
    p.add_argument("--actor", default="cli-user")

    p = sub.add_parser("case-list", help="List cases")
    p.add_argument("workspace")
    p.add_argument("--out")

    p = sub.add_parser("case-show", help="Print a case assessment")
    p.add_argument("workspace")
    p.add_argument("case_id")
    p.add_argument("--out")

    p = sub.add_parser("case-save", help="Replace a case assessment with a JSON file")
    p.add_argument("workspace")
    p.add_argument("case_id")
    p.add_argument("assessment")
    p.add_argument("--require-valid", action="store_true")
    p.add_argument("--actor", default="cli-user")

    p = sub.add_parser("validate", help="Validate a JSON file or workspace case")
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--assessment")
    source.add_argument("--case-id")
    p.add_argument("--workspace")
    p.add_argument("--out")

    p = sub.add_parser("summary", help="Summarize a JSON file or case")
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--assessment")
    source.add_argument("--case-id")
    p.add_argument("--workspace")
    p.add_argument("--out")

    p = sub.add_parser("snapshot", help="Create a controlled case snapshot")
    p.add_argument("workspace")
    p.add_argument("case_id")
    p.add_argument("--label", default="snapshot")
    p.add_argument("--actor", default="cli-user")

    p = sub.add_parser("evidence-add", help="Register local evidence bytes and an assessment evidence object")
    p.add_argument("workspace")
    p.add_argument("case_id")
    p.add_argument("file")
    p.add_argument("--title", required=True)
    p.add_argument("--type", default="OTHER")
    p.add_argument("--source", default="LOCAL FILE")
    p.add_argument("--actor", default="cli-user")
    p.add_argument("--store-only", action="store_true")

    p = sub.add_parser("evidence-verify", help="Verify registered evidence digests")
    p.add_argument("workspace")
    p.add_argument("case_id")
    p.add_argument("--out")

    p = sub.add_parser("events-verify", help="Verify the hash-chained event log")
    p.add_argument("workspace")
    p.add_argument("case_id")
    p.add_argument("--out")

    p = sub.add_parser("bundle", help="Create a controlled case ZIP bundle")
    p.add_argument("workspace")
    p.add_argument("case_id")
    p.add_argument("output")
    p.add_argument("--out")

    p = sub.add_parser("migrate", help="Migrate a v4.1.2 assessment additively to v4.2")
    p.add_argument("source")
    p.add_argument("output")

    p = sub.add_parser("observatory-import", help="Import and mechanically validate a controlled observatory release")
    p.add_argument("workspace")
    p.add_argument("release")

    p = sub.add_parser("observatory-verify", help="Validate an observatory release JSON file")
    p.add_argument("release")
    p.add_argument("--out")

    p = sub.add_parser("observatory-summary", help="Summarize a release file or imported workspace release")
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--release")
    source.add_argument("--version")
    p.add_argument("--workspace")
    p.add_argument("--out")

    p = sub.add_parser("observatory-queue", help="Show unresolved organization and source records")
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--release")
    source.add_argument("--version")
    p.add_argument("--workspace")
    p.add_argument("--out")

    p = sub.add_parser("compare", help="Compare v4.2 assessments without creating new findings")
    p.add_argument("assessments", nargs="+")
    p.add_argument("--labels", nargs="*")
    p.add_argument("--out")

    return parser


def _load_input(args: argparse.Namespace) -> dict[str, Any]:
    if args.assessment:
        return json.loads(Path(args.assessment).read_text(encoding="utf-8"))
    if not args.workspace:
        raise ValueError("--workspace is required with --case-id")
    return _workspace(args.workspace).load_case(args.case_id)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s %(message)s")
    try:
        if args.command == "init":
            workspace = Workspace.initialize(Path(args.workspace), name=args.name)
            emit({"workspace": str(workspace.root), "metadata": workspace.metadata})
        elif args.command == "doctor":
            result: dict[str, Any] = {
                "workbench_version": __version__,
                "python": sys.version,
                "jsonschema": package_version("jsonschema"),
                "runtime_ok": sys.version_info >= (3, 10),
                "boundary": "Runtime checks do not establish assessment validity or system conformance.",
            }
            if args.workspace:
                workspace = _workspace(args.workspace)
                result["workspace"] = str(workspace.root)
                result["cases"] = workspace.list_cases()
            emit(result)
        elif args.command == "serve":
            serve(_workspace(args.workspace), host=args.host, port=args.port)
        elif args.command == "case-create":
            emit(_workspace(args.workspace).create_case(args.case_id, args.title, actor=args.actor))
        elif args.command == "case-import":
            emit(_workspace(args.workspace).import_case(Path(args.assessment), case_id=args.case_id, actor=args.actor))
        elif args.command == "case-list":
            emit({"cases": _workspace(args.workspace).list_cases()}, Path(args.out) if args.out else None)
        elif args.command == "case-show":
            emit(_workspace(args.workspace).load_case(args.case_id), Path(args.out) if args.out else None)
        elif args.command == "case-save":
            assessment = json.loads(Path(args.assessment).read_text(encoding="utf-8"))
            emit(_workspace(args.workspace).save_case(args.case_id, assessment, actor=args.actor, require_valid=args.require_valid))
        elif args.command == "validate":
            report = validate_assessment(_load_input(args)).to_dict()
            emit(report, Path(args.out) if args.out else None)
            return 0 if report["valid"] else 1
        elif args.command == "summary":
            emit(summarize(_load_input(args)), Path(args.out) if args.out else None)
        elif args.command == "snapshot":
            emit(_workspace(args.workspace).snapshot(args.case_id, actor=args.actor, label=args.label))
        elif args.command == "evidence-add":
            emit(add_evidence_file(
                _workspace(args.workspace), args.case_id, Path(args.file), title=args.title,
                evidence_type=args.type, source=args.source, actor=args.actor,
                link_to_assessment=not args.store_only,
            ))
        elif args.command == "evidence-verify":
            emit(verify_evidence_files(_workspace(args.workspace), args.case_id), Path(args.out) if args.out else None)
        elif args.command == "events-verify":
            workspace = _workspace(args.workspace)
            emit(verify_chain(workspace.case_path(args.case_id) / "events.jsonl"), Path(args.out) if args.out else None)
        elif args.command == "bundle":
            emit(export_case_bundle(_workspace(args.workspace), args.case_id, Path(args.output)), Path(args.out) if args.out else None)
        elif args.command == "migrate":
            migrate_file(Path(args.source), Path(args.output))
            emit({"output": args.output, "sha256": sha256_file(Path(args.output))})
        elif args.command == "observatory-import":
            emit(import_release(Path(args.workspace), Path(args.release)))
        elif args.command == "observatory-verify":
            report = validate_release(load_release(Path(args.release)))
            emit(report, Path(args.out) if args.out else None)
            return 0 if report["valid"] else 1
        elif args.command in {"observatory-summary", "observatory-queue"}:
            if args.release:
                release = load_release(Path(args.release))
            else:
                if not args.workspace:
                    raise ValueError("--workspace is required with --version")
                release = load_imported_release(Path(args.workspace), args.version)
            value = summarize_release(release) if args.command == "observatory-summary" else queue_release(release)
            emit(value, Path(args.out) if args.out else None)
        elif args.command == "compare":
            labels = args.labels or [Path(path).stem for path in args.assessments]
            if len(labels) != len(args.assessments):
                raise ValueError("--labels must have the same length as assessments")
            cases = [(label, json.loads(Path(path).read_text(encoding="utf-8"))) for label, path in zip(labels, args.assessments)]
            for _, assessment in cases:
                report = validate_assessment(assessment)
                if not report.valid:
                    raise ValueError("Every comparison input must be a valid v4.2 assessment")
            emit(compare_assessments(cases), Path(args.out) if args.out else None)
        else:
            parser.error("Unknown command")
        return 0
    except Exception as exc:
        logging.error("%s", exc)
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.exception("Controlled command failure")
        return 2
