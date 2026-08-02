from __future__ import annotations

from pathlib import Path
from typing import Any

from ..reports import _bullets, _escape
from ..util import atomic_write_bytes, sha256_bytes


def render_narrative_markdown(query: dict[str, Any]) -> str:
    metadata = query["metadata"]
    summary = query["summary"]
    lines = [
        f"# Current-state executive report: {_escape(metadata.get('title', 'NeuroAI observatory release'))}",
        "",
        "> Narrative publication is a deterministic projection of canonical records. "
        "It does not upgrade evidence, resolve unknowns, or confer institutional authority.",
        "",
        "## Release identity",
        "",
        f"- Version: `{_escape(metadata.get('version'))}`",
        f"- Status: `{_escape(metadata.get('status'))}`",
        f"- Release SHA-256: `{query['release_sha256']}`",
        f"- Mechanical validation: `{'VALID' if summary.get('valid') else 'INVALID'}`",
        "",
        "## Withheld claims",
        "",
        _bullets(query["withheld_claims"]),
        "",
        "## Summary counts",
        "",
    ]

    if query["release_kind"] == "COMPACT_SUCCESSOR_SNAPSHOT":
        lines.extend(["| Metric | Value |", "|---|---:|"])
        for row in query["rows"].get("successor_counts", []):
            lines.append(f"| {_escape(row['metric'])} | {_escape(row['value'])} |")
        lines.extend(["", "## Reopening queue", ""])
        for row in query["rows"].get("reopening_decisions", []):
            lines.append(
                f"- `{_escape(row.get('decision_id'))}` {_escape(row.get('object'))}: {_escape(row.get('decision'))}"
            )
    else:
        lines.extend(["| Metric | Value |", "|---|---:|"])
        for row in query["rows"].get("coverage_counts", []):
            lines.append(f"| {_escape(row['metric'])} | {_escape(row['value'])} |")

    lines.extend(
        [
            "",
            "## Boundary",
            "",
            query["boundary"],
            "",
        ]
    )
    return "\n".join(lines)


def write_narrative_markdown(query: dict[str, Any], output: Path) -> dict[str, Any]:
    text = render_narrative_markdown(query)
    atomic_write_bytes(output, text.encode("utf-8"))
    return {
        "output": str(output),
        "sha256": sha256_bytes(text.encode("utf-8")),
        "bytes": len(text.encode("utf-8")),
        "format": "markdown",
        "boundary": "Narrative output restates canonical queries; Word export remains a documented limitation.",
    }
