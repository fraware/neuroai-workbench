"""CLI for read-only cross-case NeuroAI assessment analysis."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .assessment_evidence import build_assessment_evidence_analysis, write_assessment_evidence_outputs
from .portfolio import analyze_portfolio, normalize_assessment, write_portfolio_outputs
from .research_agenda import build_research_agenda, write_research_agenda_outputs
from .util import load_json


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neuroai-portfolio",
        description="Compare completed NeuroAI assessments and surface recurring requirement patterns.",
    )
    parser.add_argument("assessments", nargs="+", type=Path, help="Completed assessment JSON files.")
    parser.add_argument("--output-dir", type=Path, default=Path("portfolio-analysis"))
    parser.add_argument("--json", action="store_true", help="Also print the complete analysis JSON to stdout.")
    return parser


def _load(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ValueError(f"Assessment not found: {resolved}")
    raw = load_json(resolved)
    if not isinstance(raw, dict):
        raise ValueError(f"Assessment must be a JSON object: {resolved}")
    normalized = normalize_assessment(raw, source_path=str(resolved))
    return raw, normalized


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        loaded = [_load(path) for path in args.assessments]
        raw_assessments = [raw for raw, _ in loaded]
        assessments = [normalized for _, normalized in loaded]
        analysis = analyze_portfolio(assessments)
        agenda = build_research_agenda(assessments, analysis)
        evidence_analysis = build_assessment_evidence_analysis(raw_assessments)
        analysis["research_agenda"] = agenda
        analysis["evidence_health"] = {
            "metadata": evidence_analysis["metadata"],
            "health": evidence_analysis["health"],
        }
        output_dir = args.output_dir.expanduser().resolve()
        outputs = write_portfolio_outputs(analysis, output_dir)
        priority_outputs = write_research_agenda_outputs(agenda, output_dir)
        evidence_outputs = write_assessment_evidence_outputs(evidence_analysis, output_dir)
    except (OSError, TypeError, ValueError) as exc:
        sys.stderr.write(f"ERROR {exc}\n")
        return 2

    metadata = analysis["metadata"]
    weaknesses = analysis["recurrent_weaknesses"]
    blind_spots = analysis["universal_blind_spots"]
    modules = analysis["modules"]
    evidence_metadata = evidence_analysis["metadata"]
    evidence_health = evidence_analysis["health"]
    sys.stdout.write(
        f"Portfolio: {metadata['case_count']} cases | {metadata['requirement_universe_count']} requirements | "
        f"{len(blind_spots)} universal blind spot(s)\n"
    )
    sys.stdout.write(
        f"Evidence: {evidence_metadata['evidence_count']} records | "
        f"{evidence_metadata['evidence_requirement_link_count']} evidence→requirement links | "
        f"{evidence_health['orphan_evidence_count']} orphan evidence | "
        f"{evidence_health['zero_evidence_requirement_count']} zero-evidence requirements\n"
    )
    if modules:
        top_module = modules[0]
        sys.stdout.write(
            f"Highest weak-rate module: {top_module['module_id']} ({float(top_module['weak_rate']):.1%})\n"
        )
    if weaknesses:
        top = weaknesses[0]
        sys.stdout.write(
            f"Top recurrent weakness: {top['requirement_id']} — weak in "
            f"{top['weak_case_count']}/{metadata['case_count']} cases\n"
        )
    if agenda:
        top_priority = agenda[0]
        sys.stdout.write(
            f"Next evidence priority: {top_priority['requirement_id']} — {top_priority['recommended_focus']}\n"
        )
    sys.stdout.write(
        f"Analysis: {outputs['analysis']}\n"
        f"Matrix: {outputs['matrix']}\n"
        f"Summary: {outputs['summary']}\n"
        f"Evidence priorities: {priority_outputs['markdown']}\n"
        f"Assessment evidence: {evidence_outputs['evidence_csv']}\n"
        f"Evidence links: {evidence_outputs['links_csv']}\n"
        f"Evidence health: {evidence_outputs['health_markdown']}\n"
    )
    if args.json:
        sys.stdout.write(json.dumps(analysis, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
