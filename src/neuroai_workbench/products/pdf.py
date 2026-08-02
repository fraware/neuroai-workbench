from __future__ import annotations

from pathlib import Path
from typing import Any

from ..util import atomic_write_bytes, sha256_bytes


def render_pdf_stub(query: dict[str, Any]) -> str:
    return (
        "NeuroAI publication PDF stub\n"
        "==============================\n\n"
        "Native PDF generation requires an optional renderer (for example reportlab or weasyprint).\n"
        "This stub records release identity for manifest inclusion until a reviewed PDF path is added.\n\n"
        f"release_sha256: {query['release_sha256']}\n"
        f"release_version: {query['metadata'].get('version', 'UNRESOLVED')}\n\n"
        "Withheld claims:\n"
        + "".join(f"- {item}\n" for item in query["withheld_claims"])
        + "\nBoundary: PDF stub confirms identity only; it does not establish substantive authority.\n"
    )


def write_pdf_stub(query: dict[str, Any], output: Path) -> dict[str, Any]:
    text = render_pdf_stub(query)
    atomic_write_bytes(output, text.encode("utf-8"))
    return {
        "output": str(output),
        "sha256": sha256_bytes(text.encode("utf-8")),
        "bytes": len(text.encode("utf-8")),
        "format": "pdf-stub-text",
        "limitation": "Native PDF unavailable without optional dependencies; use Markdown/HTML dashboard instead.",
        "boundary": "Stub records release identity for reconciliation tests only.",
    }
