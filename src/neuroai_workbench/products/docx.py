from __future__ import annotations

from pathlib import Path
from typing import Any

from ..util import atomic_write_bytes, sha256_bytes


def render_docx(query: dict[str, Any]) -> bytes | None:
    try:
        from docx import Document
    except ImportError:
        return None
    document = Document()
    document.add_heading("NeuroAI observatory publication extract", level=1)
    document.add_paragraph(f"release_sha256: {query['release_sha256']}")
    document.add_paragraph(f"release_version: {query['metadata'].get('version', 'UNRESOLVED')}")
    document.add_heading("Withheld claims", level=2)
    for claim in query["withheld_claims"]:
        document.add_paragraph(claim, style="List Bullet")
    document.add_heading("Release summary", level=2)
    for row in query["rows"].get("release_summary", []):
        document.add_paragraph(
            ", ".join(f"{key}={row.get(key)}" for key in sorted(row)),
        )
    counts_key = "successor_counts" if "successor_counts" in query["rows"] else "coverage_counts"
    if counts_key in query["rows"]:
        document.add_heading("Counts", level=2)
        for row in query["rows"][counts_key]:
            document.add_paragraph(f"{row.get('metric')}: {row.get('value')}", style="List Bullet")
    document.add_paragraph(
        "Boundary: Document restates canonical JSON projections only; it does not establish substantive authority."
    )
    buffer_path_bytes = __import__("io").BytesIO()
    document.save(buffer_path_bytes)
    return buffer_path_bytes.getvalue()


def write_docx(query: dict[str, Any], output: Path) -> dict[str, Any]:
    payload = render_docx(query)
    if payload is None:
        text = (
            "NeuroAI publication Word stub\n"
            "Native .docx requires optional dependency python-docx (extra: products).\n"
            f"release_sha256: {query['release_sha256']}\n"
        )
        atomic_write_bytes(output, text.encode("utf-8"))
        return {
            "output": str(output),
            "sha256": sha256_bytes(text.encode("utf-8")),
            "bytes": len(text.encode("utf-8")),
            "format": "docx-stub-text",
            "boundary": "Stub records release identity until python-docx is installed.",
        }
    atomic_write_bytes(output, payload)
    return {
        "output": str(output),
        "sha256": sha256_bytes(payload),
        "bytes": len(payload),
        "format": "python-docx-native",
        "boundary": "DOCX is a deterministic projection of canonical JSON; no new findings.",
    }
