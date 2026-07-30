from __future__ import annotations

import argparse
import json
import logging
import sys
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any, cast

from . import __version__
from .assistance import (
    create_assistance_request,
    dispose_assistance_response,
    record_assistance_response,
    verify_assistance_record,
)
from .comparison import compare_assessments
from .events import verify_chain
from .evidence import add_evidence_file, verify_evidence_files
from .exchange import (
    create_exchange_request,
    record_exchange_response,
    render_exchange_markdown,
    verify_exchange_record,
)
from .exporter import export_case_bundle
from .metrics import summarize
from .migration import migrate_file
from .observatory import (
    import_release,
    load_imported_release,
    load_release,
    queue_release,
    summarize_release,
    validate_release,
)
from .programme_adapter import adapt_programme_file
from .reports import write_assessment_markdown, write_gap_markdown
from .review import (
    create_review_assignment,
    dispose_review_statement,
    render_review_markdown,
    submit_review_statement,
    verify_review_records,
)
from .server import serve
from .util import sha256_file
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
    p.add_argument("--allow-network", action="store_true")

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

    p = sub.add_parser("programme-adapt", help="Adapt a programme completed-assessment JSON object into native v4.2")
    p.add_argument("source")
    p.add_argument("output")
    p.add_argument("--report")

    p = sub.add_parser("report", help="Render a deterministic Markdown decision report")
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--assessment")
    source.add_argument("--case-id")
    p.add_argument("--workspace")
    p.add_argument("--output", required=True)

    p = sub.add_parser("assist-request", help="Create a controlled provider-neutral model-assistance request")
    p.add_argument("workspace")
    p.add_argument("case_id")
    p.add_argument("task_type")
    p.add_argument("--prompt", required=True)
    p.add_argument("--evidence-id", action="append", default=[])
    p.add_argument("--requirement-id", action="append", default=[])
    p.add_argument("--actor", default="cli-user")
    p.add_argument("--out")

    p = sub.add_parser("assist-record", help="Record and validate a model response without mutating the assessment")
    p.add_argument("workspace")
    p.add_argument("case_id")
    p.add_argument("request_id")
    p.add_argument("response")
    p.add_argument("--provider", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--actor", default="cli-user")
    p.add_argument("--out")

    p = sub.add_parser("assist-dispose", help="Record a human disposition for a model response")
    p.add_argument("workspace")
    p.add_argument("case_id")
    p.add_argument("request_id")
    p.add_argument("disposition")
    p.add_argument("--notes", required=True)
    p.add_argument("--actor", default="cli-user")
    p.add_argument("--out")

    p = sub.add_parser("assist-verify", help="Verify request, response, and disposition integrity")
    p.add_argument("workspace")
    p.add_argument("case_id")
    p.add_argument("request_id")
    p.add_argument("--out")

    p = sub.add_parser("gap-report", help="Render a deterministic evidence-gap and closure-request report")
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--assessment")
    source.add_argument("--case-id")
    p.add_argument("--workspace")
    p.add_argument("--output", required=True)

    p = sub.add_parser("review-assign", help="Record an attributable local review assignment")
    p.add_argument("workspace")
    p.add_argument("case_id")
    p.add_argument("reviewer_id")
    p.add_argument("role")
    p.add_argument("--scope", action="append", required=True)
    p.add_argument("--actor", default="cli-user")
    p.add_argument("--out")

    p = sub.add_parser("review-submit", help="Submit an immutable review statement or disagreement")
    p.add_argument("workspace")
    p.add_argument("case_id")
    p.add_argument("reviewer_id")
    p.add_argument("target_type")
    p.add_argument("target_id")
    p.add_argument("position")
    p.add_argument("--rationale", required=True)
    p.add_argument("--evidence-id", action="append", default=[])
    p.add_argument("--condition", action="append", default=[])
    p.add_argument("--proposed-change")
    p.add_argument("--actor")
    p.add_argument("--out")

    p = sub.add_parser("review-dispose", help="Record an authorized human disposition for a review statement")
    p.add_argument("workspace")
    p.add_argument("case_id")
    p.add_argument("statement_id")
    p.add_argument("disposition")
    p.add_argument("--rationale", required=True)
    p.add_argument("--actor", required=True)
    p.add_argument("--out")

    p = sub.add_parser("review-verify", help="Verify review records, role linkage, and event-chain integrity")
    p.add_argument("workspace")
    p.add_argument("case_id")
    p.add_argument("--out")

    p = sub.add_parser("review-report", help="Render a deterministic Markdown review and disagreement report")
    p.add_argument("workspace")
    p.add_argument("case_id")
    p.add_argument("--output", required=True)

    p = sub.add_parser("exchange-create", help="Create a protected-evidence metadata request without evidence bytes")
    p.add_argument("workspace")
    p.add_argument("case_id")
    p.add_argument("--evidence-id", action="append", required=True)
    p.add_argument("--gap-id", action="append", default=[])
    p.add_argument("--recipient", required=True)
    p.add_argument("--purpose", required=True)
    p.add_argument("--requested-material", action="append", required=True)
    p.add_argument("--authorized-use", default="ASSESSMENT_REVIEW_ONLY")
    p.add_argument("--constraint", action="append", default=[])
    p.add_argument("--actor", default="cli-user")
    p.add_argument("--out")

    p = sub.add_parser("exchange-record", help="Record an out-of-band holder response without importing bytes")
    p.add_argument("workspace")
    p.add_argument("case_id")
    p.add_argument("request_id")
    p.add_argument("response_state")
    p.add_argument("--holder", required=True)
    p.add_argument("--condition", action="append", default=[])
    p.add_argument("--materials-json")
    p.add_argument("--notes")
    p.add_argument("--actor", default="cli-user")
    p.add_argument("--out")

    p = sub.add_parser("exchange-verify", help="Verify evidence-exchange metadata and boundary integrity")
    p.add_argument("workspace")
    p.add_argument("case_id")
    p.add_argument("request_id")
    p.add_argument("--out")

    p = sub.add_parser("exchange-report", help="Render a deterministic protected-evidence exchange report")
    p.add_argument("workspace")
    p.add_argument("case_id")
    p.add_argument("request_id")
    p.add_argument("--output", required=True)

    p = sub.add_parser("compare", help="Compare v4.2 assessments without creating new findings")
    p.add_argument("assessments", nargs="+")
    p.add_argument("--labels", nargs="*")
    p.add_argument("--out")

    return parser


def _load_input(args: argparse.Namespace) -> dict[str, Any]:
    if args.assessment:
        return cast(dict[str, Any], json.loads(Path(args.assessment).read_text(encoding="utf-8")))
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
            serve(_workspace(args.workspace), host=args.host, port=args.port, allow_network=args.allow_network)
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
            emit(
                _workspace(args.workspace).save_case(
                    args.case_id, assessment, actor=args.actor, require_valid=args.require_valid
                )
            )
        elif args.command == "validate":
            report = validate_assessment(_load_input(args)).to_dict()
            emit(report, Path(args.out) if args.out else None)
            return 0 if report["valid"] else 1
        elif args.command == "summary":
            emit(summarize(_load_input(args)), Path(args.out) if args.out else None)
        elif args.command == "snapshot":
            emit(_workspace(args.workspace).snapshot(args.case_id, actor=args.actor, label=args.label))
        elif args.command == "evidence-add":
            emit(
                add_evidence_file(
                    _workspace(args.workspace),
                    args.case_id,
                    Path(args.file),
                    title=args.title,
                    evidence_type=args.type,
                    source=args.source,
                    actor=args.actor,
                    link_to_assessment=not args.store_only,
                )
            )
        elif args.command == "evidence-verify":
            emit(verify_evidence_files(_workspace(args.workspace), args.case_id), Path(args.out) if args.out else None)
        elif args.command == "events-verify":
            workspace = _workspace(args.workspace)
            emit(verify_chain(workspace.case_path(args.case_id) / "events.jsonl"), Path(args.out) if args.out else None)
        elif args.command == "bundle":
            emit(
                export_case_bundle(_workspace(args.workspace), args.case_id, Path(args.output)),
                Path(args.out) if args.out else None,
            )
        elif args.command == "migrate":
            migrate_file(Path(args.source), Path(args.output))
            emit({"output": args.output, "sha256": sha256_file(Path(args.output))})
        elif args.command == "programme-adapt":
            result = adapt_programme_file(
                Path(args.source),
                Path(args.output),
                Path(args.report) if args.report else None,
            )
            emit(result.report)
            return 0 if result.report["validation"]["valid"] else 1
        elif args.command == "report":
            emit(write_assessment_markdown(_load_input(args), Path(args.output)))
        elif args.command == "gap-report":
            emit(write_gap_markdown(_load_input(args), Path(args.output)))
        elif args.command == "review-assign":
            emit(create_review_assignment(
                _workspace(args.workspace),
                args.case_id,
                args.reviewer_id,
                args.role,
                args.scope,
                actor=args.actor,
            ), Path(args.out) if args.out else None)
        elif args.command == "review-submit":
            emit(submit_review_statement(
                _workspace(args.workspace),
                args.case_id,
                args.reviewer_id,
                args.target_type,
                args.target_id,
                args.position,
                args.rationale,
                evidence_ids=args.evidence_id,
                conditions=args.condition,
                proposed_change=args.proposed_change,
                actor=args.actor,
            ), Path(args.out) if args.out else None)
        elif args.command == "review-dispose":
            emit(dispose_review_statement(
                _workspace(args.workspace),
                args.case_id,
                args.statement_id,
                args.disposition,
                args.rationale,
                actor=args.actor,
            ), Path(args.out) if args.out else None)
        elif args.command == "review-verify":
            result = verify_review_records(_workspace(args.workspace), args.case_id)
            emit(result, Path(args.out) if args.out else None)
            return 0 if result["valid"] else 1
        elif args.command == "review-report":
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            text = render_review_markdown(_workspace(args.workspace), args.case_id)
            output.write_text(text, encoding="utf-8")
            emit({
                "output": str(output),
                "sha256": sha256_file(output),
                "boundary": "The review report attributes local records and creates no assessment or authority change.",
            })
        elif args.command == "exchange-create":
            emit(
                create_exchange_request(
                    _workspace(args.workspace),
                    args.case_id,
                    args.evidence_id,
                    recipient=args.recipient,
                    purpose=args.purpose,
                    requested_materials=args.requested_material,
                    gap_ids=args.gap_id,
                    authorized_use=args.authorized_use,
                    disclosure_constraints=args.constraint,
                    actor=args.actor,
                ),
                Path(args.out) if args.out else None,
            )
        elif args.command == "exchange-record":
            materials = []
            if args.materials_json:
                materials = json.loads(Path(args.materials_json).read_text(encoding="utf-8"))
                if not isinstance(materials, list):
                    raise ValueError("--materials-json must contain a JSON list")
            emit(
                record_exchange_response(
                    _workspace(args.workspace),
                    args.case_id,
                    args.request_id,
                    args.response_state,
                    holder=args.holder,
                    conditions=args.condition,
                    materials=materials,
                    notes=args.notes,
                    actor=args.actor,
                ),
                Path(args.out) if args.out else None,
            )
        elif args.command == "exchange-verify":
            result = verify_exchange_record(_workspace(args.workspace), args.case_id, args.request_id)
            emit(result, Path(args.out) if args.out else None)
            return 0 if result["valid"] else 1
        elif args.command == "exchange-report":
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                render_exchange_markdown(_workspace(args.workspace), args.case_id, args.request_id),
                encoding="utf-8",
            )
            emit({
                "output": str(output),
                "sha256": sha256_file(output),
                "boundary": "The exchange report contains metadata only and does not establish evidence receipt.",
            })
        elif args.command == "assist-request":
            result = create_assistance_request(
                _workspace(args.workspace),
                args.case_id,
                args.task_type,
                args.prompt,
                evidence_ids=args.evidence_id,
                requirement_ids=args.requirement_id,
                actor=args.actor,
            )
            emit(result, Path(args.out) if args.out else None)
        elif args.command == "assist-record":
            result = record_assistance_response(
                _workspace(args.workspace),
                args.case_id,
                args.request_id,
                Path(args.response),
                provider=args.provider,
                model=args.model,
                actor=args.actor,
            )
            emit(result, Path(args.out) if args.out else None)
        elif args.command == "assist-dispose":
            result = dispose_assistance_response(
                _workspace(args.workspace),
                args.case_id,
                args.request_id,
                args.disposition,
                args.notes,
                actor=args.actor,
            )
            emit(result, Path(args.out) if args.out else None)
        elif args.command == "assist-verify":
            result = verify_assistance_record(_workspace(args.workspace), args.case_id, args.request_id)
            emit(result, Path(args.out) if args.out else None)
            return 0 if result["valid"] else 1
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
            cases = [
                (label, json.loads(Path(path).read_text(encoding="utf-8")))
                for label, path in zip(labels, args.assessments)
            ]
            for _, assessment in cases:
                validation = validate_assessment(cast(dict[str, Any], assessment))
                if not validation.valid:
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
