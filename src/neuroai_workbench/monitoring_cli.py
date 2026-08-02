from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .delta.workspace import compile_delta_from_workspace
from .monitoring import (
    adjudicate_change_candidate,
    build_refresh_candidate,
    compare_snapshots,
    create_change_candidate,
    initialize_monitoring,
    load_source_registry,
    monitoring_status,
    plan_monitoring_run,
    record_snapshot_file,
    validate_source_registry,
)


def emit(value: Any, output: Path | None = None) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if output is None:
        sys.stdout.write(text)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neuroai-monitor",
        description="Controlled source monitoring and observatory refresh-candidate operations.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    command = sub.add_parser("registry-validate", help="Validate a source-monitor registry")
    command.add_argument("registry")
    command.add_argument("--out")

    command = sub.add_parser("init", help="Initialize monitoring state inside a workbench workspace")
    command.add_argument("workspace")
    command.add_argument("registry")
    command.add_argument("--actor", default="cli-user")
    command.add_argument("--out")

    command = sub.add_parser("plan", help="Build a due-source plan without retrieving network content")
    command.add_argument("workspace")
    command.add_argument("--as-of")
    command.add_argument("--source-id", action="append", default=[])
    command.add_argument("--out")

    command = sub.add_parser("snapshot", help="Register immutable bytes captured by an approved collector")
    command.add_argument("workspace")
    command.add_argument("source_id")
    command.add_argument("file")
    command.add_argument("--media-type", default="application/octet-stream")
    command.add_argument("--retrieved-at")
    command.add_argument("--actor", default="cli-user")
    command.add_argument("--out")

    command = sub.add_parser("diff", help="Compare two immutable source snapshots")
    command.add_argument("workspace")
    command.add_argument("source_id")
    command.add_argument("older_snapshot_id")
    command.add_argument("newer_snapshot_id")
    command.add_argument("--out")

    command = sub.add_parser("candidate", help="Create a non-authoritative human-review change candidate")
    command.add_argument("workspace")
    command.add_argument("source_id")
    command.add_argument("current_snapshot_id")
    command.add_argument("--previous-snapshot-id")
    command.add_argument(
        "--summary",
        default="Automated content change detected; substantive classification pending human review.",
    )
    command.add_argument("--actor", default="cli-user")
    command.add_argument("--out")

    command = sub.add_parser("adjudicate", help="Record an immutable human adjudication")
    command.add_argument("workspace")
    command.add_argument("candidate_id")
    command.add_argument("decision")
    command.add_argument("--rationale", required=True)
    command.add_argument("--change-class", default="UNCLASSIFIED")
    command.add_argument("--materiality", default="UNDETERMINED")
    command.add_argument("--reopening-effect", default="UNDETERMINED")
    command.add_argument("--actor", default="cli-user")
    command.add_argument("--out")

    command = sub.add_parser("package", help="Build a non-canonical observatory refresh candidate package")
    command.add_argument("workspace")
    command.add_argument("version")
    command.add_argument("--evidence-cutoff", required=True)
    command.add_argument("--actor", default="cli-user")
    command.add_argument("--out")

    command = sub.add_parser("delta-compile", help="Compile a non-canonical adjudicated delta from a refresh package")
    command.add_argument("workspace")
    command.add_argument("refresh_version")
    command.add_argument("predecessor")
    command.add_argument("--predecessor-release-id", required=True)
    command.add_argument("--operation-specs")
    command.add_argument("--actor", default="cli-user")
    command.add_argument("--out")

    command = sub.add_parser("status", help="Summarize monitoring state")
    command.add_argument("workspace")
    command.add_argument("--out")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "registry-validate":
            result = validate_source_registry(load_source_registry(Path(args.registry)))
            emit(result, Path(args.out) if args.out else None)
            return 0 if result["valid"] else 1
        if args.command == "init":
            result = initialize_monitoring(Path(args.workspace), Path(args.registry), actor=args.actor)
        elif args.command == "plan":
            result = plan_monitoring_run(Path(args.workspace), as_of=args.as_of, source_ids=args.source_id)
        elif args.command == "snapshot":
            result = record_snapshot_file(
                Path(args.workspace),
                args.source_id,
                Path(args.file),
                media_type=args.media_type,
                retrieved_at=args.retrieved_at,
                actor=args.actor,
            )
        elif args.command == "diff":
            result = compare_snapshots(
                Path(args.workspace), args.source_id, args.older_snapshot_id, args.newer_snapshot_id
            )
        elif args.command == "candidate":
            result = create_change_candidate(
                Path(args.workspace),
                args.source_id,
                args.current_snapshot_id,
                previous_snapshot_id=args.previous_snapshot_id,
                summary=args.summary,
                actor=args.actor,
            )
        elif args.command == "adjudicate":
            result = adjudicate_change_candidate(
                Path(args.workspace),
                args.candidate_id,
                args.decision,
                rationale=args.rationale,
                change_class=args.change_class,
                materiality=args.materiality,
                reopening_effect=args.reopening_effect,
                actor=args.actor,
            )
        elif args.command == "package":
            result = build_refresh_candidate(Path(args.workspace), args.version, args.evidence_cutoff, actor=args.actor)
        elif args.command == "delta-compile":
            result = compile_delta_from_workspace(
                Path(args.workspace),
                args.refresh_version,
                Path(args.predecessor),
                predecessor_release_id=args.predecessor_release_id,
                operation_specs_path=Path(args.operation_specs) if args.operation_specs else None,
                actor=args.actor,
            )
        elif args.command == "status":
            result = monitoring_status(Path(args.workspace))
        else:  # pragma: no cover - argparse prevents this path.
            parser.error("Unknown command")
        emit(result, Path(args.out) if args.out else None)
        return 0
    except Exception as exc:
        sys.stderr.write(f"ERROR {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
