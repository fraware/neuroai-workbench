"""Researcher CLI for NeuroAI data health, search, tracing, and evidence crosswalks."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from .data_health import build_data_health, write_data_health_outputs
from .data_search import build_search_index, search_index, write_search_outputs
from .data_trace import trace_propagation, write_trace_outputs
from .evidence_crosswalk import build_evidence_crosswalk, write_crosswalk_outputs
from .util import load_json


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neuroai-data",
        description="Inspect freshness, search, traceability, and evidence joinability across NeuroAI data.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    health = sub.add_parser("health", help="Profile release and source-registry data health")
    health.add_argument("--release", type=Path)
    health.add_argument("--registry", type=Path)
    health.add_argument("--as-of", default=date.today().isoformat())
    health.add_argument("--output-dir", type=Path, default=Path("data-analysis"))
    health.add_argument("--json", action="store_true")

    search = sub.add_parser("search", help="Search observatory, assessment, and evidence-priority records")
    search.add_argument("query")
    search.add_argument("--release", type=Path)
    search.add_argument("--registry", type=Path)
    search.add_argument(
        "--assessment",
        dest="assessments",
        type=Path,
        action="append",
        default=[],
        help="Completed assessment JSON; repeat for multiple assessments.",
    )
    search.add_argument(
        "--research-agenda",
        "--evidence-priority",
        dest="evidence_priorities",
        type=Path,
        action="append",
        default=[],
        help="Evidence-priority/research-agenda JSON; repeat for multiple payloads.",
    )
    search.add_argument("--type", dest="record_types", action="append", default=[])
    search.add_argument("--system", dest="systems", action="append", default=[])
    search.add_argument("--assessment-id", "--assessment-filter", dest="assessment_filters", action="append", default=[])
    search.add_argument("--source-class", dest="source_classes", action="append", default=[])
    search.add_argument("--priority", dest="priorities", action="append", default=[])
    search.add_argument("--status", dest="statuses", action="append", default=[])
    search.add_argument(
        "--after",
        help="Keep records with a substantive/publication/event date strictly after YYYY-MM-DD.",
    )
    search.add_argument(
        "--before",
        help="Keep records with a substantive/publication/event date strictly before YYYY-MM-DD.",
    )
    search.add_argument("--limit", type=int, default=20)
    search.add_argument("--output-dir", type=Path, default=Path("data-search"))
    search.add_argument("--json", action="store_true")

    trace = sub.add_parser("trace", help="Trace observatory sources into completed assessments")
    trace.add_argument("--release", type=Path, required=True)
    trace.add_argument(
        "--assessment",
        dest="assessments",
        type=Path,
        action="append",
        required=True,
        help="Completed assessment JSON; repeat for multiple assessments.",
    )
    trace.add_argument("--output-dir", type=Path, default=Path("data-trace"))
    trace.add_argument("--json", action="store_true")

    crosswalk = sub.add_parser("crosswalk", help="Crosswalk assessment evidence into a current source universe")
    crosswalk.add_argument(
        "--source-universe",
        dest="source_universes",
        type=Path,
        action="append",
        required=True,
        help="Controlled source JSON/JSONL payload; repeat to compose the effective source universe.",
    )
    crosswalk.add_argument(
        "--assessment",
        dest="assessments",
        type=Path,
        action="append",
        required=True,
        help="Completed assessment JSON; repeat for multiple assessments.",
    )
    crosswalk.add_argument("--output-dir", type=Path, default=Path("evidence-crosswalk"))
    crosswalk.add_argument("--json", action="store_true")
    return parser


def _load(path: Path | None) -> Any | None:
    if path is None:
        return None
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ValueError(f"Input not found: {resolved}")
    return load_json(resolved)


def _load_source_universe(path: Path) -> Any:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ValueError(f"Input not found: {resolved}")
    if resolved.suffix.casefold() != ".jsonl":
        return load_json(resolved)
    rows: list[Any] = []
    for line_number, line in enumerate(resolved.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at {resolved}:{line_number}: {exc.msg}") from exc
    return rows


def _require_input(release: Any | None, registry: Any | None) -> None:
    if release is None and registry is None:
        raise ValueError("Provide --release, --registry, or both")


def _health(args: argparse.Namespace) -> int:
    release = _load(args.release)
    registry = _load(args.registry)
    _require_input(release, registry)
    health = build_data_health(release=release, registry=registry, as_of=args.as_of)
    outputs = write_data_health_outputs(health, args.output_dir.expanduser().resolve())
    sys.stdout.write(f"Data health as of {health['metadata']['as_of']}\n")
    if "release" in health:
        profile = health["release"]
        sys.stdout.write(
            f"Release: {profile.get('version', 'UNRESOLVED')} | effective age: "
            f"{profile.get('effective_age_days', 'UNRESOLVED')} day(s)\n"
        )
    if "registry" in health:
        profile = health["registry"]
        counts = profile["freshness_counts"]
        sys.stdout.write(
            f"Registry: {profile['source_count']} sources | current {counts.get('CURRENT', 0)} | "
            f"due {counts.get('DUE', 0)} | stale {counts.get('STALE', 0)} | "
            f"never/invalid {counts.get('NEVER_OR_INVALID', 0)}\n"
        )
    sys.stdout.write(f"JSON: {outputs['json']}\nMarkdown: {outputs['markdown']}\n")
    if args.json:
        sys.stdout.write(json.dumps(health, indent=2, sort_keys=True) + "\n")
    return 0


def _search(args: argparse.Namespace) -> int:
    release = _load(args.release)
    registry = _load(args.registry)
    assessments = [_load(path) for path in args.assessments]
    evidence_priorities = [_load(path) for path in args.evidence_priorities]
    index = build_search_index(
        release=release,
        registry=registry,
        assessments=assessments,
        evidence_priorities=evidence_priorities,
    )
    results = search_index(
        index,
        args.query,
        record_types=set(args.record_types) if args.record_types else None,
        systems=set(args.systems) if args.systems else None,
        assessments=set(args.assessment_filters) if args.assessment_filters else None,
        source_classes=set(args.source_classes) if args.source_classes else None,
        priorities=set(args.priorities) if args.priorities else None,
        statuses=set(args.statuses) if args.statuses else None,
        after=args.after,
        before=args.before,
        limit=args.limit,
    )
    outputs = write_search_outputs(args.query, results, args.output_dir.expanduser().resolve())
    sys.stdout.write(f"Search: {args.query} | indexed {len(index)} records | matches {len(results)}\n")
    for rank, item in enumerate(results[:10], start=1):
        sys.stdout.write(
            f"{rank}. [{item['record_type']}] {item['record_id']} — {item['title']} (score {item['score']})\n"
        )
    sys.stdout.write(f"JSON: {outputs['json']}\nCSV: {outputs['csv']}\nMarkdown: {outputs['markdown']}\n")
    if args.json:
        sys.stdout.write(json.dumps({"query": args.query, "results": results}, indent=2, sort_keys=True) + "\n")
    return 0


def _trace(args: argparse.Namespace) -> int:
    release = _load(args.release)
    if not isinstance(release, dict):
        raise ValueError("Observatory release must be a JSON object")
    assessments = [_load(path) for path in args.assessments]
    trace = trace_propagation(release, assessments)
    outputs = write_trace_outputs(trace, args.output_dir.expanduser().resolve())
    summary = trace["summary"]
    metadata = trace["metadata"]
    sys.stdout.write(
        f"Propagation trace: {metadata['source_count']} observatory sources | "
        f"{metadata['assessment_count']} assessment(s)\n"
    )
    sys.stdout.write(
        f"Traced to assessment evidence: {summary['sources_traced_to_assessment_evidence']} | "
        f"through to requirements: {summary['sources_traced_to_requirements']} | "
        f"untraced: {summary['sources_untraced']}\n"
    )
    sys.stdout.write(
        f"JSON: {outputs['json']}\nSources CSV: {outputs['sources_csv']}\n"
        f"Records CSV: {outputs['records_csv']}\nMarkdown: {outputs['markdown']}\n"
    )
    if args.json:
        sys.stdout.write(json.dumps(trace, indent=2, sort_keys=True) + "\n")
    return 0


def _crosswalk(args: argparse.Namespace) -> int:
    source_payloads = [_load_source_universe(path) for path in args.source_universes]
    assessments = [_load(path) for path in args.assessments]
    crosswalk = build_evidence_crosswalk(source_payloads, assessments)
    outputs = write_crosswalk_outputs(crosswalk, args.output_dir.expanduser().resolve())
    metadata = crosswalk["metadata"]
    summary = crosswalk["summary"]
    sys.stdout.write(
        f"Evidence crosswalk: {metadata['source_count']} current sources | "
        f"{metadata['assessment_count']} assessment(s) | {metadata['evidence_count']} evidence records\n"
    )
    sys.stdout.write(
        f"Matched: {summary['matched_evidence_count']} | ambiguous: {summary['ambiguous_evidence_count']} | "
        f"unresolved: {summary['unresolved_evidence_count']} | "
        f"safe migration: {summary['safe_migration_candidate_count']} | "
        f"registration candidates: {summary['source_registration_candidate_count']}\n"
    )
    sys.stdout.write(f"JSON: {outputs['json']}\nCSV: {outputs['csv']}\nMarkdown: {outputs['markdown']}\n")
    if args.json:
        sys.stdout.write(json.dumps(crosswalk, indent=2, sort_keys=True) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "health":
            return _health(args)
        if args.command == "search":
            return _search(args)
        if args.command == "trace":
            return _trace(args)
        if args.command == "crosswalk":
            return _crosswalk(args)
        raise ValueError(f"Unknown command: {args.command}")
    except (OSError, TypeError, ValueError) as exc:
        sys.stderr.write(f"ERROR {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
