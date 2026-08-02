from __future__ import annotations

from pathlib import Path
from typing import Any

from ..util import atomic_write_bytes, sha256_bytes


def render_pdf(query: dict[str, Any]) -> bytes | None:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError:
        return None
    buffer = __import__("io").BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    # Keep content streams uncompressed so release identity remains greppable for reconciliation.
    pdf.setPageCompression(0)
    width, height = letter
    y = height - 72
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(72, y, "NeuroAI observatory publication extract")
    y -= 28
    pdf.setFont("Helvetica", 10)
    lines = [
        f"release_sha256: {query['release_sha256']}",
        f"release_version: {query['metadata'].get('version', 'UNRESOLVED')}",
        "",
        "Withheld claims:",
        *[f"- {claim}" for claim in query["withheld_claims"]],
        "",
        "Boundary: PDF restates canonical JSON projections only.",
    ]
    for line in lines:
        if y < 72:
            pdf.showPage()
            pdf.setFont("Helvetica", 10)
            y = height - 72
        pdf.drawString(72, y, line[:100])
        y -= 14
    pdf.save()
    return buffer.getvalue()


def render_pdf_stub(query: dict[str, Any]) -> str:
    return (
        "NeuroAI publication PDF stub\n"
        "==============================\n\n"
        "Native PDF generation requires optional reportlab (extra: products).\n"
        f"release_sha256: {query['release_sha256']}\n"
        f"release_version: {query['metadata'].get('version', 'UNRESOLVED')}\n\n"
        "Withheld claims:\n"
        + "".join(f"- {item}\n" for item in query["withheld_claims"])
        + "\nBoundary: PDF stub confirms identity only; it does not establish substantive authority.\n"
    )


def write_pdf(query: dict[str, Any], output: Path) -> dict[str, Any]:
    payload = render_pdf(query)
    if payload is None:
        text = render_pdf_stub(query)
        atomic_write_bytes(output, text.encode("utf-8"))
        return {
            "output": str(output),
            "sha256": sha256_bytes(text.encode("utf-8")),
            "bytes": len(text.encode("utf-8")),
            "format": "pdf-stub-text",
            "limitation": "Native PDF unavailable without optional dependencies.",
            "boundary": "Stub records release identity for reconciliation tests only.",
        }
    atomic_write_bytes(output, payload)
    return {
        "output": str(output),
        "sha256": sha256_bytes(payload),
        "bytes": len(payload),
        "format": "reportlab-native-pdf",
        "boundary": "PDF is a deterministic projection of canonical JSON; no new findings.",
    }


# Backward-compatible aliases
write_pdf_stub = write_pdf
