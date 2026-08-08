"""Researcher CLI for NeuroAI observatory data health and search."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from .data_health import build_data_health, write_data_health_outputs
from .data_search import build_search_index, search_index, write_search_outputs
from .util import load_json


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neuroai-data",
        description="Inspect freshness and search canonical NeuroAI observatory records.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    health = sub.add_parser("health", help="Profile release and source-registry data health")
    health.add_argument("--release", type=Path)
    health.add_argument("--registry", type=Path)
    health.add_argument("--as-of", default=date.today().isoformat())
    health.add_argument("--output-dir", type=Path, default=Path("data-analysis"))
    health.add_argument("--json", action="store_true")

    search = sub.add_parser("search", help="Search observatory releases and source registries")
    search.add_argument("query")
    search.add_argument("--release", type=Path)
    search.add_argument("--registry", type=Path)
    search.add_argument("--type", dest="record_types", action="append", default=[])
    search.add_argument("--limit", type=int, default=20)
    search.add_argument("--output-dir", type=Path, default=Path("data-search"))
    search.add_argument("--json", action="store_true")
    return parser


def _load(path: Path | None) -> Any | None:
    if path is None:
        return None
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ValueError(f"Input not found: {resolved}")
    return load_json(resolved)


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
    _require_input(release, registry)
    index = build_search_index(release=release, registry=registry)
    results = search_index(
        index,
        args.query,
        record_types=set(args.record_types) if args.record_types else None,
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


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "health":
            return _health(args)
        if args.command == "search":
            return _search(args)
        raise ValueError(f"Unknown command: {args.command}")
    except (OSError, TypeError, ValueError) as exc:
        sys.stderr.write(f"ERROR {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
